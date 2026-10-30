import itertools
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Connection, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.core.security import hash_refresh_token, keyed_hash
from app.db.models import AuditLog, RefreshToken, User
from app.main import app
from app.routers.deps import current_user
from tests.conftest import TEST_AUTH_SECRET, TEST_ORIGIN

PASSWORD = "correct horse battery"  # noqa: S105
ERR_CREDENTIALS = {"error": {"code": "INVALID_CREDENTIALS"}}
ERR_UNAUTH = {"error": {"code": "UNAUTHENTICATED"}}

MakeClient = Callable[..., TestClient]


def signup_body(email: str = "ada@example.com", **kw: Any) -> dict[str, Any]:
    return {"email": email, "password": PASSWORD, "display_name": "Ada Lovelace", **kw}


def signup(client: TestClient, email: str = "ada@example.com", **kw: Any) -> Any:
    return client.post("/api/auth/signup", json=signup_body(email, **kw))


def login(client: TestClient, email: str = "ada@example.com", password: str = PASSWORD) -> Any:
    return client.post("/api/auth/login", json={"email": email, "password": password})


def cookie_headers(response: Any) -> dict[str, str]:
    """Set-Cookie header lines by cookie name."""
    lines = response.headers.get_list("set-cookie")
    return {line.split("=", 1)[0]: line for line in lines}


def with_cookie(name: str, value: str) -> dict[str, str]:
    """An explicit Cookie header: lets a test replay an old token whatever the jar holds."""
    return {"Cookie": f"{name}={value}"}


def refresh_value(client: TestClient) -> str:
    value = client.cookies.get("indesk_refresh")
    assert value
    return str(value)


def audit_actions(conn: Connection) -> list[str]:
    with Session(bind=conn) as db:
        rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)).all()
        return sorted(r.action for r in rows)


# ---- signup ----


def test_signup_creates_user_and_sets_cookies(auth_client: TestClient) -> None:
    response = signup(auth_client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["display_name"] == "Ada Lovelace"
    assert body["handle"].startswith("ada-lovelace-")
    assert "password" not in body
    assert "password_hash" not in body
    access = cookie_headers(response)["indesk_access"]
    refresh = cookie_headers(response)["indesk_refresh"]
    for line in (access, refresh):
        assert "HttpOnly" in line
        assert "SameSite=lax" in line
        assert "Secure" not in line  # not production
    assert "Path=/;" in access
    assert "Max-Age=900" in access
    assert "Path=/api/auth" in refresh
    assert "Max-Age=21600" in refresh


def test_cookies_are_secure_only_in_production(make_client: MakeClient) -> None:
    prod = Settings(
        app_env="production",
        auth_secret=TEST_AUTH_SECRET,
        allowed_origins=["https://indesk.example"],
        trusted_proxies=["10.0.0.0/8"],
        redis_url=Settings().redis_url.get_secret_value().rsplit("/", 1)[0] + "/15",
    )
    response = signup(make_client(prod, origin="https://indesk.example"))
    assert response.status_code == 201
    for line in cookie_headers(response).values():
        assert "Secure" in line
        assert "HttpOnly" in line
        assert "SameSite=lax" in line


def test_email_is_stripped_lowercased_and_unique(auth_client: TestClient) -> None:
    assert signup(auth_client, "  Ada@Example.COM ").json()["email"] == "ada@example.com"
    again = signup(auth_client, "ada@example.com")
    assert again.status_code == 409
    assert again.json() == {"error": {"code": "EMAIL_TAKEN"}}
    assert signup(auth_client, "ADA@example.com").status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        signup_body(password="short"),  # 5
        signup_body(password="x" * 9),
        signup_body(password="x" * 129),
        signup_body(email="not-an-email"),
        signup_body(email="a" * 250 + "@x.io"),
        signup_body(display_name=""),
        signup_body(display_name="   "),
        signup_body(display_name="x" * 61),
        signup_body(display_name="bad\x00name"),
        signup_body(handle="chosen"),  # the server derives the handle
        {"email": "ada@example.com", "password": PASSWORD},  # missing display_name
        {},
    ],
)
def test_signup_rejects_bad_input_without_echo(
    auth_client: TestClient, body: dict[str, Any]
) -> None:
    response = auth_client.post("/api/auth/signup", json=body)
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "VALIDATION_ERROR"}}


