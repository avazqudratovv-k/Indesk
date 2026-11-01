"""DEV TOOL, not part of the app. One real run through the real HTTP API, then a dev-only look at the
database. Run it inside the compose network (the API is reached as http://api:8000):

    docker compose run --rm api python scripts/smoke_live.py tests/fixtures/seoul_live.csv \
        --question "Which station has the most boardings?"

PDF mode (P14a part 2): give a .pdf file and the same command. The file goes up as application/pdf,
the run goes through Owl (code), Hound (embeddings + search) and the writer, and the output adds
Hound's search payload (mode, pages, scores; no passage text), the embedding rows of ai_calls with
the estimated cost, and the report's claims with doc_quote / doc_location / doc_value. The owner runs
it live in P14b; nothing here has run against real Gemini.

--reset-quota (dev helper): before the run, deletes the smoke account's own `run` usage_events, its
own usage_daily counters and its own rl:login / rl:signup / rl:run Redis keys (its IP and email
only), so repeated calibration runs are not stopped by the free-run total, the daily caps or the
hourly limits. It refuses to do anything unless APP_ENV=development. It never touches the global
counters, other users or other keys.

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
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app` imports from /app/scripts

from sqlalchemy import delete, select, text, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import clock  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.enums import UsageKind  # noqa: E402
from app.core.ratelimit import redis_client  # noqa: E402
from app.core.security import keyed_hash  # noqa: E402
from app.db.models import UsageDaily, UsageEvent, User  # noqa: E402
from app.db.session import get_engine  # noqa: E402

ORIGIN = "http://localhost:3000"  # an allow-listed origin: writes are refused without one
EMAIL = "smoke-live@example.test"
PASSWORD = "smoke-live-throwaway-1"  # a dev throwaway account in the dev database, not a secret
POLL_SECONDS = 2.0
MAX_WAIT_SECONDS = 150.0


def mime_of(name: str) -> str:
    return "application/pdf" if name.lower().endswith(".pdf") else "text/csv"


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
                f"Content-Type: {mime_of(name)}\r\n\r\n"
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


def own_ip(api_base: str) -> str | None:
    """The address the API sees for this script: the local address of a UDP socket aimed at the API
    host (nothing is sent). None when it cannot be worked out."""
    host = urllib.parse.urlsplit(api_base).hostname or "localhost"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((host, 9))
            return str(probe.getsockname()[0])
    except OSError:
        return None


def reset_quota(settings: Settings, db: Session, redis: Any, ip: str | None) -> list[str]:
    """Dev only: clear what stops the smoke account from running again. Refuses (SystemExit with a
    message) in any environment but development, before touching anything. Returns what it did."""
    if settings.app_env != "development":
        sys.exit(
            f"--reset-quota refused: APP_ENV is {settings.app_env!r}, it only works in development."
        )
    if settings.auth_secret is None:
        sys.exit("--reset-quota needs the auth secret to compute the Redis keys.")
    secret = settings.auth_secret.get_secret_value()
    done: list[str] = []
    keys: list[str] = list(redis.scan_iter(match=f"rl:login:*:{keyed_hash(secret, EMAIL)}"))
    if ip is not None:
        keys.append(f"rl:signup:{keyed_hash(secret, ip)}")
    user_id = db.scalar(select(User.id).where(User.email == EMAIL))
    if user_id is not None:
        keys.append(f"rl:run:{user_id}")
        gone = db.scalars(
            delete(UsageEvent)
            .where(UsageEvent.user_id == user_id, UsageEvent.kind == UsageKind.RUN.value)
            .returning(UsageEvent.id)
        ).all()
        done.append(f"usage_events (run) deleted: {len(gone)}")
        # Its own daily counters only: the user's rows, never the 'global' row or another user's.
        days = db.scalars(
            delete(UsageDaily)
            .where(UsageDaily.user_id == user_id, UsageDaily.scope == f"user:{user_id}")
            .returning(UsageDaily.id)
        ).all()
        db.commit()
        done.append(f"usage_daily (this user's counters) deleted: {len(days)}")
    removed = redis.delete(*keys) if keys else 0
    done.append(f"redis rate-limit keys deleted: {removed}")
    return done


def mark_verified(settings: Settings, db: Session) -> bool:
    """Dev only: the smoke account is made through the sign-up API, so it starts unverified; mark it
    verified like every seeded account, so the run gate (EMAIL_VERIFICATION_REQUIRED) never stops
    it. Touches only email_verified_at of this one account and only when it is still empty."""
    if settings.app_env != "development":
        return False
    done = db.execute(
        update(User)
        .where(User.email == EMAIL, User.email_verified_at.is_(None))
        .values(email_verified_at=clock.utcnow())
    )
    db.commit()
    return bool(done.rowcount)  # type: ignore[attr-defined]  # CursorResult has rowcount


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
    embeds = [c for c in calls if c[0] == "embed"]
    if embeds:  # PDF runs: embedding tokens are outside max_tokens_per_run and have their own cap
        print(
            f"embed calls={len(embeds)} embed_tokens={sum(c[4] for c in embeds)} "
            f"embed_cost_usd={sum(c[7] for c in embeds)} (estimate, price from docs, not measured)"
        )
    print("\n--- trace lines (agent_steps)")
    for seq, agent, kind, state, key, args, attempt, model, _ in steps:
        print(
            f"{seq:>3} {agent:<9} {kind:<9} {state:<8} {key} {json.dumps(args, ensure_ascii=False)} a{attempt} {model or ''}"
        )
    for seq, _agent, _kind, _state, key, _args, _attempt, _model, payload in steps:
        if not payload:
            continue
        if "matched" in payload and "mode" in payload:
            dump(f"Hound search (step {seq}, {key})", payload)
            if "cosines" not in payload:  # the worker, not this script, writes the payload
                print(
                    "WARNING: this payload has no `cosines` field: the worker is running an older "
                    "image than this script. Rebuild it: docker compose up -d --build worker "
                    "scheduler api"
                )
            print(
                f"cosines (raw, kept passages): {payload.get('cosines')} | "
                f"top cosine before the floor: {payload.get('top_cosine')} | "
                f"fused scores: {payload.get('scores')}"
            )
        if "verdicts" in payload:  # Cat on a PDF: status and reason code per claim, no text
            dump(f"Cat quote-check verdicts (step {seq}, {key})", payload["verdicts"])
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
    parser.add_argument("csv", type=Path, help="a .csv or a .pdf file")
    parser.add_argument("--question", required=True)
    parser.add_argument("--api", default="http://api:8000/api")
    parser.add_argument(
        "--reset-quota", action="store_true", help="dev only: clear the smoke account's quota first"
    )
    args = parser.parse_args()
    if args.reset_quota:
        settings = get_settings()
        with Session(get_engine(settings.database_url.get_secret_value())) as db:
            redis = redis_client(settings.redis_url.get_secret_value())
            for line in reset_quota(settings, db, redis, own_ip(args.api)):
                print(f"reset-quota: {line}")
    api = Api(args.api)
    sign_in(api)
    settings = get_settings()
    with Session(get_engine(settings.database_url.get_secret_value())) as db:
        if mark_verified(settings, db):
            print("smoke account marked as email-verified (development only)")
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
    if view.get("report_id"):  # P9: the saved report, as the owner's browser would get it
        status, report = api.call("GET", f"/reports/{view['report_id']}")
        dump(f"report (GET /reports/{{id}}, HTTP {status})", report)
    else:
        print("\n--- no report_id on this run (no report row was created)")


if __name__ == "__main__":
    main()
