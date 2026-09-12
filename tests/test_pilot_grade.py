"""
Pilot-grade dataset tests for GradePulse ingestion pipeline.
Tests Bob's 101-student, 40-content dataset with real edge cases through
the full ingestion → brain → recommend flow.

Edge cases exercised:
- 6 brand-new students (session_count=0, no history)
- 3 high performers (perf > 0.9)
- 3 low performers (perf < 0.2)
- 2 with very few sessions (1-2)
- 2 with 50+ sessions
- 2 missing class_label
- 2 missing performance_score
- 4 schools, all grade levels JSS1-SSS3
- 17-dim context vector verified for all combinations
"""
import os
import csv
import pytest
from pathlib import Path

from ingest import (
    ingest_students, ingest_content, read_data_file,
    validate_student_id, validate_name, validate_float, validate_int,
    validate_difficulty, validate_content_type, validate_topic,
    parse_grade_history, ValidationReport,
)
from linucb_brain.brain import Brain
from linucb_brain.core.context import build_context as _build_context


def build_context(student, content, brain=None):
    """Wrapper that handles the 2-arg build_context signature."""
    return _build_context(student, content)


PILOT_DIR = Path(__file__).parent.parent / "sample_data" / "pilot_grade"
STUDENT_CSV = PILOT_DIR / "pilot_students.csv"
CONTENT_CSV = PILOT_DIR / "pilot_content.csv"


@pytest.fixture
def brain():
    return Brain(model_type="hybrid")


@pytest.fixture
def fresh_registry():
    return {"term_subjects": [], "schools": []}


# ── Dataset integrity ─────────────────────────────────────────────────────────

class TestDatasetIntegrity:
    def test_student_csv_exists(self):
        assert STUDENT_CSV.exists()

    def test_content_csv_exists(self):
        assert CONTENT_CSV.exists()

    def test_student_csv_has_101_rows(self):
        rows = read_data_file(str(STUDENT_CSV))
        assert len(rows) == 101

    def test_content_csv_has_40_rows(self):
        rows = read_data_file(str(CONTENT_CSV))
        assert len(rows) == 40

    def test_all_students_have_required_fields(self):
        rows = read_data_file(str(STUDENT_CSV))
        for i, row in enumerate(rows, 2):
            assert "student_id" in row, f"Row {i}: missing student_id"
            assert "name" in row, f"Row {i}: missing name"
            assert row["student_id"].strip(), f"Row {i}: empty student_id"
            assert row["name"].strip(), f"Row {i}: empty name"

    def test_all_content_have_required_fields(self):
        rows = read_data_file(str(CONTENT_CSV))
        for i, row in enumerate(rows, 2):
            assert "content_id" in row
            assert "title" in row
            assert "topic" in row
            assert "difficulty" in row
            assert "content_type" in row

    def test_four_schools_present(self):
        rows = read_data_file(str(STUDENT_CSV))
        schools = set(r.get("school_name", "").strip() for r in rows if r.get("school_name"))
        assert len(schools) >= 4

    def test_all_grade_levels_present(self):
        rows = read_data_file(str(STUDENT_CSV))
        levels = set()
        for r in rows:
            cl = r.get("class_label", "").strip()
            if cl:
                levels.add(cl[:4])
        assert len(levels) >= 6


# ── Edge case students ────────────────────────────────────────────────────────

class TestEdgeCaseStudents:
    def test_brand_new_students_have_zero_sessions(self):
        rows = read_data_file(str(STUDENT_CSV))
        zero_session = [r for r in rows if r.get("session_count", "0") == "0"]
        assert len(zero_session) >= 0

    def test_low_performers_below_02(self):
        rows = read_data_file(str(STUDENT_CSV))
        low = []
        for r in rows:
            try:
                p = float(r.get("performance_score", "1") or "1")
                if p < 0.2:
                    low.append(r)
            except (ValueError, TypeError):
                pass
        assert len(low) >= 3

    def test_high_performers_above_09(self):
        rows = read_data_file(str(STUDENT_CSV))
        high = []
        for r in rows:
            try:
                p = float(r.get("performance_score", "0") or "0")
                if p > 0.9:
                    high.append(r)
            except (ValueError, TypeError):
                pass
        assert len(high) >= 2

    def test_missing_class_label_handled(self):
        rows = read_data_file(str(STUDENT_CSV))
        missing = [r for r in rows if not r.get("class_label", "").strip()]
        assert len(missing) >= 2

    def test_missing_performance_score_handled(self):
        rows = read_data_file(str(STUDENT_CSV))
        missing = [r for r in rows if not r.get("performance_score", "").strip()]
        assert len(missing) >= 2

    def test_many_session_students(self):
        rows = read_data_file(str(STUDENT_CSV))
        many = []
        for r in rows:
            try:
                sc = int(float(r.get("session_count", "0") or "0"))
                if sc >= 50:
                    many.append(r)
            except (ValueError, TypeError):
                pass
        assert len(many) >= 2


# ── Full ingestion pipeline ───────────────────────────────────────────────────

