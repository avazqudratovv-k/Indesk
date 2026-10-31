import asyncio
import hashlib
import re
import stat
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.types import Message, Receive, Scope, Send

from app.core import clock
from app.core.bodylimit import BodyLimitMiddleware
from app.core.config import Settings, get_settings, load_limits
from app.db.models import AuditLog, Upload
from app.main import app
from tests.conftest import TEST_AUTH_SECRET, _test_redis_url
from tests.test_auth import MakeClient, signup

CSV = b"station,boardings\nHapjeong,100\nSeongsu,90\nMagok,80\n"
URL = "/api/uploads"
SMALL = load_limits().model_copy(update={"max_file_bytes": 200, "max_rows": 5, "max_columns": 4})


def settings_for(tmp_path: Path, **limits: Any) -> Settings:
    return Settings(
        app_env="test",
        auth_secret=TEST_AUTH_SECRET,
        redis_url=_test_redis_url(),
        storage_dir=tmp_path / "storage",
        limits=load_limits().model_copy(update=limits),
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.fixture
def small_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        auth_secret=TEST_AUTH_SECRET,
        redis_url=_test_redis_url(),
        storage_dir=tmp_path / "storage",
        limits=SMALL,
    )


def signed_in(
    make_client: MakeClient, settings: Settings, email: str, peer_last: int
) -> TestClient:
    client: TestClient = make_client(settings, peer=(f"203.0.113.{peer_last}", 50000))
    assert signup(client, email).status_code == 201
    return client


@pytest.fixture
def alice(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "alice@example.com", 10)


def post(
    client: TestClient,
    data: bytes = CSV,
    name: str = "ridership.csv",
    mime: str = "text/csv",
    consent: str | None = "true",
    **kw: Any,
) -> Any:
    form = {} if consent is None else {"consent": consent}
    return client.post(URL, files={"file": (name, data, mime)}, data=form, **kw)


def err(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json() == {"error": {"code": code}}


def stored_files(settings: Settings) -> list[Path]:
    root = settings.storage_dir
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


# ---- the happy path ----


def test_upload_ok(alice: TestClient, settings: Settings, session: Session) -> None:
    response = post(alice)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id",
        "user_id",
        "filename",
        "mime",
        "size",
        "page_count",
        "row_count",
        "status",
        "moderation",
        "created_at",
        "expires_at",
        "deleted_at",
    }
    assert body["filename"] == "ridership.csv"
    assert body["mime"] == "text/csv"
    assert body["size"] == len(CSV)
    assert body["row_count"] == 3
    assert body["page_count"] is None
    assert (body["status"], body["moderation"]) == ("ready", "pending")
    assert "storage_key" not in response.text
    assert "sha256" not in response.text

    (path,) = stored_files(settings)
    assert path.read_bytes() == CSV
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert re.fullmatch(r"[0-9a-f]{32}", path.name)
    assert path.parent.name == path.name[:2]
    assert "ridership" not in str(path.relative_to(settings.storage_dir))


def test_the_row_expires_24_hours_after_it_was_created_and_hashes_the_stored_bytes(
    alice: TestClient, settings: Settings, db_connection: Any
) -> None:
    upload_id = post(alice).json()["id"]
    with Session(bind=db_connection) as db:
        row = db.scalar(select(Upload).where(Upload.id == upload_id))
        assert row is not None
        assert (row.expires_at - row.created_at).total_seconds() == 24 * 3600
        assert row.sha256 == hashlib.sha256(CSV).hexdigest()
        assert row.storage_key == stored_files(settings)[0].name
        audit = db.scalars(select(AuditLog).where(AuditLog.action == "upload_created")).one()
        assert (str(audit.user_id), audit.target) == (str(row.user_id), upload_id)


def test_cp949_is_stored_as_utf8(alice: TestClient, settings: Settings, db_connection: Any) -> None:
    text = "역명,승차인원\n합정,100\n성수,90\n"
    response = post(alice, text.encode("cp949"), "서울.csv")
    assert response.status_code == 201
    assert response.json()["filename"] == "서울.csv"
    assert response.json()["row_count"] == 2
    (path,) = stored_files(settings)
    assert path.read_bytes() == text.encode("utf-8")
    with Session(bind=db_connection) as db:
        row = db.scalar(select(Upload))
        assert row is not None and row.sha256 == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_utf8_bom_is_dropped(alice: TestClient, settings: Settings) -> None:
    assert post(alice, b"\xef\xbb\xbf" + CSV).status_code == 201
    assert stored_files(settings)[0].read_bytes() == CSV


