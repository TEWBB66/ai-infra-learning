# AI Metrics API

A FastAPI-based observability service for simulated AI inference workloads.

This project simulates inference requests, writes structured logs, analyzes service-level and model-level metrics, and exposes JSON and Prometheus-style monitoring endpoints.

## Architecture

```text
scripts/load_test.py
    |
    v
POST /v1/mock-infer
    |
    v
data/day02/inference.log
    |
    v
projects/log_analyzer/analyze_logs.py
    |
    v
FastAPI metrics endpoints
    |
    +--> /metrics/logs
    +--> /metrics/models
    +--> /metrics/alerts
    +--> /metrics/prometheus
```

## Features

- mock inference endpoint
- structured inference log generation
- service-level metrics
- model-level metrics
- P95 and P99 latency
- slow request analysis
- error request filtering
- warning and critical alerting
- centralized configuration
- automated pytest tests
- load testing script
- Prometheus-style metrics endpoint
- Dockerized service startup

## Project Structure

```text
projects/ai_metrics_api/
  main.py          FastAPI application and API endpoints
  config.py        log path, thresholds, and service configuration
  README.md        project documentation

projects/log_analyzer/
  analyze_logs.py  log parsing and metric aggregation logic

scripts/
  load_test.py     simulated inference traffic generator

tests/
  test_api.py
  test_log_analyzer.py

data/day02/
  inference.log    sample inference log data
```

## Run Locally

```bash
python -m uvicorn projects.ai_metrics_api.main:app --host 0.0.0.0 --port 8000
```

## Docker

Build the Docker image:

```bash
docker build -t ai-metrics-api .
```

Run the service:

```bash
docker run --rm -p 8000:8000 ai-metrics-api
```

If port `8000` is already in use:

```bash
docker run --rm -p 8001:8000 ai-metrics-api
```

Then test the service:

```bash
curl -s http://127.0.0.1:8000/health | jq
curl -s http://127.0.0.1:8000/metrics/logs | jq
curl -s http://127.0.0.1:8000/metrics/prometheus | head -20
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/v1/mock-infer` | Send one inference request to the mock model server and append one log line |
| GET | `/metrics/logs` | Summary metrics, latency percentiles, slow requests, and model-level metrics |
| GET | `/metrics/slow` | Slow request analysis |
| GET | `/metrics/errors` | Error request analysis |
| GET | `/metrics/models` | Metrics grouped by model |
| GET | `/metrics/models?model_name=qwen2.5-7b` | Metrics for one model |
| GET | `/metrics/alerts` | Service-level and model-level alert rules |
| GET | `/metrics/incidents` | Incident summary with possible causes and suggested actions |
| GET | `/metrics/prometheus` | Prometheus-style text metrics |

## Manual API Test

```bash
curl -s http://127.0.0.1:8000/health | jq
curl -s http://127.0.0.1:8000/metrics/logs | jq
curl -s http://127.0.0.1:8000/metrics/models | jq
curl -s "http://127.0.0.1:8000/metrics/models?model_name=qwen2.5-7b" | jq
curl -i "http://127.0.0.1:8000/metrics/models?model_name=unknown-model"
curl -s http://127.0.0.1:8000/metrics/alerts | jq
curl -s http://127.0.0.1:8000/metrics/incidents | jq
curl -s http://127.0.0.1:8000/metrics/prometheus | head -20
```

## Incident Diagnosis

The `/metrics/incidents` endpoint turns raw metrics and alerts into an operator-facing incident report.

It reports:

- current service status
- incident summary
- total request count
- error rate
- P95 latency
- slow request count
- alert count
- possible causes
- suggested actions

Example:

```bash
curl -s http://127.0.0.1:8000/metrics/incidents | jq
```

## Mock Inference

```bash
curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":300,"tokens_out":80}' | jq
```

Validation examples:

```bash
curl -i -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":-1,"tokens_out":0}'

curl -i -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":10,"tokens_out":0,"force_status":999}'
```

## Load Test

Generate simulated inference traffic:

```bash
python scripts/load_test.py --count 20 --error-rate 0.1
```

Then inspect updated metrics and alerts:

```bash
curl -s http://127.0.0.1:8000/metrics/logs | jq
curl -s http://127.0.0.1:8000/metrics/alerts | jq
```