def test_password_boundaries_are_accepted(auth_client: TestClient) -> None:
    assert signup(auth_client, "a@example.com", password="x" * 10).status_code == 201
    assert signup(auth_client, "b@example.com", password="y" * 128).status_code == 201


def test_plain_password_is_never_stored_or_returned(
    auth_client: TestClient, db_connection: Connection
) -> None:
    response = signup(auth_client)
    assert PASSWORD not in response.text
    me = auth_client.get("/api/me")
    assert PASSWORD not in me.text
    assert "password_hash" not in me.json()
    with Session(bind=db_connection) as db:
        user = db.scalars(select(User)).one()
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        # Nothing in the audit log or the refresh table holds the password or the email either.
        dump = " ".join(
            str(v)
            for r in db.scalars(select(AuditLog)).all()
            for v in (r.action, r.target, r.ip_hash)
        )
        assert PASSWORD not in dump
        assert "ada@example.com" not in dump


# ---- login ----


def test_login_ok(auth_client: TestClient) -> None:
    signup(auth_client)
    auth_client.cookies.clear()
    response = login(auth_client)
    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    assert set(cookie_headers(response)) == {"indesk_access", "indesk_refresh"}
    assert auth_client.get("/api/me").status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    signup(auth_client)
    calls: list[str] = []
    from app.core import security
    from app.services import auth as service

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash[:10])
        return security.verify_password(password_hash, password)

    monkeypatch.setattr(service, "verify_password", spy)
    wrong = login(auth_client, password="not the password")
    unknown = login(auth_client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.content == unknown.content
    assert wrong.json() == ERR_CREDENTIALS
    assert "set-cookie" not in wrong.headers
    # Both paths ran exactly one Argon2 verification (the unknown one against a dummy hash).
    assert calls == ["$argon2id$", "$argon2id$"]


def test_login_does_not_echo_input(auth_client: TestClient) -> None:
    response = login(auth_client, email="nobody@example.com", password="secret-input-123")
    assert "secret-input-123" not in response.text
    assert "nobody" not in response.text


def test_short_login_password_is_just_wrong(auth_client: TestClient) -> None:
    signup(auth_client)
    assert login(auth_client, password="a").json() == ERR_CREDENTIALS


# ---- tokens ----


def test_access_token_has_only_sub_iat_exp(auth_client: TestClient) -> None:
    signup(auth_client)
    token = auth_client.cookies.get("indesk_access")
    assert token
    claims = jwt.decode(token, TEST_AUTH_SECRET, algorithms=["HS256"])
    assert set(claims) == {"sub", "iat", "exp"}
    assert claims["exp"] - claims["iat"] == 15 * 60


def test_refresh_token_is_stored_only_as_a_hash(
    auth_client: TestClient, db_connection: Connection
) -> None:
    signup(auth_client)
    token = refresh_value(auth_client)
    with Session(bind=db_connection) as db:
        row = db.scalars(select(RefreshToken)).one()
        assert row.token_hash == hash_refresh_token(token)
        assert row.token_hash != token
        assert token not in row.token_hash


def test_refresh_rotates_and_old_token_is_rejected(auth_client: TestClient) -> None:
    signup(auth_client)
    old = refresh_value(auth_client)
    response = auth_client.post("/api/auth/refresh")
    assert response.status_code == 204
    assert set(cookie_headers(response)) == {"indesk_access", "indesk_refresh"}
    new = refresh_value(auth_client)
    assert new != old
    assert auth_client.get("/api/me").status_code == 200
    stale = auth_client.post("/api/auth/refresh", headers=with_cookie("indesk_refresh", old))
    assert stale.status_code == 401
    assert stale.json() == ERR_UNAUTH


def test_reuse_of_a_rotated_token_revokes_the_family(
    auth_client: TestClient, db_connection: Connection
) -> None:
    signup(auth_client)
    first = refresh_value(auth_client)
    auth_client.post("/api/auth/refresh")
    second = refresh_value(auth_client)
    reuse = auth_client.post("/api/auth/refresh", headers=with_cookie("indesk_refresh", first))
    assert reuse.status_code == 401
    # The newest token of the family is dead too.
    after = auth_client.post("/api/auth/refresh", headers=with_cookie("indesk_refresh", second))
    assert after.status_code == 401
    with Session(bind=db_connection) as db:
        rows = db.scalars(select(RefreshToken)).all()
        assert len(rows) == 2
        assert all(r.revoked_at is not None for r in rows)
    assert "refresh_reuse" in audit_actions(db_connection)


def test_refresh_without_cookie_or_with_garbage_is_401(auth_client: TestClient) -> None:
    assert auth_client.post("/api/auth/refresh").json() == ERR_UNAUTH
    garbage = auth_client.post("/api/auth/refresh", headers=with_cookie("indesk_refresh", "nope"))
    assert garbage.status_code == 401


def test_refresh_token_expires_after_6_hours(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    signup(auth_client)
    real_now = clock.utcnow()
    monkeypatch.setattr(clock, "utcnow", lambda: real_now + timedelta(hours=5, minutes=59))
    assert auth_client.post("/api/auth/refresh").status_code == 204
    monkeypatch.setattr(clock, "utcnow", lambda: real_now + timedelta(hours=6, minutes=1))
    assert auth_client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_the_family_and_clears_cookies(auth_client: TestClient) -> None:
    signup(auth_client)
    token = refresh_value(auth_client)
    response = auth_client.post("/api/auth/logout")
    assert response.status_code == 204
    cleared = cookie_headers(response)
    assert "Max-Age=0" in cleared["indesk_access"]
    assert "Max-Age=0" in cleared["indesk_refresh"]
    assert auth_client.get("/api/me").status_code == 401
    replay = auth_client.post("/api/auth/refresh", headers=with_cookie("indesk_refresh", token))
    assert replay.status_code == 401


def test_logout_without_session_is_still_204(auth_client: TestClient) -> None:
    assert auth_client.post("/api/auth/logout").status_code == 204


def test_expired_access_token_is_401(auth_client: TestClient) -> None:
    signup(auth_client)
    user_id = auth_client.get("/api/me").json()["id"]
    past = datetime.now(UTC) - timedelta(hours=1)
    claims = {"sub": user_id, "iat": past, "exp": past + timedelta(minutes=15)}
    token = jwt.encode(claims, TEST_AUTH_SECRET, algorithm="HS256")
    response = auth_client.get("/api/me", headers=with_cookie("indesk_access", token))
    assert response.status_code == 401
    assert response.json() == ERR_UNAUTH


def test_tampered_or_unsigned_access_tokens_are_401(auth_client: TestClient) -> None:
    signup(auth_client)
    user_id = auth_client.get("/api/me").json()["id"]
    now = datetime.now(UTC)
    claims = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=15)}
    good = jwt.encode(claims, TEST_AUTH_SECRET, algorithm="HS256")
    head, payload, signature = good.split(".")
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")
    forged = {
        "bad signature": f"{head}.{payload}.{flipped}",
        "alg none": jwt.encode(claims, "", algorithm="none"),
        "other secret": jwt.encode(claims, "another-secret-" + "y" * 40, algorithm="HS256"),
        "other algorithm": jwt.encode(claims, TEST_AUTH_SECRET, algorithm="HS384"),
        "missing exp": jwt.encode(
            {"sub": user_id, "iat": now}, TEST_AUTH_SECRET, algorithm="HS256"
        ),
        "not a uuid": jwt.encode(
            {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)},
            TEST_AUTH_SECRET,
            algorithm="HS256",
        ),
        "unknown user": jwt.encode(
            {"sub": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(minutes=5)},
            TEST_AUTH_SECRET,
            algorithm="HS256",
        ),
        "garbage": "not.a.jwt",
    }
    for name, token in forged.items():
        response = auth_client.get("/api/me", headers=with_cookie("indesk_access", token))
        assert response.status_code == 401, name
        assert response.json() == ERR_UNAUTH, name


