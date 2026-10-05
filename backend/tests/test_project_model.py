"""Project 데이터 모델 및 Repository 정의 검증 테스트.

실제 DB 연결 없이도 검증 가능하도록 SQLAlchemy 메타데이터 레벨에서 확인한다.
"""
from backend.models.base import Base
from backend.models.enums import ImageCategory, ListingStatus, PropertyType, SubmissionStatus
from backend.models.repository import BaseRepository, ProjectRepository


class TestProjectTableSchema:
    """projects 테이블 스키마를 검증한다."""

    def test_project_table_registered(self) -> None:
        """Project 모델이 Base.metadata에 등록되어 있는지 확인한다."""
        assert "projects" in Base.metadata.tables

    def test_project_required_columns_exist(self) -> None:
        """새 아키텍처에 필요한 컬럼이 모두 존재하는지 확인한다."""
        columns = set(Base.metadata.tables["projects"].columns.keys())
        expected = {
            "id", "title", "address", "city", "district", "lat", "lng", "phone",
            "builder_name", "raw_type", "mapped_type", "raw_status", "mapped_status",
            "price_min", "price_max", "area_min", "area_max",
            "submission_status", "submitted_at", "attempt_count",
            "homehaver_listing_id", "last_error", "thumbnail_url",
            "created_at", "updated_at",
        }
        assert expected.issubset(columns)

    def test_related_tables_registered(self) -> None:
        """이미지/출처 테이블이 함께 등록되는지 확인한다."""
        tables = Base.metadata.tables
        for name in ("project_images", "project_sources"):
            assert name in tables

    def test_project_source_has_unique_url_constraint(self) -> None:
        """(project_id, source_url) 유니크 제약으로 같은 페이지 중복 수집이 방지되는지 확인한다."""
        table = Base.metadata.tables["project_sources"]
        unique_column_sets = {
            tuple(sorted(c.name for c in constraint.columns))
            for constraint in table.constraints
            if hasattr(constraint, "columns")
        }
        assert tuple(sorted(("project_id", "source_url"))) in unique_column_sets


class TestEnums:
    """Enum이 홈해버 API 계약을 정확히 반영하는지 검증한다."""

    def test_property_type_matches_homehaver_contract(self) -> None:
        """홈해버가 허용하는 5개 분양 유형과 정확히 일치하는지 확인한다."""
        values = {t.value for t in PropertyType}
        assert values == {"아파트", "오피스텔", "생활형숙박시설", "지식산업센터", "상가"}

    def test_listing_status_matches_homehaver_contract(self) -> None:
        """홈해버가 허용하는 3개 상태값과 정확히 일치하는지 확인한다."""
        values = {s.value for s in ListingStatus}
        assert values == {"분양예정", "분양중", "마감"}

    def test_image_category_matches_homehaver_contract(self) -> None:
        """홈해버 listing_images.category가 허용하는 3개 값과 일치하는지 확인한다."""
        values = {c.value for c in ImageCategory}
        assert values == {"썸네일", "평면도", "인프라"}

    def test_submission_status_has_four_states(self) -> None:
        """내부 전송 상태(대기/성공/실패/건너뜀)가 모두 정의되어 있는지 확인한다."""
        values = {s.value for s in SubmissionStatus}
        assert values == {"pending", "success", "failed", "skipped"}


class TestRepository:
    """Repository 패턴 구현을 검증한다."""

    def test_project_repository_bound_to_project_model(self) -> None:
        """ProjectRepository.model이 Project 모델로 지정되어 있는지 확인한다."""
        from backend.models.project import Project

        assert ProjectRepository.model is Project

    def test_project_repository_is_base_repository_subclass(self) -> None:
        """ProjectRepository가 BaseRepository를 상속하는지 확인한다."""
        assert issubclass(ProjectRepository, BaseRepository)

    def test_project_repository_has_expected_query_methods(self) -> None:
        """중복/재전송 판단에 쓰는 조회 메서드가 존재하는지 확인한다."""
        assert hasattr(ProjectRepository, "find_by_source_url")
        assert hasattr(ProjectRepository, "find_candidates_for_dedup")
        assert hasattr(ProjectRepository, "list_by_submission_status")
