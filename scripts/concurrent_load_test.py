import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


MODELS = ["qwen2.5-7b", "qwen2.5-14b", "bge-reranker"]


def percentile(values, percent):
    if not values:
        return 0

    sorted_values = sorted(values)
    index = round((percent / 100) * (len(sorted_values) - 1))
    return sorted_values[index]


def build_payload(args):
    model = args.model or random.choice(MODELS)

    payload = {
        "model": model,
        "tokens_in": args.tokens_in,
        "tokens_out": args.tokens_out,
    }

    if random.random() < args.error_rate:
        payload["force_status"] = random.choice([429, 500])

    return payload


def send_request(base_url, endpoint, payload, timeout):
    url = f"{base_url.rstrip('/')}{endpoint}"
    start_time = time.perf_counter()

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        try:
            body = response.json()
        except ValueError:
            body = {}

        return {
            "http_status": response.status_code,
            "logical_status": body.get("status"),
            "model": body.get("model", payload.get("model")),
            "client_latency_ms": max(elapsed_ms, 1),
            "error": body.get("detail"),
        }
    except httpx.RequestError as exc:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "http_status": None,
            "logical_status": None,
            "model": payload.get("model"),
            "client_latency_ms": max(elapsed_ms, 1),
            "error": str(exc),
        }


def summarize_results(results):
    client_latencies = [result["client_latency_ms"] for result in results]

    http_success_count = sum(
        1 for result in results
        if result["http_status"] is not None and 200 <= result["http_status"] < 300
    )
    http_error_count = len(results) - http_success_count

    logical_success_count = sum(
        1 for result in results
        if result["logical_status"] == 200
    )
    logical_error_count = sum(
        1 for result in results
        if result["logical_status"] is not None and result["logical_status"] >= 400
    )

    rejected_count_429 = sum(
        1 for result in results
        if result["http_status"] == 429 or result["logical_status"] == 429
    )

    http_status_counts = {}
    logical_status_counts = {}

    for result in results:
        http_status = str(result["http_status"])
        logical_status = str(result["logical_status"])

        http_status_counts[http_status] = http_status_counts.get(http_status, 0) + 1
        logical_status_counts[logical_status] = (
            logical_status_counts.get(logical_status, 0) + 1
        )

    return {
        "total_requests": len(results),
        "http_success_count": http_success_count,
        "http_error_count": http_error_count,
        "logical_success_count": logical_success_count,
        "logical_error_count": logical_error_count,
        "rejected_count_429": rejected_count_429,
        "avg_client_latency_ms": round(sum(client_latencies) / len(client_latencies), 2)
        if client_latencies else 0,
        "p95_client_latency_ms": percentile(client_latencies, 95),
        "max_client_latency_ms": max(client_latencies) if client_latencies else 0,
        "http_status_counts": http_status_counts,
        "logical_status_counts": logical_status_counts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--endpoint", default="/v1/infer")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--model", default="qwen2.5-7b")
    parser.add_argument("--tokens-in", type=int, default=100)
    parser.add_argument("--tokens-out", type=int, default=20)
    parser.add_argument("--error-rate", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    results = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = []

        for _ in range(args.count):
            payload = build_payload(args)
            futures.append(
                executor.submit(
                    send_request,
                    args.base_url,
                    args.endpoint,
                    payload,
                    args.timeout,
                )
            )

            if args.sleep > 0:
                time.sleep(args.sleep)

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if not args.quiet:
                print(
                    "http_status={http_status} "
                    "logical_status={logical_status} "
                    "model={model} "
                    "client_latency_ms={client_latency_ms} "
                    "error={error}".format(**result)
                )

    summary = summarize_results(results)

    print()
    print("Concurrent load test summary")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()