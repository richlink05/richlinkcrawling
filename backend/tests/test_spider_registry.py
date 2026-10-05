"""spiders.registry.collect_all()이 모든 Spider를 돌리고 실패를 격리하는지 검증."""
from __future__ import annotations

import pytest

from backend.base.schemas import ProjectData
from backend.spiders import registry as registry_module


class _FakeSpider:
    def __init__(self, fetcher: object) -> None:
        pass

    async def collect(self) -> list[ProjectData]:
        return [
            ProjectData(
                title="테스트", address="주소", city="서울특별시", district="강남구",
                raw_type="아파트", source_url="https://example.com/1", spider_name="fake",
            )
        ]


class _FailingSpider(_FakeSpider):
    async def collect(self) -> list[ProjectData]:
        raise RuntimeError("spider crashed")


class TestCollectAll:
    async def test_aggregates_results_from_every_spider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry_module, "SPIDER_REGISTRY", [_FakeSpider, _FakeSpider])
        monkeypatch.setattr(registry_module, "HttpFetcher", lambda: object())

        items = await registry_module.collect_all()

        assert len(items) == 2

    async def test_one_spider_failure_does_not_stop_others(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry_module, "SPIDER_REGISTRY", [_FailingSpider, _FakeSpider])
        monkeypatch.setattr(registry_module, "HttpFetcher", lambda: object())

        items = await registry_module.collect_all()

        assert len(items) == 1