def test_me_without_cookie_is_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/me")
    assert response.status_code == 401
    assert response.json() == ERR_UNAUTH


def test_soft_deleted_user_cannot_log_in_refresh_or_use_me(
    auth_client: TestClient, db_connection: Connection
) -> None:
    signup(auth_client)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET deleted_at = now()"))
        db.commit()
    assert auth_client.get("/api/me").status_code == 401
    assert auth_client.post("/api/auth/refresh").status_code == 401
    assert login(auth_client).json() == ERR_CREDENTIALS


# ---- current_user dependency ----


@pytest.fixture
def whoami_route() -> Iterator[None]:
    def whoami(user: User = Depends(current_user)) -> dict[str, str]:  # noqa: B008
        return {"id": str(user.id)}

    app.add_api_route("/api/_whoami", whoami)
    yield
    app.router.routes.pop()


@pytest.mark.usefixtures("whoami_route")
def test_current_user_dependency(auth_client: TestClient) -> None:
    assert auth_client.get("/api/_whoami").status_code == 401
    signup(auth_client)
    response = auth_client.get("/api/_whoami")
    assert response.status_code == 200
    assert response.json()["id"] == auth_client.get("/api/me").json()["id"]


@pytest.mark.usefixtures("whoami_route")
def test_dev_session_cookie_is_ignored(auth_client: TestClient) -> None:
    response = auth_client.get("/api/_whoami", headers=with_cookie("dev_session", "in"))
    assert response.status_code == 401


