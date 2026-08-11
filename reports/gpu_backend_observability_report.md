# GPU Backend Observability Validation Report

## Date

2026-08-10

## Goal

Validate that the observability system can route inference traffic to a real GPU-backed model server through the same backend protocol used by the mock server.

## Environment

- Host: A5000
- GPU: NVIDIA RTX A5000
- GPU used for experiment: GPU 0 only
- GPU isolation: CUDA_VISIBLE_DEVICES=0
- Driver version: 590.48.01
- CUDA version shown by nvidia-smi: 13.1
- Python: 3.10.12
- torch: 2.13.0+cu130
- transformers: 5.14.1
- Model: Qwen/Qwen2.5-0.5B-Instruct
- Project path on GPU host: /home/rrj/projects/model-observability

## Services

GPU model server:

```bash
cd /home/rrj/projects/model-observability

CUDA_VISIBLE_DEVICES=0 \
HF_HOME=/home/rrj/.cache/huggingface \
GPU_MODEL_MODE=transformers \
GPU_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct \
python3 -m uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

Metrics API using the remote HTTP backend:

```bash
cd /home/rrj/projects/model-observability

MODEL_BACKEND=remote_http \
MODEL_SERVER_URL=http://127.0.0.1:8002/generate \
MODEL_SERVER_TIMEOUT_SECONDS=60 \
python3 -m uvicorn projects.ai_metrics_api.main:app --host 127.0.0.1 --port 8000
```

## Validation Commands

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-0.5b","tokens_in":100,"tokens_out":20}'

tail -n 3 data/day02/inference.log

curl -s http://127.0.0.1:8000/metrics/logs

curl -s http://127.0.0.1:8000/metrics/prometheus | grep ai_inference_model
```

## Observed Results

The health endpoint returned successfully:

```json
{"status":"ok","service":"ai-metrics-api"}
```

The API routed one inference request through the GPU model server and returned a protocol-compatible response:

```json
{
  "request_id": "req-73b0dff6",
  "model": "qwen2.5-0.5b",
  "status": 200,
  "latency_ms": 399,
  "tokens_in": 100,
  "tokens_out": 20
}
```

The inference log contained the GPU-backed request:

```text
2026-08-10T08:30:08Z request_id=req-73b0dff6 model=qwen2.5-0.5b endpoint=/v1/mock-infer status=200 latency_ms=399 tokens_in=100 tokens_out=20
```

The metrics endpoint included the real GPU-backed model:

```json
"qwen2.5-0.5b": {
  "request_count": 1,
  "error_count": 0,
  "avg_latency_ms": 399.0,
  "p95_latency_ms": 399,
  "error_rate": 0.0
}
```

Prometheus metrics also exposed model-level labels for the GPU-backed model.

## GPU Usage

During the transformers-mode experiment, nvidia-smi showed one python3 process on GPU 0 using about 1268 MiB of GPU memory.

The experiment intentionally used only GPU 0:

```bash
CUDA_VISIBLE_DEVICES=0
```

No training job was started. The model server was used only for short inference validation.

## Issues Encountered

Codespaces could not directly reach the lab machine at:

```text
http://10.20.4.6:8002/health
```

Because of that, the end-to-end validation was run locally on the GPU host by starting both the GPU model server and the metrics API on the same machine.

The GPU server initially returned Internal Server Error in transformers mode because the system Pillow package was too old and did not provide PIL.Image.Resampling. This was fixed with a user-level package upgrade:

```bash
python3 -m pip install --user --upgrade Pillow
```

The GPU host does not provide the python command, only python3. All GPU-host commands should therefore use python3 and python3 -m pip.

Creating a venv failed because python3.10-venv is not installed system-wide. Since this is a shared lab machine, no sudo or system-level package changes were made. Dependencies were installed only under the user's home directory.

## Interpretation

This validates that the project is no longer only a mock observability demo. The same ai-metrics-api service can now route inference traffic to a real GPU-backed model server through the remote_http backend.

The observability layer did not need to know whether the backend was mock or transformers-based. It only depended on the shared model backend protocol:

```text
HTTP request -> model backend -> standardized response -> inference log -> metrics -> Prometheus
```

This is the key engineering value of the project: backend implementation can change while logging, metrics, alerts, and incident analysis remain stable.

## Next Steps

1. Run a small repeated-request experiment against the GPU backend.
2. Run a larger-token request experiment and compare latency.
3. Run a backend-failure experiment by stopping the GPU model server and checking API error handling.
4. Improve GPU model server error handling so dependency and generation failures return structured HTTP errors instead of generic Internal Server Error.

## Backend Failure Retest

After implementing failed backend request logging, the GPU backend failure experiment was repeated.

For this test, the GPU model server was intentionally left stopped. Only the metrics API was started with the remote_http backend.

Metrics API startup command:

    MODEL_BACKEND=remote_http \
    MODEL_SERVER_URL=http://127.0.0.1:8002/generate \
    MODEL_SERVER_TIMEOUT_SECONDS=5 \
    python3 -m uvicorn projects.ai_metrics_api.main:app --host 127.0.0.1 --port 8000

The request returned a 502 response as expected:

    HTTP/1.1 502 Bad Gateway
    {"detail":"model server is unavailable"}

The failed backend request was written to the inference log:

    2026-08-10T08:58:26Z request_id=req-9255dff6 model=qwen2.5-0.5b endpoint=/v1/mock-infer status=502 latency_ms=72 tokens_in=100 tokens_out=0

The metrics endpoint also reflected the failure:

    total_requests: 16
    failed_requests: 4
    error_rate: 0.25
    qwen2.5-0.5b request_count: 2
    qwen2.5-0.5b error_count: 1
    qwen2.5-0.5b error_rate: 0.5

This confirms the reliability fix:

    Before:
    GPU backend unavailable -> API returned 502, but no inference log record was written.

    After:
    GPU backend unavailable -> API returned 502, wrote a failed inference log record, and updated metrics and incident signals.

This is important because a production observability system must not lose failed backend calls. User-visible failures should become system-visible telemetry.

## GPU Stability Sample Experiment

A 10-request stability sample was run against the real GPU backend.

Request shape:

    model: qwen2.5-0.5b
    tokens_in: 100
    tokens_out: 20

Observed latency:

    request 1: 1369 ms
    request 2: 350 ms
    request 3: 352 ms
    request 4: 352 ms
    request 5: 354 ms
    request 6: 352 ms
    request 7: 343 ms
    request 8: 351 ms
    request 9: 349 ms
    request 10: 351 ms

Metrics summary:

    request_count: 12
    error_count: 1
    avg_latency_ms: 416.17
    p95_latency_ms: 399
    error_rate: 0.0833

Interpretation:

The first request was slower because of model warmup. After warmup, requests 2 through 10 stayed around 343-354 ms.

This shows that the system can observe repeated successful GPU inference traffic, not only one-off GPU backend validation.
