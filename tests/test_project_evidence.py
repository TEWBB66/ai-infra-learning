from pathlib import Path


PUBLIC_DOCS = [
    Path("README.md"),
    Path("projects/ai_metrics_api/README.md"),
    Path("docs/ALERTING_RUNBOOK.md"),
    Path("docs/PRODUCTION_GAPS.md"),
    Path("docs/MODEL_BACKEND_PROTOCOL.md"),
    Path("docs/reliability_experiments.md"),
]


def test_project_evidence_files_exist():
    required_paths = [
        "docs/ALERTING_RUNBOOK.md",
        "docs/PRODUCTION_GAPS.md",
        "docs/reliability_experiments.md",
        "docs/MODEL_BACKEND_PROTOCOL.md",
        "reports/vllm_benchmark_2026_08_18/README.md",
        "reports/vllm_admission_control_2026_08_19/README.md",
        "monitoring/prometheus-rules.yml",
        "projects/ai_metrics_api/log_store.py",
        "projects/ai_metrics_api/rate_limiter.py",
    ]

    for path in required_paths:
        assert Path(path).exists(), f"missing project evidence file: {path}"


def test_readme_links_core_evidence():
    readme = Path("README.md").read_text(encoding="utf-8")

    expected_snippets = [
        "Real vLLM GPU Serving Validation",
        "reports/vllm_benchmark_2026_08_18/README.md",
        "reports/vllm_admission_control_2026_08_19/README.md",
        "docs/ALERTING_RUNBOOK.md",
        "docs/PRODUCTION_GAPS.md",
        "Project Boundary",
    ]

    for snippet in expected_snippets:
        assert snippet in readme


def test_readme_documents_serving_controls():
    readme = Path("README.md").read_text(encoding="utf-8")

    expected_snippets = [
        "optional SQLite log storage",
        "API key protection",
        "request tracing",
        "per-client rate limiting",
        "API-side backpressure",
        "LOG_BACKEND=file|sqlite",
        "RATE_LIMIT_ENABLED=false",
        "ai_inference_rate_limit_rejected_total",
        "ai_inference_queue_rejected_total",
    ]

    for snippet in expected_snippets:
        assert snippet in readme


def test_api_readme_documents_runtime_controls():
    readme = Path("projects/ai_metrics_api/README.md").read_text(encoding="utf-8")

    expected_snippets = [
        "Optional API key authentication",
        "Optional per-client inference rate limiting",
        "File and SQLite inference log backends",
        "request id, trace id, client id",
        "ai_inference_rate_limit_rejected_total",
        "rate limiting is per API process",
    ]

    for snippet in expected_snippets:
        assert snippet in readme


def test_public_docs_do_not_contain_private_process_terms():
    blocked_terms = [
        "P" + "01",
        "up" + "grade",
        "9" + "/10",
        "8" + "/10",
        "career" + " plan",
        "master" + "y",
        "\u5347\u7ea7",
        "\u8bc4\u5206",
        "\u8ba1\u5212",
        "\u6211\u4eec",
        "Co" + "dex",
        "\u4e0b\u4e00\u6b65",
        "\u7b80\u5386",
        "\u9762\u8bd5",
        "\u5b66\u4e60\u8def\u7ebf",
    ]

    for path in PUBLIC_DOCS:
        text = path.read_text(encoding="utf-8")
        for term in blocked_terms:
            assert term not in text, f"{path} contains private process term"
