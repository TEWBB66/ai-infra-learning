from pathlib import Path


def test_project_evidence_files_exist():
    required_paths = [
        "docs/ALERTING_RUNBOOK.md",
        "docs/PRODUCTION_GAPS.md",
        "docs/reliability_experiments.md",
        "docs/MODEL_BACKEND_PROTOCOL.md",
        "reports/vllm_benchmark_2026_08_18/README.md",
        "reports/vllm_admission_control_2026_08_19/README.md",
        "monitoring/prometheus-rules.yml",
    ]

    for path in required_paths:
        assert Path(path).exists(), f"missing project evidence file: {path}"


def test_readme_links_core_evidence():
    readme = Path("README.md").read_text(encoding="utf-8")

    expected_snippets = [
        "Real vLLM GPU Serving Validation",
        "reports/vllm_benchmark_2026_08_18/README.md",
        "docs/ALERTING_RUNBOOK.md",
        "docs/PRODUCTION_GAPS.md",
        "Project Boundary",
    ]

    for snippet in expected_snippets:
        assert snippet in readme


def test_public_docs_do_not_contain_private_upgrade_process_terms():
    public_docs = [
        Path("README.md"),
        Path("docs/ALERTING_RUNBOOK.md"),
        Path("docs/PRODUCTION_GAPS.md"),
        Path("docs/MODEL_BACKEND_PROTOCOL.md"),
        Path("docs/reliability_experiments.md"),
    ]
    blocked_terms = ["9/10", "8/10", "career plan", "mastery", "升级计划", "评分"]

    for path in public_docs:
        text = path.read_text(encoding="utf-8")
        for term in blocked_terms:
            assert term not in text, f"{path} contains private process term: {term}"
