import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean
from urllib import error, request


PROMPT_PROFILES = {
    "short": "Say hello in one concise sentence.",
    "medium": (
        "Explain why API-side backpressure is useful in an LLM serving system. "
        "Keep the answer practical and focus on latency, overload, and reliability."
    ),
    "long": (
        "You are evaluating an LLM serving reliability layer in front of a vLLM backend. "
        "Discuss admission control, request latency, p95 and p99 tail behavior, throughput, "
        "output token rate, error handling, and operational limits for a single-GPU deployment."
    ),
}


def percentile(values, percentile_value):
    if not values:
        return 0.0

    sorted_values = sorted(values)
    index = int(round((percentile_value / 100) * (len(sorted_values) - 1)))
    return sorted_values[index]


def post_json(url, payload, timeout):
    encoded = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed_body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed_body = {"detail": body}
        return exc.code, parsed_body
    except error.URLError as exc:
        return 0, {"detail": str(exc.reason)}
    except TimeoutError:
        return 0, {"detail": "request timed out"}


def build_payload(args, request_index):
    prompt = PROMPT_PROFILES[args.prompt_profile]
    return {
        "model": args.model,
        "tokens_in": args.tokens_in,
        "tokens_out": args.max_tokens,
        "prompt": f"{prompt}\nRequest index: {request_index}",
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }


def send_one(args, request_index):
    start_time = time.perf_counter()
    http_status, body = post_json(
        url=args.url,
        payload=build_payload(args, request_index),
        timeout=args.timeout,
    )
    latency_ms = (time.perf_counter() - start_time) * 1000

    logical_status = body.get("status")
    if logical_status is None:
        logical_status = http_status

    tokens_out = body.get("tokens_out", 0)
    try:
        tokens_out = int(tokens_out or 0)
    except (TypeError, ValueError):
        tokens_out = 0

    return {
        "request_index": request_index,
        "http_status": int(http_status),
        "logical_status": int(logical_status) if str(logical_status).isdigit() else 0,
        "client_latency_ms": latency_ms,
        "tokens_out": tokens_out,
        "error_detail": body.get("detail"),
    }


def summarize(results, elapsed_seconds):
    latencies = [result["client_latency_ms"] for result in results]
    output_tokens = sum(result["tokens_out"] for result in results)
    http_status_counts = Counter(str(result["http_status"]) for result in results)
    logical_status_counts = Counter(str(result["logical_status"]) for result in results)

    return {
        "total_requests": len(results),
        "http_status_counts": dict(sorted(http_status_counts.items())),
        "logical_status_counts": dict(sorted(logical_status_counts.items())),
        "rejected_count_429": http_status_counts.get("429", 0),
        "avg_client_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
        "p95_client_latency_ms": round(percentile(latencies, 95), 2),
        "p99_client_latency_ms": round(percentile(latencies, 99), 2),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_req_per_sec": round(len(results) / elapsed_seconds, 3)
        if elapsed_seconds > 0
        else 0.0,
        "output_tokens_per_sec": round(output_tokens / elapsed_seconds, 3)
        if elapsed_seconds > 0
        else 0.0,
        "total_output_tokens": output_tokens,
    }


def print_summary(summary):
    print("Load test summary")
    print(f"  total_requests: {summary['total_requests']}")
    print(f"  http_status_counts: {summary['http_status_counts']}")
    print(f"  logical_status_counts: {summary['logical_status_counts']}")
    print(f"  rejected_count_429: {summary['rejected_count_429']}")
    print(f"  avg_client_latency_ms: {summary['avg_client_latency_ms']}")
    print(f"  p95_client_latency_ms: {summary['p95_client_latency_ms']}")
    print(f"  p99_client_latency_ms: {summary['p99_client_latency_ms']}")
    print(f"  throughput_req_per_sec: {summary['throughput_req_per_sec']}")
    print(f"  output_tokens_per_sec: {summary['output_tokens_per_sec']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run concurrent load against /v1/infer.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/infer")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--model", default="qwen2.5-7b")
    parser.add_argument("--tokens-in", type=int, default=256)
    parser.add_argument("--prompt-profile", choices=sorted(PROMPT_PROFILES), default="short")
    parser.add_argument("--max-tokens", type=int, default=80)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--json-output")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    if args.max_tokens < 1:
        raise SystemExit("--max-tokens must be >= 1")

    start_time = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(send_one, args, request_index)
            for request_index in range(args.count)
        ]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if not args.quiet:
                print(
                    f"request={result['request_index']} "
                    f"http_status={result['http_status']} "
                    f"logical_status={result['logical_status']} "
                    f"latency_ms={result['client_latency_ms']:.2f} "
                    f"tokens_out={result['tokens_out']}"
                )

    elapsed_seconds = time.perf_counter() - start_time
    summary = summarize(results, elapsed_seconds)

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "config": {
                        "url": args.url,
                        "count": args.count,
                        "concurrency": args.concurrency,
                        "timeout": args.timeout,
                        "model": args.model,
                        "tokens_in": args.tokens_in,
                        "prompt_profile": args.prompt_profile,
                        "max_tokens": args.max_tokens,
                        "temperature": args.temperature,
                    },
                    "summary": summary,
                    "results": sorted(results, key=lambda item: item["request_index"]),
                },
                indent=2,
            )
            + "\n"
        )

    print_summary(summary)


if __name__ == "__main__":
    main()
