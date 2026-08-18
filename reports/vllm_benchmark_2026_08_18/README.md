# vLLM GPU Serving Benchmark - 2026-08-18

Environment:
- Host: A5000 lab GPU server
- GPU used: NVIDIA RTX A5000, GPU 0 only
- Model: Qwen/Qwen2.5-0.5B-Instruct
- vLLM: 0.11.0
- API backend: MODEL_BACKEND=vllm
- vLLM config: max_model_len=1024, gpu_memory_utilization=0.50, max_num_seqs=16
- Requests per case: 50

| concurrency | max_tokens | requests | HTTP counts | logical counts | 429 | avg ms | p95 ms | p99 ms | req/s | out tok/s |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 32 | 50 | {'200': 50} | {'200': 50} | 0 | 267.57 | 220.37 | 3283.64 | 3.736 | 119.561 |
| 2 | 32 | 50 | {'200': 50} | {'200': 50} | 0 | 261.93 | 275.64 | 280.32 | 7.629 | 244.139 |
| 4 | 32 | 50 | {'200': 50} | {'200': 50} | 0 | 302.7 | 439.58 | 442.42 | 13.121 | 419.879 |
| 8 | 32 | 50 | {'200': 50} | {'200': 50} | 0 | 568.91 | 733.81 | 742.75 | 13.489 | 431.642 |
| 16 | 32 | 50 | {'200': 50} | {'200': 50} | 0 | 653.13 | 904.39 | 922.03 | 22.408 | 717.07 |
| 1 | 128 | 50 | {'200': 50} | {'200': 50} | 0 | 546.58 | 559.21 | 569.75 | 1.829 | 234.148 |
| 2 | 128 | 50 | {'200': 50} | {'200': 50} | 0 | 651.14 | 667.69 | 679.54 | 3.071 | 393.037 |
| 4 | 128 | 50 | {'200': 50} | {'200': 50} | 0 | 673.24 | 854.43 | 860.25 | 5.842 | 747.713 |
| 8 | 128 | 50 | {'200': 50} | {'200': 50} | 0 | 868.28 | 1171.45 | 1177.59 | 8.887 | 1137.531 |
| 16 | 128 | 50 | {'200': 50} | {'200': 50} | 0 | 1069.77 | 1451.79 | 1454.5 | 13.461 | 1723.014 |
| 1 | 512 | 50 | {'200': 50} | {'200': 50} | 0 | 1950.17 | 2006.31 | 2009.66 | 0.513 | 257.215 |
| 2 | 512 | 50 | {'200': 50} | {'200': 50} | 0 | 2300.97 | 2440.11 | 2501.52 | 0.868 | 437.786 |
| 4 | 512 | 50 | {'200': 50} | {'200': 50} | 0 | 2332.11 | 2540.93 | 2547.04 | 1.656 | 829.946 |
| 8 | 512 | 50 | {'200': 50} | {'200': 50} | 0 | 2575.98 | 3002.78 | 3009.22 | 2.85 | 1431.601 |
| 16 | 512 | 50 | {'200': 50} | {'200': 50} | 0 | 3125.19 | 3733.14 | 3737.2 | 4.406 | 2228.539 |

Aggregate API metrics after the matrix:
- total_requests: 750
- success_requests: 750
- failed_requests: 0
- error_rate: 0.0
- ai_inference_current_in_flight_requests returned to 0

vLLM metrics snapshot after the matrix:
- vllm:num_requests_running = 0
- vllm:num_requests_waiting = 0
- vllm:prompt_tokens_total = 48600
- vllm:generation_tokens_total = 165754

GPU snapshot after the matrix:
- GPU 0 memory: about 12485 MiB / 24564 MiB
- GPU 1/2/3 were not used by vLLM

Notes:
- This is a single-node, single-GPU benchmark.
- Backpressure was disabled for benchmark throughput by setting MAX_IN_FLIGHT_REQUESTS=32.
- Separate real-backend backpressure smoke test used MAX_IN_FLIGHT_REQUESTS=2 and produced 28 HTTP 429 responses out of 30 requests.

