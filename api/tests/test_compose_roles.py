"""The database-role split in the compose files (10c). Same lookup as test_compose_sandbox."""

from typing import Any

import pytest
import yaml

from tests.test_compose_sandbox import load


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    return load("compose.yaml")


def test_app_services_use_the_app_role_and_only_migrate_uses_the_migrator(
    compose: dict[str, Any],
) -> None:
    services = compose["services"]
    for name in ("api", "worker", "scheduler"):
        assert "indesk_app:" in services[name]["environment"]["DATABASE_URL"], name
        assert services[name]["depends_on"]["migrate"]["condition"] == (
            "service_completed_successfully"
        )
    assert "indesk_migrator:" in services["migrate"]["environment"]["MIGRATE_DATABASE_URL"]
    assert set(services["migrate"]["environment"]) == {"MIGRATE_DATABASE_URL"}
    assert "env_file" not in services["migrate"]
    assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
    assert "indesk:" not in yaml.safe_dump(compose["x-api-env"])  # never the superuser


def test_mounts_and_the_superuser_url_are_only_in_the_override(compose: dict[str, Any]) -> None:
    assert not any("compose" in str(v) for v in compose["services"]["api"]["volumes"])
    assert "TEST_ADMIN_DATABASE_URL" not in yaml.safe_dump(compose)
    override = load("compose.override.yaml")
    assert "TEST_ADMIN_DATABASE_URL" in override["services"]["api"]["environment"]


def test_production_file_has_no_source_mount_and_no_published_database(
    compose: dict[str, Any],
) -> None:
    prod = load("compose.prod.yaml")
    assert "ports" not in compose["services"]["db"] and "ports" not in prod["services"]["db"]
    assert "ports" not in compose["services"]["redis"]
    assert "ports" not in prod["services"]["redis"]
    for name, service in prod["services"].items():
        for volume in service.get("volumes", []):
            # Named volumes and the db's read-only role script; never source or compose files.
            assert not volume.startswith(("./api:", "./web:", "./compose")), (name, volume)
    text = yaml.safe_dump(prod)
    assert "APP_ENV: production" in text and "TEST_ADMIN" not in text
