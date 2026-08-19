"""Prometheus histogram helpers for inference latency metrics."""

from __future__ import annotations

import json
import re
from pathlib import Path


LATENCY_HISTOGRAM_BUCKETS_MS = (100, 250, 500, 1000, 2500, 5000)
_LATENCY_MS_RE = re.compile(r"(?:^|\s)latency_ms=(?P<value>[0-9]+(?:\.[0-9]+)?)")


def extract_latency_ms_values(log_path: str | Path) -> list[float]:
    path = Path(log_path)
    if not path.exists():
        return []

    values: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        value = None
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = {}
            value = parsed.get("latency_ms")

        if value is None:
            match = _LATENCY_MS_RE.search(stripped)
            if match:
                value = match.group("value")

        try:
            if value is not None:
                values.append(float(value))
        except (TypeError, ValueError):
            continue

    return values


def build_latency_histogram_prometheus_from_values(latencies: list[float]) -> list[str]:
    total = len(latencies)
    latency_sum = round(sum(latencies), 3)

    lines = [
        "# HELP ai_inference_latency_ms Request latency histogram in milliseconds",
        "# TYPE ai_inference_latency_ms histogram",
    ]

    for bucket in LATENCY_HISTOGRAM_BUCKETS_MS:
        count = sum(1 for latency in latencies if latency <= bucket)
        lines.append(f'ai_inference_latency_ms_bucket{{le="{bucket}"}} {count}')

    lines.append(f'ai_inference_latency_ms_bucket{{le="+Inf"}} {total}')
    lines.append(f"ai_inference_latency_ms_count {total}")
    lines.append(f"ai_inference_latency_ms_sum {latency_sum}")
    return lines

def build_latency_histogram_prometheus_from_records(records: list[dict]) -> list[str]:
    latencies = []
    for record in records:
        try:
            latencies.append(float(record["latency_ms"]))
        except (KeyError, TypeError, ValueError):
            continue
    return build_latency_histogram_prometheus_from_values(latencies)


def build_latency_histogram_prometheus(log_path: str | Path) -> list[str]:
    return build_latency_histogram_prometheus_from_values(
        extract_latency_ms_values(log_path)
    )
