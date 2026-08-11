# ai-infra-learning

My AI infrastructure learning journey.

## AI Inference Observability and Reliability Platform

This repository contains a small AI inference observability project built with FastAPI, Docker Compose, Prometheus, Grafana, structured inference logs, alerting, incident diagnosis, load testing, and automated tests.

The goal of this project is to practice the engineering workflow around AI model serving:

- receive inference requests
- call a backend model service
- record structured inference logs
- calculate latency and error metrics
- expose Prometheus metrics
- visualize service health in Grafana
- detect alerts and incidents
- verify behavior with tests and load traffic

This is not a production-scale distributed system. It is a self-built learning project for understanding AI deployment, observability, and reliability.

## System Components

The Docker Compose stack includes:

- `ai-metrics-api`: FastAPI service for inference logs, metrics, alerts, incidents, and Prometheus metrics
- `mock-model-server`: mock backend model service used by `/v1/mock-infer`
- `prometheus`: scrapes metrics from `ai-metrics-api`
- `grafana`: loads the provisioned Prometheus datasource and dashboard

## Architecture

```mermaid
flowchart LR
    Client["Client / curl / load_test.py"] --> API["ai-metrics-api<br/>FastAPI service"]

    API --> MockModel["mock-model-server<br/>/generate"]
    MockModel --> API

    API --> LogFile["data/day02/inference.log<br/>structured inference logs"]

    API --> Metrics["/metrics/logs<br/>/metrics/models<br/>/metrics/slow<br/>/metrics/errors"]
    API --> Alerts["/metrics/alerts"]
    API --> Incidents["/metrics/incidents"]

    API --> PromEndpoint["/metrics/prometheus"]
    Prometheus["Prometheus"] --> PromEndpoint
    Grafana["Grafana dashboard"] --> Prometheus
```

The main request flow is:

1. A client or load test sends an inference request to `/v1/mock-infer`.
2. `ai-metrics-api` calls the separated `mock-model-server`.
3. The API records the request result into `data/day02/inference.log`.
4. Metrics endpoints parse the log file and calculate request count, error rate, latency percentiles, slow requests, and model-level metrics.
5. `/metrics/prometheus` exposes these metrics in Prometheus text format.
6. Prometheus scrapes the API metrics endpoint.
7. Grafana reads from Prometheus and visualizes service health.
8. Alert and incident endpoints summarize abnormal error rate, latency, and model-level behavior.

## Run with Docker Compose

Start the full stack:

```bash
cd /workspaces/ai-infra-learning
docker compose up --build
```

Expected service URLs:

```text
AI metrics API:     http://127.0.0.1:8000
Mock model server:  http://127.0.0.1:8001
Prometheus:         http://127.0.0.1:9090
Grafana:            http://127.0.0.1:3000
```

Stop all services:

```bash
docker compose down
```

Restart from a clean compose state:

```bash
docker compose down
docker compose up --build
```

## Verify the Services

Run these commands in a second terminal while Docker Compose is running:

```bash
cd /workspaces/ai-infra-learning

curl -s http://127.0.0.1:8000/health | jq
curl -s http://127.0.0.1:8001/health | jq
curl -s http://127.0.0.1:8000/metrics/logs | jq
curl -s http://127.0.0.1:8000/metrics/alerts | jq
curl -s http://127.0.0.1:8000/metrics/incidents | jq
curl -s http://127.0.0.1:8000/metrics/prometheus | head -20
```

Expected result:

- `8000 /health` returns `ai-metrics-api`
- `8001 /health` returns `mock-model-server`
- `/metrics/logs` returns request counts, error rate, latency percentiles, slow requests, and model-level metrics
- `/metrics/prometheus` returns Prometheus text metrics such as `ai_inference_total_requests`, `ai_inference_error_rate`, and `ai_inference_p95_latency_ms`

## Send a Mock Inference Request

```bash
curl -i -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":300,"tokens_out":80}'
```

Check that a new inference log line was written:

```bash
tail -n 3 data/day02/inference.log
```

## API Endpoints

AI metrics API:

```text
GET  /health
POST /v1/mock-infer
GET  /metrics/logs
GET  /metrics/slow
GET  /metrics/errors
GET  /metrics/models
GET  /metrics/alerts
GET  /metrics/incidents
GET  /metrics/prometheus
```

Mock model server:

```text
GET  /health
POST /generate
```

## Run Tests

```bash
python -m pytest -q
```

Current expected result:

```text
12 passed, 1 warning
```

The warning comes from FastAPI/Starlette test client internals and does not indicate a project behavior failure.

## Current Capabilities

The project currently supports:

