import json
from pathlib import Path


DASHBOARD_PATH = Path("monitoring/grafana/dashboards/ai_metrics_dashboard.json")


def load_dashboard():
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


def panel_expressions(dashboard):
    expressions = []
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            expressions.append(target.get("expr", ""))
    return expressions


def test_grafana_dashboard_is_valid_json():
    dashboard = load_dashboard()

    assert dashboard["title"] == "AI Metrics API Dashboard"
    assert dashboard["schemaVersion"] >= 39
    assert dashboard["refresh"] == "5s"
    assert len(dashboard["panels"]) >= 12


def test_grafana_dashboard_panel_ids_are_unique():
    dashboard = load_dashboard()
    ids = [panel["id"] for panel in dashboard["panels"]]

    assert len(ids) == len(set(ids))


def test_grafana_dashboard_covers_service_and_model_metrics():
    expressions = panel_expressions(load_dashboard())

    required = [
        "ai_inference_total_requests",
        "ai_inference_error_rate",
        "ai_inference_p95_latency_ms",
        "ai_inference_failed_requests",
        "ai_inference_slow_request_count",
        "ai_inference_status_requests",
        "ai_inference_model_requests",
        "ai_inference_model_error_rate",
        "ai_inference_model_p95_latency_ms",
    ]

    for expr in required:
        assert expr in expressions


def test_grafana_dashboard_covers_serving_controls():
    expressions = panel_expressions(load_dashboard())

    required = [
        "ai_inference_current_in_flight_requests",
        "ai_inference_queue_depth",
        "ai_inference_queue_rejected_total",
        "ai_inference_queue_timeout_total",
        "ai_inference_admission_mode",
        "ai_inference_rate_limit_enabled",
        "ai_inference_rate_limit_active_clients",
        "ai_inference_rate_limit_rejected_total",
    ]

    for expr in required:
        assert expr in expressions


def test_grafana_dashboard_covers_histogram_quantile():
    expressions = panel_expressions(load_dashboard())

    assert (
        "histogram_quantile(0.95, sum(rate(ai_inference_latency_ms_bucket[5m])) by (le))"
        in expressions
    )
