import json

def summarize_latencies(latencies):
    # 如果列表为空，进行安全处理
    if not latencies:
        return {
            "平均延迟": 0,
            "最大延迟": 0,
            "超过150ms的请求数": 0,
            "从小到大排序后的延迟列表": []
        }
    
    # 1. 计算平均延迟
    avg_latency = sum(latencies) / len(latencies)
    
    # 2. 获取最大延迟
    max_latency = max(latencies)
    
    # 3. 计算超过 150ms 的请求数（此处“超过”按严格大于 > 150 计算）
    count_over_150 = sum(1 for x in latencies if x > 150)
    
    # 4. 获取从小到大排序后的延迟列表
    sorted_list = sorted(latencies)
    
    # 返回包含结果的字典
    return {
        "平均延迟": round(avg_latency, 2),  # 保留两位小数，更易读
        "最大延迟": max_latency,
        "超过150ms的请求数": count_over_150,
        "从小到大排序后的延迟列表": sorted_list
    }

def main():
    latencies = [120, 80, 240, 100, 300, 90, 150]
    result = summarize_latencies(latencies)
    print(json.dumps(result, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()