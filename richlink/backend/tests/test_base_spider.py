"""BaseSpider.collect()가 fetch/parse를 올바르게 조합하고, 개별 URL 실패를
격리하는지 검증하는 테스트.

아키텍처 변경(2026-10): save/update/remove_duplicate는 SubmissionService로
옮겨갔으므로, BaseSpider 테스트는 collect()만 검증한다.
"""
from __future__ import annotations

from backend.base.base_spider import BaseSpider
from backend.base.schemas import ProjectData


class _FakeFetcher:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self._html_by_url = html_by_url

    async def fetch_html(self, url: str) -> str:
        return self._html_by_url[url]


class _FailingFetcher:
    async def fetch_html(self, url: str) -> str:
        raise RuntimeError("network error")


class _EchoSpider(BaseSpider):
    """테스트 전용 최소 Spider 구현체."""

    name = "echo"

    async def target_urls(self) -> list[str]:
        return ["https://example.com/list"]

    def parse(self, html: str, source_url: str) -> list[ProjectData]:
        return [
            ProjectData(
                title=html,
                address="서울특별시 강남구 테헤란로 1",
                city="서울특별시",
                district="강남구",
                raw_type="아파트",
                source_url=source_url,
                spider_name=self.name,
            )
        ]


class TestCollect:
    """collect()가 fetch → parse를 올바르게 조합하는지 검증한다."""

    async def test_collect_calls_fetch_then_parse(self) -> None:
        fetcher = _FakeFetcher({"https://example.com/list": "테스트 아파트"})
        spider = _EchoSpider(fetcher=fetcher)

        results = await spider.collect()

        assert len(results) == 1
        assert results[0].title == "테스트 아파트"

    async def test_collect_isolates_single_url_failure(self) -> None:
        """한 URL이 실패해도 전체 수집이 중단되지 않고 빈 목록을 반환하는지 확인한다."""
        spider = _EchoSpider(fetcher=_FailingFetcher())

        results = await spider.collect()

        assert results == []
