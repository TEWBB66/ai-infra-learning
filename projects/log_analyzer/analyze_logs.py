import json


REQUIRED_LOG_FIELDS = {
    "request_id",
    "model",
    "status",
    "latency_ms",
    "tokens_in",
    "tokens_out",
}


def parse_log_line(line):
    parts = line.strip().split()
    record = {}

    for part in parts:
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        record[key] = value

    return record


def is_valid_record(record):
    if not REQUIRED_LOG_FIELDS.issubset(record):
        return False

    try:
        int(record["status"])
        int(record["latency_ms"])
    except ValueError:
        return False

    return True


def percentile(values, percent):
    if not values:
        return 0

    sorted_values = sorted(values)
    index = round((percent / 100) * (len(sorted_values) - 1))
    return sorted_values[index]


def empty_metrics():
    return {
        "total_requests": 0,
        "success_requests": 0,
        "failed_requests": 0,
        "success_rate": 0,
        "error_rate": 0,
        "avg_latency_ms": 0,
        "p95_latency_ms": 0,
        "p99_latency_ms": 0,
        "avg_success_latency_ms": 0,
        "slow_request_count": 0,
        "requests_by_status": {},
        "top_3_slowest_requests": [],
        "metrics_by_model": {},
    }


def analyze_records(records):
    total_requests = len(records)

    if total_requests == 0:
        return empty_metrics()

    success_records = [
        record for record in records
        if int(record["status"]) == 200
    ]
    failed_requests = total_requests - len(success_records)
    success_rate = len(success_records) / total_requests
    error_rate = failed_requests / total_requests

    latencies = [int(record["latency_ms"]) for record in records]
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = percentile(latencies, 95)
    p99_latency = percentile(latencies, 99)

    success_latencies = [int(record["latency_ms"]) for record in success_records]
    if success_latencies:
        avg_success_latency = sum(success_latencies) / len(success_latencies)
    else:
        avg_success_latency = 0

    slow_requests = sum(1 for latency in latencies if latency > 200)

    requests_by_status = {}
    metrics_by_model = {}

    for record in records:
        model = record["model"]
        latency = int(record["latency_ms"])
        status = int(record["status"])
        status_key = str(status)

        requests_by_status[status_key] = requests_by_status.get(status_key, 0) + 1

        if model not in metrics_by_model:
            metrics_by_model[model] = {
                "request_count": 0,
                "error_count": 0,
                "latencies": [],
                "status_counts": {},
            }

        metrics_by_model[model]["request_count"] += 1
        metrics_by_model[model]["latencies"].append(latency)
        metrics_by_model[model]["status_counts"][status_key] = (
            metrics_by_model[model]["status_counts"].get(status_key, 0) + 1
        )

        if status >= 400:
            metrics_by_model[model]["error_count"] += 1

    for model, metrics in metrics_by_model.items():
        model_latencies = metrics["latencies"]
        metrics["avg_latency_ms"] = round(sum(model_latencies) / len(model_latencies), 2)
        metrics["p95_latency_ms"] = percentile(model_latencies, 95)
        metrics["error_rate"] = round(
            metrics["error_count"] / metrics["request_count"],
            4,
        )
        del metrics["latencies"]

    slowest_records = sorted(
        records,
        key=lambda record: int(record["latency_ms"]),
        reverse=True,
    )[:3]

    slowest_requests = []
    for record in slowest_records:
        slowest_requests.append({
            "request_id": record["request_id"],
            "model": record["model"],
            "status": int(record["status"]),
            "latency_ms": int(record["latency_ms"]),
        })

    return {
        "total_requests": total_requests,
        "success_requests": len(success_records),
        "failed_requests": failed_requests,
        "success_rate": round(success_rate, 4),
        "error_rate": round(error_rate, 4),
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": p95_latency,
        "p99_latency_ms": p99_latency,
        "avg_success_latency_ms": round(avg_success_latency, 2),
        "slow_request_count": slow_requests,
        "requests_by_status": requests_by_status,
        "top_3_slowest_requests": slowest_requests,
        "metrics_by_model": metrics_by_model,
    }


def analyze_logs(log_path):
    records = []

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            record = parse_log_line(line)
            if is_valid_record(record):
                records.append(record)

    return analyze_records(records)

def main():
    log_path = "data/day02/inference.log"
    result = analyze_logs(log_path)
    print(json.dumps(result, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()