The load test script sends multiple requests to `/v1/mock-infer`, randomly selects models and token sizes, and optionally injects simulated error responses based on `--error-rate`.

## Prometheus Metrics

Expose metrics in Prometheus text format:

```bash
curl -s http://127.0.0.1:8000/metrics/prometheus
```

Example metrics:

```text
ai_inference_total_requests 20
ai_inference_error_rate 0.2
ai_inference_p95_latency_ms 495
ai_inference_model_request_count{model="qwen2.5-7b"} 7
ai_inference_model_error_rate{model="qwen2.5-7b"} 0.2857
```

## Prometheus Integration

Start the API service and Prometheus together:

```bash
docker compose up --build
```

Prometheus is available at:

```text
http://127.0.0.1:9090
```

Example Prometheus queries:

```text
ai_inference_total_requests
ai_inference_error_rate
ai_inference_p95_latency_ms
ai_inference_model_request_count
ai_inference_model_error_rate
```

The Prometheus scrape configuration is defined in `monitoring/prometheus.yml`. It scrapes the API service at `/metrics/prometheus` every 5 seconds.

## Grafana Dashboard

This project includes a minimal Grafana dashboard for visualizing AI inference service metrics.

Dashboard JSON file:

```text
monitoring/grafana/dashboards/ai_metrics_dashboard.json
```

Start the API service, Prometheus, and Grafana with Docker Compose:

```bash
docker compose up --build
```

Open Grafana:

```text
http://127.0.0.1:3000
```

Default Grafana login:

```text
username: admin
password: admin
```

After logging in, add Prometheus as a data source.

Prometheus data source URL:

```text
http://prometheus:9090
```

Then import the dashboard JSON from:

```text
monitoring/grafana/dashboards/ai_metrics_dashboard.json
```

The dashboard includes four basic panels:

```text
Total Requests
Error Rate
P95 Latency
Slow Requests
```

These panels are based on the Prometheus metrics exposed by the API at:

```text
/metrics/prometheus
```

## Load Test and Observability Validation

The project includes a simple load testing script for generating mock inference traffic and validating that metrics are reflected in the observability stack.

Run a low-error-rate load test:

```bash
python scripts/load_test.py --count 10 --error-rate 0.1
```

Example result:

```text
total_requests=10
success_count=9
error_count=1
avg_latency_ms=315.4
max_latency_ms=524
```

After this test, the Grafana dashboard reflected updated metrics:

```text
Total Requests: 25
Error Rate: 0.160
P95 Latency: 524
Slow Requests: 12
```

Run a high-error-rate load test:

```bash
python scripts/load_test.py --count 10 --error-rate 0.5
```

Example result:

```text
total_requests=10
success_count=4
error_count=6
avg_latency_ms=319.5
max_latency_ms=515
```

After this test, the Grafana dashboard reflected a clear service degradation:

```text
Total Requests: 35
Error Rate: 0.286
P95 Latency: 515
Slow Requests: 20
```

This validates the full observability flow:

```text
load_test.py
-> mock inference API
-> inference log file
-> metrics API
-> Prometheus scrape
-> Grafana dashboard
```

The goal is to verify that the monitoring system responds to both normal traffic and degraded traffic.

## Automated Test

```bash
python -m pytest -q
```

Current test coverage includes:

- log analyzer summary metrics
- health check endpoint
- log metrics endpoint
- model metrics endpoint
- model filtering
- alerting endpoint
- Prometheus metrics endpoint
- mock inference success path
- mock inference validation errors

## Configuration

Key service settings are defined in `projects/ai_metrics_api/config.py`, including:

- log file path
- default slow request threshold
- allowed forced status codes for mock inference
- service-level alert thresholds
- model-level alert thresholds

## Design Notes

This project separates log analysis from API serving. The log analyzer handles parsing and metric aggregation, while the FastAPI service exposes those metrics through JSON and Prometheus-style endpoints.

The alerting logic uses both service-level and model-level metrics. This makes it possible to distinguish between a global service issue and a model-specific reliability or latency problem.

Docker support improves environment consistency and makes the service easier to run on another machine or server.

## Roadmap

- add architecture diagram
- add Prometheus scrape config
- add Grafana dashboard
- connect to a real model serving backend such as vLLM or Triton
- add performance comparison under different traffic patterns