"""등록된 전체 Spider 목록과, 전체 Spider를 동시에 돌려 결과를 모으는 함수.

새 Spider(GSSpider, XiSpider, PrugioSpider, HillstateSpider, HanwhaSpider,
DaewooSpider ...)를 추가하면 이 리스트에 등록하기만 하면 된다.
"""
from __future__ import annotations

import asyncio

from backend.base.base_spider import BaseSpider
from backend.base.schemas import ProjectData
from backend.config.settings import get_settings
from backend.spiders.builders.lotte_spider import LotteSpider
from backend.utils.fetcher import HttpFetcher
from backend.utils.logger import get_logger

logger = get_logger("spiders.registry")

SPIDER_REGISTRY: list[type[BaseSpider]] = [
    LotteSpider,
]


async def collect_all() -> list[ProjectData]:
    """등록된 모든 Spider를 최대 동시 실행 개수 제한하에 병렬로 돌려 결과를 합친다."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.max_concurrent_spiders)

    async def _run(spider_cls: type[BaseSpider]) -> list[ProjectData]:
        async with semaphore:
            fetcher = HttpFetcher()
            spider = spider_cls(fetcher=fetcher)
            try:
                return await spider.collect()
            except Exception:  # noqa: BLE001 - 한 Spider의 예외가 전체를 막지 않도록 격리
                logger.error(f"{spider_cls.__name__} 수집 중 예상치 못한 오류", exc_info=True)
                return []

    results = await asyncio.gather(*(_run(spider_cls) for spider_cls in SPIDER_REGISTRY))
    items: list[ProjectData] = []
    for result in results:
        items.extend(result)
    return items
