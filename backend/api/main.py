"""FastAPI 애플리케이션 진입점.

uvicorn backend.api.main:app --reload 로 로컬 실행한다.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from backend.admin.router import router as admin_router

app = FastAPI(title="RichLink Admin API", version="0.1.0")
app.include_router(admin_router)

_ADMIN_STATIC_DIR = Path(__file__).resolve().parent.parent / "admin" / "static"


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """헬스체크 엔드포인트 (Docker/로드밸런서 상태 확인용)."""
    return {"status": "ok"}


@app.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    """어드민 화면(HTML). 데이터 조회 자체는 화면 안에서 토큰을 입력해야 된다."""
    return FileResponse(_ADMIN_STATIC_DIR / "index.html")
