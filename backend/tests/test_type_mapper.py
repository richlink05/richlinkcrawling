"""크롤링 원본 표현 → 홈해버 허용값 변환 검증 테스트."""
from __future__ import annotations

from backend.models.enums import ListingStatus, PropertyType
from backend.utils.type_mapper import map_listing_status, map_property_type


class TestMapPropertyType:
    def test_maps_known_synonyms(self) -> None:
        assert map_property_type("생숙") == PropertyType.LIVING_ACCOMMODATION
        assert map_property_type("주상복합") == PropertyType.APARTMENT
        assert map_property_type("도시형생활주택") == PropertyType.APARTMENT
        assert map_property_type("지산") == PropertyType.KNOWLEDGE_INDUSTRY_CENTER

    def test_maps_exact_homehaver_values_to_themselves(self) -> None:
        for value in PropertyType:
            assert map_property_type(value.value) == value

    def test_unknown_type_returns_none(self) -> None:
        assert map_property_type("듣도보도못한유형") is None


class TestMapListingStatus:
    def test_maps_known_synonyms(self) -> None:
        assert map_listing_status("분양완료") == ListingStatus.CLOSED
        assert map_listing_status("완판") == ListingStatus.CLOSED
        assert map_listing_status("분양중") == ListingStatus.ONGOING

    def test_none_input_returns_none(self) -> None:
        assert map_listing_status(None) is None

    def test_unknown_status_returns_none(self) -> None:
        assert map_listing_status("알수없음") is None
