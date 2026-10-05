"""평형별 데이터 → Project 상단 가격/면적 범위 집계 검증 테스트."""
from __future__ import annotations

from backend.base.schemas import UnitTypeData
from backend.utils.listing_aggregator import aggregate_area_range, aggregate_price_range


class TestAggregatePriceRange:
    def test_aggregates_min_and_max_across_units(self) -> None:
        units = [
            UnitTypeData(raw_type="84A", price_text="22.8억"),
            UnitTypeData(raw_type="84B", price_text="25.3억"),
        ]

        price_min, price_max = aggregate_price_range(units)

        assert price_min == 228_000
        assert price_max == 253_000

    def test_returns_none_tuple_when_no_parsable_price(self) -> None:
        units = [UnitTypeData(raw_type="84A", price_text="미정")]

        assert aggregate_price_range(units) == (None, None)

    def test_returns_none_tuple_for_empty_list(self) -> None:
        assert aggregate_price_range([]) == (None, None)


class TestAggregateAreaRange:
    def test_aggregates_min_and_max_across_units(self) -> None:
        units = [
            UnitTypeData(raw_type="84A", area_sqm=84.98),
            UnitTypeData(raw_type="59A", area_sqm=59.12),
        ]

        area_min, area_max = aggregate_area_range(units)

        assert area_min == 59.12
        assert area_max == 84.98

    def test_returns_none_tuple_when_no_area_given(self) -> None:
        units = [UnitTypeData(raw_type="84A")]

        assert aggregate_area_range(units) == (None, None)
