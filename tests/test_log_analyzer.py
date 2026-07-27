from projects.log_analyzer.analyze_logs import analyze_logs


def test_analyze_logs_summary_metrics():
    metrics = analyze_logs("data/day02/inference.log")

    assert metrics["total_requests"] >= 1
    assert metrics["success_requests"] >= 1
    assert metrics["failed_requests"] >= 1
    assert "error_rate" in metrics
    assert "p95_latency_ms" in metrics
    assert "metrics_by_model" in metrics