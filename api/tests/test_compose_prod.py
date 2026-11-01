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


# Each secret and who may hold it. A service not listed for a variable must not have it.
ENV_ALLOW_LIST: dict[str, set[str]] = {
    "GEMINI_API_KEY": {"worker"},  # only the worker runs the model gateway
    "RESEND_API_KEY": {"worker"},  # only the worker sends email; the api just enqueues
    "EMAIL_FROM": {"worker"},
    "APP_BASE_URL": {"api", "worker", "scheduler"},  # the x-api-env anchor
    "EMAIL_VERIFICATION_REQUIRED": {"api", "worker", "scheduler"},
}


def test_each_secret_goes_only_to_the_services_allowed_to_have_it(prod: dict[str, Any]) -> None:
    for variable, allowed in ENV_ALLOW_LIST.items():
        holders = {
            name
            for name, service in prod["services"].items()
            if variable in (service.get("environment") or {})
        }
        assert holders == allowed, variable
    assert "env_file" not in yaml.safe_dump(prod)


def test_the_email_settings_are_required_with_no_default(prod: dict[str, Any]) -> None:
    worker = prod["services"]["worker"]["environment"]
    api = prod["services"]["api"]["environment"]
    for env, name in ((worker, "RESEND_API_KEY"), (worker, "EMAIL_FROM"), (api, "APP_BASE_URL")):
        assert env[name] == f"${{{name}:?set {name}}}", name
    assert api["EMAIL_VERIFICATION_REQUIRED"].startswith("${EMAIL_VERIFICATION_REQUIRED:?")


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
    assert sorted(sharing) == ["sandbox", "worker"]  # the api is NOT here (P14a fix)


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


def test_the_parser_is_a_hardened_parse_only_copy_on_its_own_network(prod: dict[str, Any]) -> None:
    parser = prod["services"]["parser"]
    assert parser["build"] == "./api/sandbox"
    assert parser["command"] == ["python", "-m", "indesk_sandbox.parser_server"]
    assert parser["read_only"] is True
    assert parser["cap_drop"] == ["ALL"]
    assert "cap_add" not in parser
    assert any(o.startswith("no-new-privileges") for o in parser["security_opt"])
    assert 0 < parser["pids_limit"] <= 128
    assert parser["mem_limit"] and parser["memswap_limit"] == parser["mem_limit"]
    assert 0 < float(parser["cpus"]) <= 4
    assert parser["restart"] == "unless-stopped"
    for key in (
        "ports", "expose", "volumes", "volumes_from", "environment", "env_file", "secrets",
        "privileged", "network_mode", "devices", "user", "depends_on",
    ):  # fmt: skip
        assert key not in parser, key
    assert parser["networks"] == ["parse_net"]
    assert prod["networks"]["parse_net"] == {"internal": True}
    members = sorted(
        n for n, s in prod["services"].items() if "parse_net" in (s.get("networks") or [])
    )
    assert members == ["api", "parser"]
    assert prod["services"]["api"]["networks"] == ["edge", "backend", "parse_net"]
