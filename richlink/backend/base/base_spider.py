"""모든 사이트별 Spider가 상속하는 추상 베이스 클래스.

아키텍처 변경(2026-10): Spider의 책임은 "사이트에서 데이터를 긁어와 파싱하는
것"(collect/parse)까지로 좁혔다. 예전에 있던 save()/update()/remove_duplicate()는
SubmissionService로 옮겼다 — 여러 Spider의 수집 결과를 한데 모아 중복
판단과 홈해버 전송을 한꺼번에 처리하는 게(배치 전송 50건 제한에도 맞고)
Spider 하나하나가 각자 저장/전송까지 책임지는 것보다 합리적이기 때문이다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.base.protocols import Fetcher
from backend.base.schemas import ProjectData
from backend.utils.logger import get_logger


class BaseSpider(ABC):
    """사이트별 Spider의 공통 수집 파이프라인(target_urls → fetch → parse)."""

    #: 하위 클래스가 반드시 지정해야 하는 Spider 식별자 (예: "lotte", "gs")
    name: str

    def __init__(self, fetcher: Fetcher) -> None:
        """Fetcher를 주입받는다."""
        self._fetcher = fetcher
        self._logger = get_logger(f"spider.{self.name}")

    @abstractmethod
    async def target_urls(self) -> list[str]:
        """수집 대상 목록/상세 페이지 URL을 반환한다. 사이트마다 구현이 다르다."""

    @abstractmethod
    def parse(self, html: str, source_url: str) -> list[ProjectData]:
        """HTML을 파싱해 ProjectData 리스트로 변환한다."""

    async def collect(self) -> list[ProjectData]:
        """target_urls()를 순회하며 fetch → parse를 수행하고 결과를 모은다.

        개별 URL 처리 실패가 전체 수집을 중단시키지 않도록 예외를 격리한다.
        """
        results: list[ProjectData] = []
        for url in await self.target_urls():
            try:
                html = await self._fetcher.fetch_html(url)
                parsed = self.parse(html, url)
                results.extend(parsed)
                self._logger.success(f"수집 성공: {url} ({len(parsed)}건)")
            except Exception:  # noqa: BLE001 - 개별 URL 실패를 격리하기 위한 의도적 광범위 캐치
                self._logger.error(f"수집 실패: {url}", exc_info=True)
        return results
