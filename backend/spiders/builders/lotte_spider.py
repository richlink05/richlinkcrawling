"""롯데건설(롯데캐슬) 분양 사이트 Spider.

실제 사이트(2026-10 확인) 구조:
- 목록 페이지: https://www.lottecastle.co.kr/aptInfo/lots/list.do
  (예전에 넣어둔 "/Sale/List"는 실제로 존재하지 않는 추측 URL이었다 — 사용자가
  실제 페이지를 저장해 보내줘서 바로잡았다.)
- 카드 1개 = `.list_box` 하나. 안에 있는 `.heart_icon` div의 data-* 속성에
  이름/주소/세대수/분양일/입주일/전화번호가 이미 구조화된 값으로 들어있어서,
  화면에 보이는 텍스트를 더듬어 파싱하는 것보다 이 속성들을 쓰는 게 훨씬
  안정적이다(사이트 디자인이 바뀌어도 data-* 속성명은 잘 안 바뀌는 편).
- 분양 상태("분양예정"/"분양중")는 `.txt_box .txt span`의 텍스트가 홈해버
  enum 표현과 그대로 일치해서 바로 raw_status로 쓴다.

알려진 한계: 목록 페이지 첫 로드 시 일부만 내려오고(예: 전체 18건 중 9건),
나머지는 "더 보기" 버튼이 AJAX로 더 불러오는 방식이다. 그 AJAX 엔드포인트는
아직 확인 전이라, 지금은 첫 페이지에 보이는 현장만 수집한다. 전체를 다 모으고
싶으면 `target_urls()`/`parse()`를 "더 보기" 엔드포인트까지 따라가도록 확장하면
된다.
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend.base.base_spider import BaseSpider
from backend.base.schemas import ImageData, ProjectData

_BASE_URL = "https://www.lottecastle.co.kr"
_LISTING_URL = f"{_BASE_URL}/aptInfo/lots/list.do"


class LotteSpider(BaseSpider):
    """롯데캐슬 분양현장 정보를 수집하는 Spider."""

    name = "lotte"

    async def target_urls(self) -> list[str]:
        """수집 대상 URL 목록을 반환한다."""
        return [_LISTING_URL]

    def parse(self, html: str, source_url: str) -> list[ProjectData]:
        """목록 페이지 HTML에서 분양현장 카드(.list_box)들을 파싱한다."""
        soup = BeautifulSoup(html, "lxml")
        items: list[ProjectData] = []

        for box in soup.select(".list_box"):
            info = box.select_one(".heart_icon[data-apt-nm]")
            if info is None:
                continue

            title = (info.get("data-apt-nm") or "").strip()
            address = (info.get("data-loctn") or "").strip()
            if not title or not address:
                continue

            city, district = self._split_address(address)
            phone = (info.get("data-inqy-tel") or "").strip() or None

            supply_count = self._parse_int(info.get("data-tot-houshd-cnt"))

            detail_link = box.select_one("a.txt_box")
            detail_href = detail_link.get("href") if detail_link else None
            detail_url = urljoin(_BASE_URL, detail_href) if detail_href else source_url

            status_el = box.select_one(".txt_box .txt span")
            raw_status = status_el.get_text(strip=True) if status_el else None

            images: list[ImageData] = []
            img_el = box.select_one(".img img")
            if img_el and img_el.get("src"):
                images.append(
                    ImageData(
                        source_url=urljoin(_BASE_URL, img_el["src"]),
                        category_hint="썸네일",
                    )
                )

            items.append(
                ProjectData(
                    title=title,
                    address=address,
                    city=city,
                    district=district,
                    phone=phone,
                    builder_name="롯데건설",
                    raw_type="아파트",  # 이 목록 페이지는 전부 아파트(APT) 단지만 노출한다
                    raw_status=raw_status,
                    supply_count=supply_count,
                    move_in_date=(info.get("data-movin-dt") or "").strip() or None,
                    subscription_date=(info.get("data-lots-dt") or "").strip() or None,
                    unit_types=[],
                    images=images,
                    source_url=detail_url,
                    spider_name=self.name,
                )
            )
        return items

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        """"1249" 같은 문자열을 정수로 변환한다. 비어있거나 숫자가 아니면 None."""
        if value and value.strip().isdigit():
            return int(value.strip())
        return None

    @staticmethod
    def _split_address(address: str) -> tuple[str, str]:
        """"서울특별시 강남구 테헤란로 1" 형태 주소에서 시/구를 분리한다."""
        parts = address.split()
        city = parts[0] if len(parts) > 0 else ""
        district = parts[1] if len(parts) > 1 else ""
        return city, district
