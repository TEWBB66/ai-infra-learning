# GPU Server Setup Guide

This document describes how to prepare a remote GPU server for the GPU model backend experiment.

The goal is to run `projects/gpu_model_server` on a GPU machine and connect `ai-metrics-api` to it through the `remote_http` backend.

The default project should still be runnable without GPU access. The GPU server is used only for a short-term validation experiment.

## Target Architecture

```text
client / load_test.py
        |
        v
ai-metrics-api
        |
        v
remote_http backend
        |
        v
GPU model server
        |
        v
inference log -> metrics -> Prometheus -> Grafana -> alerts/incidents
```

## Step 1. Connect to the GPU Server

Use VS Code Remote SSH or a normal SSH terminal.

After connecting, confirm the working directory and user:

```bash
pwd
whoami
hostname
```

## Step 2. Check GPU Availability

Run:

```bash
nvidia-smi
```

Expected result:

- NVIDIA driver information is shown
- GPU name is visible
- memory usage is visible

If `nvidia-smi` is not available, record the error before changing the environment.

## Step 3. Check Python Environment

Run:

```bash
python --version
which python
pip --version
```

If a conda environment is used:

```bash
conda env list
```

If a virtual environment is used:

```bash
python -m venv .venv
source .venv/bin/activate
```

## Step 4. Check Existing PyTorch Installation

Before installing anything, check whether PyTorch is already available:

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

If PyTorch with CUDA is already installed, do not reinstall it unless necessary.

## Step 5. Install Server Dependencies

Install lightweight API dependencies:

```bash
pip install fastapi uvicorn
```

Install model dependencies only if needed:

```bash
pip install transformers accelerate
```

Install PyTorch only if it is missing or unusable. Prefer the official PyTorch install command that matches the GPU server CUDA version.

## Step 6. Get the Project Code

Clone or pull the project on the GPU server:

```bash
git clone https://github.com/TEWBB66/ai-infra-learning.git
cd ai-infra-learning
```

If the repository already exists:

```bash
cd ai-infra-learning
git pull
git status
```

## Step 7. Run the Template GPU Model Server

Start with template mode first. This verifies that the HTTP service works before loading a real model.

```bash
GPU_MODEL_MODE=template \
uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

In another terminal on the GPU server, verify health:

```bash
curl -s http://127.0.0.1:8002/health
```

Verify generation:

```bash
curl -s -X POST http://127.0.0.1:8002/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-0.5b","tokens_in":100,"tokens_out":20}'
```

Expected response shape:

```json
{
  "model": "qwen2.5-0.5b",
  "status": 200,
  "latency_ms": 59,
  "tokens_in": 100,
  "tokens_out": 20
}
```

## Step 8. Test Network Access from Codespaces

From Codespaces, test whether the GPU server is reachable.

```bash
curl -s http://<gpu-server-host>:8002/health
```

If this fails, check:

- whether the GPU server firewall allows the port
- whether the port is bound to `0.0.0.0`
- whether the server requires SSH tunneling
- whether Codespaces can reach the server network

If direct access is not available, use SSH port forwarding if permitted.

## Step 9. Connect ai-metrics-api to the GPU Server

In Codespaces, configure `ai-metrics-api` to call the remote GPU backend:

```bash
MODEL_BACKEND=remote_http
MODEL_SERVER_URL=http://<gpu-server-host>:8002/generate
MODEL_SERVER_TIMEOUT_SECONDS=60
```

Then start the observability stack:

```bash
docker compose up --build
```

Send a request through `ai-metrics-api`:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-0.5b","tokens_in":100,"tokens_out":20}'
```

Check logs and metrics:

```bash
tail -n 3 data/day02/inference.log
curl -s http://127.0.0.1:8000/metrics/logs
curl -s http://127.0.0.1:8000/metrics/prometheus | grep ai_inference_model
curl -s http://127.0.0.1:8000/metrics/incidents
```

## Step 10. Future Transformers Mode

After template mode works on the GPU server, switch to transformers mode:

```bash
GPU_MODEL_MODE=transformers \
GPU_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct \
uvicorn projects.gpu_model_server.main:app --host 0.0.0.0 --port 8002
```

The first target model should be small:

```text
Qwen/Qwen2.5-0.5B-Instruct
```

Use a larger model only after the small model works.

## Step 11. What To Record

For the final GPU backend report, record:

- GPU model name
- GPU type
- whether CUDA is available
- server startup command
- successful `/health` response
- successful `/generate` response
- `ai-metrics-api` request response
- inference log examples
- `/metrics/logs` output
- model-level Prometheus metrics
- incident output
- any network or dependency issue

## Troubleshooting

### `nvidia-smi` Not Found

The server may not expose GPU drivers in the current environment.

Record the error and ask whether the assigned machine actually has GPU access.

### `torch.cuda.is_available()` Is False

Possible causes:

- CPU-only PyTorch was installed
- CUDA version mismatch
- GPU is not visible inside the current environment
- running inside a container without GPU passthrough

### Codespaces Cannot Reach GPU Server

Possible causes:

- private network
- firewall
- port not open
- service bound to `127.0.0.1` instead of `0.0.0.0`

First confirm the service works locally on the GPU server, then debug remote access.

### Model Download Is Slow

Start with the smallest model.

If model download is blocked or slow, record this as an environment limitation and continue with template mode until the download issue is resolved.