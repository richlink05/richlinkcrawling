"""평형별 데이터(unit_types)를 Project 상단의 가격/면적 범위로 집계.

홈해버 listings 테이블은 평형별 상세가 아니라 price_min/price_max,
area_min/area_max라는 "범위"만 받으므로, Spider가 모아온 평형 목록에서
최소/최대를 뽑아낸다.
"""
from __future__ import annotations

from backend.base.schemas import UnitTypeData
from backend.utils.price_parser import parse_price_to_manwon


def aggregate_price_range(unit_types: list[UnitTypeData]) -> tuple[float | None, float | None]:
    """평형별 price_text들을 만원 단위로 변환해 최소/최대를 구한다."""
    prices = [
        parse_price_to_manwon(unit.price_text)
        for unit in unit_types
        if unit.price_text is not None
    ]
    prices = [price for price in prices if price is not None]
    if not prices:
        return None, None
    return min(prices), max(prices)


def aggregate_area_range(unit_types: list[UnitTypeData]) -> tuple[float | None, float | None]:
    """평형별 area_sqm들의 최소/최대를 구한다."""
    areas = [unit.area_sqm for unit in unit_types if unit.area_sqm is not None]
    if not areas:
        return None, None
    return min(areas), max(areas)
