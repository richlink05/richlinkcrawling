"""어드민 API 인증.

어드민 화면/API는 인터넷에 공개되는 주소에 떠 있기 때문에, 아무나 데이터를
보거나 지우지 못하도록 아주 간단한 토큰 인증을 건다. 환경변수 ADMIN_TOKEN과
요청 헤더 `X-Admin-Token` 값이 일치해야만 통과한다.

ADMIN_TOKEN을 아예 설정하지 않았다면(빈 문자열), 실수로 누구나 접근 가능한
상태로 배포되는 사고를 막기 위해 모든 요청을 거부한다.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from backend.config.settings import get_settings


async def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """FastAPI Depends로 라우터 전체에 거는 인증 체크."""
    settings = get_settings()
    if not settings.admin_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ADMIN_TOKEN 환경변수가 설정되지 않아 어드민 기능을 쓸 수 없습니다.",
        )
    if x_admin_token != settings.admin_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 올바르지 않습니다.")