# ---- CSRF: Origin and content type ----


def test_write_without_origin_is_rejected(make_client: MakeClient, auth_settings: Settings) -> None:
    client = make_client(auth_settings, origin=None)
    response = signup(client)
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "ORIGIN_NOT_ALLOWED"}}
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/refresh").status_code == 403


@pytest.mark.parametrize(
    "origin", ["http://evil.example", "null", "http://localhost:3001", "https://localhost:3000"]
)
def test_write_with_wrong_origin_is_rejected(
    make_client: MakeClient, auth_settings: Settings, origin: str
) -> None:
    response = signup(make_client(auth_settings, origin=origin))
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "ORIGIN_NOT_ALLOWED"}}


def test_write_with_right_origin_passes(make_client: MakeClient, auth_settings: Settings) -> None:
    assert signup(make_client(auth_settings, origin=TEST_ORIGIN + "/")).status_code == 201


def test_referer_is_used_when_origin_is_missing(
    make_client: MakeClient, auth_settings: Settings
) -> None:
    client = make_client(auth_settings, origin=None)
    ok = client.post(
        "/api/auth/signup", json=signup_body(), headers={"Referer": TEST_ORIGIN + "/signup?x=1"}
    )
    assert ok.status_code == 201
    bad = client.post(
        "/api/auth/signup",
        json=signup_body("b@example.com"),
        headers={"Referer": "http://evil.example/signup"},
    )
    assert bad.status_code == 403


def test_wrong_origin_is_not_rescued_by_a_good_referer(
    make_client: MakeClient, auth_settings: Settings
) -> None:
    client = make_client(auth_settings, origin="http://evil.example")
    response = client.post(
        "/api/auth/signup", json=signup_body(), headers={"Referer": TEST_ORIGIN + "/"}
    )
    assert response.status_code == 403


def test_reads_do_not_need_an_origin(make_client: MakeClient, auth_settings: Settings) -> None:
    client = make_client(auth_settings, origin=None)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/me").status_code == 401  # not 403


def test_allowed_origins_come_from_settings(
    make_client: MakeClient, auth_settings: Settings
) -> None:
    other = auth_settings.model_copy(update={"allowed_origins": ["https://app.example"]})
    assert signup(make_client(other, origin=TEST_ORIGIN)).status_code == 403
    assert signup(make_client(other, origin="https://app.example")).status_code == 201


@pytest.mark.parametrize(
    "content_type", ["text/plain", "application/x-www-form-urlencoded", "text/xml"]
)
def test_only_json_and_multipart_bodies_are_accepted(
    auth_client: TestClient, content_type: str
) -> None:
    response = auth_client.post(
        "/api/auth/signup", content=b"email=a@b.co", headers={"Content-Type": content_type}
    )
    assert response.status_code == 415
    assert response.json() == {"error": {"code": "UNSUPPORTED_TYPE"}}


def test_body_without_content_type_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post("/api/auth/signup", content=b'{"a": 1}')
    assert response.status_code == 415


