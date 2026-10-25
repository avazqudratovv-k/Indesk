from fastapi.testclient import TestClient

from app.main import app


def test_unknown_path_is_404_with_code(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND"}}


def test_wrong_method_is_405_with_code(client: TestClient) -> None:
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json() == {"error": {"code": "METHOD_NOT_ALLOWED"}}


def test_unhandled_exception_is_500_without_stack_trace(client: TestClient) -> None:
    def boom() -> None:
        raise RuntimeError("secret-detail-do-not-leak")

    app.add_api_route("/api/_boom", boom)
    try:
        response = client.get("/api/_boom")
    finally:
        app.router.routes.pop()
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL"}}
    assert "secret-detail" not in response.text
    assert "Traceback" not in response.text
