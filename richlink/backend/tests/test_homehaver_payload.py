"""Project → 홈해버 API 요청 JSON 변환 검증 테스트."""
from __future__ import annotations

from backend.models.enums import ImageCategory
from backend.models.project import Project, ProjectImage
from backend.services.homehaver_payload import build_listing_payload


def _make_project(**overrides: object) -> Project:
    base: dict[str, object] = dict(
        title="힐스테이트 강남", address="서울특별시 강남구 테헤란로 1",
        city="서울특별시", district="강남구", raw_type="아파트", mapped_type="아파트",
    )
    base.update(overrides)
    return Project(**base)


class TestBuildListingPayload:
    def test_includes_required_fields(self) -> None:
        project = _make_project()

        payload = build_listing_payload(project)

        assert payload["title"] == "힐스테이트 강남"
        assert payload["type"] == "아파트"
        assert payload["address"] == "서울특별시 강남구 테헤란로 1"
        assert payload["client_ref"] == str(project.id)

    def test_omits_manager_fields(self) -> None:
        payload = build_listing_payload(_make_project())

        assert "manager_name" not in payload
        assert "manager_phone" not in payload

    def test_omits_lat_lng_when_unknown(self) -> None:
        payload = build_listing_payload(_make_project(lat=None, lng=None))

        assert "lat" not in payload
        assert "lng" not in payload

    def test_includes_lat_lng_when_known(self) -> None:
        payload = build_listing_payload(_make_project(lat=37.5, lng=127.0))

        assert payload["lat"] == 37.5
        assert payload["lng"] == 127.0

    def test_includes_images_with_category(self) -> None:
        project = _make_project()
        project.images.append(ProjectImage(category=ImageCategory.FLOOR_PLAN, image_url="https://a.jpg"))

        payload = build_listing_payload(project)

        assert payload["images"] == [{"image_url": "https://a.jpg", "category": "평면도"}]

    def test_includes_status_only_when_mapped(self) -> None:
        with_status = build_listing_payload(_make_project(mapped_status="분양중"))
        without_status = build_listing_payload(_make_project(mapped_status=None))

        assert with_status["status"] == "분양중"
        assert "status" not in without_status
