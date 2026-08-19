from projects.ai_metrics_api.rate_limiter import FixedWindowRateLimiter


def test_disabled_rate_limiter_allows_requests():
    limiter = FixedWindowRateLimiter(enabled=False, max_requests=0, window_seconds=60)

    assert limiter.allow("client-a")
    assert limiter.allow("client-a")
    assert limiter.snapshot()["rejected_total"] == 0


def test_fixed_window_rate_limiter_rejects_after_limit():
    limiter = FixedWindowRateLimiter(enabled=True, max_requests=2, window_seconds=60)

    assert limiter.allow("client-a", now=10.0)
    assert limiter.allow("client-a", now=11.0)
    assert not limiter.allow("client-a", now=12.0)

    snapshot = limiter.snapshot()
    assert snapshot["active_clients"] == 1
    assert snapshot["rejected_total"] == 1


def test_fixed_window_rate_limiter_resets_after_window():
    limiter = FixedWindowRateLimiter(enabled=True, max_requests=1, window_seconds=10)

    assert limiter.allow("client-a", now=10.0)
    assert not limiter.allow("client-a", now=15.0)
    assert limiter.allow("client-a", now=20.0)


def test_fixed_window_rate_limiter_tracks_clients_independently():
    limiter = FixedWindowRateLimiter(enabled=True, max_requests=1, window_seconds=60)

    assert limiter.allow("client-a", now=10.0)
    assert not limiter.allow("client-a", now=11.0)
    assert limiter.allow("client-b", now=12.0)
