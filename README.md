# RichLink

전국 분양정보(아파트 / 오피스텔 / 생활형숙박시설 / 지식산업센터 / 상가)를
건설사·시행사·분양대행사·공식 분양 홈페이지·청약정보 사이트·뉴스로부터
자동으로 수집해서, **홈해버(homehaber.com)의 등록 API로 전달하는** 백엔드.

## 아키텍처 (2026-10 확정)

RichLink는 홈해버 DB에 절대 직접 연결하지 않는다. 대신:

```
[크롤링] → [RichLink 자신의 수집함(staging) DB] → [홈해버 등록 API] → [홈해버 관리자 승인] → 노출
                      ↑ 여기서만
                 "이미 아는 현장인지" 비교
```

1. **수집**: Spider가 각 사이트를 크롤링해서 분양현장 정보를 모은다.
2. **중복 판단**: RichLink 자신의 수집함 DB(홈해버 DB와 별개의 Supabase 프로젝트) 안에서만
   비교한다 — 정확히 같은 페이지를 또 크롤링한 경우, 그리고 이름+주소+좌표+전화번호
   유사도 90% 이상인 경우를 "이미 아는 현장"으로 본다. 이미 전송 성공한 건 다시 안 보내고,
   실패했거나 처음 보는 건만 전송 대상이 된다. 정보가 바뀌어도 업데이트하지 않는다
   (RichLink의 역할은 "보낼지 말지"만 판단하는 것).
3. **전송**: 비밀 토큰을 들고 홈해버의 `POST /api/crawler/listings`를 호출한다 (직접 DB 접속 아님).
   좌표(lat/lng)는 모르면 아예 안 보내고, 홈해버 서버가 주소로 카카오 지오코딩을 자동으로 해준다.
4. **승인**: 전송된 데이터는 홈해버 관리자가 직접 확인 후 승인해야 실제로 노출된다
   (현장근무이행각서 확인 등 기존 검증 절차는 그대로 유지됨). 같은 현장이 서로 다른
   사이트에서 수집돼 중복으로 전송되더라도, 이 승인 단계에서 관리자가 거절할 수 있다.

## 진행 단계

- [x] 1단계 — 프로젝트 구조 생성
- [x] 2단계 — DB 설계 (RichLink 자신의 수집함 스키마)
- [x] 3단계 — BaseSpider 작성 (수집 전담, 저장/전송은 SubmissionService로 분리)
- [x] 4단계 — Lotte Spider 작성
- [x] 5단계 — Playwright 공통 모듈 작성
- [x] 6단계 — ~~이미지 저장 모듈~~ → 이미지는 다운로드하지 않고 URL만 전달 (불필요해짐)
- [x] 7단계 — 중복 판단 엔진 (RichLink 수집함 내부 비교 전용으로 축소)
- [x] 8단계 — 주기 실행 (GitHub Actions 주 1회, Celery는 선택 사항)
- [x] 9단계 — FastAPI Admin (조회/삭제/재시도 — 승인 기능은 홈해버 쪽에 있음)
- [x] 10단계 — Docker 배포 / Railway 배포

## 폴더 구조

```
richlink/
├── pyproject.toml
├── .env.example
├── backend/
│   ├── spiders/              # 사이트별 Spider 구현체
│   │   ├── builders/         # 건설사(롯데, GS, 자이, 푸르지오, 힐스테이트, 한화, 대우 등)
│   │   ├── agencies/         # 분양대행사
│   │   ├── subscription/     # 청약정보 사이트
│   │   ├── news/             # 뉴스
│   │   └── registry.py       # 등록된 Spider 목록 + collect_all()
│   ├── base/                 # BaseSpider, Pydantic 스키마
│   ├── services/
│   │   ├── submission_service.py   # 수집→중복판단→저장→전송 오케스트레이션
│   │   ├── duplicate_service.py    # RichLink 수집함 내부 유사도 비교
│   │   ├── homehaver_client.py     # 홈해버 등록 API 호출
│   │   ├── homehaver_payload.py    # Project → 홈해버 API 요청 JSON 변환
│   │   └── admin_service.py
│   ├── models/                # SQLAlchemy ORM 모델(RichLink 수집함 전용) + Repository
│   ├── api/                   # FastAPI 앱 진입점
│   ├── admin/                 # FastAPI Admin 라우터
│   ├── scheduler/
│   │   ├── run_once.py        # GitHub Actions가 호출하는 진입점 (기본 운영 방식)
│   │   ├── celery_app.py      # Celery Beat (선택 사항)
│   │   └── tasks.py
│   ├── utils/                 # 로거, 가격/면적 파싱, type/status 매핑 등
│   ├── config/                 # 환경설정 (Pydantic Settings)
│   └── tests/                  # pytest 테스트
└── migrations/                 # Alembic (RichLink 수집함 DB 전용)
```

## 개발 환경 준비

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
```

`.env`에 최소 아래 두 가지를 채워야 한다:
- `DATABASE_URL`: RichLink 자신의 Supabase 프로젝트 (홈해버 DB와 별개)
- `HOMEHAVER_API_TOKEN`: 홈해버가 발급한 비밀 토큰

## 테스트 실행

```bash
pytest -v
```

## 로컬에서 한 번 실행해보기

```bash
alembic upgrade head              # RichLink 수집함 DB에 테이블 생성 (최초 1회)
python -m backend.scheduler.run_once   # 수집 + 전송을 한 번 실행
```

## 운영 방식 — GitHub Actions + Supabase + Railway

서버를 직접 띄워두지 않는 서버리스 구조. Celery / Redis는 쓰지 않아도 된다.

1. **RichLink 전용 Supabase 프로젝트**를 새로 만든다 (홈해버가 쓰는 프로젝트와는 별개).
   Project Settings → Database에서 연결 문자열을 복사해 `postgresql+asyncpg://` 형식으로
   바꾸고 끝에 `?ssl=require`를 붙인다.
2. 로컬에서 딱 한 번, 그 연결 문자열로 `alembic upgrade head`를 실행해 테이블을 만든다
   (또는 GitHub Actions의 `DB 마이그레이션 적용` 워크플로를 수동 실행해도 된다).
3. GitHub 저장소 → Settings → Secrets and variables → Actions 에서 등록:
   - `DATABASE_URL` — 1번에서 만든 RichLink 전용 Supabase 연결 문자열
   - `HOMEHAVER_API_URL` — `https://www.homehaber.com/api/crawler/listings`
   - `HOMEHAVER_API_TOKEN` — 홈해버가 발급한 비밀 토큰
4. `.github/workflows/collect.yml`이 **매주 월요일 03:00(KST)**에 자동으로 수집+전송을
   실행한다. Actions 탭의 "Run workflow" 버튼으로 수동 실행도 가능하다.
5. 수집 현황을 확인/삭제/재시도하는 FastAPI Admin은 Railway에 올린다 — 이 저장소의
   `Dockerfile`을 그대로 쓰면 되고, Railway에도 `DATABASE_URL` / `HOMEHAVER_API_URL` /
   `HOMEHAVER_API_TOKEN` 세 가지를 동일하게 환경변수로 등록하면 된다. "재시도" 기능이
   내부적으로 홈해버 API를 다시 호출하기 때문에 Admin API에도 토큰이 필요하다.