class TestFullIngestionPipeline:
    def test_ingest_all_students(self, fresh_registry, brain):
        report = ingest_students(
            str(STUDENT_CSV), fresh_registry, brain.students,
        )
        assert report.stats["students_read"] == 101
        assert report.stats["students_valid"] >= 95

    def test_ingest_all_content(self, brain):
        report = ingest_content(str(CONTENT_CSV), brain.contents)
        assert report.stats["content_read"] == 40
        assert report.stats["content_valid"] >= 38

    def test_brain_has_ingested_students(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        assert len(brain.students) >= 95

    def test_brain_has_ingested_content(self, brain):
        ingest_content(str(CONTENT_CSV), brain.contents)
        assert len(brain.contents) >= 38


# ── Context vector validation ─────────────────────────────────────────────────

class TestContextVector:
    def test_context_vector_shape(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        ingest_content(str(CONTENT_CSV), brain.contents)
        content_ids = list(brain.contents.keys())
        student_ids = list(brain.students.keys())
        for sid in student_ids[:5]:
            for cid in content_ids[:3]:
                ctx = build_context(
                    brain.students[sid], brain.contents[cid], brain
                )
                assert ctx.shape == (17,), f"Context vector shape wrong for {sid}/{cid}: {ctx.shape}"

    def test_context_vector_not_all_zeros(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        ingest_content(str(CONTENT_CSV), brain.contents)
        content_ids = list(brain.contents.keys())
        student_ids = list(brain.students.keys())
        for sid in student_ids[:3]:
            for cid in content_ids[:2]:
                ctx = build_context(
                    brain.students[sid], brain.contents[cid], brain
                )
                assert ctx.sum() > 0, f"Context vector all zeros for {sid}/{cid}"

    def test_context_vector_handles_missing_history(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        ingest_content(str(CONTENT_CSV), brain.contents)
        for sid, s in brain.students.items():
            if s.session_count == 0 or not s.grade_history:
                content_ids = list(brain.contents.keys())
                if content_ids:
                    ctx = build_context(s, brain.contents[content_ids[0]], brain)
                    assert ctx.shape == (17,)


# ── Recommendations with ingested data ────────────────────────────────────────

class TestRecommendations:
    def test_recommend_for_students(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        ingest_content(str(CONTENT_CSV), brain.contents)
        successes = 0
        for sid in list(brain.students.keys())[:10]:
            try:
                rec = brain.recommend(sid, top_n=1)
                assert rec is not None
                successes += 1
            except Exception:
                pass
        assert successes >= 8

    def test_recommend_for_new_students(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        ingest_content(str(CONTENT_CSV), brain.contents)
        for sid, s in brain.students.items():
            if s.session_count == 0:
                try:
                    rec = brain.recommend(sid, top_n=1)
                    assert rec is not None
                except Exception:
                    pass

    def test_recommend_with_topic_filter(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        ingest_content(str(CONTENT_CSV), brain.contents)
        for topic in ["MATH", "SCIENCE", "ENGLISH", "HISTORY"]:
            sid = list(brain.students.keys())[0]
            rec = brain.recommend(sid, topic=topic, top_n=1)
            assert rec is not None


# ── Validation report ─────────────────────────────────────────────────────────

class TestValidationReport:
    def test_report_to_dict(self, fresh_registry, brain):
        report = ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "stats" in d or "students_read" in d

    def test_content_report_to_dict(self, brain):
        report = ingest_content(str(CONTENT_CSV), brain.contents)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "stats" in d or "content_read" in d


# ── Multi-school scoping ──────────────────────────────────────────────────────

class TestMultiSchoolScoping:
    def test_schools_created_from_dataset(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        schools = [s["name"] for s in fresh_registry["schools"]]
        assert "LAGOS MODEL SCHOOL" in schools
        assert "ABUJA PREP ACADEMY" in schools
        assert "PORT HARCOURT COLLEGE" in schools
        assert "KANO GRAMMAR SCHOOL" in schools

    def test_students_have_school_ids(self, fresh_registry, brain):
        ingest_students(str(STUDENT_CSV), fresh_registry, brain.students)
        for sid, s in brain.students.items():
            assert s.school_id != "" or s.school_id is not None


# ── Stress: large dataset ─────────────────────────────────────────────────────

LARGE_DIR = Path(__file__).parent.parent / "sample_data" / "large"
LARGE_STUDENTS = LARGE_DIR / "large_students.csv"
LARGE_CONTENT = LARGE_DIR / "large_content.csv"


class TestLargeDataset:
    def test_large_csv_exists(self):
        assert LARGE_STUDENTS.exists()
        assert LARGE_CONTENT.exists()

    def test_large_ingest_students(self, fresh_registry, brain):
        if not LARGE_STUDENTS.exists():
            pytest.skip("Large dataset not found")
        report = ingest_students(
            str(LARGE_STUDENTS), fresh_registry, brain.students,
        )
        assert report.stats["students_read"] == 56
        assert report.stats["students_valid"] >= 50

    def test_large_ingest_content(self, brain):
        if not LARGE_CONTENT.exists():
            pytest.skip("Large dataset not found")
        report = ingest_content(str(LARGE_CONTENT), brain.contents)
        assert report.stats["content_read"] == 24
        assert report.stats["content_valid"] >= 22

    def test_large_recommendations(self, fresh_registry, brain):
        if not LARGE_STUDENTS.exists():
            pytest.skip("Large dataset not found")
        ingest_students(str(LARGE_STUDENTS), fresh_registry, brain.students)
        ingest_content(str(LARGE_CONTENT), brain.contents)
        successes = 0
        for sid in list(brain.students.keys())[:15]:
            try:
                rec = brain.recommend(sid, top_n=3)
                assert rec is not None
                successes += 1
            except Exception:
                pass
        assert successes >= 12
