from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/tests.yml")


def test_ci_workflow_runs_python_validation_steps():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    expected_steps = [
        "python -m pytest -q",
        "python -m compileall -q projects tests scripts",
        "python -m json.tool monitoring/grafana/dashboards/ai_metrics_dashboard.json",
        "git diff --check",
        "python scripts/check_public_text.py",
    ]

    for step in expected_steps:
        assert step in workflow


def test_ci_workflow_builds_docker_image():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "docker-build:" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "docker build -t ai-metrics-api:ci ." in workflow



def test_public_text_checker_is_available():
    assert Path("scripts/check_public_text.py").exists()
