"""Guards that keep real Gemini out of the test suite and Google's host in exactly one file."""

import re
import urllib.error
import urllib.request
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.ai.gateway import GatewayError, build_gateway
from app.ai.real_client import GeminiRestClient
from app.core.config import Settings
from app.core.enums import AiPurpose, GatewayOutcome
from app.db.session import get_engine
from tests.fake_model_client import API_KEY, new_user_id

API_DIR = Path(__file__).resolve().parents[1]


def test_the_guard_blocks_a_real_httpx_transport(network_guard: list[str]) -> None:
    with pytest.raises(RuntimeError, match="blocked"), httpx.Client() as http:
        http.get("https://generativelanguage.googleapis.com/v1beta/models")
    assert network_guard == ["generativelanguage.googleapis.com"]
    network_guard.clear()  # the point of the test; otherwise teardown would fail it


def test_the_guard_does_not_touch_urllib_or_the_test_client(
    network_guard: list[str], client: TestClient
) -> None:
    with pytest.raises(urllib.error.URLError):  # a closed local port: an ordinary failure
        urllib.request.urlopen("http://127.0.0.1:9", timeout=1)  # noqa: S310
    assert client.get("/api/health").status_code == 200
    assert network_guard == []


def test_the_real_client_is_never_built_under_test_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(self: object, *args: object, **kwargs: object) -> None:
        raise AssertionError("the real Gemini client was constructed in a test")

    monkeypatch.setattr(GeminiRestClient, "__init__", refuse)
    settings = Settings(app_env="test", gemini_api_key=SecretStr(API_KEY))
    gateway = build_gateway(settings, lambda: pytest.fail("no database should be needed"))
    assert gateway._client is None
    result = gateway.ask("hi", purpose=AiPurpose.ROUTE, user_id=new_user_id())
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.MODEL_UNAVAILABLE


def test_outside_tests_a_key_builds_the_real_client_and_no_key_builds_none() -> None:
    engine = get_engine  # the factory is never called here
    with_key = build_gateway(
        Settings(app_env="development", gemini_api_key=SecretStr(API_KEY)),
        lambda: engine,  # type: ignore[arg-type,return-value]
    )
    without = build_gateway(
        Settings(app_env="development", gemini_api_key=None),
        lambda: engine,  # type: ignore[arg-type,return-value]
    )
    assert isinstance(with_key._client, GeminiRestClient) and API_KEY not in repr(with_key._client)
    assert without._client is None


def _python_files(*folders: str) -> list[Path]:
    return [p for f in folders for p in (API_DIR / f).rglob("*.py") if ".venv" not in p.parts]


def test_googles_host_appears_in_one_file_only() -> None:
    hits = {
        p.relative_to(API_DIR).as_posix()
        for p in _python_files("app", "scripts")
        if "googleapis.com" in p.read_text()
    }
    assert hits == {"app/ai/real_client.py"}


def test_only_the_gateway_and_the_script_import_the_real_client() -> None:
    pattern = re.compile(
        r"^\s*(from|import)\s+app\.ai\.real_client|^\s*from app\.ai import .*real_client", re.M
    )
    users = {
        p.relative_to(API_DIR).as_posix()
        for p in _python_files("app", "scripts")
        if pattern.search(p.read_text())
    }
    assert users == {"app/ai/gateway.py", "scripts/list_models.py"}


def test_no_google_sdk_is_used() -> None:
    pattern = re.compile(r"^\s*(from|import)\s+(google|genai)", re.M)
    assert not [p for p in _python_files("app", "scripts") if pattern.search(p.read_text())]
