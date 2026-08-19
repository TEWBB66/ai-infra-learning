import argparse
import json
import sys
import urllib.error
import urllib.request


def build_url(base_url, path):
    return base_url.rstrip("/") + path


def request_json(base_url, method, path, payload=None, headers=None, timeout=5.0):
    body = None
    request_headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        build_url(base_url, path),
        data=body,
        headers=request_headers,
        method=method,
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_body = response.read().decode("utf-8")
        return response.status, json.loads(response_body)


def request_text(base_url, path, timeout=5.0):
    request = urllib.request.Request(
        build_url(base_url, path),
        headers={"Accept": "text/plain"},
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def print_ok(message):
    print(f"OK {message}")


def run_smoke_test(args):
    headers = {"X-Client-ID": args.client_id, "X-Trace-ID": args.trace_id}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    status, health = request_json(args.base_url, "GET", "/health", timeout=args.timeout)
    require(status == 200, "/health did not return HTTP 200")
    require(health.get("status") == "ok", "/health response did not report ok")
    print_ok("/health")

    status, ready = request_json(args.base_url, "GET", "/ready", timeout=args.timeout)
    require(status == 200, "/ready did not return HTTP 200")
    require(ready.get("status") == "ready", "/ready response did not report ready")
    require("backend" in ready, "/ready response did not include backend")
    print_ok(f"/ready backend={ready['backend']}")

    payload = {
        "model": args.model,
        "tokens_in": args.tokens_in,
        "tokens_out": args.tokens_out,
    }
    if args.force_status is not None:
        payload["force_status"] = args.force_status
    status, inference = request_json(
        args.base_url,
        "POST",
        "/v1/infer",
        payload=payload,
        headers=headers,
        timeout=args.timeout,
    )
    require(status == 200, "/v1/infer did not return HTTP 200")
    require(inference.get("status") == 200, "/v1/infer payload did not report status 200")
    require(inference.get("model"), "/v1/infer response did not include model")
    require(inference.get("request_id"), "/v1/infer response did not include request_id")
    print_ok(f"/v1/infer request_id={inference['request_id']}")

    status, logs = request_json(args.base_url, "GET", "/metrics/logs", timeout=args.timeout)
    require(status == 200, "/metrics/logs did not return HTTP 200")
    for key in ["total_requests", "error_rate", "p95_latency_ms", "metrics_by_model"]:
        require(key in logs, f"/metrics/logs missing {key}")
    require(logs["total_requests"] >= 1, "/metrics/logs did not include the smoke request")
    print_ok("/metrics/logs")

    status, prometheus = request_text(args.base_url, "/metrics/prometheus", timeout=args.timeout)
    require(status == 200, "/metrics/prometheus did not return HTTP 200")
    for metric in [
        "ai_inference_total_requests",
        "ai_inference_status_requests",
        "ai_inference_current_in_flight_requests",
        "ai_inference_queue_depth",
        "ai_inference_rate_limit_enabled",
    ]:
        require(metric in prometheus, f"/metrics/prometheus missing {metric}")
    print_ok("/metrics/prometheus")

    print("Local smoke test passed")


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Run a local smoke test against ai-metrics-api.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--client-id", default="local-smoke-test")
    parser.add_argument("--trace-id", default="local-smoke-test-trace")
    parser.add_argument("--model", default="qwen2.5-7b")
    parser.add_argument("--tokens-in", type=int, default=32)
    parser.add_argument("--tokens-out", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--force-status", type=int, default=200)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run_smoke_test(args)
    except urllib.error.HTTPError as exc:
        print(f"Smoke test failed: HTTP {exc.code} from {exc.url}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