@pytest.mark.parametrize("mime", ["application/vnd.ms-excel", "application/csv", ""])
def test_browsers_that_report_another_csv_type(alice: TestClient, mime: str) -> None:
    assert post(alice, mime=mime).status_code == 201


# ---- refusals, in the order the endpoint checks ----


def test_no_consent(alice: TestClient, settings: Settings) -> None:
    for consent in (None, "", "false", "True", "1", "yes"):
        err(post(alice, consent=consent), 422, "CONSENT_REQUIRED")
    assert stored_files(settings) == []


def test_size_limit_to_the_byte(make_client: MakeClient, small_settings: Settings) -> None:
    roomy = small_settings.model_copy(
        update={"limits": SMALL.model_copy(update={"max_rows": 1000})}
    )
    client = signed_in(make_client, roomy, "size@example.com", 11)
    row = b"x,y\n"
    exactly = row + b"1,2\n" * ((SMALL.max_file_bytes - len(row)) // 4)
    assert len(exactly) == SMALL.max_file_bytes
    assert post(client, exactly).status_code == 201
    err(post(client, exactly + b"1"), 413, "FILE_TOO_LARGE")  # max + 1 byte
    assert len(stored_files(roomy)) == 1  # only the first


def test_the_real_limit_is_five_megabytes(alice: TestClient, settings: Settings) -> None:
    max_bytes = 5 * 1024 * 1024
    line = b"x" * 2047 + b"\n"
    body = b"h\n" + line * ((max_bytes - 2) // len(line))
    body += b"y" * (max_bytes - len(body) - 1) + b"\n"
    assert len(body) == max_bytes
    assert post(alice, body).status_code == 201
    err(post(alice, body + b"z"), 413, "FILE_TOO_LARGE")


def test_a_body_far_over_the_limit_is_cut_off_before_it_is_parsed(alice: TestClient) -> None:
    huge = b"a,b\n" + b"1,2\n" * (2 * 1024 * 1024)  # 8 MB
    err(post(alice, huge), 413, "FILE_TOO_LARGE")


@pytest.mark.parametrize("data", [b"", b"a,b\n", b"a,b\n\n\n"])
def test_empty_and_header_only(alice: TestClient, data: bytes) -> None:
    err(post(alice, data), 422, "EMPTY_FILE")


@pytest.mark.parametrize(
    ("name", "mime", "status", "code"),
    [
        ("data.txt", "text/plain", 415, "UNSUPPORTED_TYPE"),
        ("data.xlsx", "", 415, "UNSUPPORTED_TYPE"),
        ("data", "text/csv", 415, "TYPE_MISMATCH"),
        ("data.csv", "application/pdf", 415, "TYPE_MISMATCH"),
        ("data.csv", "image/png", 415, "TYPE_MISMATCH"),
        ("data.png", "text/csv", 415, "TYPE_MISMATCH"),
    ],
)
def test_declared_type(alice: TestClient, name: str, mime: str, status: int, code: str) -> None:
    err(post(alice, CSV, name, mime), status, code)


@pytest.mark.parametrize(
    "data",
    [b"PK\x03\x04" + b"\x00" * 50, b"%PDF-1.7\n1 0 obj\n", b"a,b\n1,\x00\n"],
    ids=["xlsx-renamed", "pdf-renamed", "nul-bytes"],
)
def test_content_that_is_not_csv_even_with_a_csv_name_and_type(
    alice: TestClient, data: bytes
) -> None:
    err(post(alice, data), 415, "TYPE_MISMATCH")


def test_undecodable_bytes(alice: TestClient) -> None:
    err(post(alice, b"a,b\n\xff\xfe,1\n"), 422, "BAD_CSV")


def test_too_many_rows_and_columns_and_ragged(
    make_client: MakeClient, small_settings: Settings
) -> None:
    client = signed_in(make_client, small_settings, "shape@example.com", 12)
    too_many = post(client, b"a,b\n" + b"1,2\n" * 6)
    assert too_many.status_code == 422
    assert too_many.json() == {"error": {"code": "TOO_MANY_ROWS", "rows": 6, "max": 5}}
    assert post(client, b"a,b\n" + b"1,2\n" * 5).status_code == 201
    err(post(client, b"a,b,c,d,e\n1,2,3,4,5\n"), 422, "TOO_MANY_COLUMNS")
    err(post(client, b"a,b,c\n1,2,3\n4,5\n"), 422, "BAD_CSV")
    err(post(client, b"a,b\n1,2,3\n"), 422, "BAD_CSV")
    assert len(stored_files(small_settings)) == 1  # a refusal never leaves a file


def test_no_file_is_a_validation_error(alice: TestClient) -> None:
    other = {"other": ("o.csv", CSV, "text/csv")}
    err(alice.post(URL, data={"consent": "true"}, files=other), 422, "VALIDATION_ERROR")
    err(alice.post(URL, data={"consent": "true"}), 415, "UNSUPPORTED_TYPE")  # not a multipart body


# ---- filenames never reach the disk layout ----


@pytest.mark.parametrize(
    ("sent", "label"),
    [
        ("../../etc/passwd.csv", "passwd.csv"),
        ("/etc/passwd.csv", "passwd.csv"),
        ("..\\..\\windows\\system.csv", "system.csv"),
        ("C:\\temp\\x.csv", "x.csv"),
        ("a%00b.csv", "a%00b.csv"),
    ],
)
def test_path_tricks_in_the_filename(
    alice: TestClient, settings: Settings, tmp_path: Path, sent: str, label: str
) -> None:
    response = post(alice, name=sent)
    assert response.status_code == 201
    assert response.json()["filename"] == label
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files) == 1
    relative = files[0].relative_to(settings.storage_dir)  # inside STORAGE_DIR, nothing elsewhere
    assert re.fullmatch(r"[0-9a-f]{2}/[0-9a-f]{32}", relative.as_posix())


def test_a_name_without_csv_after_cleaning_is_refused(
    alice: TestClient, settings: Settings
) -> None:
    err(post(alice, name="/etc/passwd", mime=""), 415, "UNSUPPORTED_TYPE")
    err(post(alice, name="../..", mime=""), 415, "UNSUPPORTED_TYPE")
    assert stored_files(settings) == []


# ---- who may call ----


def test_unauthenticated(make_client: MakeClient, settings: Settings) -> None:
    anon = make_client(settings)
    err(post(anon), 401, "UNAUTHENTICATED")
    err(anon.get(URL), 401, "UNAUTHENTICATED")
    err(anon.get(f"{URL}/00000000-0000-0000-0000-000000000000"), 401, "UNAUTHENTICATED")
    assert stored_files(settings) == []


def test_origin_is_checked(alice: TestClient, make_client: MakeClient, settings: Settings) -> None:
    err(post(alice, headers={"Origin": "https://evil.example"}), 403, "ORIGIN_NOT_ALLOWED")
    no_origin = make_client(settings, origin=None)
    err(post(no_origin), 403, "ORIGIN_NOT_ALLOWED")
    assert stored_files(settings) == []


def test_list_and_get_own_uploads_newest_first(alice: TestClient) -> None:
    first = post(alice, name="one.csv").json()
    second = post(alice, name="two.csv").json()
    listed = alice.get(URL)
    assert listed.status_code == 200
    assert [u["id"] for u in listed.json()] == [second["id"], first["id"]]
    assert "storage_key" not in listed.text and "sha256" not in listed.text
    one = alice.get(f"{URL}/{first['id']}")
    assert one.status_code == 200 and one.json() == first
    assert "storage_key" not in one.text and "sha256" not in one.text


def test_another_users_upload_is_a_404_identical_to_a_missing_one(
    make_client: MakeClient, settings: Settings, alice: TestClient
) -> None:
    mine = post(alice).json()
    bob = signed_in(make_client, settings, "bob@example.com", 20)
    theirs = bob.get(f"{URL}/{mine['id']}")
    missing = bob.get(f"{URL}/00000000-0000-4000-8000-000000000000")
    malformed = bob.get(f"{URL}/not-a-uuid")
    for response in (theirs, missing, malformed):
        err(response, 404, "NOT_FOUND")
    assert theirs.content == missing.content == malformed.content
    assert bob.get(URL).json() == []
    assert [u["id"] for u in alice.get(URL).json()] == [mine["id"]]


def test_expired_and_deleted_uploads_are_hidden(alice: TestClient, db_connection: Any) -> None:
    keep = post(alice, name="keep.csv").json()
    old = post(alice, name="old.csv").json()
    gone = post(alice, name="gone.csv").json()
    with Session(bind=db_connection) as db:
        db.execute(
            update(Upload)
            .where(Upload.id == old["id"])
            .values(expires_at=clock.utcnow() - timedelta(seconds=1))
        )
        db.execute(update(Upload).where(Upload.id == gone["id"]).values(deleted_at=clock.utcnow()))
        db.commit()
    assert [u["id"] for u in alice.get(URL).json()] == [keep["id"]]
    err(alice.get(f"{URL}/{old['id']}"), 404, "NOT_FOUND")
    err(alice.get(f"{URL}/{gone['id']}"), 404, "NOT_FOUND")


# ---- the body limit middleware on its own (chunked bodies have no Content-Length) ----


async def _drain_app(scope: Scope, receive: Receive, send: Send) -> None:
    more = True
    while more:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        more = message.get("more_body", False)
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _call(app: Any, chunks: list[bytes], headers: list[tuple[bytes, bytes]]) -> list[Message]:
    queue = [
        {"type": "http.request", "body": c, "more_body": i < len(chunks) - 1}
        for i, c in enumerate(chunks)
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/up", "headers": headers}
    await app(scope, receive, send)
    return sent


def test_body_limit_middleware_counts_real_bytes_not_the_header() -> None:
    app = BodyLimitMiddleware(_drain_app, method="POST", path="/up", limit=lambda: 10)
    under = asyncio.run(_call(app, [b"12345", b"12345"], []))
    assert under[0]["status"] == 200
    over = asyncio.run(_call(app, [b"12345", b"123456"], []))  # chunked: no Content-Length
    assert over[0]["status"] == 413 and b"FILE_TOO_LARGE" in over[1]["body"]
    liar = asyncio.run(_call(app, [b"1234567890123"], [(b"content-length", b"3")]))
    assert liar[0]["status"] == 413
    declared = asyncio.run(_call(app, [b"x"], [(b"content-length", b"11")]))
    assert declared[0]["status"] == 413


# ---- max columns and the upload rate limit ----


def wide_csv(columns: int) -> bytes:
    return (
        ",".join(f"c{i}" for i in range(columns)) + "\n" + ",".join(["1"] * columns) + "\n"
    ).encode()


def test_too_many_columns_is_422_and_stores_nothing(
    make_client: MakeClient, settings: Settings
) -> None:
    client = signed_in(make_client, settings, "wide@example.com", 40)
    columns = settings.limits.max_columns or 0
    assert columns == 200
    assert post(client, wide_csv(columns)).status_code == 201
    err(post(client, wide_csv(columns + 1)), 422, "TOO_MANY_COLUMNS")
    assert len(stored_files(settings)) == 1


def test_the_31st_upload_in_an_hour_is_429_with_retry_after(
    make_client: MakeClient, settings: Settings
) -> None:
    assert settings.limits.uploads_per_hour == 30
    client = signed_in(make_client, settings, "busy@example.com", 41)
    for _ in range(30):
        assert post(client).status_code == 201
    blocked = post(client)
    err(blocked, 429, "RATE_LIMITED")
    assert 0 < int(blocked.headers["retry-after"]) <= 3600
    other = signed_in(make_client, settings, "calm@example.com", 42)
    assert post(other).status_code == 201  # the limit is per user


def test_refused_attempts_count_too(make_client: MakeClient, tmp_path: Path) -> None:
    settings = settings_for(tmp_path, uploads_per_hour=3)
    client = signed_in(make_client, settings, "bad@example.com", 43)
    err(post(client, consent=None), 422, "CONSENT_REQUIRED")
    err(post(client, b"", name="empty.csv"), 422, "EMPTY_FILE")
    err(post(client, name="x.png", mime="image/png"), 415, "UNSUPPORTED_TYPE")
    err(post(client), 429, "RATE_LIMITED")


def test_signed_out_attempts_do_not_count(make_client: MakeClient, tmp_path: Path) -> None:
    settings = settings_for(tmp_path, uploads_per_hour=2)
    client = signed_in(make_client, settings, "out@example.com", 44)
    anonymous = make_client(settings, peer=("203.0.113.45", 50000))
    for _ in range(5):
        err(post(anonymous), 401, "UNAUTHENTICATED")
    assert post(client).status_code == 201
    assert post(client).status_code == 201


def test_redis_down_refuses_the_upload(make_client: MakeClient, tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    client = signed_in(make_client, settings, "down@example.com", 46)
    down = settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/15")})
    app.dependency_overrides[get_settings] = lambda: down
    err(post(client), 503, "NOT_READY")
    assert stored_files(settings) == []


def test_semicolon_upload_is_stored_comma_separated(
    alice: TestClient, settings: Settings, db_connection: Any
) -> None:
    response = post(alice, "역명;승차인원\n합정;100\n성수;90\n".encode(), "서울.csv")
    assert response.status_code == 201
    assert response.json()["row_count"] == 2
    (path,) = stored_files(settings)
    stored = "역명,승차인원\n합정,100\n성수,90\n".encode()
    assert path.read_bytes() == stored
    with Session(bind=db_connection) as db:
        row = db.scalar(select(Upload))
        assert row is not None and row.sha256 == hashlib.sha256(stored).hexdigest()