- FastAPI inference metrics service
- separated mock model backend service
- structured inference log parsing
- service-level request, success, error, and latency metrics
- model-level request count, error count, average latency, P95 latency, and error rate
- slow request analysis
- error request filtering
- warning and critical alert generation
- incident diagnosis summary
- Prometheus metrics export
- service-level Prometheus metrics
- model-level Prometheus metrics with `model` labels
- Prometheus scrape configuration
- Grafana datasource and dashboard provisioning
- Docker Compose startup
- load testing script
- pytest-based automated tests
- model server failure handling

Example model-level Prometheus metrics:

```text
ai_inference_model_request_count{model="qwen2.5-7b"} 7
ai_inference_model_error_count{model="qwen2.5-7b"} 2
ai_inference_model_error_rate{model="qwen2.5-7b"} 0.2857
ai_inference_model_avg_latency_ms{model="qwen2.5-7b"} 289.0
ai_inference_model_p95_latency_ms{model="qwen2.5-7b"} 910
```

These metrics make it possible to compare traffic, errors, and latency across different model names.

## Load Test

Generate controlled traffic:

```bash
python scripts/load_test.py --count 10 --error-rate 0.1
```

After running the load test, check:

```bash
curl -s http://127.0.0.1:8000/metrics/logs | jq
curl -s http://127.0.0.1:8000/metrics/alerts | jq
curl -s http://127.0.0.1:8000/metrics/incidents | jq
```

Prometheus and Grafana should reflect the updated metrics after the API writes new inference logs.

## Current Limitations

- The inference log is stored in a local file instead of a database, queue, or log aggregation system.
- The backend model service is still a mock model server, not a real model runtime.
- The system is designed for local learning and demonstration, not production deployment.
- Kubernetes, distributed tracing, GPU metrics, and real model serving are future extensions.

## Next Steps

Planned improvements:

1. Add an architecture diagram.
2. Improve Prometheus metric semantics with model-level or endpoint-level labels.
3. Add a real model backend.
4. Add backend selection between mock and real model services.
5. Improve structured error handling.
6. Add a load test report with concrete metrics.
7. Polish final project documentation and resume bullets.

## Current Project Status

This project has evolved from a mock inference metrics API into a small AI inference observability and reliability platform.

It currently supports:

- FastAPI metrics API for inference requests, structured logs, model metrics, alerts, incidents, and Prometheus metrics
- Mock model server for reproducible local experiments
- Remote HTTP backend mode for connecting the metrics API to an external model server
- GPU model server template with both template mode and transformers mode
- Real GPU backend validation using Qwen/Qwen2.5-0.5B-Instruct on an NVIDIA RTX A5000
- Model-level Prometheus metrics
- Grafana dashboard panels for service-level and model-level observability
- Backend failure logging so unavailable model backends become visible in logs, metrics, and incidents
- GPU model server readiness endpoint separating process health from backend readiness

## Architecture

    client
      -> ai-metrics-api
      -> model backend
          -> mock-model-server
          -> remote_http GPU model server
      -> inference log
      -> metrics APIs
      -> Prometheus
      -> Grafana

## Backend Modes

The metrics API supports two backend modes:

    MODEL_BACKEND=mock
    MODEL_BACKEND=remote_http

The mock backend is used for repeatable local development and tests.

The remote_http backend allows the same observability pipeline to call a separate model server, including a GPU-backed server running on a remote machine.

The GPU model server supports:

    GPU_MODEL_MODE=template
    GPU_MODEL_MODE=transformers

Template mode returns protocol-compatible responses with estimated latency.

Transformers mode runs a real Hugging Face Transformers model and returns protocol-compatible inference metrics.

## GPU Validation

The project includes a real GPU backend validation report:

    reports/gpu_backend_observability_report.md

The report covers:

- Running Qwen/Qwen2.5-0.5B-Instruct on an NVIDIA RTX A5000
- Routing ai-metrics-api traffic to the GPU model server through remote_http
- Recording successful GPU-backed inference requests
- Observing backend failure as 502 responses, failed inference logs, metrics, and incident signals
- Running a 10-request stability sample
- Comparing small-token and large-token latency

## Reliability Work

The project includes several reliability-focused behaviors:

- Failed backend calls are written to the inference log
- Backend unavailable errors are exposed as structured 502 responses
- Transformers dependency, model loading, and generation failures return structured errors
- GPU model server exposes both /health and /ready
- /ready checks whether the selected runtime mode is actually ready to serve requests

This makes the project useful for discussing AI infrastructure reliability, not only model serving.

## Key Documentation

- `docs/MODEL_BACKEND_PROTOCOL.md`
- `docs/GPU_SERVER_SETUP.md`
- `projects/gpu_model_server/README.md`
- `reports/gpu_backend_observability_report.md`