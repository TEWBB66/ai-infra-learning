from pathlib import Path


K8S_FILES = [
    Path("k8s/configmap.yaml"),
    Path("k8s/secret.example.yaml"),
    Path("k8s/persistent-volume-claim.yaml"),
    Path("k8s/deployment.yaml"),
    Path("k8s/service.yaml"),
]



def _block_after(text: str, marker: str, stop_at_prefix: str) -> str:
    start = text.index(marker)
    tail = text[start:]
    lines = tail.splitlines()
    block = [lines[0]]
    for line in lines[1:]:
        if line.startswith(stop_at_prefix):
            break
        block.append(line)
    return "\n".join(block)


def _metadata_name(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == "metadata:":
            for metadata_line in lines[index + 1:]:
                if metadata_line and not metadata_line.startswith(" "):
                    break
                stripped = metadata_line.strip()
                if stripped.startswith("name: "):
                    return stripped.removeprefix("name: ")
    raise AssertionError("metadata.name was not found")


def _data_keys(text: str) -> set[str]:
    lines = text.splitlines()
    keys = set()
    in_data = False

    for line in lines:
        if line == "data:":
            in_data = True
            continue
        if in_data and line and not line.startswith(" "):
            break
        if in_data and line.startswith("  "):
            stripped = line.strip()
            if ":" in stripped:
                keys.add(stripped.split(":", 1)[0])

    return keys


def _selector_labels(text: str) -> set[str]:
    block = _block_after(text, "  selector:", stop_at_prefix="  template:")
    return {
        line.strip()
        for line in block.splitlines()
        if line.strip().startswith("app.kubernetes.io/")
    }


def _template_labels(text: str) -> set[str]:
    start = text.index("      labels:")
    tail = text[start:]
    lines = tail.splitlines()
    labels = set()
    for line in lines[1:]:
        if line.startswith("      annotations:"):
            break
        stripped = line.strip()
        if stripped.startswith("app.kubernetes.io/"):
            labels.add(stripped)
    return labels


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



def test_deployment_selector_matches_template_labels():
    deployment = Path("k8s/deployment.yaml").read_text(encoding="utf-8")

    assert _selector_labels(deployment) == _template_labels(deployment)


def test_service_selector_matches_deployment_labels():
    deployment = Path("k8s/deployment.yaml").read_text(encoding="utf-8")
    service = Path("k8s/service.yaml").read_text(encoding="utf-8")

    for label in _selector_labels(deployment):
        assert label in service


def test_deployment_references_existing_config_secret_and_pvc():
    deployment = Path("k8s/deployment.yaml").read_text(encoding="utf-8")
    configmap = Path("k8s/configmap.yaml").read_text(encoding="utf-8")
    secret = Path("k8s/secret.example.yaml").read_text(encoding="utf-8")
    pvc = Path("k8s/persistent-volume-claim.yaml").read_text(encoding="utf-8")

    assert f"name: {_metadata_name(configmap)}" in deployment
    assert f"name: {_metadata_name(secret)}" in deployment
    assert f"claimName: {_metadata_name(pvc)}" in deployment


def test_deployment_probe_paths_and_named_port_are_consistent():
    deployment = Path("k8s/deployment.yaml").read_text(encoding="utf-8")
    service = Path("k8s/service.yaml").read_text(encoding="utf-8")

    assert "name: http" in deployment
    assert "containerPort: 8000" in deployment
    assert "targetPort: http" in service
    assert "path: /health" in deployment
    assert "path: /ready" in deployment
    assert "prometheus.io/path: \"/metrics/prometheus\"" in deployment


def test_deployment_resources_are_set_for_requests_and_limits():
    deployment = Path("k8s/deployment.yaml").read_text(encoding="utf-8")

    resources = _block_after(deployment, "          resources:", stop_at_prefix="          volumeMounts:")
    for snippet in [
        "requests:",
        "cpu: \"250m\"",
        "memory: \"256Mi\"",
        "limits:",
        "cpu: \"1\"",
        "memory: \"1Gi\"",
    ]:
        assert snippet in resources


def test_configmap_contains_all_runtime_keys_used_by_api():
    configmap = Path("k8s/configmap.yaml").read_text(encoding="utf-8")
    keys = _data_keys(configmap)

    expected_keys = {
        "INFERENCE_LOG_PATH",
        "LOG_BACKEND",
        "SQLITE_LOG_PATH",
        "MODEL_BACKEND",
        "VLLM_BASE_URL",
        "VLLM_MODEL",
        "MODEL_SERVER_TIMEOUT_SEC",
        "MAX_IN_FLIGHT_REQUESTS",
        "ADMISSION_MODE",
        "MAX_QUEUE_SIZE",
        "QUEUE_TIMEOUT_MS",
        "REQUIRE_API_KEY",
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_MAX_REQUESTS",
        "RATE_LIMIT_WINDOW_SECONDS",
        "READINESS_CHECK_BACKEND",
    }

    assert expected_keys <= keys
