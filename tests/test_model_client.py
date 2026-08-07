import pytest
from fastapi import HTTPException

from projects.ai_metrics_api import model_client


def test_call_model_server_rejects_unsupported_backend(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "unsupported")

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "unsupported model backend: unsupported"