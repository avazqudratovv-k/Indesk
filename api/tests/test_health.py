from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.main import app


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_with_real_db_and_redis(client: TestClient) -> None:
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_503_when_redis_unreachable(client: TestClient, settings: Settings) -> None:
    broken = settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/0")})
    app.dependency_overrides[get_settings] = lambda: broken
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "NOT_READY"}}


def test_ready_503_when_db_unreachable(client: TestClient, settings: Settings) -> None:
    broken = settings.model_copy(
        update={"database_url": SecretStr("postgresql+psycopg://x:y@127.0.0.1:1/z")}
    )
    app.dependency_overrides[get_settings] = lambda: broken
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "NOT_READY"}}
