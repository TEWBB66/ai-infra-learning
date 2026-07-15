# Log Analyzer

This project analyzes simulated AI inference service logs.

It can report:

- total requests
- successful requests
- failed requests
- average latency
- P95 and P99 latency
- average latency of successful requests
- slow request count
- top 3 slowest requests
- per-model request count, error count, average latency, and P95 latency

Run:

```bash
python projects/log_analyzer/analyze_logs.py