def test_json_with_charset_and_multipart_pass_the_type_check(auth_client: TestClient) -> None:
    ok = auth_client.post(
        "/api/auth/signup",
        content=b'{"email": "bad"}',
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    assert ok.status_code == 422  # past the type check, stopped by validation
    multipart = auth_client.post("/api/auth/signup", files={"f": ("a.txt", b"x")})
    assert multipart.status_code == 422


# ---- rate limits ----


def test_sixth_signup_from_one_ip_is_429(auth_client: TestClient) -> None:
    for n in range(5):
        assert signup(auth_client, f"user{n}@example.com").status_code == 201
    blocked = signup(auth_client, "user5@example.com")
    assert blocked.status_code == 429
    assert blocked.json() == {"error": {"code": "RATE_LIMITED"}}
    retry_after = int(blocked.headers["retry-after"])
    assert 0 < retry_after <= 3600


def test_signup_limit_is_per_ip(make_client: MakeClient, auth_settings: Settings) -> None:
    first = make_client(auth_settings, peer=("203.0.113.1", 1))
    for n in range(5):
        assert signup(first, f"user{n}@example.com").status_code == 201
    assert signup(first, "user5@example.com").status_code == 429
    second = make_client(auth_settings, peer=("203.0.113.2", 1))
    assert signup(second, "user5@example.com").status_code == 201


def test_eleventh_login_attempt_is_429_and_another_email_is_not_blocked(
    auth_client: TestClient,
) -> None:
    signup(auth_client)
    signup(auth_client, "grace@example.com")
    for _ in range(10):
        assert login(auth_client, password="wrong password!").status_code == 401
    blocked = login(auth_client, password="wrong password!")
    assert blocked.status_code == 429
    assert blocked.json() == {"error": {"code": "RATE_LIMITED"}}
    assert int(blocked.headers["retry-after"]) > 0
    # Even the right password waits, for this IP and email only.
    assert login(auth_client).status_code == 429
    assert login(auth_client, email="grace@example.com").status_code == 200


def test_forwarded_header_is_ignored_without_a_trusted_proxy(
    make_client: MakeClient, auth_settings: Settings
) -> None:
    client = make_client(auth_settings, peer=("10.0.0.2", 1))
    for n in range(5):
        response = client.post(
            "/api/auth/signup",
            json=signup_body(f"user{n}@example.com"),
            headers={"X-Forwarded-For": f"198.51.100.{n}"},
        )
        assert response.status_code == 201
    spoofed = client.post(
        "/api/auth/signup",
        json=signup_body("user9@example.com"),
        headers={"X-Forwarded-For": "198.51.100.99"},
    )
    assert spoofed.status_code == 429


def test_forwarded_header_is_honoured_from_a_trusted_proxy(
    make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    trusted = auth_settings.model_copy(update={"trusted_proxies": ["10.0.0.0/8"]})
    client = make_client(trusted, peer=("10.0.0.2", 1))
    for n in range(6):
        response = client.post(
            "/api/auth/signup",
            json=signup_body(f"user{n}@example.com"),
            headers={"X-Forwarded-For": f"198.51.100.{n}"},
        )
        assert response.status_code == 201  # each forwarded client has its own window
    # Rightmost untrusted address wins: a client cannot prepend a fake one.
    client.post(
        "/api/auth/signup",
        json=signup_body("last@example.com"),
        headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.50, 10.0.0.9"},
    )
    with Session(bind=db_connection) as db:
        hashes = set(db.scalars(select(AuditLog.ip_hash)).all())
    assert keyed_hash(TEST_AUTH_SECRET, "203.0.113.50") in hashes
    assert keyed_hash(TEST_AUTH_SECRET, "6.6.6.6") not in hashes
    assert keyed_hash(TEST_AUTH_SECRET, "10.0.0.2") not in hashes


def test_garbage_forwarded_header_falls_back_to_the_peer(
    make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    trusted = auth_settings.model_copy(update={"trusted_proxies": ["10.0.0.0/8"]})
    client = make_client(trusted, peer=("10.0.0.2", 1))
    client.post("/api/auth/signup", json=signup_body(), headers={"X-Forwarded-For": "not-an-ip"})
    with Session(bind=db_connection) as db:
        assert db.scalars(select(AuditLog.ip_hash)).one() == keyed_hash(
            TEST_AUTH_SECRET, "10.0.0.2"
        )


def test_redis_down_fails_closed(make_client: MakeClient, auth_settings: Settings) -> None:
    down = auth_settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/15")})
    client = make_client(down)
    for response in (signup(client), login(client)):
        assert response.status_code == 503
        assert response.json() == {"error": {"code": "NOT_READY"}}


# ---- AUTH_SECRET ----


@pytest.mark.parametrize("secret", [None, "short-secret"])
def test_auth_is_off_without_a_good_secret(
    make_client: MakeClient, auth_settings: Settings, secret: str | None
) -> None:
    off = auth_settings.model_copy(
        update={"auth_secret": None if secret is None else SecretStr(secret)}
    )
    client = make_client(off)
    assert signup(client).json() == {"error": {"code": "NOT_READY"}}
    assert login(client).status_code == 503
    assert client.get("/api/me").status_code == 503
    assert client.post("/api/auth/refresh").status_code == 503


def test_the_missing_secret_is_logged_once_without_a_value(
    make_client: MakeClient, auth_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    from app.routers import deps

    deps._warned_missing_secret = False
    client = make_client(
        auth_settings.model_copy(update={"auth_secret": SecretStr("short-secret")})
    )
    with caplog.at_level("ERROR", logger="indesk.auth"):
        signup(client)
        signup(client)
    messages = [r.getMessage() for r in caplog.records if r.name == "indesk.auth"]
    assert len(messages) == 1
    assert "short-secret" not in messages[0]


# ---- audit log ----


def test_audit_rows_are_written_without_raw_ip_or_email(
    auth_client: TestClient, db_connection: Connection
) -> None:
    signup(auth_client)
    login(auth_client, password="wrong password!")
    login(auth_client)
    auth_client.post("/api/auth/logout")
    assert audit_actions(db_connection) == ["login", "login_failed", "logout", "signup"]
    expected = keyed_hash(TEST_AUTH_SECRET, "203.0.113.7")
    with Session(bind=db_connection) as db:
        rows = db.scalars(select(AuditLog)).all()
        assert all(r.ip_hash == expected for r in rows)
        assert all(r.target is None for r in rows)
        dump = " ".join(str(v) for r in rows for v in (r.action, r.target, r.ip_hash))
        assert "203.0.113.7" not in dump
        assert "ada@example.com" not in dump
        assert all(r.user_id is not None for r in rows)


def test_failed_login_for_unknown_email_is_audited_without_a_user(
    auth_client: TestClient, db_connection: Connection
) -> None:
    login(auth_client, email="nobody@example.com")
    with Session(bind=db_connection) as db:
        row = db.scalars(select(AuditLog)).one()
        assert (row.action, row.user_id) == ("login_failed", None)


# ---- handles ----


def test_handle_collision_retries_with_a_new_suffix(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import auth as service

    suffixes = itertools.chain(["aaaaaa", "aaaaaa", "bbbbbb"], itertools.repeat("cccccc"))
    monkeypatch.setattr(service, "_suffix", lambda: next(suffixes))
    first = signup(auth_client, "a@example.com", display_name="Kim")
    second = signup(auth_client, "b@example.com", display_name="Kim")
    assert first.json()["handle"] == "kim-aaaaaa"
    assert second.status_code == 201
    assert second.json()["handle"] == "kim-bbbbbb"


def test_handle_gives_up_after_five_collisions(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import auth as service

    monkeypatch.setattr(service, "_suffix", lambda: "aaaaaa")
    assert signup(auth_client, "a@example.com", display_name="Kim").status_code == 201
    response = signup(auth_client, "b@example.com", display_name="Kim")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL"}}


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Ada Lovelace", "ada-lovelace"),
        ("김민수", "user"),
        ("  !!  ", "user"),
        ("Zoë Müller", "zoe-muller"),
        ("x" * 60, "x" * 20),
    ],
)
def test_make_handle(name: str, slug: str) -> None:
    from app.services.auth import make_handle

    handle = make_handle(name, "abc123")
    assert handle == f"{slug}-abc123"
    assert 3 <= len(handle) <= 30
    assert handle == handle.lower()
