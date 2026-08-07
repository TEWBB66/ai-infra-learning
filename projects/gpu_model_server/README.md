# GPU Model Server

This directory contains the remote GPU model server template for the AI inference observability project.

The service implements the backend protocol documented in:

```text
docs/MODEL_BACKEND_PROTOCOL.md
```

It exposes:

```text
GET  /health
POST /generate
```

The current version returns protocol-compatible responses with estimated latency. It does not load a real model yet.

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

This allows `ai-metrics-api` to observe a real or semi-real GPU-hosted model backend without making GPU access a permanent dependency of the project.

## Recommended First Real Model Path

Use FastAPI + Transformers for the first GPU experiment.

Recommended model options:

```text
Qwen/Qwen2.5-0.5B-Instruct
Qwen/Qwen2.5-1.5B-Instruct
```

Start with the smaller model if GPU memory or setup time is limited.

The goal is not to demonstrate model quality. The goal is to validate the serving and observability chain:

```text
client -> ai-metrics-api -> remote_http backend -> GPU model server -> inference log -> metrics -> Prometheus -> Grafana -> incidents
```

## Suggested GPU Environment Dependencies

Install these dependencies on the GPU server environment, not necessarily in the root project environment:

```bash
pip install fastapi uvicorn torch transformers accelerate
```

If the GPU server already has PyTorch and CUDA installed, avoid reinstalling PyTorch unless necessary.

## Local Template Run Command

Run the template service:

```bash
uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

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
MODEL_SERVER_TIMEOUT_SECONDS=30
```

For local testing where both services run on the same machine:

```bash
MODEL_BACKEND=remote_http
MODEL_SERVER_URL=http://127.0.0.1:8002/generate
MODEL_SERVER_TIMEOUT_SECONDS=30
```

Then call:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-0.5b","tokens_in":100,"tokens_out":20}' | jq
```

## Future Upgrade

The next version can replace estimated latency with real model inference:

1. Load tokenizer and model at service startup.
2. Convert the request into a prompt.
3. Run generation on GPU.
4. Measure actual inference latency.
5. Return the same response fields required by the backend protocol.

The response schema should stay stable so the observability stack does not need to change.