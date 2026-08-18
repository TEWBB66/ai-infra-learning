# Alerting Runbook

This project exports Prometheus metrics for inference serving, backend behavior, latency histograms, and admission control.

## Alert Rules

Prometheus loads alert rules from `monitoring/prometheus-rules.yml`.

| Alert | Severity | Signal | First check |
| --- | --- | --- | --- |
| `AIInferenceHighP95Latency` | warning | p95 latency is above 800 ms | Check `/metrics/logs`, recent slow requests, backend health, and prompt/output token sizes. |
| `AIInferenceHighErrorRate` | warning | non-2xx inference status share is above 5 percent | Check status counts, backend errors, and model server availability. |
| `AIInferenceInFlightSaturation` | warning | in-flight gate is saturated | Check concurrency, `MAX_IN_FLIGHT_REQUESTS`, and backend latency. |
| `AIInferenceQueueBacklog` | warning | queued requests are waiting | Check whether queue mode is absorbing burst traffic or hiding sustained overload. |
| `AIInferenceQueueTimeouts` | critical | queued requests timed out | Reduce load, increase backend capacity, or lower queue wait expectations. |
| `AIInferenceQueueRejections` | warning | queue was full and rejected requests | Increase queue capacity only if latency SLO still holds; otherwise shed load earlier. |

## Validation Commands

```bash
docker compose up --build -d
docker compose exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
docker compose exec -T prometheus promtool check rules /etc/prometheus/prometheus-rules.yml
curl -s http://127.0.0.1:9090/api/v1/rules | python -m json.tool
```

## Incident Notes

- `reject` admission mode protects the backend by returning HTTP 429 quickly when in-flight capacity is full.
- `queue` admission mode absorbs short bursts, but queue depth and timeout alerts are required so overload is not hidden.
- The latency histogram is generated from structured inference logs and gives Prometheus a direct p95/p99 signal.
- Real vLLM benchmark evidence is stored under `reports/vllm_benchmark_2026_08_18/`.
