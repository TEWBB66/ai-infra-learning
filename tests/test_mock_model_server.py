from fastapi.testclient import TestClient

from projects.mock_model_server.main import app


client = TestClient(app)


def test_mock_model_server_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "mock-model-server",
    }


def test_mock_model_server_generate_success(monkeypatch):
    from projects.mock_model_server import main

    monkeypatch.setattr(main, "MOCK_MODEL_DELAY_SCALE", 0)

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-7b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 200,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "qwen2.5-7b"
    assert data["status"] == 200
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 20
    assert data["latency_ms"] > 0


def test_mock_model_server_rejects_invalid_force_status():
    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-7b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "force_status must be one of 200, 400, 429, 500"


def test_mock_model_server_applies_configurable_delay(monkeypatch):
    from projects.mock_model_server import main

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(main, "MOCK_MODEL_DELAY_SCALE", 0.5)
    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-7b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 200,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == (data["latency_ms"] / 1000) * 0.5