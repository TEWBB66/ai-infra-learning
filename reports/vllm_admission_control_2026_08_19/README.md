# Real vLLM Admission Control Benchmark

This report compares two API-side admission modes in front of the same real vLLM backend.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-08-19 |
| GPU | NVIDIA RTX A5000 |
| GPU used | GPU 0 only |
| Model backend | vLLM OpenAI-compatible API |
| Served model | Qwen/Qwen2.5-0.5B-Instruct |
| vLLM port | 127.0.0.1:8001 |
| API port | 127.0.0.1:8000 |
| API max in-flight requests | 2 |
| Request count | 30 |
| Client concurrency | 10 |
| Prompt profile | medium |
| Max output tokens | 128 |

## Result Summary

| Mode | HTTP 200 | HTTP 429 | Rejected 429 | Avg latency ms | P95 latency ms | P99 latency ms | Req/s | Output tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| reject | 2 | 28 | 28 | 67.18 | 775.09 | 777.29 | 38.436 | 327.987 |
| queue | 30 | 0 | 0 | 3077.51 | 3634.25 | 3642.12 | 2.823 | 361.342 |

## Engineering Interpretation

The reject mode protects the backend by admitting only the configured number of in-flight requests and returning HTTP 429 quickly for excess requests.

The queue mode absorbs the same burst without HTTP 429 responses. This improves request acceptance but increases average and tail latency because requests wait behind the in-flight gate.

This benchmark demonstrates that the API admission layer works in front of a real vLLM backend, not only against the mock backend.

## Evidence Files

- `reject_result.json`
- `reject_api_metrics.json`
- `reject_prometheus.txt`
- `reject_vllm_summary.txt`
- `reject_nvidia_smi.txt`
- `queue_result.json`
- `queue_api_metrics.json`
- `queue_prometheus.txt`
- `queue_vllm_summary.txt`
- `queue_nvidia_smi.txt`
