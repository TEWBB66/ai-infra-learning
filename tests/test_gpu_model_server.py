from fastapi.testclient import TestClient

from projects.gpu_model_server.main import app


client = TestClient(app)


def test_gpu_model_server_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "gpu-model-server",
    }


def test_gpu_model_server_generate_success(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "template")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "qwen2.5-0.5b"
    assert data["status"] == 200
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 20
    assert data["latency_ms"] > 0


def test_gpu_model_server_generate_with_forced_status(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "template")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 500,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == 500


def test_gpu_model_server_rejects_invalid_force_status(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "template")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "force_status must be one of 200, 400, 429, 500"


def test_gpu_model_server_rejects_unsupported_mode(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "unsupported")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "unsupported GPU_MODEL_MODE: unsupported"


def test_gpu_model_server_transformers_mode_reports_missing_dependencies(monkeypatch):
    from projects.gpu_model_server import main

    def fake_find_spec(package_name):
        if package_name in {"torch", "transformers"}:
            return None
        return object()

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "transformers")
    monkeypatch.setattr(main.importlib.util, "find_spec", fake_find_spec)

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "transformers mode requires missing dependencies: torch, transformers"
    )


def test_gpu_model_server_transformers_mode_reports_not_implemented(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "transformers")
    monkeypatch.setattr(main, "GPU_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
    monkeypatch.setattr(main.importlib.util, "find_spec", lambda package_name: object())

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 501
    assert response.json()["detail"] == (
        "transformers mode is not implemented yet for Qwen/Qwen2.5-0.5B-Instruct"
    )