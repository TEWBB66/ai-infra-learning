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

    success_latencies = [int(record["latency_ms"]) for record in success_records]
    avg_success_latency = sum(success_latencies) / len(success_latencies)

    slow_requests = sum(1 for latency in latencies if latency > 200)

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
        "总请求数": total_requests,
        "成功请求数": len(success_records),
        "失败请求数": failed_requests,
        "平均延迟ms": round(avg_latency, 2),
        "成功请求平均延迟ms": round(avg_success_latency, 2),
        "慢请求数量": slow_requests,
        "最慢的3条请求": slowest_requests,
    }

    return result


def main():
    log_path = "data/day02/inference.log"
    result = analyze_logs(log_path)
    print(json.dumps(result, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()