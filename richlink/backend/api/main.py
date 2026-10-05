"""FastAPI 애플리케이션 진입점.

uvicorn backend.api.main:app --reload 로 로컬 실행한다.
"""
from __future__ import annotations

from fastapi import FastAPI

from backend.admin.router import router as admin_router

app = FastAPI(title="RichLink Admin API", version="0.1.0")
app.include_router(admin_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """헬스체크 엔드포인트 (Docker/로드밸런서 상태 확인용)."""
    return {"status": "ok"}
