import argparse
import json
import random
import time
from urllib import request


MODELS = ["qwen2.5-7b", "qwen2.5-14b", "bge-reranker"]


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def build_payload(error_rate):
    model = random.choice(MODELS)

    if model == "bge-reranker":
        tokens_in = random.randint(80, 300)
        tokens_out = 0
    elif model == "qwen2.5-7b":
        tokens_in = random.randint(200, 700)
        tokens_out = random.randint(50, 160)
    else:
        tokens_in = random.randint(500, 1200)
        tokens_out = random.randint(100, 260)

    payload = {
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }

    if random.random() < error_rate:
        payload["force_status"] = random.choice([429, 500])

    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--error-rate", type=float, default=0.1)
    parser.add_argument("--sleep", type=float, default=0.1)
    args = parser.parse_args()

    endpoint = f"{args.base_url}/v1/mock-infer"

    success_count = 0
    error_count = 0
    latencies = []

    for i in range(args.count):
        payload = build_payload(args.error_rate)
        result = post_json(endpoint, payload)

        status = result["status"]
        latency_ms = result["latency_ms"]
        latencies.append(latency_ms)

        if status >= 400:
            error_count += 1
        else:
            success_count += 1

        print(
            f"{i + 1}/{args.count} "
            f"model={result['model']} "
            f"status={status} "
            f"latency_ms={latency_ms}"
        )

        time.sleep(args.sleep)

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0

    print()
    print("Load test summary")
    print(f"total_requests={args.count}")
    print(f"success_count={success_count}")
    print(f"error_count={error_count}")
    print(f"avg_latency_ms={avg_latency}")
    print(f"max_latency_ms={max(latencies) if latencies else 0}")


if __name__ == "__main__":
    main()