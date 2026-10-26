"""compose.prod.yaml is a standalone file (ROADMAP 5.6). A test reads it, so an edit that lets a dev
default, a dev port or a weaker sandbox into production fails here."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.test_compose_sandbox import load


@pytest.fixture(scope="module")
def prod() -> dict[str, Any]:
    return load("compose.prod.yaml")


def prod_text() -> str:
    for folder in (Path("/compose"), Path(__file__).resolve().parents[2]):
        if (folder / "compose.prod.yaml").is_file():
            return (folder / "compose.prod.yaml").read_text()
    pytest.fail("compose.prod.yaml not found")


def test_no_dev_defaults_anywhere() -> None:
    text = prod_text()
    # No `${VAR:-default}`: every setting is required or fixed.
    assert "${" in text and ":-" not in text
    assert "dev_password" not in text


def test_only_web_is_published_on_loopback(prod: dict[str, Any]) -> None:
    published = {n: s["ports"] for n, s in prod["services"].items() if "ports" in s}
    assert published == {"web": ["127.0.0.1:4100:3000"]}


def test_the_dev_stub_is_off_and_production_mode_is_fixed(prod: dict[str, Any]) -> None:
    for name in ("api", "worker", "scheduler"):
        env = prod["services"][name]["environment"]
        assert env["APP_ENV"] == "production", name
        assert env["RUNS_DEV_STUB"] == "0", name
    assert "SANDBOX_TEST_MODE" not in yaml.safe_dump(prod)


def test_only_the_worker_gets_the_gemini_key(prod: dict[str, Any]) -> None:
    for name, service in prod["services"].items():
        has_key = "GEMINI_API_KEY" in (service.get("environment") or {})
        assert has_key == (name == "worker"), name
    assert "env_file" not in yaml.safe_dump(prod)


def test_database_roles(prod: dict[str, Any]) -> None:
    services = prod["services"]
    for name in ("api", "worker", "scheduler"):
        assert "indesk_app:" in services[name]["environment"]["DATABASE_URL"], name
    assert "indesk_migrator:" in services["migrate"]["environment"]["MIGRATE_DATABASE_URL"]
    assert set(services["migrate"]["environment"]) == {"MIGRATE_DATABASE_URL"}
    assert services["migrate"]["restart"] == "no"
    for name in ("api", "worker", "scheduler"):
        assert services[name]["depends_on"]["migrate"]["condition"] == (
            "service_completed_successfully"
        )


def test_sandbox_hardening_is_kept(prod: dict[str, Any]) -> None:
    sandbox = prod["services"]["sandbox"]
    assert sandbox["read_only"] is True
    assert sandbox["cap_drop"] == ["ALL"]
    assert "cap_add" not in sandbox
    assert any(o.startswith("no-new-privileges") for o in sandbox["security_opt"])
    assert 0 < sandbox["pids_limit"] <= 256
    assert sandbox["mem_limit"] and sandbox["memswap_limit"] == sandbox["mem_limit"]
    assert 0 < float(sandbox["cpus"]) <= 4
    for key in ("ports", "expose", "volumes", "environment", "env_file", "secrets", "privileged"):
        assert key not in sandbox, key
    assert sandbox["networks"] == ["sandbox_net"]
    assert prod["networks"]["sandbox_net"] == {"internal": True}
    sharing = [n for n, s in prod["services"].items() if "sandbox_net" in (s.get("networks") or [])]
    assert sorted(sharing) == ["sandbox", "worker"]


def test_db_and_redis_cannot_reach_the_internet(prod: dict[str, Any]) -> None:
    assert prod["networks"]["backend"] == {"internal": True}
    for name in ("db", "redis"):
        assert prod["services"][name]["networks"] == ["backend"], name
    on_egress = [n for n, s in prod["services"].items() if "egress" in (s.get("networks") or [])]
    assert on_egress == ["worker"]


def test_every_long_running_service_restarts_and_is_limited(prod: dict[str, Any]) -> None:
    for name, service in prod["services"].items():
        assert service["mem_limit"] == service["memswap_limit"], name
        if name != "migrate":
            assert service["restart"] == "unless-stopped", name
