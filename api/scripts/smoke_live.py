"""DEV TOOL, not part of the app. One real run through the real HTTP API, then a dev-only look at the
database. Run it inside the compose network (the API is reached as http://api:8000):

    docker compose run --rm api python scripts/smoke_live.py tests/fixtures/seoul_live.csv \
        --question "Which station has the most boardings?"

It logs in as one throwaway user (signing it up the first time; signup is limited to 5 per hour per
IP) and reuses that user's upload of the same file name while it is still stored. It posts the run,
follows it until it ends, then prints the outcome, the trace lines, one row per model call (model,
tokens, latency, status, from ai_calls) and, read straight from agent_steps.payload, Owl's plan,
Beaver's code and Beaver's result.

The payload is never exposed by the API (RunView has no step payload); this script reads it from
the database for developer inspection only. It never prints the key (it never sees it) and never
prints a prompt: prompts are not stored anywhere."""

# ruff: noqa: E501, S105, S310 # a dev throwaway password; the URL is always our own http API

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app` imports from /app/scripts

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_engine  # noqa: E402

ORIGIN = "http://localhost:3000"  # an allow-listed origin: writes are refused without one
EMAIL = "smoke-live@example.test"
PASSWORD = "smoke-live-throwaway-1"  # a dev throwaway account in the dev database, not a secret
POLL_SECONDS = 2.0
MAX_WAIT_SECONDS = 150.0


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def call(
        self, method: str, path: str, *, body: bytes | None = None, content_type: str | None = None
    ) -> tuple[int, Any]:
        request = urllib.request.Request(f"{self.base}{path}", data=body, method=method)
        request.add_header("Origin", ORIGIN)
        if content_type:
            request.add_header("Content-Type", content_type)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, None

    def json_call(self, method: str, path: str, data: dict[str, Any]) -> tuple[int, Any]:
        return self.call(
            method, path, body=json.dumps(data).encode(), content_type="application/json"
        )

    def upload(self, name: str, data: bytes) -> tuple[int, Any]:
        boundary = uuid.uuid4().hex
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="consent"\r\n\r\ntrue\r\n'.encode(),
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                "Content-Type: text/csv\r\n\r\n"
            ).encode(),
            data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        return self.call(
            "POST",
            "/uploads",
            body=b"".join(parts),
            content_type=f"multipart/form-data; boundary={boundary}",
        )


def sign_in(api: Api) -> None:
    status, _ = api.json_call("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
    if status == 200:
        return
    status, body = api.json_call(
        "POST", "/auth/signup", {"email": EMAIL, "password": PASSWORD, "display_name": "Smoke Live"}
    )
    if status != 201:
        sys.exit(f"sign-in failed: HTTP {status} {json.dumps(body)[:300]}")


def find_or_upload(api: Api, path: Path) -> str:
    status, listing = api.call("GET", "/uploads")
    if status == 200 and isinstance(listing, list):
        for item in listing:
            if item.get("filename") == path.name and item.get("deleted_at") is None:
                return str(item["id"])
    status, body = api.upload(path.name, path.read_bytes())
    if status != 201:
        sys.exit(f"upload failed: HTTP {status} {json.dumps(body)[:300]}")
    return str(body["id"])


def follow(api: Api, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        status, view = api.call("GET", f"/runs/{run_id}")
        if status == 200 and view and view.get("status") == "finished":
            return dict(view)
        time.sleep(POLL_SECONDS)
    sys.exit("the run did not finish in time")


def dump(title: str, value: Any) -> None:
    print(f"\n--- {title}")
    print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))


def inspect(run_id: str) -> None:
    engine = get_engine(get_settings().database_url.get_secret_value())
    with Session(engine) as db:
        calls = db.execute(
            text(
                "SELECT purpose, model, attempt, status, tokens_in, tokens_out, latency_ms, est_cost_usd "
                "FROM ai_calls WHERE run_id = :r ORDER BY created_at"
            ),
            {"r": run_id},
        ).all()
        steps = db.execute(
            text(
                "SELECT seq, agent, kind, state, key, args, attempt, model, payload FROM agent_steps "
                "WHERE run_id = :r ORDER BY seq"
            ),
            {"r": run_id},
        ).all()
    print("\n--- model calls (ai_calls)")
    print("purpose | model | attempt | status | tokens_in | tokens_out | latency_ms | est_cost_usd")
    for call in calls:
        print(" | ".join(str(cell) for cell in call))
    print(
        f"calls={len(calls)} tokens_in={sum(c[4] for c in calls)} tokens_out={sum(c[5] for c in calls)}"
    )
    print("\n--- trace lines (agent_steps)")
    for seq, agent, kind, state, key, args, attempt, model, _ in steps:
        print(
            f"{seq:>3} {agent:<9} {kind:<9} {state:<8} {key} {json.dumps(args, ensure_ascii=False)} a{attempt} {model or ''}"
        )
    for seq, _agent, _kind, _state, key, _args, _attempt, _model, payload in steps:
        if not payload:
            continue
        if "plan" in payload:
            dump(f"Owl plan (step {seq}, {key})", payload["plan"])
        if "code" in payload:
            dump(f"Beaver code (step {seq}, {key})", payload["code"])
            dump(
                "Beaver result",
                {k: v for k, v in payload.items() if k not in ("code", "plan")},
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("csv", type=Path)
    parser.add_argument("--question", required=True)
    parser.add_argument("--api", default="http://api:8000/api")
    args = parser.parse_args()
    api = Api(args.api)
    sign_in(api)
    upload_id = find_or_upload(api, args.csv)
    status, created = api.json_call(
        "POST",
        "/runs",
        {
            "mode": "ask",
            "question": args.question,
            "files": [{"upload_id": upload_id, "role": "subject"}],
        },
    )
    if status != 202:
        sys.exit(f"run refused: HTTP {status} {json.dumps(created, ensure_ascii=False)[:300]}")
    run_id = str(created["id"])
    print(f"question: {args.question}\nrun: {run_id}")
    view = follow(api, run_id)
    print(
        f"\noutcome={view.get('outcome')} reason={view.get('reason')} "
        f"tokens_in={view.get('tokens_in')} tokens_out={view.get('tokens_out')}"
    )
    inspect(run_id)


if __name__ == "__main__":
    main()
