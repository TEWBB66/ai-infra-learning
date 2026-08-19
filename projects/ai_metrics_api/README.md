# AI Metrics API

FastAPI service for LLM inference observability, backend routing, structured logs, Prometheus metrics, alerts, incidents, and API-side backpressure.

This subproject can run locally against the deterministic mock backend or route real traffic to an OpenAI-compatible vLLM backend.

## Current Capabilities

- Stable inference endpoint: `POST /v1/infer`
- Backward-compatible mock endpoint: `POST /v1/mock-infer`
- Backend switching with `MODEL_BACKEND=mock|vllm`
- Deterministic mock backend for local tests, failure injection, and overload experiments
- vLLM backend client using `/v1/chat/completions`
- Structured inference logs with request id, trace id, client id, model, endpoint, status, latency, and token counts
- File and SQLite inference log backends
- Service-level metrics: request count, success rate, error rate, average latency, p95, p99, slow requests
- Model-level metrics: request count, error count, status counts, p95 latency, error rate
- Prometheus text endpoint with service, status, in-flight, queue, rate-limit, and model metrics
- API-side in-flight backpressure with HTTP 429 rejection
- Optional API key authentication for inference endpoints
- Optional per-client inference rate limiting
- Alert and incident summary endpoints for degraded behavior

## Runtime Architecture

```text
client / load test
    -> ai-metrics-api /v1/infer
    -> optional API key check
    -> optional per-client rate limit
    -> in-flight admission gate
    -> backend client abstraction
       -> mock-model-server /generate
       -> vLLM /v1/chat/completions
    -> file or SQLite inference log
    -> metrics APIs
    -> /metrics/prometheus
    -> Prometheus
    -> Grafana
```

## Key Files

```text
projects/ai_metrics_api/main.py             FastAPI app, request handling, logs, metrics, alerts, incidents
projects/ai_metrics_api/config.py           Runtime configuration and thresholds
projects/ai_metrics_api/log_store.py        File and SQLite inference log storage
projects/ai_metrics_api/rate_limiter.py     Per-client fixed-window rate limiter
projects/ai_metrics_api/model_client.py     Backend client factory
projects/ai_metrics_api/backend_clients.py  Mock and vLLM backend clients
projects/log_analyzer/analyze_logs.py       Log parser and metrics aggregation
scripts/concurrent_load_test.py             Concurrent load and benchmark runner
```

## Backend Modes

Default local mode:

```text
MODEL_BACKEND=mock
MOCK_MODEL_SERVER_URL=http://mock-model-server:8001/generate
```

Real vLLM mode:

```text
MODEL_BACKEND=vllm
VLLM_BASE_URL=http://127.0.0.1:8001/v1
VLLM_MODEL=Qwen/Qwen2.5-0.5B-Instruct
MODEL_SERVER_TIMEOUT_SEC=60
```

`mock` is used for repeatable local validation. `vllm` is used for real LLM serving tests and maps OpenAI-compatible usage fields into the same internal response shape used by logs and metrics.

## API Endpoints

```text
GET  /health
GET  /ready
POST /v1/infer
POST /v1/mock-infer
GET  /metrics/logs
GET  /metrics/models
GET  /metrics/slow
GET  /metrics/errors
GET  /metrics/alerts
GET  /metrics/incidents
GET  /metrics/prometheus
```

## Request Shape

```json
{
  "model": "Qwen/Qwen2.5-0.5B-Instruct",
  "tokens_in": 32,
  "tokens_out": 32,
  "prompt": "Say hello in one short sentence.",
  "max_tokens": 32,
  "temperature": 0
}
```

`force_status` is supported for mock-backend failure injection and accepts `200`, `400`, `429`, or `500`.

## Response Shape

```json
{
  "request_id": "req-1234abcd",
  "trace_id": "trace-1234abcd",
  "model": "Qwen/Qwen2.5-0.5B-Instruct",
  "status": 200,
  "latency_ms": 173,
  "tokens_in": 36,
  "tokens_out": 10
}
```

## Prometheus Metrics

Service and admission-control metrics:

```text
ai_inference_total_requests
ai_inference_success_requests
ai_inference_failed_requests
ai_inference_error_rate
ai_inference_p95_latency_ms
ai_inference_p99_latency_ms
ai_inference_slow_request_count
ai_inference_current_in_flight_requests
ai_inference_queue_depth
ai_inference_queue_rejected_total
ai_inference_queue_timeout_total
ai_inference_rate_limit_enabled
ai_inference_rate_limit_active_clients
ai_inference_rate_limit_rejected_total
ai_inference_status_requests{status="200"}
ai_inference_status_requests{status="429"}
```

Model-level metrics:

```text
ai_inference_model_requests{model="..."}
ai_inference_model_errors{model="..."}
ai_inference_model_error_rate{model="..."}
ai_inference_model_p95_latency_ms{model="..."}
```

## Local Validation

Run the default mock stack:

```bash
docker compose up --build
```

Run tests:

```bash
python -m pytest -q
```

Expected result:

```text
56 passed, 1 warning
```

The warning is the known FastAPI / Starlette TestClient warning.

## Real vLLM Validation

The current implementation was validated against a real vLLM backend on August 18, 2026:

```text
Host: A5000 lab GPU server
GPU: NVIDIA RTX A5000, GPU 0 only
Model: Qwen/Qwen2.5-0.5B-Instruct
vLLM: 0.11.0
API backend: MODEL_BACKEND=vllm
```

Validation evidence:

- `/ready` reported `backend=vllm`
- `/v1/infer` successfully routed to vLLM
- vLLM token usage was captured as `tokens_in` and `tokens_out`
- real-backend backpressure returned 28 HTTP 429 responses out of 30 requests when `MAX_IN_FLIGHT_REQUESTS=2`
- benchmark matrix completed 750/750 successful requests
- Prometheus metrics captured status, model, and in-flight metrics

Full report:

```text
reports/vllm_benchmark_2026_08_18/README.md
```

## Project Boundary

This service is a single-instance learning prototype. It demonstrates the serving reliability layer around LLM inference, not a production distributed serving platform.

Known limits are documented in:

```text
docs/PRODUCTION_GAPS.md
```

Important current limits:

- API key authentication is intentionally simple and does not replace full authorization
- rate limiting is per API process, not distributed across replicas
- SQLite storage is local and not a replacement for an external production database
- request and trace identifiers are propagated, but no tracing backend is integrated
- no GPU scheduler
- no autoscaling
- no production deployment manifests
