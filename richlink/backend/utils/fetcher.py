"""HTML 수집 공통 모듈 (Fetcher 구현체).

크롤링 방식 요구사항을 그대로 구현한다:
1. 먼저 httpx(Requests 계열)로 시도한다.
2. 실패하거나 Cloudflare 챌린지가 감지되면 Playwright로 시도한다.
3. 그래도 Cloudflare 챌린지가 감지되면 Playwright + Stealth로 재시도한다.
"""
from __future__ import annotations

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import Settings, get_settings
from backend.utils.logger import get_logger

logger = get_logger("fetcher")

_CLOUDFLARE_MARKERS = ("cf-browser-verification", "Checking your browser", "cf-chl-")
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


class HttpFetcher:
    """backend.base.protocols.Fetcher 구현체."""

    def __init__(self, settings: Settings | None = None) -> None:
        """설정을 주입받는다. 미지정시 전역 Settings를 사용한다."""
        self._settings = settings or get_settings()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _fetch_with_httpx(self, url: str) -> str:
        """httpx(Requests 계열 비동기 클라이언트)로 정적 HTML을 가져온다."""
        async with httpx.AsyncClient(
            timeout=self._settings.request_timeout_seconds, follow_redirects=True
        ) as client:
            response = await client.get(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
            response.raise_for_status()
            return response.text

    async def _fetch_with_playwright(self, url: str, *, stealth: bool) -> str:
        """Playwright로 JS 렌더링 후 HTML을 가져온다. stealth=True면 탐지 우회 패치를 적용한다."""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._settings.playwright_headless)
            try:
                page = await browser.new_page(user_agent=_DEFAULT_USER_AGENT)
                if stealth:
                    await stealth_async(page)
                await page.goto(url, timeout=self._settings.request_timeout_seconds * 1000)
                await page.wait_for_load_state("networkidle")
                return await page.content()
            finally:
                await browser.close()

    @staticmethod
    def _looks_like_cloudflare_challenge(html: str) -> bool:
        """Cloudflare 챌린지 페이지 여부를 간단한 마커 매칭으로 판단한다."""
        return any(marker in html for marker in _CLOUDFLARE_MARKERS)

    async def fetch_html(self, url: str) -> str:
        """크롤링 방식 우선순위(httpx → Playwright → Playwright+Stealth)를 순차 적용한다."""
        try:
            html = await self._fetch_with_httpx(url)
            if not self._looks_like_cloudflare_challenge(html):
                logger.info(f"httpx로 수집 성공: {url}")
                return html
            logger.warning(f"Cloudflare 챌린지 감지, Playwright+Stealth로 전환: {url}")
        except Exception:  # noqa: BLE001 - 1차 수단 실패 시 다음 수단으로 넘어가기 위한 의도적 처리
            logger.warning(f"httpx 실패, Playwright로 전환: {url}")

        try:
            html = await self._fetch_with_playwright(url, stealth=False)
            if not self._looks_like_cloudflare_challenge(html):
                logger.info(f"Playwright로 수집 성공: {url}")
                return html
        except Exception:  # noqa: BLE001
            logger.warning(f"Playwright 실패, Stealth 모드로 전환: {url}")

        html = await self._fetch_with_playwright(url, stealth=True)
        logger.success(f"Playwright+Stealth로 수집 성공: {url}")
        return html
