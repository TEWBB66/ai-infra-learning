# Local Validation

This document records the local validation workflow for the AI inference observability project.

## Start the Stack

Run the full Docker Compose stack:

    cd /workspaces/ai-infra-learning
    docker compose up --build

The stack starts:

- ai-metrics-api
- mock-model-server
- Prometheus
- Grafana

## Run Tests

In a second terminal:

    cd /workspaces/ai-infra-learning
    python -m pytest -q

Expected result:

    all tests passed, with at most the known FastAPI / Starlette TestClient warning

The warning comes from FastAPI / Starlette TestClient and does not indicate a project failure.

## Smoke Test Endpoints

Check the metrics API health endpoint:

    curl -s http://127.0.0.1:8000/health

Expected response:

    {"status":"ok","service":"ai-metrics-api"}

Check the metrics API readiness endpoint:

    curl -s http://127.0.0.1:8000/ready

Expected response in the default Docker Compose setup:

    {"status":"ready","service":"ai-metrics-api","backend":"mock","model_server_url":"http://mock-model-server:8001/generate"}

Check the mock model server health endpoint:

    curl -s http://127.0.0.1:8001/health

Expected response:

    {"status":"ok","service":"mock-model-server"}

Send an inference request:

    curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
      -H "Content-Type: application/json" \
      -d '{"model":"qwen2.5-7b","tokens_in":100,"tokens_out":20}'

Expected response shape:

    {
      "request_id": "req-...",
      "model": "qwen2.5-7b",
      "status": 200,
      "latency_ms": 113,
      "tokens_in": 100,
      "tokens_out": 20
    }

The exact request_id and latency_ms can vary.

## Metrics Validation

Check aggregated log metrics:

    curl -s http://127.0.0.1:8000/metrics/logs

Expected behavior:

- total_requests is returned
- success_requests and failed_requests are returned
- error_rate is returned
- p95_latency_ms and p99_latency_ms are returned
- metrics_by_model is returned

Check Prometheus metrics:

    curl -s http://127.0.0.1:8000/metrics/prometheus | head -30

Expected metrics include:

    ai_inference_total_requests
    ai_inference_success_requests
    ai_inference_failed_requests
    ai_inference_error_rate
    ai_inference_p95_latency_ms
    ai_inference_p99_latency_ms
    ai_inference_slow_request_count
    ai_inference_model_requests
    ai_inference_model_errors

## Dashboards

Prometheus is available at:

    http://127.0.0.1:9090

Grafana is available at:

    http://127.0.0.1:3000

The Grafana dashboard is provisioned from:

    monitoring/grafana/dashboards/ai_metrics_dashboard.json

The dashboard includes service-level, model-level, admission control, rate-limit, and histogram-based latency panels.

## Cleanup

Stop the Docker Compose stack:

    docker compose down

The inference log is runtime data. If local validation modifies it, restore it before committing:

    git restore data/day02/inference.log

A clean validation run should end with:

    git status

Expected result:

    nothing to commit, working tree clean

## Final Validation Results

Final local validation was completed on 2026-08-11.

Docker Compose validation passed:

- pytest completed with all tests passing and the known TestClient warning
- ai-metrics-api /health returned ok
- ai-metrics-api /ready returned ready with backend=mock
- mock-model-server /health returned ok
- deterministic /v1/mock-infer with force_status=200 returned status=200
- /metrics/logs returned aggregated request metrics
- /metrics/prometheus exposed service-level and model-level metrics
- Prometheus target API reported ai-metrics-api health=up
- Grafana /api/health returned 200 OK
- Grafana dashboard search found AI Metrics API Dashboard
- Grafana dashboard JSON contains service, model, admission queue, rate-limit, and histogram latency panels

Grafana API validation should use the admin password configured in docker-compose.yml.

GPU final smoke test also passed on the A5000 host:

- gpu-model-server /health returned ok
- gpu-model-server /ready returned ready with mode=transformers
- /generate returned status=200 for qwen2.5-0.5b
- The service was stopped immediately after validation
- GPU resources were released after the smoke test

The GPU smoke test was intentionally short and used CUDA_VISIBLE_DEVICES=0.