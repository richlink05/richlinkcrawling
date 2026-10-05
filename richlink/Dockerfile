FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

# Playwright + Chromium 및 필요한 시스템 의존성 설치 (크롤링용)
RUN playwright install --with-deps chromium

EXPOSE 8000

# Railway 등 PaaS는 PORT 환경변수로 실제 사용할 포트를 지정해준다.
# 로컬(docker-compose)처럼 PORT가 없는 환경에서는 8000번을 기본값으로 쓴다.
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
