# GPU Model Server

This directory contains the remote GPU model server for the AI inference observability project.

The service implements the backend protocol documented in:

```text
docs/MODEL_BACKEND_PROTOCOL.md
```

It exposes:

```text
GET  /health
POST /generate
```

## Purpose

The default project remains runnable with the local mock backend:

```text
MODEL_BACKEND=mock
MODEL_SERVER_URL=http://mock-model-server:8001/generate
```

The GPU model server is used for a short-term remote GPU experiment:

```text
MODEL_BACKEND=remote_http
MODEL_SERVER_URL=http://<gpu-server-host>:<port>/generate
```

This allows `ai-metrics-api` to observe a GPU-hosted model backend without making GPU access a permanent dependency of the project.

## Runtime Modes

The GPU model server supports runtime modes through an environment variable:

```bash
GPU_MODEL_MODE=template
```

Supported modes:

```text
template
transformers
```

## Template Mode

Template mode is the default mode.

```bash
GPU_MODEL_MODE=template
```

In this mode, the server does not load a real model. It returns protocol-compatible responses with estimated latency.

This mode is useful for:

- local development
- protocol testing
- API integration tests
- validating the remote backend path without GPU dependencies

Run template mode:

```bash
uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

## Transformers Mode

Transformers mode loads a Hugging Face causal language model and runs generation through `transformers`.

```bash
GPU_MODEL_MODE=transformers
GPU_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct
```

In this mode, the server:

1. checks that `torch` and `transformers` are installed
2. lazily loads tokenizer and model
3. moves the model to CUDA if available
4. builds a short prompt from the request
5. runs `model.generate(...)`
6. measures inference latency
7. returns the same backend protocol response schema

The response schema stays unchanged:

```json
{
  "model": "qwen2.5-0.5b",
  "status": 200,
  "latency_ms": 123,
  "tokens_in": 100,
  "tokens_out": 20
}
```

Keeping the response schema stable allows `ai-metrics-api`, Prometheus, Grafana, alerts, and incidents to work without changes.

## Recommended First Real Model

Start with the smaller model:

```text
Qwen/Qwen2.5-0.5B-Instruct
```

Only try a larger model after the smaller model works.

Possible larger option:

```text
Qwen/Qwen2.5-1.5B-Instruct
```

The goal is not to demonstrate model quality. The goal is to validate the serving and observability chain:

```text
client -> ai-metrics-api -> remote_http backend -> GPU model server -> inference log -> metrics -> Prometheus -> Grafana -> incidents
```

## Suggested GPU Environment Dependencies

Install these dependencies on the GPU server environment, not necessarily in the root project environment:

```bash
pip install fastapi uvicorn transformers accelerate
```

Install or reuse PyTorch based on the GPU server CUDA version.

Before installing PyTorch, check whether it already exists:

```bash
python - <<'PY'
try:
    import torch
    print("torch version:", torch.__version__)
    print("cuda available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("cuda device:", torch.cuda.get_device_name(0))
except ImportError:
    print("torch is not installed")
PY
```

If PyTorch with CUDA is already installed, avoid reinstalling it unless necessary.

## Run Commands

Run template mode:

```bash
GPU_MODEL_MODE=template \
uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

Run transformers mode:

```bash
GPU_MODEL_MODE=transformers \
GPU_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct \
uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

## Verify the Server

Health check:

```bash
curl -s http://127.0.0.1:8002/health | jq
```

Generate request:

```bash
curl -s -X POST http://127.0.0.1:8002/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-0.5b","tokens_in":100,"tokens_out":20}' | jq
```

## Connect ai-metrics-api to This Server

When this service is running, configure `ai-metrics-api` with:

```bash
MODEL_BACKEND=remote_http
MODEL_SERVER_URL=http://<gpu-server-host>:8002/generate
MODEL_SERVER_TIMEOUT_SECONDS=60
```

For local testing where both services run on the same machine:

```bash
MODEL_BACKEND=remote_http
MODEL_SERVER_URL=http://127.0.0.1:8002/generate
MODEL_SERVER_TIMEOUT_SECONDS=60
```

Then call:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-0.5b","tokens_in":100,"tokens_out":20}' | jq
```

## Why Template Mode Remains the Default

The default mode stays lightweight because the main repository must remain reproducible without GPU access.

The remote GPU experiment is optional:

```text
default local demo -> mock backend / template backend
short-term GPU validation -> remote_http backend + transformers mode
```

## Readiness and Structured Errors

The GPU model server exposes two health-style endpoints:

    GET /health
    GET /ready

`/health` only checks whether the service process is alive.

`/ready` checks whether the selected runtime mode is ready to serve requests.

Template mode readiness response:

    {
      "status": "ready",
      "mode": "template"
    }

Transformers mode readiness response:

    {
      "status": "ready",
      "mode": "transformers",
      "model": "Qwen/Qwen2.5-0.5B-Instruct"
    }

If transformers dependencies are missing, `/ready` returns 503:

    {
      "detail": "transformers mode is not ready; missing dependencies: torch, transformers"
    }

If the selected GPU model mode is unsupported, `/ready` returns 503:

    {
      "detail": "unsupported GPU_MODEL_MODE: unsupported"
    }

The transformers runtime also returns structured errors for expected failure classes:

    transformers mode requires missing dependencies: torch, transformers
    transformers model loading failed for Qwen/Qwen2.5-0.5B-Instruct: <error>
    transformers generation failed for qwen2.5-0.5b: <error>

This separates liveness from readiness and makes backend failures easier to diagnose during deployment and GPU experiments.