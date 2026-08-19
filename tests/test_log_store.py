from projects.ai_metrics_api.log_store import InferenceLogStore


def _line(request_id, status=200, latency_ms=50, model="qwen"):
    return (
        "2026-08-19T00:00:00Z "
        f"request_id={request_id} "
        f"model={model} "
        "endpoint=/v1/infer "
        f"status={status} "
        f"latency_ms={latency_ms} "
        "tokens_in=1 "
        "tokens_out=2"
    )


def test_file_log_store_appends_and_analyzes_records(tmp_path):
    store = InferenceLogStore(
        backend="file",
        log_path=tmp_path / "inference.log",
        sqlite_path=tmp_path / "unused.sqlite3",
    )

    store.append(_line("req-1", status=200, latency_ms=50))
    store.append(_line("req-2", status=500, latency_ms=700))

    metrics = store.analyze()

    assert metrics["total_requests"] == 2
    assert metrics["requests_by_status"] == {"200": 1, "500": 1}
    assert metrics["metrics_by_model"]["qwen"]["request_count"] == 2


def test_sqlite_log_store_appends_and_analyzes_records(tmp_path):
    store = InferenceLogStore(
        backend="sqlite",
        log_path=tmp_path / "unused.log",
        sqlite_path=tmp_path / "inference.sqlite3",
    )

    store.append(_line("req-1", status=200, latency_ms=50))
    store.append(_line("req-2", status=429, latency_ms=20))
    store.append("bad line without required fields")

    records = store.load_records()
    metrics = store.analyze()

    assert [record["request_id"] for record in records] == ["req-1", "req-2"]
    assert metrics["total_requests"] == 2
    assert metrics["requests_by_status"] == {"200": 1, "429": 1}


def test_sqlite_log_store_exports_latency_histogram(tmp_path):
    store = InferenceLogStore(
        backend="sqlite",
        log_path=tmp_path / "unused.log",
        sqlite_path=tmp_path / "inference.sqlite3",
    )

    store.append(_line("req-1", latency_ms=50))
    store.append(_line("req-2", latency_ms=700))

    lines = store.build_latency_histogram_prometheus()

    assert 'ai_inference_latency_ms_bucket{le="100"} 1' in lines
    assert 'ai_inference_latency_ms_bucket{le="1000"} 2' in lines
    assert "ai_inference_latency_ms_count 2" in lines


def test_log_store_rejects_unknown_backend(tmp_path):
    try:
        InferenceLogStore(
            backend="unknown",
            log_path=tmp_path / "inference.log",
            sqlite_path=tmp_path / "inference.sqlite3",
        )
    except ValueError as exc:
        assert "unsupported log backend" in str(exc)
    else:
        raise AssertionError("expected ValueError")
