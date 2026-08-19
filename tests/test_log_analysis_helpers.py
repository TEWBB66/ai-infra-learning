from pathlib import Path

from projects.ai_metrics_api.prometheus_histogram import (
    build_latency_histogram_prometheus,
    build_latency_histogram_prometheus_from_records,
)
from projects.log_analyzer.analyze_logs import analyze_logs, analyze_records


def test_analyze_records_matches_file_metrics(tmp_path):
    records = [
        {"request_id": "req-1", "model": "qwen", "status": "200", "latency_ms": "50", "tokens_in": "1", "tokens_out": "2"},
        {"request_id": "req-2", "model": "qwen", "status": "500", "latency_ms": "700", "tokens_in": "1", "tokens_out": "0"},
    ]

    log_path = tmp_path / "inference.log"
    log_path.write_text(
        "\n".join(
            "request_id={request_id} model={model} status={status} latency_ms={latency_ms} tokens_in={tokens_in} tokens_out={tokens_out}".format(**record)
            for record in records
        )
        + "\n",
        encoding="utf-8",
    )

    assert analyze_records(records) == analyze_logs(log_path)


def test_histogram_from_records_matches_file_metrics(tmp_path):
    records = [
        {"latency_ms": "50"},
        {"latency_ms": "120"},
        {"latency_ms": "700"},
    ]

    log_path = tmp_path / "inference.log"
    log_path.write_text(
        "\n".join(f"latency_ms={record['latency_ms']}" for record in records) + "\n",
        encoding="utf-8",
    )

    assert build_latency_histogram_prometheus_from_records(records) == build_latency_histogram_prometheus(log_path)
