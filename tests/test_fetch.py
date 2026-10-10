import httpx
import pytest
import time

from fetcher.fetch import FetchResult, fetch_all, fetch_url

def fake_get_ok(url, **kwargs):
    return httpx.Response(200)

def make_raiser(exc):
    """Build a fake httpx.get that raises the given exception."""
    def fake_get(url, **kwargs):
        raise exc
    return fake_get

class TestFetchURL:

    def test_fetch_url_success(self, monkeypatch):
        monkeypatch.setattr(httpx, "get", fake_get_ok)

        result = fetch_url("https://example.com")

        assert result.url == "https://example.com"
        assert result.status_code == 200
        assert result.error is None
        assert result.duration_ms >= 0

    @pytest.mark.parametrize("exc", [
        httpx.ConnectError("connection refused"),
        httpx.ConnectTimeout("connect timed out"),
        httpx.ReadTimeout("read timed out"),
        httpx.UnsupportedProtocol("missing http:// or https://"),
    ])
    def test_request_errors_become_error_results(self, monkeypatch, exc):
        monkeypatch.setattr(httpx, "get", make_raiser(exc))

        result = fetch_url("https://example.test")

        assert result.url == "https://example.test"
        assert result.status_code is None
        assert result.error == f"{type(exc).__name__}: {exc}"

    def test_failure_duration_includes_time_before_error(self, monkeypatch):
        def slow_then_fail(url, **kwargs):
            time.sleep(0.05)
            raise httpx.ReadTimeout("read timed out")

        monkeypatch.setattr(httpx, "get", slow_then_fail)

        result = fetch_url("https://example.test")

        assert result.duration_ms >= 50

    def test_non_request_errors_are_not_swallowed(self, monkeypatch):
        monkeypatch.setattr(httpx, "get", make_raiser(ValueError("bug in our code")))

        with pytest.raises(ValueError):
            fetch_url("https://example.test")

    @pytest.mark.parametrize("status", [404, 500])
    def test_http_error_status_is_not_a_failure(self, monkeypatch, status):
        monkeypatch.setattr(httpx, "get", lambda url, **kwargs: httpx.Response(status))

        result = fetch_url("https://example.test")

        assert result.status_code == status
        assert result.error is None

class TestFetchAll:

    def test_fetch_all_preserves_order(self, monkeypatch):
        monkeypatch.setattr(httpx, "get", fake_get_ok)
        urls = ["https://a.test", "https://b.test", "https://c.test"]

        results = fetch_all(urls)

        assert [r.url for r in results] == urls