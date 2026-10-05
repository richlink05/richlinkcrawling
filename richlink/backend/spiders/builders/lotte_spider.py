"""롯데건설(롯데캐슬) 분양 사이트 Spider.

주의: 아래 CSS 선택자는 대표적인 목록/카드형 분양 사이트 구조를 가정한
예시다. 실제 사이트는 개편이 잦으므로 운영 투입 전 반드시 실제 마크업에
맞춰 SELECTORS를 검증/조정해야 한다.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from backend.base.base_spider import BaseSpider
from backend.base.schemas import ImageData, ProjectData, UnitTypeData

_LISTING_URL = "https://www.lottecastle.co.kr/Sale/List"


class LotteSpider(BaseSpider):
    """롯데캐슬 분양현장 정보를 수집하는 Spider."""

    name = "lotte"

    async def target_urls(self) -> list[str]:
        """수집 대상 URL 목록을 반환한다.

        목록 페이지 하나를 대상으로 등록하고, 개별 현장 카드는 parse()에서
        한 번에 여러 건을 추출한다. 상세 페이지까지 순회가 필요하면
        parse() 1차 결과에서 링크를 뽑아 재귀적으로 fetch하도록 확장한다.
        """
        return [_LISTING_URL]

    def parse(self, html: str, source_url: str) -> list[ProjectData]:
        """목록 페이지 HTML에서 분양현장 카드들을 파싱한다."""
        soup = BeautifulSoup(html, "lxml")
        items: list[ProjectData] = []

        for card in soup.select(".sale-list .sale-item"):
            title_el = card.select_one(".sale-item__title")
            address_el = card.select_one(".sale-item__address")
            if title_el is None or address_el is None:
                continue

            phone_el = card.select_one(".sale-item__tel")
            type_el = card.select_one(".sale-item__type")
            status_el = card.select_one(".sale-item__status")
            address = address_el.get_text(strip=True)
            city, district = self._split_address(address)

            unit_types = [
                UnitTypeData(
                    raw_type=el.get_text(strip=True),
                    price_text=el.get("data-price"),
                )
                for el in card.select(".sale-item__unit-type")
            ]
            images = [
                ImageData(source_url=img["src"])
                for img in card.select(".sale-item__thumb img")
                if img.get("src")
            ]

            items.append(
                ProjectData(
                    title=title_el.get_text(strip=True),
                    address=address,
                    city=city,
                    district=district,
                    phone=phone_el.get_text(strip=True) if phone_el else None,
                    builder_name="롯데건설",
                    raw_type=type_el.get_text(strip=True) if type_el else "아파트",
                    raw_status=status_el.get_text(strip=True) if status_el else None,
                    unit_types=unit_types,
                    images=images,
                    source_url=source_url,
                    spider_name=self.name,
                )
            )
        return items

    @staticmethod
    def _split_address(address: str) -> tuple[str, str]:
        """"서울특별시 강남구 테헤란로 1" 형태 주소에서 시/구를 분리한다."""
        parts = address.split()
        city = parts[0] if len(parts) > 0 else ""
        district = parts[1] if len(parts) > 1 else ""
        return city, district
