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


def test_gpu_model_server_generate_success():
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


def test_gpu_model_server_generate_with_forced_status():
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


def test_gpu_model_server_rejects_invalid_force_status():
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
