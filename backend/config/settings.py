"""애플리케이션 전역 설정.

모든 설정값은 환경변수(.env)에서 로드하며, 하드코딩을 금지한다.
Settings는 애플리케이션 전체에서 의존성 주입을 통해 사용된다.

아키텍처 변경(2026-10): RichLink는 더 이상 홈해버 DB에 직접 쓰지 않는다.
- database_url: RichLink 자신의 "수집함(staging)" DB. 홈해버 DB와는 완전히 별개의
  Supabase 프로젝트를 가리켜야 한다.
- homehaver_api_url / homehaver_api_token: 홈해버가 제공한 Next.js API
  (POST /api/crawler/listings)에 등록 요청을 보낼 때 사용한다. 직접 DB에 접속하지
  않는다.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수로부터 로드되는 애플리케이션 설정.

    각 필드는 .env 파일 또는 실제 환경변수에서 값을 읽는다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["local", "dev", "staging", "prod"] = Field(default="local")
    app_debug: bool = Field(default=True)

    # Database — RichLink 자신의 수집함(staging) DB. 홈해버 DB와 별개여야 한다.
    database_url: str = Field(
        default="postgresql+asyncpg://richlink:richlink@localhost:5432/richlink"
    )
    database_echo: bool = Field(default=False)

    # Redis — Celery로 셀프 호스팅할 때만 쓰는 선택 항목 (기본 운영 방식인
    # GitHub Actions만 쓴다면 설정하지 않아도 된다)
    redis_url: str = Field(default="redis://localhost:6379/0")

    # 홈해버 등록 API (직접 DB 접속 대신 이 API를 통해서만 데이터를 전달한다)
    homehaver_api_url: str = Field(default="https://www.homehaber.com/api/crawler/listings")
    homehaver_api_token: str = Field(default="")
    homehaver_api_batch_size: int = Field(default=50)
    homehaver_api_timeout_seconds: int = Field(default=30)

    # 청약홈(한국부동산원) 분양정보 OpenAPI — 공공데이터포털에서 발급받은 일반 인증키.
    # 요청 주소에 포함되는 비밀값이므로 로그에 남기지 않는다(GitHub Secrets에만 보관).
    applyhome_api_key: str = Field(default="")
    applyhome_base_url: str = Field(default="https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1")
    applyhome_lookback_days: int = Field(default=30)  # 모집공고일이 오늘-N일 이후인 공고만 수집
    applyhome_per_page: int = Field(default=100)
    applyhome_unit_concurrency: int = Field(default=5)  # 주택형별(가격) 조회 동시 호출 수

    # 이번 실행에서 돌릴 Spider 이름(쉼표 구분, 예: "applyhome" 또는 "applyhome,lotte").
    # "all"이면 등록된 전부를 돌린다. GitHub Actions 수동 실행 화면에서 고를 수 있다.
    enabled_spiders: str = Field(default="applyhome")

    # 어드민 화면/API 보호용 토큰. 인터넷에 공개되는 주소라서, 이 값과 요청의
    # X-Admin-Token 헤더가 일치해야만 어드민 API를 쓸 수 있다. 비워두면(기본값)
    # 안전을 위해 어드민 API 자체를 막는다.
    admin_token: str = Field(default="")

    # Crawling
    max_concurrent_spiders: int = Field(default=20)
    request_timeout_seconds: int = Field(default=30)
    playwright_headless: bool = Field(default=True)

    @field_validator("homehaver_api_url", mode="before")
    @classmethod
    def _clean_homehaver_url(cls, value: object) -> object:
        """GitHub Secret이 비어 있거나 앞뒤 공백/따옴표가 섞여 들어와도 기본 주소로 안전하게 동작시킨다."""
        if value is None:
            return value
        cleaned = str(value).strip().strip("\"'").strip()
        return cleaned or "https://www.homehaber.com/api/crawler/listings"

    @field_validator("homehaver_api_token", "applyhome_api_key", mode="before")
    @classmethod
    def _strip_secret(cls, value: object) -> object:
        """비밀값 앞뒤의 공백/줄바꿈(붙여넣기 실수)을 제거한다."""
        return value.strip() if isinstance(value, str) else value

    # Duplicate detection — RichLink 자신의 수집함 DB 내부에서만 비교한다.
    duplicate_similarity_threshold: float = Field(default=0.90)


@lru_cache
def get_settings() -> Settings:
    """설정 객체를 싱글턴으로 반환한다.

    lru_cache를 사용하여 프로세스 내에서 단 한 번만 .env를 파싱하도록 한다.
    FastAPI의 Depends(get_settings)로 의존성 주입에 사용된다.
    """
    return Settings()
