import os


def _bool_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).lower()
    if value not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
        raise ValueError(f"{name} must be a boolean value")
    return value in {"1", "true", "yes", "on"}


def _int_env(name: str, default: str, minimum: int | None = None) -> int:
    raw_value = os.getenv(name, default)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")

    return value


def _float_env(name: str, default: str, minimum: float | None = None) -> float:
    raw_value = os.getenv(name, default)
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")

    return value


def _choice_env(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).lower()
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {allowed_values}")
    return value


LOG_PATH = os.getenv("INFERENCE_LOG_PATH", "data/day02/inference.log")
LOG_BACKEND = _choice_env("LOG_BACKEND", "file", {"file", "sqlite"})
SQLITE_LOG_PATH = os.getenv("SQLITE_LOG_PATH", "data/day02/inference.sqlite3")

DEFAULT_SLOW_THRESHOLD_MS = 200

ALLOWED_FORCE_STATUS_CODES = {200, 400, 429, 500}

SERVICE_ERROR_RATE_WARNING_THRESHOLD = 0.1
SERVICE_ERROR_RATE_CRITICAL_THRESHOLD = 0.2

SERVICE_P95_LATENCY_WARNING_MS = 400
SERVICE_P95_LATENCY_CRITICAL_MS = 800

SERVICE_SLOW_REQUEST_WARNING_COUNT = 3
SERVICE_SLOW_REQUEST_CRITICAL_COUNT = 5

MODEL_ERROR_RATE_WARNING_THRESHOLD = 0.2
MODEL_ERROR_RATE_CRITICAL_THRESHOLD = 0.3

MODEL_P95_LATENCY_WARNING_MS = 400
MODEL_P95_LATENCY_CRITICAL_MS = 800

MODEL_BACKEND = _choice_env("MODEL_BACKEND", "mock", {"mock", "remote_http", "vllm"})
MOCK_MODEL_SERVER_URL = os.getenv(
    "MOCK_MODEL_SERVER_URL",
    os.getenv("MODEL_SERVER_URL", "http://mock-model-server:8001/generate"),
)
MODEL_SERVER_URL = MOCK_MODEL_SERVER_URL
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001/v1").rstrip("/")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
MODEL_SERVER_TIMEOUT_SEC = _float_env(
    "MODEL_SERVER_TIMEOUT_SEC",
    os.getenv("MODEL_SERVER_TIMEOUT_SECONDS", "30"),
    minimum=0.001,
)
MODEL_SERVER_TIMEOUT_SECONDS = MODEL_SERVER_TIMEOUT_SEC
MAX_IN_FLIGHT_REQUESTS = _int_env("MAX_IN_FLIGHT_REQUESTS", "8", minimum=1)

ADMISSION_MODE = _choice_env("ADMISSION_MODE", "reject", {"reject", "queue"})
MAX_QUEUE_SIZE = _int_env("MAX_QUEUE_SIZE", "32", minimum=0)
QUEUE_TIMEOUT_MS = _int_env("QUEUE_TIMEOUT_MS", "500", minimum=0)

REQUIRE_API_KEY = _bool_env("REQUIRE_API_KEY")
API_KEY = os.getenv("API_KEY", "")

RATE_LIMIT_ENABLED = _bool_env("RATE_LIMIT_ENABLED")
RATE_LIMIT_MAX_REQUESTS = _int_env("RATE_LIMIT_MAX_REQUESTS", "60", minimum=0)
RATE_LIMIT_WINDOW_SECONDS = _int_env("RATE_LIMIT_WINDOW_SECONDS", "60", minimum=1)
