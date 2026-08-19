# vLLM Soak Benchmark - 2026-08-19

This report records a sustained real-backend smoke and soak run through `ai-metrics-api` in front of vLLM.

## Environment

| Item | Value |
| --- | --- |
| Host | A5000 |
| GPU | NVIDIA RTX A5000 |
| GPU used | GPU 0 only |
| Model backend | vLLM OpenAI-compatible API |
| Served model | Qwen/Qwen2.5-0.5B-Instruct |
| vLLM version | 0.11.0 |
| API backend | `MODEL_BACKEND=vllm` |
| API admission mode | queue |
| API max in-flight requests | 32 |
| Queue size / timeout | 64 / 5000 ms |
| vLLM max model length | 1024 |
| vLLM GPU memory utilization | 0.50 |
| vLLM max sequences | 16 |

## Workload

| Item | Value |
| --- | ---: |
| Benchmark requests | 600 |
| Repeats | 6 |
| Requests per repeat | 100 |
| Warmup requests per repeat | 5 |
| Client concurrency | 8 |
| Max output tokens | 128 |
| Input token setting | 256 |
| Prompt profile | medium |
| Temperature | 0.0 |

## Result Summary

| Metric | Value |
| --- | ---: |
| Benchmark HTTP 200 responses | 600 / 600 |
| Benchmark logical 200 responses | 600 / 600 |
| Benchmark HTTP 429 responses | 0 |
| API total requests after smoke, warmup, and benchmark | 631 |
| API success requests | 631 |
| API failed requests | 0 |
| API error rate | 0.0 |
| API p95 latency ms | 942 |
| API p99 latency ms | 1033 |
| Repeat p95 latency range ms | 912.297 - 1066.813 |
| Repeat p99 latency range ms | 925.621 - 1101.973 |
| Repeat throughput range req/s | 9.553 - 10.731 |
| Repeat output throughput range tok/s | 1098.179 - 1236.350 |

## Repeat-Level Results

| repeat | concurrency | max_tokens | requests | HTTP counts | logical counts | 429 | avg ms | p95 ms | p99 ms | req/s | out tok/s |
| ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 8 | 128 | 100 | `{"200": 100}` | `{"200": 100}` | 0 | 760.289 | 912.297 | 925.621 | 10.299 | 1176.02 |
| 2 | 8 | 128 | 100 | `{"200": 100}` | `{"200": 100}` | 0 | 817.911 | 966.535 | 998.766 | 9.553 | 1098.179 |
| 3 | 8 | 128 | 100 | `{"200": 100}` | `{"200": 100}` | 0 | 720.074 | 984.129 | 993.79 | 10.731 | 1236.35 |
| 4 | 8 | 128 | 100 | `{"200": 100}` | `{"200": 100}` | 0 | 776.761 | 1032.16 | 1101.973 | 10.117 | 1154.84 |
| 5 | 8 | 128 | 100 | `{"200": 100}` | `{"200": 100}` | 0 | 749.023 | 981.558 | 1074.604 | 10.343 | 1186.137 |
| 6 | 8 | 128 | 100 | `{"200": 100}` | `{"200": 100}` | 0 | 765.515 | 1066.813 | 1075.939 | 10.251 | 1170.308 |

## Evidence Files

- `metadata.json`
- `summary.csv`
- `raw_results.jsonl`
- `api_metrics.json`
- `api_prometheus.txt`
- `vllm_metrics.txt`
- `nvidia_smi_after.txt`

## Boundary

This is a single-node, single-GPU soak benchmark. It validates sustained traffic through the API and vLLM backend on one NVIDIA RTX A5000. It does not validate distributed serving, multi-GPU scheduling, autoscaling, external storage, or a production Kubernetes deployment.
