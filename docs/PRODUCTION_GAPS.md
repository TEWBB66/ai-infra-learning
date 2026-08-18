# Production Gaps

This project is a learning-oriented AI inference observability and reliability platform. It demonstrates the core workflow around inference requests, backend routing, structured logs, metrics, Prometheus, Grafana, GPU backend validation, and failure observability.

It is not yet a production-scale serving platform. This document records the main gaps between the current project and a production deployment.

## Authentication and Authorization

Current state:

- API endpoints are open inside the local development environment.
- There is no user authentication.
- There is no service-to-service authentication between ai-metrics-api and model backends.

Production expectation:

- Add API authentication for external clients.
- Add service credentials or mTLS between internal services.
- Separate user roles for read-only metrics access and inference request submission.

## Rate Limiting and Abuse Protection

Current state:

- Requests are accepted without per-user or per-client limits.
- There is no protection against accidental request bursts.

Production expectation:

- Add rate limits per API key, user, or client service.
- Add request size limits for tokens_in and tokens_out.
- Return structured 429 errors when limits are exceeded.

## Request Queue and Backpressure

Current state:

- Requests are handled synchronously.
- The API includes a single-instance in-memory in-flight gate.
- Overload can be rejected with HTTP 429 when `MAX_IN_FLIGHT_REQUESTS` is reached.
- The in-flight gate was validated against both the mock backend and a real vLLM backend.
- There is no durable request queue, retry policy, or distributed global rate limit.

Production expectation:

- Introduce a request queue for GPU-bound workloads when queueing is preferable to fast rejection.
- Track queue latency separately from model generation latency.
- Coordinate limits across multiple API replicas.
- Add per-client, per-model, or priority-aware admission control.
- Use autoscaling and scheduler signals from GPU utilization, queue depth, and vLLM metrics.

## Persistent Log Storage

Current state:

- Inference logs are written to a local file.
- The log file is useful for learning and local experiments.
- It is not suitable for distributed production workloads.

Production expectation:

- Write logs to durable storage such as object storage, a database, or a log platform.
- Include retention policies.
- Support querying logs by request_id, model, status, and time range.
- Separate runtime logs from version-controlled sample logs.

## Metrics Storage and Retention

Current state:

- Metrics are calculated from local inference logs.
- Prometheus scrapes current metrics from the API.

Production expectation:

- Use Prometheus or a managed metrics backend with retention.
- Define recording rules for high-value metrics.
- Preserve historical metrics for SLO and incident review.
- Control label cardinality, especially model names and request dimensions.

## Distributed Tracing

Current state:

- Requests have request_id values in inference logs.
- There is no distributed trace across client, ai-metrics-api, and model backend.

Production expectation:

- Add OpenTelemetry tracing.
- Propagate trace_id and request_id across services.
- Measure time spent in API handling, queueing, backend calls, and model generation.

## Error Taxonomy

Current state:

- The project has structured errors for backend unavailable, timeout, invalid JSON, unsupported backend mode, missing transformers dependencies, model loading failure, and generation failure.

Production expectation:

- Define a formal error taxonomy.
- Separate client errors, backend errors, infrastructure errors, and model runtime errors.
- Make error codes stable for dashboards, alerts, and incident automation.

## GPU Scheduling and Isolation

Current state:

- GPU experiments use CUDA_VISIBLE_DEVICES=0.
- Experiments are short-lived and manually stopped.
- The project does not schedule GPU workloads.

Production expectation:

- Use a scheduler such as Kubernetes with GPU support, Slurm, or another workload manager.
- Isolate workloads by GPU, memory, priority, and user.
- Enforce safe defaults for shared GPU environments.
- Track GPU utilization, memory usage, and model-level capacity.

## Autoscaling

Current state:

- Services run as fixed local processes or Docker Compose containers.
- There is no autoscaling.

Production expectation:

- Scale API workers based on request volume.
- Scale model backend replicas based on queue depth, latency, and GPU utilization.
- Keep warm replicas for latency-sensitive models.
- Use readiness checks before routing traffic to new replicas.

## SLOs and Alert Policy

Current state:

- The project calculates error rate, p95 latency, slow request count, alerts, and incidents.
- Thresholds are static and learning-oriented.

Production expectation:

- Define service-level objectives such as availability and p95 latency.
- Separate warning and critical thresholds by model.
- Add alert routing and on-call ownership.
- Track alert quality to reduce noisy alerts.

## Deployment

Current state:

- Local development uses Docker Compose.
- GPU experiments run manually on a remote lab GPU server.
- Real vLLM serving was validated on a single RTX A5000 GPU, but not deployed as a managed production service.

Production expectation:

- Define deployment manifests.
- Use environment-specific configuration.
- Add readiness and liveness probes.
- Add CI checks before deployment.
- Separate development, staging, and production environments.

## Security

Current state:

- No secrets are required for the default mock backend.
- GPU experiments may access Hugging Face model downloads through local user cache.

Production expectation:

- Manage secrets through a secret manager.
- Avoid committing credentials or runtime logs.
- Restrict network access between services.
- Scan dependencies and container images.

## Cost and Capacity Management

Current state:

- GPU experiments are small and manually controlled.
- There is no cost accounting.

Production expectation:

- Track GPU usage per model, project, and user.
- Add quotas or budgets.
- Prefer smaller models for low-latency or low-cost workloads when acceptable.
- Measure cost per successful request.

## Summary

The current project intentionally focuses on the core observability and reliability workflow:

    inference request -> model backend -> structured log -> metrics -> alerts -> incident signals

The next production step would not be "add a bigger model". It would be to improve operational controls: authentication, rate limiting, queueing, durable storage, tracing, deployment, and GPU scheduling.