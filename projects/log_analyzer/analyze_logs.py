import json


def parse_log_line(line):
    parts = line.strip().split()
    record = {}

    for part in parts:
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        record[key] = value

    return record

def percentile(values, percent):
    if not values:
        return 0

    sorted_values = sorted(values)
    index = round((percent / 100) * (len(sorted_values) - 1))
    return sorted_values[index]

def analyze_logs(log_path):
    records = []

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            record = parse_log_line(line)
            records.append(record)

    total_requests = len(records)
    success_records = [record for record in records if record["status"] == "200"]
    failed_requests = total_requests - len(success_records)

    latencies = [int(record["latency_ms"]) for record in records]
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = percentile(latencies, 95)
    p99_latency = percentile(latencies, 99)

    success_latencies = [int(record["latency_ms"]) for record in success_records]
    avg_success_latency = sum(success_latencies) / len(success_latencies)

    slow_requests = sum(1 for latency in latencies if latency > 200)
    metrics_by_model = {}

    for record in records:
        model = record["model"]
        latency = int(record["latency_ms"])
        status = int(record["status"])

        if model not in metrics_by_model:
            metrics_by_model[model] = {
                "request_count": 0,
                "error_count": 0,
                "latencies": [],
            }

        metrics_by_model[model]["request_count"] += 1
        metrics_by_model[model]["latencies"].append(latency)

        if status >= 400:
            metrics_by_model[model]["error_count"] += 1

    for model, metrics in metrics_by_model.items():
        model_latencies = metrics["latencies"]
        metrics["avg_latency_ms"] = round(sum(model_latencies) / len(model_latencies), 2)
        metrics["p95_latency_ms"] = percentile(model_latencies, 95)
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

    result = {
        "total_requests": total_requests,
        "success_requests": len(success_records),
        "failed_requests": failed_requests,
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": p95_latency,
        "p99_latency_ms": p99_latency,
        "avg_success_latency_ms": round(avg_success_latency, 2),
        "slow_request_count": slow_requests,
        "top_3_slowest_requests": slowest_requests,
        "metrics_by_model": metrics_by_model,
    }

    return result


def main():
    log_path = "data/day02/inference.log"
    result = analyze_logs(log_path)
    print(json.dumps(result, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()