"""의존성 주입을 위한 Protocol(구조적 서브타이핑) 정의.

BaseSpider는 구체 구현(Playwright 등)에 의존하지 않고 이 Protocol에만
의존한다.
"""
from __future__ import annotations

from typing import Protocol


class Fetcher(Protocol):
    """HTML을 가져오는 컴포넌트가 구현해야 하는 인터페이스."""

    async def fetch_html(self, url: str) -> str:
        """주어진 URL의 렌더링된 HTML을 문자열로 반환한다."""
        ...
