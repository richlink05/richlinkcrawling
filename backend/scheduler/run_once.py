"""크론 환경(GitHub Actions 등)에서 직접 실행하는 진입점 스크립트.

이 스크립트 하나만 실행하면:
1. 등록된 모든 Spider가 수집을 수행하고
2. RichLink 자신의 수집함 DB에서 신규/중복을 판단해 저장하고
3. 아직 전송 안 했거나 지난번에 실패한 건들을 홈해버 API로 전송한다.

사용법:
    python -m backend.scheduler.run_once
"""
from __future__ import annotations

import asyncio

from backend.models.base import AsyncSessionLocal
from backend.services.submission_service import SubmissionService
from backend.spiders.registry import collect_all
from backend.utils.logger import get_logger

logger = get_logger("scheduler.run_once")


async def run_once_async() -> None:
    """수집 → 저장/중복판단 → 홈해버 전송까지 전체 파이프라인을 1회 실행한다."""
    logger.info("크롤링 시작")
    items = await collect_all()
    logger.success(f"크롤링 완료: 총 {len(items)}건 수집")

    async with AsyncSessionLocal() as session:
        service = SubmissionService(session)
        await service.ingest(items)
        await session.commit()

        summary = await service.submit_pending()
        logger.success(
            f"홈해버 전송 완료: 시도 {summary['attempted']}건 "
            f"(성공 {summary['success']}건, 실패 {summary['failed']}건)"
        )


def main() -> None:
    """엔트리 포인트."""
    asyncio.run(run_once_async())


if __name__ == "__main__":
    main()
