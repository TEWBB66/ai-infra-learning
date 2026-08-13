from projects.log_analyzer.analyze_logs import analyze_logs, percentile


def write_log(tmp_path, text):
    log_path = tmp_path / "inference.log"
    log_path.write_text(text, encoding="utf-8")
    return log_path


def test_analyze_logs_summary_metrics():
    metrics = analyze_logs("data/day02/inference.log")

    assert metrics["total_requests"] >= 1
    assert metrics["success_requests"] >= 1
    assert metrics["failed_requests"] >= 1
    assert "error_rate" in metrics
    assert "p95_latency_ms" in metrics
    assert "requests_by_status" in metrics
    assert "metrics_by_model" in metrics


def test_analyze_logs_empty_file(tmp_path):
    log_path = write_log(tmp_path, "")

    metrics = analyze_logs(log_path)

    assert metrics["total_requests"] == 0
    assert metrics["success_requests"] == 0
    assert metrics["failed_requests"] == 0
    assert metrics["success_rate"] == 0
    assert metrics["error_rate"] == 0
    assert metrics["avg_latency_ms"] == 0
    assert metrics["avg_success_latency_ms"] == 0
    assert metrics["requests_by_status"] == {}
    assert metrics["metrics_by_model"] == {}


def test_analyze_logs_all_failed_requests(tmp_path):
    log_path = write_log(
        tmp_path,
        "\n".join([
            "2026-08-13T00:00:01Z request_id=req-1 model=qwen2.5-7b endpoint=/v1/infer status=500 latency_ms=300 tokens_in=100 tokens_out=0",
            "2026-08-13T00:00:02Z request_id=req-2 model=qwen2.5-7b endpoint=/v1/infer status=429 latency_ms=20 tokens_in=100 tokens_out=0",
        ]),
    )

    metrics = analyze_logs(log_path)

    assert metrics["total_requests"] == 2
    assert metrics["success_requests"] == 0
    assert metrics["failed_requests"] == 2
    assert metrics["success_rate"] == 0
    assert metrics["error_rate"] == 1
    assert metrics["avg_success_latency_ms"] == 0
    assert metrics["requests_by_status"] == {
        "500": 1,
        "429": 1,
    }


def test_analyze_logs_skips_malformed_lines(tmp_path):
    log_path = write_log(
        tmp_path,
        "\n".join([
            "this is not a structured inference log line",
            "2026-08-13T00:00:01Z request_id=req-1 model=qwen2.5-7b endpoint=/v1/infer status=200 latency_ms=120 tokens_in=100 tokens_out=20",
            "2026-08-13T00:00:02Z request_id=req-2 model=qwen2.5-7b endpoint=/v1/infer status=bad latency_ms=120 tokens_in=100 tokens_out=20",
        ]),
    )

    metrics = analyze_logs(log_path)

    assert metrics["total_requests"] == 1
    assert metrics["success_requests"] == 1
    assert metrics["requests_by_status"] == {
        "200": 1,
    }


def test_percentile_uses_sorted_values():
    values = [50, 10, 40, 20, 30]

    assert percentile(values, 50) == 30
    assert percentile(values, 95) == 50
    assert percentile([], 95) == 0


def test_analyze_logs_model_metrics_exact_values(tmp_path):
    log_path = write_log(
        tmp_path,
        "\n".join([
            "2026-08-13T00:00:01Z request_id=req-1 model=qwen2.5-7b endpoint=/v1/infer status=200 latency_ms=100 tokens_in=100 tokens_out=20",
            "2026-08-13T00:00:02Z request_id=req-2 model=qwen2.5-7b endpoint=/v1/infer status=500 latency_ms=300 tokens_in=100 tokens_out=0",
            "2026-08-13T00:00:03Z request_id=req-3 model=bge-reranker endpoint=/v1/infer status=200 latency_ms=50 tokens_in=200 tokens_out=0",
        ]),
    )

    metrics = analyze_logs(log_path)

    assert metrics["total_requests"] == 3
    assert metrics["success_requests"] == 2
    assert metrics["failed_requests"] == 1
    assert metrics["requests_by_status"] == {
        "200": 2,
        "500": 1,
    }

    qwen_metrics = metrics["metrics_by_model"]["qwen2.5-7b"]
    assert qwen_metrics["request_count"] == 2
    assert qwen_metrics["error_count"] == 1
    assert qwen_metrics["avg_latency_ms"] == 200
    assert qwen_metrics["error_rate"] == 0.5
    assert qwen_metrics["status_counts"] == {
        "200": 1,
        "500": 1,
    }

    reranker_metrics = metrics["metrics_by_model"]["bge-reranker"]
    assert reranker_metrics["request_count"] == 1
    assert reranker_metrics["error_count"] == 0
    assert reranker_metrics["status_counts"] == {
        "200": 1,
    }