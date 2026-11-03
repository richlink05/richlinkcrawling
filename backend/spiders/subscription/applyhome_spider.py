"""청약홈(한국부동산원) 분양정보 OpenAPI Spider.

사이트 HTML을 긁는 다른 Spider와 달리, 공공데이터포털이 제공하는 공식 API
(청약홈 분양정보 조회 서비스, ApplyhomeInfoDetailSvc)를 호출한다. 그래서
BaseSpider의 target_urls()/parse()는 쓰지 않고 collect()를 직접 구현한다.

수집 범위(1차):
- APT 분양정보           getAPTLttotPblancDetail   (+ 주택형별 getAPTLttotPblancMdl)
- 오피스텔/도시형/민간임대/생활숙박시설
                         getUrbtyOfctlLttotPblancDetail (+ 주택형별 ...Mdl)
잔여세대·공공지원 민간임대·임의공급은 이미 나온 현장의 재공급이 많거나 날짜
형식이 달라 1차에서는 제외했다.

동작 방식:
1. 모집공고일이 (오늘 - lookback_days) 이후인 공고를 상세조회로 전부 가져온다.
2. 공고마다 주택형별 조회를 한 번 더 호출해 가격/면적 범위를 만든다(실패해도
   그 현장은 가격만 빠진 채로 수집한다).
3. 현장 고유 URL(모집공고 상세 URL)을 source_url로 써서, 이미 수집한 공고는
   SubmissionService가 정확히 일치 비교로 건너뛴다.

보안: 서비스 키는 요청 주소에 들어가므로, 어떤 로그/예외 메시지에도 주소나 키가
나오지 않게 한다(httpx 예외를 그대로 올리면 주소가 메시지에 포함되기 때문).
"""
from __future__ import annotations

import asyncio
import calendar
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote

import httpx

from backend.base.base_spider import BaseSpider
from backend.base.protocols import Fetcher
from backend.base.schemas import ProjectData, UnitTypeData
from backend.config.settings import Settings, get_settings

_KST = timezone(timedelta(hours=9))

# 수집 종류별 (상세조회 오퍼레이션, 주택형별 오퍼레이션)
_KINDS: dict[str, tuple[str, str]] = {
    "apt": ("getAPTLttotPblancDetail", "getAPTLttotPblancMdl"),
    "urbty": ("getUrbtyOfctlLttotPblancDetail", "getUrbtyOfctlLttotPblancMdl"),
}

# 오피스텔/도시형/민간임대/생활숙박시설 응답의 search_house_secd 코드 → 상품 유형
_URBTY_TYPE_BY_CODE = {
    "0201": "도시형생활주택",
    "0202": "오피스텔",
    "0203": "민간임대",
    "0204": "생활형숙박시설",
}

_MAX_PAGES = 200  # 무한 반복 방지용 안전장치


class ApplyhomeApiError(Exception):
    """청약홈 API 호출 실패. 메시지에 요청 주소/서비스 키를 절대 넣지 않는다."""

    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(f"{operation}: {reason}")


