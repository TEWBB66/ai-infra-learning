from pathlib import Path


K8S_FILES = [
    Path("k8s/configmap.yaml"),
    Path("k8s/secret.example.yaml"),
    Path("k8s/persistent-volume-claim.yaml"),
    Path("k8s/deployment.yaml"),
    Path("k8s/service.yaml"),
]


def test_k8s_manifest_files_exist():
    for path in K8S_FILES:
        assert path.exists(), f"missing manifest: {path}"


def test_deployment_exposes_health_readiness_and_metrics():
    text = Path("k8s/deployment.yaml").read_text(encoding="utf-8")

    required = [
        "kind: Deployment",
        "replicas: 1",
        "containerPort: 8000",
        "prometheus.io/scrape: \"true\"",
        "prometheus.io/path: \"/metrics/prometheus\"",
        "livenessProbe:",
        "path: /health",
        "readinessProbe:",
        "path: /ready",
        "configMapRef:",
        "name: ai-metrics-api-config",
        "secretRef:",
        "name: ai-metrics-api-secret",
        "resources:",
        "persistentVolumeClaim:",
        "claimName: ai-metrics-api-data",
    ]

    for snippet in required:
        assert snippet in text


def test_configmap_covers_runtime_controls():
    text = Path("k8s/configmap.yaml").read_text(encoding="utf-8")

    required = [
        "LOG_BACKEND: \"sqlite\"",
        "MODEL_BACKEND: \"vllm\"",
        "VLLM_BASE_URL:",
        "VLLM_MODEL:",
        "MAX_IN_FLIGHT_REQUESTS:",
        "ADMISSION_MODE: \"queue\"",
        "MAX_QUEUE_SIZE:",
        "QUEUE_TIMEOUT_MS:",
        "REQUIRE_API_KEY: \"true\"",
        "RATE_LIMIT_ENABLED: \"true\"",
        "READINESS_CHECK_BACKEND: \"true\"",
    ]

    for snippet in required:
        assert snippet in text


def test_secret_template_does_not_store_real_key():
    text = Path("k8s/secret.example.yaml").read_text(encoding="utf-8")

    assert "kind: Secret" in text
    assert "API_KEY:" in text
    assert "replace-with-runtime-secret" in text
    assert "test-key" not in text


def test_service_targets_api_container_port():
    text = Path("k8s/service.yaml").read_text(encoding="utf-8")

    assert "kind: Service" in text
    assert "type: ClusterIP" in text
    assert "port: 8000" in text
    assert "targetPort: http" in text


def test_k8s_defaults_match_documented_single_replica_boundary():
    deployment = Path("k8s/deployment.yaml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    production_gaps = Path("docs/PRODUCTION_GAPS.md").read_text(encoding="utf-8")

    assert "replicas: 1" in deployment
    assert "replicas: 2" not in deployment
    assert "one API replica by default" in readme
    assert "single API replica" in production_gaps
    assert "not been applied to a live cluster" in production_gaps
    assert "No image registry release workflow is included yet." in production_gaps
