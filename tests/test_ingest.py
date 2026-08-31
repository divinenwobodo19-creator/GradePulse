"""
Malformed-input tests for the GradePulse data ingestion pipeline.
Tests error handling, validation, edge cases, and data integrity.

These tests validate that ingest.py handles real-world messy data gracefully.
Bob's code — QA writes tests only, does not modify ingest.py.
"""
import csv
import os
import tempfile
import pytest
from pathlib import Path

from ingest import (
    read_csv, read_data_file, ValidationReport,
    validate_student_id, validate_name, validate_float, validate_int,
    validate_difficulty, validate_content_type, validate_topic,
    parse_grade_history, ingest_students, ingest_content,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_csv(rows, path, header=True):
    with open(path, "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def _make_student_row(**overrides):
    base = {
        "student_id": "S001",
        "name": "Test Student",
        "class_label": "JSS1A",
        "school_name": "Test School",
        "performance_score": "0.75",
        "session_count": "10",
        "current_topic": "Math",
    }
    base.update(overrides)
    return base


def _make_content_row(**overrides):
    base = {
        "content_id": "C001",
        "title": "Test Content",
        "topic": "Math",
        "difficulty": "3",
        "content_type": "video",
    }
    base.update(overrides)
    return base


def _fresh_registry():
    return {"term_subjects": [], "schools": []}


# ── File Reader Tests ──────────────────────────────────────────────────────────

class TestFileReaders:
    def test_read_csv_normal(self, tmp_path):
        path = tmp_path / "test.csv"
        _write_csv([_make_student_row()], path)
        rows = read_csv(str(path))
        assert len(rows) == 1
        assert rows[0]["student_id"] == "S001"

    def test_read_csv_semicolon_delimiter(self, tmp_path):
        path = tmp_path / "test.csv"
        with open(path, "w", encoding="utf-8") as f:
            f.write("student_id;name;performance_score\n")
            f.write("S001;Test Student;0.75\n")
        rows = read_csv(str(path))
        assert len(rows) == 1
        assert rows[0]["student_id"] == "S001"

    def test_read_csv_tab_delimiter(self, tmp_path):
        path = tmp_path / "test.csv"
        with open(path, "w", encoding="utf-8") as f:
            f.write("student_id\tname\tperformance_score\n")
            f.write("S001\tTest Student\t0.75\n")
        rows = read_csv(str(path))
        assert len(rows) == 1

    def test_read_csv_latin1_encoding(self, tmp_path):
        path = tmp_path / "test.csv"
        with open(path, "w", encoding="latin-1") as f:
            f.write("student_id,name\n")
            f.write("S001,José García\n")
        rows = read_csv(str(path))
        assert len(rows) == 1
        assert rows[0]["name"] == "José García"

    def test_read_csv_whitespace_stripped(self, tmp_path):
        path = tmp_path / "test.csv"
        _write_csv([{"student_id": "  S001  ", "name": "  Test Student  "}], path)
        rows = read_csv(str(path))
        assert rows[0]["student_id"] == "S001"
        assert rows[0]["name"] == "Test Student"

    def test_read_csv_unsupported_format(self, tmp_path):
        path = tmp_path / "test.xyz"
        path.write_text("data")
        with pytest.raises(ValueError, match="Unsupported file format"):
            read_data_file(str(path))

    def test_read_csv_empty_file(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("")
        rows = read_csv(str(path))
        assert rows == []


# ── Validator Unit Tests ───────────────────────────────────────────────────────

class TestValidators:
    def test_validate_student_id_valid(self):
        report = ValidationReport()
        assert validate_student_id("S001", report, 1) == "S001"
        assert len(report.errors) == 0

    def test_validate_student_id_empty(self):
        report = ValidationReport()
        assert validate_student_id("", report, 1) is None
        assert len(report.errors) == 1

    def test_validate_student_id_whitespace_only(self):
        report = ValidationReport()
        assert validate_student_id("   ", report, 1) is None
        assert len(report.errors) == 1

    def test_validate_student_id_too_long(self):
        report = ValidationReport()
        long_id = "X" * 60
        result = validate_student_id(long_id, report, 1)
        assert result is not None
        assert len(report.warnings) == 1

    def test_validate_name_valid(self):
        report = ValidationReport()
        assert validate_name("Alice", report, 1) is not None
        assert len(report.errors) == 0

    def test_validate_name_empty(self):
        report = ValidationReport()
        assert validate_name("", report, 1) is None
        assert len(report.errors) == 1

    def test_validate_name_single_char(self):
        report = ValidationReport()
        result = validate_name("A", report, 1)
        assert result is not None
        assert len(report.warnings) == 1

    def test_validate_name_contains_digits(self):
        report = ValidationReport()
        result = validate_name("Alice123", report, 1)
        assert result is not None
        assert len(report.warnings) == 1

    def test_validate_float_valid(self):
        report = ValidationReport()
        assert validate_float("0.75", 0.5, "test", 1, report) == 0.75

    def test_validate_float_empty_returns_default(self):
        report = ValidationReport()
        assert validate_float("", 0.5, "test", 1, report) == 0.5

    def test_validate_float_invalid_returns_default(self):
        report = ValidationReport()
        assert validate_float("abc", 0.5, "test", 1, report) == 0.5
        assert len(report.warnings) == 1

    def test_validate_float_out_of_range_clamps(self):
        report = ValidationReport()
        assert validate_float("1.5", 0.5, "test", 1, report, max_val=1.0) == 1.0
        assert len(report.warnings) == 1

    def test_validate_int_valid(self):
        report = ValidationReport()
        assert validate_int("10", 5, "test", 1, report) == 10

    def test_validate_int_float_string(self):
        report = ValidationReport()
        assert validate_int("3.7", 5, "test", 1, report) == 3

    def test_validate_difficulty_valid(self):
        report = ValidationReport()
        assert validate_difficulty("3", 1, report) == 3

    def test_validate_difficulty_empty(self):
        report = ValidationReport()
        assert validate_difficulty("", 1, report) == 3
        assert len(report.errors) == 1

    def test_validate_difficulty_out_of_range(self):
        report = ValidationReport()
        assert validate_difficulty("10", 1, report) == 5
        assert len(report.warnings) == 1

    def test_validate_content_type_valid(self):
        report = ValidationReport()
        assert validate_content_type("video", 1, report) == "video"

    def test_validate_content_type_case_insensitive(self):
        report = ValidationReport()
        assert validate_content_type("VIDEO", 1, report) == "video"

    def test_validate_content_type_unknown(self):
        report = ValidationReport()
        assert validate_content_type("podcast", 1, report) == "reading"
        assert len(report.warnings) == 1

    def test_validate_content_type_empty(self):
        report = ValidationReport()
        assert validate_content_type("", 1, report) == "reading"
        assert len(report.errors) == 1

    def test_validate_topic_valid(self):
        report = ValidationReport()
        assert validate_topic("Math", 1, report) == "MATH"

    def test_validate_topic_empty(self):
        report = ValidationReport()
        assert validate_topic("", 1, report) == "General"
        assert len(report.errors) == 1


# ── Grade History Parsing Tests ────────────────────────────────────────────────

class TestGradeHistoryParsing:
    def test_parse_valid_history(self):
        report = ValidationReport()
        row = {"grade_history_math": "0.5;0.6;0.7", "grade_history_science": "0.8;0.9"}
        result = parse_grade_history(row, 1, report)
        assert "MATH" in result
        assert result["MATH"] == [0.5, 0.6, 0.7]
        assert "SCIENCE" in result
        assert result["SCIENCE"] == [0.8, 0.9]

    def test_parse_history_clamps_values(self):
        report = ValidationReport()
        row = {"grade_history_math": "0.5;1.5;-0.1"}
        result = parse_grade_history(row, 1, report)
        assert result["MATH"] == [0.5, 1.0, 0.0]

    def test_parse_history_invalid_values(self):
        report = ValidationReport()
        row = {"grade_history_math": "abc;def"}
        result = parse_grade_history(row, 1, report)
        assert "MATH" not in result
        assert len(report.warnings) == 1

    def test_parse_history_empty_column(self):
        report = ValidationReport()
        row = {"grade_history_math": ""}
        result = parse_grade_history(row, 1, report)
        assert result == {}

    def test_parse_history_semicolon_with_spaces(self):
        report = ValidationReport()
        row = {"grade_history_math": " 0.5 ; 0.6 ; 0.7 "}
        result = parse_grade_history(row, 1, report)
        assert result["MATH"] == [0.5, 0.6, 0.7]


# ── Full Ingestion Tests — Student CSV ────────────────────────────────────────

class TestStudentIngestion:
    def test_valid_student_csv(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row()], path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert report.stats["students_valid"] == 1
        assert report.stats["students_skipped"] == 0
        assert len(report.errors) == 0

    def test_missing_required_column(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([{"name": "Test", "performance_score": "0.5"}], path)
        registry = _fresh_registry()
        report = ingest_students(str(path), registry, {})
        assert report.stats["students_valid"] == 0
        assert len(report.errors) == 1
        assert "Missing required columns" in report.errors[0]

    def test_empty_student_id_skips_row(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row(student_id="")], path)
        registry = _fresh_registry()
        report = ingest_students(str(path), registry, {})
        assert report.stats["students_skipped"] == 1

    def test_empty_name_skips_row(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row(name="")], path)
        registry = _fresh_registry()
        report = ingest_students(str(path), registry, {})
        assert report.stats["students_skipped"] == 1

    def test_invalid_performance_score_uses_default(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row(performance_score="not_a_number")], path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert report.stats["students_valid"] == 1
        assert len(report.warnings) >= 1
        assert "S001" in brain_students
        assert brain_students["S001"].performance_score == 0.5

    def test_performance_score_out_of_range_clamped(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row(performance_score="2.5")], path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert brain_students["S001"].performance_score == 1.0
        assert any("outside" in w for w in report.warnings)

    def test_duplicate_student_ids_update_existing(self, tmp_path):
        path = tmp_path / "students.csv"
        rows = [
            _make_student_row(student_id="S001", performance_score="0.5"),
            _make_student_row(student_id="S001", performance_score="0.9"),
        ]
        _write_csv(rows, path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert report.stats["students_valid"] == 2
        assert brain_students["S001"].performance_score == 0.9

    def test_multiple_schools_created(self, tmp_path):
        path = tmp_path / "students.csv"
        rows = [
            _make_student_row(student_id="S001", school_name="School A"),
            _make_student_row(student_id="S002", school_name="School B"),
        ]
        _write_csv(rows, path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert len(registry["schools"]) == 2

    def test_class_creation(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row(class_label="JSS1A")], path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert report.stats["classes_created"] >= 1

    def test_dry_run_does_not_write(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row()], path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students, dry_run=True)
        assert report.stats["students_valid"] == 1
        assert len(brain_students) == 0

    def test_empty_csv_file(self, tmp_path):
        path = tmp_path / "students.csv"
        path.write_text("")
        registry = _fresh_registry()
        report = ingest_students(str(path), registry, {})
        assert len(report.warnings) >= 1

    def test_unicode_student_names(self, tmp_path):
        path = tmp_path / "students.csv"
        _write_csv([_make_student_row(student_id="S001", name="Chidinma Eze")], path)
        registry = _fresh_registry()
        brain_students = {}
        report = ingest_students(str(path), registry, brain_students)
        assert report.stats["students_valid"] == 1
        assert "S001" in brain_students


# ── Full Ingestion Tests — Content CSV ─────────────────────────────────────────

class TestContentIngestion:
    def test_valid_content_csv(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row()], path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert report.stats["content_valid"] == 1
        assert len(report.errors) == 0

    def test_missing_required_column(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([{"title": "Test", "topic": "Math"}], path)
        report = ingest_content(str(path), {})
        assert report.stats["content_valid"] == 0
        assert len(report.errors) == 1

    def test_empty_content_id_skips(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(content_id="")], path)
        report = ingest_content(str(path), {})
        assert report.stats["content_skipped"] == 1

    def test_empty_title_skips(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(title="")], path)
        report = ingest_content(str(path), {})
        assert report.stats["content_skipped"] == 1

    def test_invalid_difficulty_uses_default(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(difficulty="abc")], path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert report.stats["content_valid"] == 1
        assert brain_contents["C001"].difficulty == 3

    def test_difficulty_out_of_range_clamped(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(difficulty="10")], path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert brain_contents["C001"].difficulty == 5

    def test_unknown_content_type_defaults_to_reading(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(content_type="podcast")], path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert brain_contents["C001"].content_type == "reading"

    def test_topic_normalized_to_uppercase(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(topic="math")], path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert brain_contents["C001"].topic == "MATH"

    def test_empty_topic_defaults_to_general(self, tmp_path):
        path = tmp_path / "content.csv"
        _write_csv([_make_content_row(topic="")], path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert brain_contents["C001"].topic == "General"

    def test_duplicate_content_ids_update(self, tmp_path):
        path = tmp_path / "content.csv"
        rows = [
            _make_content_row(content_id="C001", title="Original"),
            _make_content_row(content_id="C001", title="Updated"),
        ]
        _write_csv(rows, path)
        brain_contents = {}
        report = ingest_content(str(path), brain_contents)
        assert brain_contents["C001"].title == "Updated"


# ── Validation Report Tests ────────────────────────────────────────────────────

class TestValidationReport:
    def test_report_summary_with_no_issues(self):
        report = ValidationReport()
        report.stats["students_valid"] = 5
        report.stats["students_read"] = 5
        summary = report.summary()
        assert "5 valid" in summary
        assert "Errors" not in summary

    def test_report_summary_with_errors(self):
        report = ValidationReport()
        report.error("Test error")
        report.warn("Test warning")
        summary = report.summary()
        assert "Test error" in summary
        assert "Test warning" in summary

    def test_report_truncates_many_errors(self):
        report = ValidationReport()
        for i in range(25):
            report.error(f"Error {i}")
        summary = report.summary()
        assert "... and 5 more" in summary
