"""5단계: HttpFetcher가 요구된 크롤링 우선순위를 따르는지 검증한다.

실제 네트워크/브라우저를 띄우지 않도록 내부 메서드를 monkeypatch로 대체한다.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.utils.fetcher import HttpFetcher


@pytest.fixture
def fetcher() -> HttpFetcher:
    return HttpFetcher()


class TestFetchHtml:
    async def test_uses_httpx_result_when_successful_and_not_cloudflare(
        self, fetcher: HttpFetcher, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fetcher, "_fetch_with_httpx", AsyncMock(return_value="<html>ok</html>"))
        playwright_mock = AsyncMock()
        monkeypatch.setattr(fetcher, "_fetch_with_playwright", playwright_mock)

        html = await fetcher.fetch_html("https://example.com")

        assert html == "<html>ok</html>"
        playwright_mock.assert_not_called()

    async def test_falls_back_to_playwright_when_httpx_raises(
        self, fetcher: HttpFetcher, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fetcher, "_fetch_with_httpx", AsyncMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr(fetcher, "_fetch_with_playwright", AsyncMock(return_value="<html>pw</html>"))

        html = await fetcher.fetch_html("https://example.com")

        assert html == "<html>pw</html>"

    async def test_falls_back_to_stealth_when_cloudflare_detected_twice(
        self, fetcher: HttpFetcher, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            fetcher, "_fetch_with_httpx", AsyncMock(return_value="Checking your browser")
        )
        calls: list[bool] = []

        async def fake_playwright(url: str, *, stealth: bool) -> str:
            calls.append(stealth)
            return "Checking your browser" if not stealth else "<html>real</html>"

        monkeypatch.setattr(fetcher, "_fetch_with_playwright", fake_playwright)

        html = await fetcher.fetch_html("https://example.com")

        assert html == "<html>real</html>"
        assert calls == [False, True]


class TestCloudflareDetection:
    def test_detects_cloudflare_marker(self, fetcher: HttpFetcher) -> None:
        assert fetcher._looks_like_cloudflare_challenge("cf-chl-abc")

    def test_normal_html_is_not_flagged(self, fetcher: HttpFetcher) -> None:
        assert not fetcher._looks_like_cloudflare_challenge("<html>normal</html>")
