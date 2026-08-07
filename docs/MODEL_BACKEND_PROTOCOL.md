# Model Backend Protocol

This document defines the HTTP protocol that any model backend must implement in order to work with `ai-metrics-api`.

The goal is to make the observability system backend-agnostic. The API service should be able to call either:

- the local mock model server
- a remote GPU model server
- a future real model serving runtime

as long as the backend follows the same request and response contract.

## Required Health Endpoint

### `GET /health`

The model backend should expose a health endpoint.

Example response:

```json
{
  "status": "ok",
  "service": "mock-model-server"
}
```

For a remote GPU backend, the service name can be different:

```json
{
  "status": "ok",
  "service": "gpu-model-server"
}
```

## Required Generation Endpoint

### `POST /generate`

The model backend must expose a `/generate` endpoint.

Request body:

```json
{
  "model": "qwen2.5-7b",
  "tokens_in": 300,
  "tokens_out": 80,
  "force_status": null
}
```

Required fields:

- `model`: model name requested by the client
- `tokens_in`: number of input tokens or estimated input tokens
- `tokens_out`: number of output tokens or requested output tokens

Optional field:

- `force_status`: used by the mock backend for controlled failure testing

## Response Body

A successful backend response must return:

```json
{
  "model": "qwen2.5-7b",
  "status": 200,
  "latency_ms": 186,
  "tokens_in": 300,
  "tokens_out": 80
}
```

Required response fields:

- `model`: model name used by the backend
- `status`: logical inference status recorded into inference logs
- `latency_ms`: backend inference latency in milliseconds
- `tokens_in`: input token count
- `tokens_out`: output token count

`ai-metrics-api` uses these fields to write structured inference logs and calculate metrics.

## Error Behavior

The backend may return non-2xx HTTP responses when the backend itself fails.

`ai-metrics-api` currently handles these backend failure cases:

- request timeout -> API returns `504`
- backend unavailable -> API returns `502`
- backend HTTP status >= 400 -> API returns `502`
- backend returns invalid JSON -> API returns `502`

The backend may also return a JSON response with a logical `status` field such as `400`, `429`, or `500`. This is recorded into the inference log and reflected in metrics.

## Mock Backend

Default local backend:

```text
MODEL_BACKEND=mock
MODEL_SERVER_URL=http://mock-model-server:8001/generate
```

The mock backend is used for reproducible local testing, failure injection, Prometheus metrics, Grafana validation, and automated tests.

## Remote GPU Backend

Future remote GPU backend:

```text
MODEL_BACKEND=remote_http
MODEL_SERVER_URL=http://<gpu-server-host>:<port>/generate
```

The remote GPU backend should implement the same `/health` and `/generate` endpoints.

The first GPU version does not need to be complex. It only needs to:

1. load a small model or wrap an existing model runtime
2. accept the required JSON request
3. run or simulate generation
4. measure latency
5. return the required response fields

## Design Rule

`ai-metrics-api` should not depend on model-specific implementation details.

The observability system should only depend on this protocol:

```text
HTTP request -> model backend -> standardized response -> inference log -> metrics -> alerts -> incidents
```