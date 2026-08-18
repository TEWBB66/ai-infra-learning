"""Run a serving benchmark matrix against /v1/infer.

This script is intentionally independent from concurrent_load_test.py so it can
produce benchmark-grade artifacts: raw JSONL, summary CSV, Markdown report, and
run metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMPTS = {
    "short": "Say hello in one short sentence.",
    "medium": (
        "Explain why observability matters for an LLM serving system in "
        "three concise bullet points."
    ),
    "long": (
        "You are evaluating an LLM serving reliability system. Explain how "
        "request logging, latency metrics, backpressure, and backend health "
        "checks work together during overload."
    ),
}


def parse_int_list(value: str) -> list[int]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("value must contain at least one integer")
    parsed: list[int] = []
    for item in items:
        try:
            number = int(item)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid integer: {item}") from exc
        if number <= 0:
            raise argparse.ArgumentTypeError("all values must be positive")
        parsed.append(number)
    return parsed


def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def build_cases(concurrency_values: list[int], max_tokens_values: list[int], repeats: int) -> list[dict[str, int]]:
    cases: list[dict[str, int]] = []
    for repeat in range(1, repeats + 1):
        for max_tokens in max_tokens_values:
            for concurrency in concurrency_values:
                cases.append(
                    {
                        "repeat": repeat,
                        "concurrency": concurrency,
                        "max_tokens": max_tokens,
                    }
                )
    return cases


def make_payload(args: argparse.Namespace, max_tokens: int) -> dict[str, Any]:
    return {
        "model": args.model,
        "tokens_in": args.tokens_in,
        "tokens_out": max_tokens,
        "prompt": PROMPTS[args.prompt_profile],
        "max_tokens": max_tokens,
        "temperature": args.temperature,
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((len(ordered) - 1) * q)
    return round(ordered[index], 3)


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any], float]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            latency_ms = (time.perf_counter() - started) * 1000
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw_body": raw}
            return response.status, parsed, latency_ms
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        latency_ms = (time.perf_counter() - started) * 1000
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw_body": raw}
        return exc.code, parsed, latency_ms
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return 0, {"error": repr(exc)}, latency_ms


def run_one_request(args: argparse.Namespace, case: dict[str, int], request_index: int) -> dict[str, Any]:
    payload = make_payload(args, case["max_tokens"])
    http_status, response_body, latency_ms = post_json(args.url, payload, args.timeout)

    logical_status = response_body.get("status", http_status)
    tokens_out = response_body.get("tokens_out", 0)
    request_id = response_body.get("request_id")

    return {
        "repeat": case["repeat"],
        "concurrency": case["concurrency"],
        "max_tokens": case["max_tokens"],
        "request_index": request_index,
        "http_status": http_status,
        "logical_status": logical_status,
        "client_latency_ms": round(latency_ms, 3),
        "tokens_out": tokens_out if isinstance(tokens_out, int) else 0,
        "request_id": request_id,
        "response": response_body,
    }


def summarize_results(case: dict[str, int], results: list[dict[str, Any]], elapsed_sec: float) -> dict[str, Any]:
    latencies = [float(item["client_latency_ms"]) for item in results]
    output_tokens = [int(item.get("tokens_out", 0)) for item in results]
    http_counts = Counter(str(item["http_status"]) for item in results)
    logical_counts = Counter(str(item["logical_status"]) for item in results)

    total_requests = len(results)
    total_output_tokens = sum(output_tokens)

    return {
        "repeat": case["repeat"],
        "concurrency": case["concurrency"],
        "max_tokens": case["max_tokens"],
        "total_requests": total_requests,
        "http_status_counts": dict(sorted(http_counts.items())),
        "logical_status_counts": dict(sorted(logical_counts.items())),
        "rejected_count_429": http_counts.get("429", 0),
        "avg_client_latency_ms": round(statistics.mean(latencies), 3) if latencies else 0.0,
        "p95_client_latency_ms": percentile(latencies, 0.95),
        "p99_client_latency_ms": percentile(latencies, 0.99),
        "throughput_req_per_sec": round(total_requests / elapsed_sec, 3) if elapsed_sec > 0 else 0.0,
        "output_tokens_per_sec": round(total_output_tokens / elapsed_sec, 3) if elapsed_sec > 0 else 0.0,
        "total_output_tokens": total_output_tokens,
        "elapsed_sec": round(elapsed_sec, 3),
    }


def run_case(args: argparse.Namespace, case: dict[str, int], raw_file: Path) -> dict[str, Any]:
    if args.warmup > 0 and not args.quiet:
        print(
            f"warmup repeat={case['repeat']} concurrency={case['concurrency']} "
            f"max_tokens={case['max_tokens']} count={args.warmup}"
        )

    for index in range(args.warmup):
        run_one_request(args, case, -(index + 1))

    if not args.quiet:
        print(
            f"run repeat={case['repeat']} concurrency={case['concurrency']} "
            f"max_tokens={case['max_tokens']} count={args.count}"
        )

    started = time.perf_counter()
    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=case["concurrency"]) as executor:
        futures = [
            executor.submit(run_one_request, args, case, index)
            for index in range(args.count)
        ]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            raw_file.write_text(
                raw_file.read_text() + json.dumps(result, sort_keys=True) + "\n"
                if raw_file.exists()
                else json.dumps(result, sort_keys=True) + "\n"
            )

    elapsed_sec = time.perf_counter() - started
    results.sort(key=lambda item: item["request_index"])
    return summarize_results(case, results, elapsed_sec)


def metadata(args: argparse.Namespace, cases: list[dict[str, int]]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "host": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "url": args.url,
        "model": args.model,
        "tokens_in": args.tokens_in,
        "prompt_profile": args.prompt_profile,
        "temperature": args.temperature,
        "count": args.count,
        "warmup": args.warmup,
        "repeats": args.repeats,
        "concurrency_values": args.concurrency_matrix,
        "max_tokens_values": args.max_tokens_matrix,
        "dry_run": args.dry_run,
        "case_count": len(cases),
    }


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "repeat",
        "concurrency",
        "max_tokens",
        "total_requests",
        "http_status_counts",
        "logical_status_counts",
        "rejected_count_429",
        "avg_client_latency_ms",
        "p95_client_latency_ms",
        "p99_client_latency_ms",
        "throughput_req_per_sec",
        "output_tokens_per_sec",
        "total_output_tokens",
        "elapsed_sec",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            encoded["http_status_counts"] = json.dumps(row["http_status_counts"], sort_keys=True)
            encoded["logical_status_counts"] = json.dumps(row["logical_status_counts"], sort_keys=True)
            writer.writerow(encoded)


def write_markdown(path: Path, meta: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Serving Benchmark Matrix Report",
        "",
        "## Metadata",
        "",
        "```json",
        json.dumps(meta, indent=2, sort_keys=True),
        "```",
        "",
        "## Summary",
        "",
        "| repeat | concurrency | max_tokens | requests | HTTP counts | logical counts | 429 | avg ms | p95 ms | p99 ms | req/s | out tok/s |",
        "| ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in rows:
        lines.append(
            "| {repeat} | {concurrency} | {max_tokens} | {total_requests} | `{http}` | `{logical}` | "
            "{rejected_count_429} | {avg_client_latency_ms} | {p95_client_latency_ms} | "
            "{p99_client_latency_ms} | {throughput_req_per_sec} | {output_tokens_per_sec} |".format(
                repeat=row["repeat"],
                concurrency=row["concurrency"],
                max_tokens=row["max_tokens"],
                total_requests=row["total_requests"],
                http=json.dumps(row["http_status_counts"], sort_keys=True),
                logical=json.dumps(row["logical_status_counts"], sort_keys=True),
                rejected_count_429=row["rejected_count_429"],
                avg_client_latency_ms=row["avg_client_latency_ms"],
                p95_client_latency_ms=row["p95_client_latency_ms"],
                p99_client_latency_ms=row["p99_client_latency_ms"],
                throughput_req_per_sec=row["throughput_req_per_sec"],
                output_tokens_per_sec=row["output_tokens_per_sec"],
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report is generated by `scripts/serving_benchmark_matrix.py`.",
            "- Use mock backend for dry validation and vLLM backend for real GPU evidence.",
            "- Interpret results with the configured backend, model, warmup, repeat count, and GPU state.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {value}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a serving benchmark matrix against /v1/infer.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/infer")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--tokens-in", type=positive_int, default=32)
    parser.add_argument("--prompt-profile", choices=sorted(PROMPTS), default="short")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--count", type=positive_int, default=50)
    parser.add_argument("--warmup", type=positive_int, default=0)
    parser.add_argument("--repeats", type=positive_int, default=1)
    parser.add_argument("--concurrency-matrix", type=parse_int_list, default=parse_int_list("1,2,4,8,16"))
    parser.add_argument("--max-tokens-matrix", type=parse_int_list, default=parse_int_list("32,128,512"))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    return Path("reports") / f"serving_benchmark_matrix_{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.repeats <= 0:
        parser.error("--repeats must be positive")
    if args.count <= 0 and not args.dry_run:
        parser.error("--count must be positive unless --dry-run is used")

    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = build_cases(args.concurrency_matrix, args.max_tokens_matrix, args.repeats)
    meta = metadata(args, cases)

    metadata_path = output_dir / "metadata.json"
    raw_path = output_dir / "raw_results.jsonl"
    csv_path = output_dir / "summary.csv"
    markdown_path = output_dir / "README.md"

    metadata_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw_path.write_text("", encoding="utf-8")

    if args.dry_run:
        dry_rows = [
            {
                "repeat": case["repeat"],
                "concurrency": case["concurrency"],
                "max_tokens": case["max_tokens"],
                "total_requests": 0,
                "http_status_counts": {},
                "logical_status_counts": {},
                "rejected_count_429": 0,
                "avg_client_latency_ms": 0.0,
                "p95_client_latency_ms": 0.0,
                "p99_client_latency_ms": 0.0,
                "throughput_req_per_sec": 0.0,
                "output_tokens_per_sec": 0.0,
                "total_output_tokens": 0,
                "elapsed_sec": 0.0,
            }
            for case in cases
        ]
        (output_dir / "dry_run_cases.json").write_text(
            json.dumps(cases, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_summary_csv(csv_path, dry_rows)
        write_markdown(markdown_path, meta, dry_rows)
        if not args.quiet:
            print(f"dry-run cases: {len(cases)}")
            print(f"output_dir: {output_dir}")
        return 0

    rows: list[dict[str, Any]] = []
    for case in cases:
        row = run_case(args, case, raw_path)
        rows.append(row)

    write_summary_csv(csv_path, rows)
    write_markdown(markdown_path, meta, rows)

    if not args.quiet:
        print(f"cases: {len(cases)}")
        print(f"output_dir: {output_dir}")
        print(f"summary_csv: {csv_path}")
        print(f"summary_md: {markdown_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
