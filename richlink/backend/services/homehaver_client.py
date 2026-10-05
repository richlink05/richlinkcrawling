"""홈해버 등록 API(POST /api/crawler/listings) 호출 클라이언트.

중요: RichLink는 홈해버 Supabase DB에 절대 직접 연결하지 않는다. 오직 이
클라이언트를 통해 비밀 토큰을 들고 홈해버가 제공한 Next.js API만 호출한다.

홈해버 쪽 계약(2026-10 확인):
- POST https://www.homehaber.com/api/crawler/listings
- 헤더: Authorization: Bearer {HOMEHAVER_API_TOKEN}
- 바디: {"listings": [...]} 최대 50건/요청
- 응답(200): {"ok": true, "total": N, "inserted": N, "failed": N,
              "results": [{"client_ref": "...", "success": bool,
                            "listing_id"?: "...", "error"?: "..."}]}
- 인증 실패: 401 {"ok": false, "error": "Unauthorized"}
- 요청 형식 오류: 400 {"ok": false, "error": "...", "details": {...}}
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from backend.config.settings import Settings, get_settings
from backend.utils.logger import get_logger

logger = get_logger("homehaver_client")


@dataclass
class SubmissionResult:
    """홈해버 API가 응답한 건별 결과 1개."""

    client_ref: str
    success: bool
    listing_id: str | None = None
    error: str | None = None


class HomehaverApiError(Exception):
    """배치 전체가 실패했을 때(네트워크 오류, 401, 400 등) 발생시키는 예외.

    이 경우 그 배치에 포함된 모든 건을 호출부가 FAILED로 기록하고 다음
    주기에 재시도하게 한다.
    """


class HomehaverApiClient:
    """홈해버 크롤러 등록 API를 호출하는 클라이언트."""

    def __init__(self, settings: Settings | None = None) -> None:
        """설정(토큰/URL/배치 크기)을 주입받는다."""
        self._settings = settings or get_settings()

    async def submit_batch(self, payloads: list[dict]) -> list[SubmissionResult]:
        """최대 homehaver_api_batch_size건씩 나누어 전송하고 건별 결과를 모아 반환한다.

        배치 하나가 통째로 실패(네트워크 오류/인증 오류/요청 형식 오류)하면
        HomehaverApiError를 발생시키지 않고, 그 배치의 모든 client_ref를
        success=False로 채운 SubmissionResult로 변환해 반환한다 — 호출부가
        예외 처리 없이 건별로 FAILED 기록을 남길 수 있게 하기 위해서다.
        """
        if not payloads:
            return []

        batch_size = self._settings.homehaver_api_batch_size
        results: list[SubmissionResult] = []
        for start in range(0, len(payloads), batch_size):
            chunk = payloads[start : start + batch_size]
            results.extend(await self._submit_chunk(chunk))
        return results

    async def _submit_chunk(self, chunk: list[dict]) -> list[SubmissionResult]:
        """한 번의 HTTP 요청(최대 batch_size건)을 보낸다."""
        client_refs = [item["client_ref"] for item in chunk]
        headers = {
            "Authorization": f"Bearer {self._settings.homehaver_api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.homehaver_api_timeout_seconds
            ) as client:
                response = await client.post(
                    self._settings.homehaver_api_url,
                    headers=headers,
                    json={"listings": chunk},
                )
        except httpx.HTTPError as exc:
            logger.error(f"홈해버 API 요청 자체가 실패함(네트워크 오류): {exc}")
            return [
                SubmissionResult(client_ref=ref, success=False, error=f"네트워크 오류: {exc}")
                for ref in client_refs
            ]

        if response.status_code == 401:
            logger.error("홈해버 API 인증 실패(401) — 토큰이 잘못되었거나 만료됨")
            return [
                SubmissionResult(client_ref=ref, success=False, error="인증 실패(토큰 확인 필요)")
                for ref in client_refs
            ]

        if response.status_code >= 400:
            error_detail = _safe_extract_error(response)
            logger.error(f"홈해버 API 요청 오류({response.status_code}): {error_detail}")
            return [
                SubmissionResult(client_ref=ref, success=False, error=error_detail)
                for ref in client_refs
            ]

        body = response.json()
        logger.success(
            f"홈해버 API 전송 완료: 총 {body.get('total')}건 중 성공 {body.get('inserted')}건, "
            f"실패 {body.get('failed')}건"
        )
        return [
            SubmissionResult(
                client_ref=item["client_ref"],
                success=item["success"],
                listing_id=item.get("listing_id"),
                error=item.get("error"),
            )
            for item in body.get("results", [])
        ]


def _safe_extract_error(response: httpx.Response) -> str:
    """응답 바디가 JSON이 아니어도 에러 메시지 추출이 깨지지 않게 한다."""
    try:
        body = response.json()
        return str(body.get("error", body))
    except ValueError:
        return response.text[:500]
