"""크롤링 결과를 받아서 "신규/중복 판단 → 저장 → 홈해버 전송 → 결과 기록"까지
전체 파이프라인을 조율하는 서비스.

크게 두 단계로 나뉜다:
1. ingest(): 크롤링 결과를 받아 RichLink 자신의 수집함에 새로 저장할지,
   이미 아는 현장이라 그냥 둘지를 결정한다. 이 단계에서는 홈해버로 아무것도
   보내지 않는다.
2. submit_pending(): 아직 전송 안 했거나(PENDING) 지난번에 실패한(FAILED)
   건들을 모아 홈해버 API로 보내고, 성공/실패를 기록한다.

이렇게 나눈 이유: 여러 Spider의 수집 결과를 전부 모은 다음, 한꺼번에
최대 50건씩 묶어 전송하는 게(배치) 한 건씩 바로 보내는 것보다 효율적이고
홈해버 쪽 배치 제한(50건/요청)에도 맞기 때문이다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.base.schemas import ImageData, ProjectData
from backend.models.enums import ImageCategory, SubmissionStatus
from backend.models.project import Project, ProjectImage, ProjectSource
from backend.models.repository import ProjectRepository
from backend.services.duplicate_service import DuplicateDetectionService
from backend.services.homehaver_client import HomehaverApiClient
from backend.services.homehaver_payload import build_listing_payload
from backend.utils.listing_aggregator import aggregate_area_range, aggregate_price_range
from backend.utils.logger import get_logger
from backend.utils.type_mapper import map_listing_status, map_property_type

logger = get_logger("submission_service")


def _map_image_category(hint: str | None) -> ImageCategory:
    """크롤링 사이트가 알려준 힌트 문자열을 홈해버 이미지 카테고리로 변환한다."""
    if hint and "평면" in hint:
        return ImageCategory.FLOOR_PLAN
    if hint and "썸네일" in hint:
        return ImageCategory.THUMBNAIL
    return ImageCategory.INFRA


def _pick_thumbnail(images: list[ImageData]) -> tuple[ImageData | None, list[ImageData]]:
    """대표 썸네일 1장과 나머지 이미지 목록을 분리한다.

    "썸네일" 힌트가 붙은 이미지가 있으면 그걸 우선하고, 없으면 첫 번째
    이미지를 대표로 삼는다.
    """
    if not images:
        return None, []
    for image in images:
        if image.category_hint == "썸네일":
            return image, [img for img in images if img is not image]
    return images[0], images[1:]


class SubmissionService:
    """크롤링 결과 수집 → 중복 판단 → 홈해버 전송까지의 파이프라인."""

    def __init__(self, session: AsyncSession, api_client: HomehaverApiClient | None = None) -> None:
        """세션과(선택) API 클라이언트를 주입받는다."""
        self._session = session
        self._repository = ProjectRepository(session)
        self._dedup = DuplicateDetectionService(session)
        self._client = api_client or HomehaverApiClient()

    async def ingest(self, items: list[ProjectData]) -> None:
        """크롤링 결과 목록을 받아 신규 저장/중복 판단만 수행한다 (전송 X)."""
        for item in items:
            exact_match = await self._repository.find_by_source_url(item.source_url)
            if exact_match is not None:
                logger.info(f"이미 아는 페이지라 건너뜀: {item.source_url}")
                continue

            duplicate = await self._dedup.find_existing(item)
            if duplicate is not None:
                await self._attach_source_if_new(duplicate, item)
                continue

            project = await self._create_project(item)
            logger.success(f"신규 현장 발견: {project.title}")

        await self._session.flush()

    async def submit_pending(self) -> dict[str, int]:
        """PENDING/FAILED 상태 건들을 모아 전송하고 결과를 기록한다.

        반환값은 {"attempted": N, "success": N, "failed": N} 요약이다.
        """
        pending = await self._repository.list_by_submission_status(SubmissionStatus.PENDING)
        failed = await self._repository.list_by_submission_status(SubmissionStatus.FAILED)
        candidates = pending + failed
        if not candidates:
            logger.info("전송할 대상 없음")
            return {"attempted": 0, "success": 0, "failed": 0}

        payloads = [build_listing_payload(project) for project in candidates]
        by_ref = {str(project.id): project for project in candidates}

        results = await self._client.submit_batch(payloads)
        now = datetime.now(timezone.utc)
        success_count = 0
        failed_count = 0

        for result in results:
            project = by_ref.get(result.client_ref)
            if project is None:
                continue
            project.attempt_count += 1
            project.submitted_at = now
            if result.success:
                project.submission_status = SubmissionStatus.SUCCESS
                project.homehaver_listing_id = result.listing_id
                project.last_error = None
                success_count += 1
                logger.success(f"전송 성공: {project.title}")
            else:
                project.submission_status = SubmissionStatus.FAILED
                project.last_error = result.error
                failed_count += 1
                logger.error(f"전송 실패: {project.title} — {result.error}")
            self._session.add(project)

        await self._session.commit()
        return {"attempted": len(candidates), "success": success_count, "failed": failed_count}

    async def _create_project(self, item: ProjectData) -> Project:
        """완전히 새로운 현장을 Project 행으로 만들어 저장한다 (전송은 아직 안 함)."""
        mapped_type = map_property_type(item.raw_type)
        mapped_status = map_listing_status(item.raw_status)
        price_min, price_max = aggregate_price_range(item.unit_types)
        area_min, area_max = aggregate_area_range(item.unit_types)

        is_mappable = mapped_type is not None
        project = Project(
            title=item.title,
            address=item.address,
            city=item.city,
            district=item.district,
            lat=item.lat,
            lng=item.lng,
            phone=item.phone,
            builder_name=item.builder_name,
            raw_type=item.raw_type,
            mapped_type=mapped_type.value if mapped_type else None,
            raw_status=item.raw_status,
            mapped_status=mapped_status.value if mapped_status else None,
            price_min=price_min,
            price_max=price_max,
            area_min=area_min,
            area_max=area_max,
            supply_count=item.supply_count,
            move_in_date=item.move_in_date,
            subscription_date=item.subscription_date,
            model_house=item.model_house,
            description=item.description,
            submission_status=(
                SubmissionStatus.PENDING if is_mappable else SubmissionStatus.SKIPPED
            ),
            last_error=(
                None
                if is_mappable
                else f"분양 유형 매핑 실패: '{item.raw_type}'를 홈해버 허용값으로 변환할 수 없음"
            ),
        )

        primary_image, rest_images = _pick_thumbnail(item.images)
        if primary_image is not None:
            project.thumbnail_url = primary_image.source_url
        for image in rest_images:
            project.images.append(
                ProjectImage(
                    category=_map_image_category(image.category_hint),
                    image_url=image.source_url,
                )
            )

        project.sources.append(ProjectSource(spider_name=item.spider_name, source_url=item.source_url))

        await self._repository.add(project)
        return project

    async def _attach_source_if_new(self, project: Project, item: ProjectData) -> None:
        """다른 사이트에서 같은 현장을 또 발견했을 때, 출처 기록만 추가한다."""
        already_linked = any(source.source_url == item.source_url for source in project.sources)
        if already_linked:
            return
        project.sources.append(ProjectSource(spider_name=item.spider_name, source_url=item.source_url))
        self._session.add(project)
        await self._session.flush()
