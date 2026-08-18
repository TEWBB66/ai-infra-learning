from pathlib import Path


def test_prometheus_loads_alert_rule_file():
    prometheus_config = Path("monitoring/prometheus.yml").read_text(encoding="utf-8")
    compose_config = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "prometheus-rules.yml" in prometheus_config
    assert "./monitoring/prometheus-rules.yml:/etc/prometheus/prometheus-rules.yml" in compose_config


def test_alert_rules_cover_latency_errors_and_admission_control():
    rules = Path("monitoring/prometheus-rules.yml").read_text(encoding="utf-8")

    expected_alerts = [
        "AIInferenceHighP95Latency",
        "AIInferenceHighErrorRate",
        "AIInferenceInFlightSaturation",
        "AIInferenceQueueBacklog",
        "AIInferenceQueueTimeouts",
        "AIInferenceQueueRejections",
    ]
    for alert in expected_alerts:
        assert f"alert: {alert}" in rules

    expected_metrics = [
        "ai_inference_latency_ms_bucket",
        "ai_inference_status_requests",
        "ai_inference_current_in_flight_requests",
        "ai_inference_queue_depth",
        "ai_inference_queue_timeout_total",
        "ai_inference_queue_rejected_total",
    ]
    for metric in expected_metrics:
        assert metric in rules