class ApplyhomeSpider(BaseSpider):
    """청약홈 분양정보 API로 신규 분양공고를 수집하는 Spider."""

    name = "applyhome"

    def __init__(
        self,
        fetcher: Fetcher | None = None,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        today: date | None = None,
        retry_base_delay: float = 1.0,
    ) -> None:
        """설정을 주입받는다. transport/today/retry_base_delay는 테스트용이다."""
        super().__init__(fetcher=fetcher)  # type: ignore[arg-type]  # API Spider는 fetcher를 쓰지 않는다
        self._settings = settings or get_settings()
        self._transport = transport
        self._today = today
        self._retry_base_delay = retry_base_delay
        # 포털에서 Encoding 키(%2B 등 포함)를 붙여넣어도 동작하도록 한 번 풀어 준다.
        # (httpx가 요청 시 다시 인코딩하므로, 풀지 않으면 이중 인코딩되어 인증 실패가 난다.)
        self._key = unquote(self._settings.applyhome_api_key.strip())

    # ---- BaseSpider 추상 메서드: API 방식이라 사용하지 않는다 ----
    async def target_urls(self) -> list[str]:
        """HTML 페이지를 쓰지 않으므로 빈 목록."""
        return []

    def parse(self, html: str, source_url: str) -> list[ProjectData]:
        """HTML 파싱을 쓰지 않으므로 빈 목록."""
        return []

    # ---- 수집 ----
    async def collect(self) -> list[ProjectData]:
        """최근 lookback_days일 이내 모집공고를 API로 수집해 ProjectData 목록으로 돌려준다."""
        if not self._key:
            self._logger.error("청약홈 서비스 키(APPLYHOME_API_KEY)가 비어 있어 수집을 건너뜁니다")
            return []

        today = self._today or datetime.now(_KST).date()
        since = today - timedelta(days=self._settings.applyhome_lookback_days)
        self._logger.info(f"청약홈 수집 시작: 모집공고일 {since.isoformat()} 이후")

        semaphore = asyncio.Semaphore(self._settings.applyhome_unit_concurrency)
        items: list[ProjectData] = []
        async with httpx.AsyncClient(
            timeout=self._settings.request_timeout_seconds, transport=self._transport
        ) as client:
            for kind, (detail_op, model_op) in _KINDS.items():
                try:
                    rows = await self._fetch_details(client, detail_op, since)
                except ApplyhomeApiError as exc:
                    self._logger.error(f"청약홈 {kind} 조회 실패: {exc}")
                    continue
                self._logger.success(f"청약홈 {kind}: 공고 {len(rows)}건 조회")

                unit_lists = await asyncio.gather(
                    *(self._fetch_units(client, model_op, row, semaphore) for row in rows)
                )
                for row, units in zip(rows, unit_lists):
                    try:
                        item = self._to_project(kind, row, units, today)
                    except Exception as exc:  # noqa: BLE001 - 한 건의 이상 데이터가 전체를 막지 않게 격리
                        self._logger.error(f"청약홈 {kind} 변환 실패({type(exc).__name__}) — 건너뜀")
                        continue
                    if item is not None:
                        items.append(item)
        return items

    # ---- API 호출 ----
    async def _get_json(
        self, client: httpx.AsyncClient, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """오퍼레이션 1회 호출(실패 시 최대 3회 시도). 예외 메시지에 주소/키가 없도록 가공한다."""
        query = {**params, "serviceKey": self._key, "returnType": "JSON"}
        reason = "알 수 없는 오류"
        for attempt in range(3):
            try:
                response = await client.get(f"{self._settings.applyhome_base_url}/{operation}", params=query)
            except httpx.HTTPError as exc:
                reason = f"네트워크 오류({type(exc).__name__})"
            else:
                if response.status_code == 200:
                    try:
                        body = response.json()
                    except ValueError:
                        reason = "응답이 JSON이 아님"
                    else:
                        if isinstance(body, dict):
                            return body
                        reason = "응답 형식이 예상과 다름"
                elif response.status_code == 401:
                    raise ApplyhomeApiError(operation, "인증 실패(401) — 서비스 키를 확인하세요")
                else:
                    reason = f"HTTP {response.status_code}"
            if attempt < 2:
                await asyncio.sleep(self._retry_base_delay * (2**attempt))
        raise ApplyhomeApiError(operation, reason)

    async def _fetch_details(
        self, client: httpx.AsyncClient, operation: str, since: date
    ) -> list[dict[str, Any]]:
        """모집공고일이 since 이상인 공고 상세를 페이지를 넘기며 전부 가져온다."""
        per_page = self._settings.applyhome_per_page
        rows: list[dict[str, Any]] = []
        for page in range(1, _MAX_PAGES + 1):
            body = await self._get_json(
                client,
                operation,
                {
                    "page": page,
                    "perPage": per_page,
                    "cond[RCRIT_PBLANC_DE::GTE]": since.isoformat(),
                },
            )
            data = body.get("data") or []
            rows.extend(row for row in data if isinstance(row, dict))
            match_count = body.get("matchCount")
            if len(data) < per_page or (isinstance(match_count, int) and len(rows) >= match_count):
                break
        return rows

    async def _fetch_units(
        self,
        client: httpx.AsyncClient,
        operation: str,
        row: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> list[UnitTypeData]:
        """공고 1건의 주택형별(가격/면적) 정보를 가져온다. 실패하면 빈 목록(가격만 빠짐)."""
        house_manage_no = _text(_get(row, "house_manage_no"))
        pblanc_no = _text(_get(row, "pblanc_no"))
        if not house_manage_no or not pblanc_no:
            return []
        async with semaphore:
            try:
                body = await self._get_json(
                    client,
                    operation,
                    {
                        "page": 1,
                        "perPage": 100,
                        "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
                        "cond[PBLANC_NO::EQ]": pblanc_no,
                    },
                )
            except ApplyhomeApiError as exc:
                self._logger.warning(f"주택형별 조회 실패(가격 없이 진행): {exc}")
                return []

        units: list[UnitTypeData] = []
        for model in body.get("data") or []:
            if not isinstance(model, dict):
                continue
            amount = _digits(_get(model, "lttot_top_amount") or _get(model, "suply_amount"))
            area = _to_float(_get(model, "excluse_ar")) or _leading_number(_get(model, "house_ty"))
            if not amount and area is None:
                continue
            units.append(
                UnitTypeData(
                    raw_type=_text(_get(model, "house_ty")) or _text(_get(model, "model_no")) or "-",
                    area_sqm=area,
                    price_text=f"{amount}만원" if amount else None,
                )
            )
        return units

    # ---- 변환 ----
    def _to_project(
        self, kind: str, row: dict[str, Any], units: list[UnitTypeData], today: date
    ) -> ProjectData | None:
        """API 응답 1행을 ProjectData로 변환한다. 필수값(현장명/주소)이 없으면 None."""
        title = _text(_get(row, "house_nm"))
        address = _text(_get(row, "hssply_adres")) or _text(_get(row, "hssply_hshldco"))
        if not title or not address:
            return None

        parts = address.split()
        city = parts[0] if parts else (_text(_get(row, "subscrpt_area_code_nm")) or "")
        district = parts[1] if len(parts) > 1 else ""

        house_manage_no = _text(_get(row, "house_manage_no")) or ""
        pblanc_no = _text(_get(row, "pblanc_no")) or ""
        source_url = _text(_get(row, "pblanc_url")) or (
            f"applyhome://{kind}/{house_manage_no}/{pblanc_no}"
        )

        if kind == "apt":
            raw_type = "아파트"
            subscription_start = _to_date(_get(row, "rcept_bgnde"))
            subscription_end = _to_date(_get(row, "rcept_endde"))
            builder_name = _text(_get(row, "cnstrct_entrps_nm"))
        else:
            code = _text(_get(row, "search_house_secd")) or ""
            raw_type = (
                _URBTY_TYPE_BY_CODE.get(code) or _text(_get(row, "house_dtl_secd_nm")) or "미확인"
            )
            subscription_start = _to_date(_get(row, "subscrpt_rcept_bgnde"))
            subscription_end = _to_date(_get(row, "subscrpt_rcept_endde"))
            builder_name = None  # 오피스텔류 응답에는 시공사 항목이 없다(시행사는 시공사가 아님)

        contract_end = _to_date(_get(row, "cntrct_cncls_endde"))
        raw_status = _compute_status(today, subscription_start, contract_end or subscription_end)

        return ProjectData(
            title=title,
            address=address,
            city=city,
            district=district,
            phone=_format_phone(_get(row, "mdhs_telno")),
            builder_name=builder_name,
            raw_type=raw_type,
            raw_status=raw_status,
            supply_count=_to_int(_get(row, "tot_suply_hshldco")),
            move_in_date=_month_end(_get(row, "mvn_prearnge_ym")),
            subscription_date=subscription_start,
            description=_build_description(row, subscription_start, subscription_end, contract_end),
            unit_types=units,
            source_url=source_url,
            spider_name=self.name,
        )


# ---------------------------------------------------------------- 값 변환 도우미
def _get(row: dict[str, Any], key: str) -> Any:
    """응답 키는 대문자(HOUSE_NM)로 오므로 대소문자 구분 없이 꺼낸다."""
    if key in row:
        return row[key]
    return row.get(key.upper())


def _text(value: Any) -> str | None:
    """공백 제거. 비어 있거나 '-'면 None."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ("", "-") else text


def _digits(value: Any) -> str | None:
    """'80,720' 같은 금액 문자열에서 쉼표를 빼 숫자만 남긴다. 0이거나 숫자가 아니면 None."""
    text = _text(value)
    if text is None:
        return None
    cleaned = text.replace(",", "")
    return cleaned if cleaned.isdigit() and int(cleaned) > 0 else None


def _to_int(value: Any) -> int | None:
    text = _text(value)
    if text is None:
        return None
    cleaned = text.replace(",", "")
    return int(cleaned) if cleaned.isdigit() else None


def _to_float(value: Any) -> float | None:
    text = _text(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    return number if number > 0 else None


def _leading_number(value: Any) -> float | None:
    """'058.8500A' 같은 주택형 표기 앞부분의 숫자(전용면적, ㎡)를 읽는다."""
    text = _text(value)
    if text is None:
        return None
    match = re.match(r"\s*(\d+(?:\.\d+)?)", text)
    if match is None:
        return None
    number = float(match.group(1))
    return number if number > 0 else None


def _to_date(value: Any) -> date | None:
    """'2022-05-23' 또는 '20220523' 형식을 date로 변환한다. 해석 불가면 None."""
    text = _text(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _month_end(value: Any) -> date | None:
    """입주예정월 '202502' → 그 달의 마지막 날(2025-02-28). 해석 불가면 None."""
    text = _text(value)
    if text is None or not re.fullmatch(r"\d{6}", text):
        return None
    year, month = int(text[:4]), int(text[4:])
    if not 1 <= month <= 12:
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


def _format_phone(value: Any) -> str | None:
    """'16684888' → '1668-4888', '0234520100' → '02-3452-0100'. 모르는 형식은 숫자만 돌려준다."""
    digits = re.sub(r"\D", "", _text(value) or "")
    if not digits:
        return None
    if len(digits) == 8 and digits.startswith("1"):
        return f"{digits[:4]}-{digits[4:]}"
    if digits.startswith("02") and len(digits) in (9, 10):
        return f"02-{digits[2:-4]}-{digits[-4:]}"
    if digits.startswith("0") and len(digits) in (10, 11):
        return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"
    return digits


def _compute_status(today: date, start: date | None, end: date | None) -> str | None:
    """날짜로 분양 상태를 계산한다(청약홈 응답에는 상태 항목이 없다).

    청약 접수 전 = 분양예정 / 접수 시작 ~ 계약(또는 접수) 종료 = 분양중 / 그 후 = 분양완료.
    접수 시작일을 모르면 None(홈해버 서버 기본값 '분양예정'이 적용된다).
    """
    if start is None:
        return None
    if today < start:
        return "분양예정"
    if end is not None and today > end:
        return "분양완료"
    return "분양중"


def _build_description(
    row: dict[str, Any],
    subscription_start: date | None,
    subscription_end: date | None,
    contract_end: date | None,
) -> str | None:
    """일정/시행사/홈페이지를 짧은 소개 문구로 만든다. 값이 없는 줄은 뺀다."""
    lines: list[str] = []
    announced = _to_date(_get(row, "rcrit_pblanc_de"))
    if announced:
        lines.append(f"모집공고일: {announced.isoformat()}")
    if subscription_start:
        end = f" ~ {subscription_end.isoformat()}" if subscription_end else ""
        lines.append(f"청약접수: {subscription_start.isoformat()}{end}")
    winner = _to_date(_get(row, "przwner_presnatn_de"))
    if winner:
        lines.append(f"당첨자 발표: {winner.isoformat()}")
    contract_start = _to_date(_get(row, "cntrct_cncls_bgnde"))
    if contract_start:
        end = f" ~ {contract_end.isoformat()}" if contract_end else ""
        lines.append(f"계약: {contract_start.isoformat()}{end}")
    developer = _text(_get(row, "bsns_mby_nm"))
    if developer:
        lines.append(f"시행사: {developer}")
    homepage = _text(_get(row, "hmpg_adres"))
    if homepage:
        lines.append(f"홈페이지: {homepage}")
    return "\n".join(lines) if lines else None
