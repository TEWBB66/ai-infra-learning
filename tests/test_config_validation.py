import importlib
from types import SimpleNamespace

import pytest

from projects.ai_metrics_api import config


CONFIG_ENV_KEYS = [
    "LOG_BACKEND",
    "MODEL_BACKEND",
    "MODEL_SERVER_TIMEOUT_SEC",
    "MAX_IN_FLIGHT_REQUESTS",
    "ADMISSION_MODE",
    "MAX_QUEUE_SIZE",
    "QUEUE_TIMEOUT_MS",
    "REQUIRE_API_KEY",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
]


def snapshot_config(module):
    return SimpleNamespace(
        LOG_BACKEND=module.LOG_BACKEND,
        MODEL_BACKEND=module.MODEL_BACKEND,
        MODEL_SERVER_TIMEOUT_SEC=module.MODEL_SERVER_TIMEOUT_SEC,
        MAX_IN_FLIGHT_REQUESTS=module.MAX_IN_FLIGHT_REQUESTS,
        ADMISSION_MODE=module.ADMISSION_MODE,
        MAX_QUEUE_SIZE=module.MAX_QUEUE_SIZE,
        QUEUE_TIMEOUT_MS=module.QUEUE_TIMEOUT_MS,
        REQUIRE_API_KEY=module.REQUIRE_API_KEY,
        RATE_LIMIT_ENABLED=module.RATE_LIMIT_ENABLED,
        RATE_LIMIT_MAX_REQUESTS=module.RATE_LIMIT_MAX_REQUESTS,
        RATE_LIMIT_WINDOW_SECONDS=module.RATE_LIMIT_WINDOW_SECONDS,
    )


def reload_config(monkeypatch, **env):
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    try:
        return snapshot_config(importlib.reload(config))
    finally:
        for key in CONFIG_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        importlib.reload(config)


def test_default_config_is_valid(monkeypatch):
    cfg = reload_config(monkeypatch)

    assert cfg.LOG_BACKEND == "file"
    assert cfg.MODEL_BACKEND == "mock"
    assert cfg.ADMISSION_MODE == "reject"
    assert cfg.MAX_IN_FLIGHT_REQUESTS == 8


@pytest.mark.parametrize(
    "name,value",
    [
        ("LOG_BACKEND", "bad"),
        ("MODEL_BACKEND", "bad"),
        ("ADMISSION_MODE", "bad"),
    ],
)
def test_config_rejects_invalid_choices(monkeypatch, name, value):
    with pytest.raises(ValueError, match=name):
        reload_config(monkeypatch, **{name: value})


@pytest.mark.parametrize(
    "name,value",
    [
        ("MAX_IN_FLIGHT_REQUESTS", "0"),
        ("MAX_QUEUE_SIZE", "-1"),
        ("QUEUE_TIMEOUT_MS", "-1"),
        ("RATE_LIMIT_MAX_REQUESTS", "-1"),
        ("RATE_LIMIT_WINDOW_SECONDS", "0"),
    ],
)
def test_config_rejects_invalid_integer_ranges(monkeypatch, name, value):
    with pytest.raises(ValueError, match=name):
        reload_config(monkeypatch, **{name: value})


@pytest.mark.parametrize(
    "name,value",
    [
        ("MAX_IN_FLIGHT_REQUESTS", "abc"),
        ("RATE_LIMIT_MAX_REQUESTS", "abc"),
    ],
)
def test_config_rejects_invalid_integer_values(monkeypatch, name, value):
    with pytest.raises(ValueError, match=name):
        reload_config(monkeypatch, **{name: value})


def test_config_rejects_invalid_timeout(monkeypatch):
    with pytest.raises(ValueError, match="MODEL_SERVER_TIMEOUT_SEC"):
        reload_config(monkeypatch, MODEL_SERVER_TIMEOUT_SEC="0")


@pytest.mark.parametrize("name", ["REQUIRE_API_KEY", "RATE_LIMIT_ENABLED"])
def test_config_rejects_invalid_boolean_values(monkeypatch, name):
    with pytest.raises(ValueError, match=name):
        reload_config(monkeypatch, **{name: "maybe"})


def test_config_accepts_enabled_runtime_controls(monkeypatch):
    cfg = reload_config(
        monkeypatch,
        LOG_BACKEND="sqlite",
        MODEL_BACKEND="vllm",
        ADMISSION_MODE="queue",
        REQUIRE_API_KEY="true",
        RATE_LIMIT_ENABLED="true",
        RATE_LIMIT_MAX_REQUESTS="5",
        RATE_LIMIT_WINDOW_SECONDS="10",
    )

    assert cfg.LOG_BACKEND == "sqlite"
    assert cfg.MODEL_BACKEND == "vllm"
    assert cfg.ADMISSION_MODE == "queue"
    assert cfg.REQUIRE_API_KEY is True
    assert cfg.RATE_LIMIT_ENABLED is True
    assert cfg.RATE_LIMIT_MAX_REQUESTS == 5
    assert cfg.RATE_LIMIT_WINDOW_SECONDS == 10
