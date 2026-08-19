from pathlib import Path

from projects.ai_metrics_api import config


REQUIRED_ENV_KEYS = [
    "INFERENCE_LOG_PATH",
    "SQLITE_LOG_PATH",
    "LOG_BACKEND",
    "MODEL_BACKEND",
    "MOCK_MODEL_SERVER_URL",
    "VLLM_BASE_URL",
    "VLLM_MODEL",
    "MODEL_SERVER_TIMEOUT_SEC",
    "MAX_IN_FLIGHT_REQUESTS",
    "ADMISSION_MODE",
    "MAX_QUEUE_SIZE",
    "QUEUE_TIMEOUT_MS",
    "REQUIRE_API_KEY",
    "API_KEY",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "READINESS_CHECK_BACKEND",
    "MOCK_MODEL_DELAY_SCALE",
    "GRAFANA_ADMIN_PASSWORD",
]


def test_env_example_documents_runtime_config():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for key in REQUIRED_ENV_KEYS:
        assert f"{key}=" in env_example


def test_compose_passes_documented_runtime_config():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    for key in REQUIRED_ENV_KEYS:
        assert f"${{{key}" in compose, f"docker-compose.yml does not pass {key}"


def test_config_module_exposes_api_runtime_settings():
    assert config.MODEL_BACKEND == "mock"
    assert config.LOG_BACKEND in {"file", "sqlite"}
    assert config.SQLITE_LOG_PATH
    assert config.VLLM_BASE_URL
    assert config.VLLM_MODEL
    assert config.MAX_IN_FLIGHT_REQUESTS >= 1
    assert config.ADMISSION_MODE in {"reject", "queue"}
    assert config.MAX_QUEUE_SIZE >= 0
    assert config.QUEUE_TIMEOUT_MS >= 0
    assert isinstance(config.REQUIRE_API_KEY, bool)
    assert isinstance(config.API_KEY, str)
    assert isinstance(config.RATE_LIMIT_ENABLED, bool)
    assert config.RATE_LIMIT_MAX_REQUESTS >= 0
    assert config.RATE_LIMIT_WINDOW_SECONDS >= 1
