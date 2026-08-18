from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from projects.ai_metrics_api import main
from projects.ai_metrics_api.prometheus_histogram import build_latency_histogram_prometheus


def test_latency_histogram_helper_parses_key_value_and_json_logs(tmp_path):
    log_path = tmp_path / "inference.log"
    log_path.write_text(
        "\n".join(
            [
                "2026-08-18T00:00:00Z request_id=req-1 model=qwen endpoint=/v1/infer status=200 latency_ms=50 tokens_in=1 tokens_out=2",
                "2026-08-18T00:00:01Z request_id=req-2 model=qwen endpoint=/v1/infer status=200 latency_ms=120 tokens_in=1 tokens_out=2",
                '{"request_id":"req-3","model":"qwen","status":200,"latency_ms":700,"tokens_in":1,"tokens_out":2}',
                "bad line without latency",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    lines = build_latency_histogram_prometheus(log_path)

    assert 'ai_inference_latency_ms_bucket{le="100"} 1' in lines
    assert 'ai_inference_latency_ms_bucket{le="250"} 2' in lines
    assert 'ai_inference_latency_ms_bucket{le="500"} 2' in lines
    assert 'ai_inference_latency_ms_bucket{le="1000"} 3' in lines
    assert 'ai_inference_latency_ms_bucket{le="+Inf"} 3' in lines
    assert "ai_inference_latency_ms_count 3" in lines
    assert "ai_inference_latency_ms_sum 870.0" in lines


def _patch_main_log_path(monkeypatch, log_path: Path) -> None:
    for name in ["INFERENCE_LOG_PATH", "INFERENCE_LOG_FILE", "LOG_PATH", "LOG_FILE", "LOG_FILE_PATH"]:
        if hasattr(main, name):
            current = getattr(main, name)
            patched = log_path if isinstance(current, Path) else str(log_path)
            monkeypatch.setattr(main, name, patched)
            return
    pytest.fail("Could not find main module log path variable")


def test_prometheus_endpoint_exports_latency_histogram(monkeypatch, tmp_path):
    log_path = tmp_path / "inference.log"
    log_path.write_text(
        "\n".join(
            [
                "2026-08-18T00:00:00Z request_id=req-1 model=qwen endpoint=/v1/infer status=200 latency_ms=50 tokens_in=1 tokens_out=2",
                "2026-08-18T00:00:01Z request_id=req-2 model=qwen endpoint=/v1/infer status=200 latency_ms=120 tokens_in=1 tokens_out=2",
                "2026-08-18T00:00:02Z request_id=req-3 model=qwen endpoint=/v1/infer status=200 latency_ms=700 tokens_in=1 tokens_out=2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _patch_main_log_path(monkeypatch, log_path)

    client = TestClient(main.app)
    response = client.get("/metrics/prometheus")

    assert response.status_code == 200
    body = response.text
    assert "# TYPE ai_inference_latency_ms histogram" in body
    assert 'ai_inference_latency_ms_bucket{le="100"} 1' in body
    assert 'ai_inference_latency_ms_bucket{le="250"} 2' in body
    assert 'ai_inference_latency_ms_bucket{le="+Inf"} 3' in body
    assert "ai_inference_latency_ms_count 3" in body
    assert "ai_inference_latency_ms_sum 870.0" in body
