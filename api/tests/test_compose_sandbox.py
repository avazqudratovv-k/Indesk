"""The sandbox hardening lives in compose.yaml, so a test reads it: an edit that weakens the
sandbox fails here. (The api container sees the files read-only under /compose; in CI the repo
root is the parent of api/.)"""

from pathlib import Path
from typing import Any

import pytest
import yaml

CANDIDATES = (Path("/compose"), Path(__file__).resolve().parents[2])


def load(name: str) -> dict[str, Any]:
    for folder in CANDIDATES:
        if (folder / name).is_file():
            data: dict[str, Any] = yaml.safe_load((folder / name).read_text())
            return data
    pytest.fail(f"{name} not found; run the tests through docker compose or from the repo")


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    return load("compose.yaml")


@pytest.fixture(scope="module")
def sandbox(compose: dict[str, Any]) -> dict[str, Any]:
    service: dict[str, Any] = compose["services"]["sandbox"]
    return service


def test_hardening_keys_are_present(sandbox: dict[str, Any]) -> None:
    assert sandbox["read_only"] is True
    assert sandbox["cap_drop"] == ["ALL"]
    assert "cap_add" not in sandbox
    assert any(o.startswith("no-new-privileges") for o in sandbox["security_opt"])
    assert 0 < sandbox["pids_limit"] <= 256
    assert sandbox["mem_limit"] and sandbox["memswap_limit"] == sandbox["mem_limit"]
    assert 0 < float(sandbox["cpus"]) <= 4
    assert len(sandbox["tmpfs"]) == 1 and sandbox["tmpfs"][0].startswith("/tmp:")
    assert "size=" in sandbox["tmpfs"][0]
    assert "privileged" not in sandbox and "network_mode" not in sandbox
    assert sandbox["build"] == "./api/sandbox"


def test_nothing_is_published_mounted_or_passed_in(sandbox: dict[str, Any]) -> None:
    for key in ("ports", "expose", "volumes", "volumes_from", "environment", "env_file", "secrets"):
        assert key not in sandbox, key
    assert "devices" not in sandbox and "user" not in sandbox  # the image sets a non-root user
    assert "depends_on" not in sandbox


def test_sandbox_is_on_the_internal_network_only(
    compose: dict[str, Any], sandbox: dict[str, Any]
) -> None:
    assert sandbox["networks"] == ["sandbox_net"]
    assert compose["networks"]["sandbox_net"] == {"internal": True}
    sharing = [
        name
        for name, service in compose["services"].items()
        if "sandbox_net" in (service.get("networks") or [])
    ]
    assert sorted(sharing) == ["sandbox", "worker"]
    assert "default" in compose["services"]["worker"]["networks"]  # keeps db and redis


def test_test_mode_is_only_in_the_override(compose: dict[str, Any]) -> None:
    assert "SANDBOX_TEST_MODE" not in yaml.safe_dump(compose)
    override = load("compose.sandbox-test.yaml")
    assert override == {"services": {"sandbox": {"environment": {"SANDBOX_TEST_MODE": "1"}}}}


def test_sandbox_has_a_healthcheck_without_curl(sandbox: dict[str, Any]) -> None:
    test = sandbox["healthcheck"]["test"]
    assert test[:3] == ["CMD", "python", "-c"] and "curl" not in " ".join(test)


def test_the_scheduler_has_a_healthcheck(compose: dict[str, Any]) -> None:
    assert compose["services"]["scheduler"]["healthcheck"]["test"][-1] == (
        "app.jobs.scheduler_health"
    )
