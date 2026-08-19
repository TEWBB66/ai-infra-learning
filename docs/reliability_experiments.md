# Reliability Experiments

This project validates the inference observability and reliability path with three controlled experiments:

1. Successful inference traffic
2. Backend logical failure traffic
3. Overload / backpressure traffic

## Environment

The experiments were run with Docker Compose.

Configurable runtime variables:

- `INFERENCE_LOG_PATH`: runtime inference log path inside the API container
- `MAX_IN_FLIGHT_REQUESTS`: maximum concurrent in-flight inference requests accepted by the API
- `MOCK_MODEL_DELAY_SCALE`: mock backend delay multiplier

## Experiment 1: Successful Traffic Baseline

API service command:

```bash
INFERENCE_LOG_PATH=/app/data/day02/reliability_normal.log \
MAX_IN_FLIGHT_REQUESTS=8 \
MOCK_MODEL_DELAY_SCALE=0 \
docker compose up --build
```

Load command:

```bash
python scripts/concurrent_load_test.py \
  --count 50 \
  --concurrency 5 \
  --force-status 200
```

Result:

- Total requests: 50
- HTTP 200: 50
- Logical 200: 50
- Rejected 429: 0
- Log analyzer success rate: 1.0
- Log analyzer error rate: 0.0
- Prometheus status metric: `ai_inference_status_requests{status="200"} 50`
- Final in-flight gauge: `ai_inference_current_in_flight_requests 0`
- Incident status: healthy

Conclusion:

The normal inference path is observable end to end: API request, mock backend response, structured log, analyzer summary, Prometheus metric, and incident status.

## Experiment 2: Backend Logical Failure

API service command:

```bash
INFERENCE_LOG_PATH=/app/data/day02/reliability_backend_error.log \
MAX_IN_FLIGHT_REQUESTS=8 \
MOCK_MODEL_DELAY_SCALE=0 \
docker compose up --build
```

Load command:

```bash
python scripts/concurrent_load_test.py \
  --count 50 \
  --concurrency 5 \
  --force-status 500
```

Result:

- Total requests: 50
- HTTP 200: 50
- Logical 500: 50
- Logical success: 0
- Logical error: 50
- Rejected 429: 0
- Log analyzer error rate: 1.0
- Prometheus status metric: `ai_inference_status_requests{status="500"} 50`
- Final in-flight gauge: `ai_inference_current_in_flight_requests 0`
- Incident status: critical

Conclusion:

The API distinguishes transport-level success from backend logical failure. Even when HTTP requests complete successfully, backend failure status is captured in structured logs, metrics, and incident summaries.

## Experiment 3: Overload / Backpressure

API service command:

```bash
INFERENCE_LOG_PATH=/app/data/day02/reliability_overload.log \
MAX_IN_FLIGHT_REQUESTS=2 \
MOCK_MODEL_DELAY_SCALE=1.0 \
docker compose up --build
```

Load command:

```bash
python scripts/concurrent_load_test.py \
  --count 50 \
  --concurrency 10 \
  --force-status 200 \
  --timeout 10
```

Result:

- Total requests: 50
- HTTP 200: 22
- HTTP 429: 28
- Rejected 429: 28
- Logical 200: 22
- Log analyzer success rate: 0.44
- Log analyzer error rate: 0.56
- Prometheus status metrics:
  - `ai_inference_status_requests{status="429"} 28`
  - `ai_inference_status_requests{status="200"} 22`
- Final in-flight gauge: `ai_inference_current_in_flight_requests 0`
- Incident status: critical

Conclusion:

The API applies single-instance backpressure under overload. With a slow backend and client concurrency higher than the configured in-flight limit, excessive requests are rejected with HTTP 429 instead of being accepted unboundedly. The in-flight gauge returning to 0 confirms that successful and rejected paths do not leak slots.

## Interview Notes

This experiment set is not intended to claim production-scale performance. Its value is that the failure modes are controlled and reproducible:

- Normal success traffic validates the end-to-end observability path.
- Backend logical failure validates model-service failure telemetry.
- Overload traffic validates API-side backpressure and slot release behavior.

The current backpressure implementation is single-instance and in-memory. In a multi-replica deployment, the next step would be to combine per-instance gates with load balancing, autoscaling metrics, and possibly distributed rate limiting depending on the serving architecture.

## Real vLLM Backend Reliability Experiments

After the mock reliability experiments, the same API reliability layer was tested in front of a real vLLM backend.

Environment:

- Date: 2026-08-18
- Host: A5000 lab GPU server
- GPU used: NVIDIA RTX A5000, GPU 0 only
- Model: Qwen/Qwen2.5-0.5B-Instruct
- vLLM: 0.11.0
- API backend: `MODEL_BACKEND=vllm`
- vLLM base URL: `http://127.0.0.1:8001/v1`

### Real vLLM Smoke Test

Validated behavior:

- vLLM `/v1/models` returned the served model
- vLLM `/v1/chat/completions` generated a response
- `/v1/infer` routed through vLLM
- Structured logs captured vLLM latency and token counts
- Prometheus metrics captured status and model request counts

### Real vLLM Small Load Sample

Load result:

- Total requests: 10
- HTTP 200: 10
- Logical 200: 10
- Rejected 429: 0
- Average client latency: 176.97 ms
- P95 client latency: 215.78 ms
- Throughput: 11.265 requests/sec
- Output tokens/sec: 112.648

### Real vLLM Backpressure

The API was restarted with `MAX_IN_FLIGHT_REQUESTS=2` and `MODEL_BACKEND=vllm`.

Load result:

- Total requests: 30
- HTTP 200: 2
- HTTP 429: 28
- Logical 200: 2
- Logical 429: 28
- Rejected 429: 28
- Final in-flight gauge: `ai_inference_current_in_flight_requests 0`

Conclusion:

The same single-instance in-flight gate that worked against the mock backend also protected a real vLLM backend. Excess requests were rejected quickly with HTTP 429 instead of being forwarded unboundedly to the model server.

### Real vLLM Benchmark Matrix

Matrix:

- Concurrency: 1, 2, 4, 8, 16
- Max tokens: 32, 128, 512
- Requests per case: 50
- Total benchmark requests: 750

Aggregate result:

- Successful requests: 750
- Failed requests: 0
- Error rate: 0.0
- Final in-flight gauge: 0
- vLLM running requests after matrix: 0
- vLLM waiting requests after matrix: 0
- vLLM prompt tokens total: 48600
- vLLM generation tokens total: 165754
- GPU 0 memory after matrix: about 12485 MiB / 24564 MiB
- GPU 1/2/3 were not used by vLLM

Full benchmark report:

`reports/vllm_benchmark_2026_08_18/README.md`

This does not make the system production-grade or distributed. The honest claim is narrower and stronger: this is a single-node, single-GPU LLM serving reliability prototype with real vLLM benchmark evidence.
