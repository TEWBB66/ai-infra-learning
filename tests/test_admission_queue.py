import threading
import time

from fastapi.testclient import TestClient

from projects.ai_metrics_api import main
from projects.ai_metrics_api.main import InferenceGate


def test_reject_mode_preserves_fast_rejection():
    gate = InferenceGate(max_in_flight=1, admission_mode="reject")

    assert gate.try_acquire() is True
    assert gate.try_acquire() is False

    snapshot = gate.snapshot()
    assert snapshot["current_in_flight"] == 1
    assert snapshot["current_queued"] == 0
    assert snapshot["queue_rejected_total"] == 0
    assert snapshot["queue_timeout_total"] == 0

    gate.release()
    assert gate.snapshot()["current_in_flight"] == 0


def test_queue_mode_waits_for_released_slot():
    gate = InferenceGate(
        max_in_flight=1,
        admission_mode="queue",
        max_queue_size=1,
        queue_timeout_ms=1000,
    )
    acquired = []

    assert gate.try_acquire() is True

    worker = threading.Thread(target=lambda: acquired.append(gate.try_acquire()))
    worker.start()

    time.sleep(0.05)
    assert gate.snapshot()["current_queued"] == 1

    gate.release()
    worker.join(timeout=1)

    assert acquired == [True]
    assert gate.snapshot()["current_in_flight"] == 1
    assert gate.snapshot()["current_queued"] == 0

    gate.release()
    assert gate.snapshot()["current_in_flight"] == 0


def test_queue_mode_rejects_when_queue_is_full():
    gate = InferenceGate(
        max_in_flight=1,
        admission_mode="queue",
        max_queue_size=0,
        queue_timeout_ms=1000,
    )

    assert gate.try_acquire() is True
    assert gate.try_acquire() is False

    snapshot = gate.snapshot()
    assert snapshot["queue_rejected_total"] == 1
    assert snapshot["queue_timeout_total"] == 0

    gate.release()


def test_queue_mode_times_out_waiting_for_slot():
    gate = InferenceGate(
        max_in_flight=1,
        admission_mode="queue",
        max_queue_size=1,
        queue_timeout_ms=10,
    )

    assert gate.try_acquire() is True
    assert gate.try_acquire() is False

    snapshot = gate.snapshot()
    assert snapshot["current_queued"] == 0
    assert snapshot["queue_rejected_total"] == 0
    assert snapshot["queue_timeout_total"] == 1

    gate.release()


def test_prometheus_exports_queue_metrics(monkeypatch, tmp_path):
    log_path = tmp_path / "inference.log"
    log_path.write_text(
        "2026-08-18T00:00:00Z request_id=req-1 model=qwen endpoint=/v1/infer status=200 latency_ms=50 tokens_in=1 tokens_out=2\n",
        encoding="utf-8",
    )

    gate = InferenceGate(
        max_in_flight=1,
        admission_mode="queue",
        max_queue_size=0,
        queue_timeout_ms=1000,
    )
    assert gate.try_acquire() is True
    assert gate.try_acquire() is False

    monkeypatch.setattr(main, "LOG_PATH", str(log_path))
    monkeypatch.setattr(main, "INFERENCE_GATE", gate)

    client = TestClient(main.app)
    response = client.get("/metrics/prometheus")

    assert response.status_code == 200
    body = response.text
    assert "ai_inference_current_in_flight_requests 1" in body
    assert "ai_inference_queue_depth 0" in body
    assert "ai_inference_queue_rejected_total 1" in body
    assert "ai_inference_queue_timeout_total 0" in body
    assert 'ai_inference_admission_mode{mode="queue"} 1' in body

    gate.release()
