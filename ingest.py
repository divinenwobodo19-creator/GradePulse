#!/usr/bin/env python3
"""
GradePulse Data Ingestion Pipeline
===================================
Pilot-school data ingestion into Sam's multi-tenant schema and 17-dim context vector.

Usage:
    python ingest.py --students students.csv --content content.csv --school "MY SCHOOL"
    python ingest.py --students students.xlsx --content content.xlsx --school-id 8aa6f66b
    python ingest.py --validate-only --students students.csv

Author: Bob (Data Engineer)
"""

import argparse
import csv
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from linucb_brain.models.student import Student, normalize_label
from linucb_brain.models.content import Content
from linucb_brain.registry import load_registry, save_registry, ensure_school, add_class
from linucb_brain.core.context import get_context_dimension, CONTENT_TYPES
from linucb_brain.sync import BrainSynchronizer

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_CONTENT_TYPES = set(CONTENT_TYPES)  # ["video", "quiz", "exercise", "reading"]
VALID_GRADE_LEVELS = ["JSS1", "JSS2", "JSS3", "SSS1", "SSS2", "SSS3", "300 LEVEL", "400 LEVEL"]
DEFAULT_IMD_BAND = 0.5
DEFAULT_REGION_CODE = 0.0
DEFAULT_EDUCATION_LEVEL = 0.0
DEFAULT_AGE_BAND = 0.0
DEFAULT_CREDITS = 0.0
MAX_DIFFICULTY = 5
MIN_DIFFICULTY = 1

# Required columns for student CSV
STUDENT_REQUIRED = ["student_id", "name"]
STUDENT_OPTIONAL = [
    "class_label", "grade_level", "arm", "school_name",
    "performance_score", "session_count", "current_topic",
    "education_level", "age_band", "credits_studied", "imd_band", "region_code",
    "grade_history_math", "grade_history_science", "grade_history_english",
    "grade_history_history",
]

# Required columns for content CSV
CONTENT_REQUIRED = ["content_id", "title", "topic", "difficulty", "content_type"]
CONTENT_OPTIONAL = []


# ── Validation Results ─────────────────────────────────────────────────────────

class ValidationReport:
    """Collects errors and warnings during data validation."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats = {
            "students_read": 0,
            "students_valid": 0,
            "students_skipped": 0,
            "content_read": 0,
            "content_valid": 0,
            "content_skipped": 0,
            "schools_created": 0,
            "classes_created": 0,
        }

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def summary(self) -> str:
        lines = ["=" * 60, "INGESTION REPORT", "=" * 60]
        lines.append(f"\nStudents: {self.stats['students_valid']} valid / {self.stats['students_read']} read / {self.stats['students_skipped']} skipped")
        lines.append(f"Content:  {self.stats['content_valid']} valid / {self.stats['content_read']} read / {self.stats['content_skipped']} skipped")
        lines.append(f"Schools created: {self.stats['schools_created']}")
        lines.append(f"Classes created: {self.stats['classes_created']}")
        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for w in self.warnings[:20]:
                lines.append(f"  ⚠ {w}")
            if len(self.warnings) > 20:
                lines.append(f"  ... and {len(self.warnings) - 20} more")
        if self.errors:
            lines.append(f"\nErrors ({len(self.errors)}):")
            for e in self.errors[:20]:
                lines.append(f"  ✗ {e}")
            if len(self.errors) > 20:
                lines.append(f"  ... and {len(self.errors) - 20} more")
        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Convert report to dictionary for JSON serialization (API responses)."""
        return {
            "stats": self.stats.copy(),
            "errors": self.errors,
            "warnings": self.warnings,
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
        }


# ── File Readers ───────────────────────────────────────────────────────────────

def read_csv(filepath: str) -> List[Dict]:
    """Read CSV file, handling various encodings and edge cases."""
    rows = []
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc, newline="") as f:
                # Sniff dialect
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(f, dialect=dialect)
                for row in reader:
                    # Strip whitespace from keys and values
                    cleaned = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
                    rows.append(cleaned)
            return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Could not read {filepath} with any supported encoding")


def read_excel(filepath: str) -> List[Dict]:
    """Read Excel file using pandas."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for Excel files. Install with: pip install pandas openpyxl")
    df = pd.read_excel(filepath, dtype=str)
    df = df.fillna("")
    return df.to_dict("records")


def read_data_file(filepath: str) -> List[Dict]:
    """Read CSV or Excel file based on extension."""
    ext = Path(filepath).suffix.lower()
    if ext == ".csv":
        return read_csv(filepath)
    elif ext in (".xlsx", ".xls"):
        return read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .csv or .xlsx")


# ── Validators ─────────────────────────────────────────────────────────────────

def validate_student_id(raw: str, report: ValidationReport, row_num: int) -> Optional[str]:
    """Validate and clean student ID."""
    if not raw or not raw.strip():
        report.error(f"Row {row_num}: Empty student_id")
        return None
    sid = raw.strip()
    if len(sid) > 50:
        report.warn(f"Row {row_num}: student_id unusually long ({len(sid)} chars): {sid[:20]}...")
    return sid


def validate_name(raw: str, report: ValidationReport, row_num: int) -> Optional[str]:
    """Validate and clean student name."""
    if not raw or not raw.strip():
        report.error(f"Row {row_num}: Empty name")
        return None
    name = normalize_label(raw)
    if len(name) < 2:
        report.warn(f"Row {row_num}: Name very short: '{name}'")
    if any(c.isdigit() for c in name):
        report.warn(f"Row {row_num}: Name contains digits: '{name}'")
    return name


def validate_float(raw: str, default: float, field_name: str, row_num: int,
                   report: ValidationReport, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Validate and convert to float with bounds checking."""
    if not raw or not str(raw).strip():
        return default
    try:
        val = float(str(raw).strip())
        if val < min_val or val > max_val:
            report.warn(f"Row {row_num}: {field_name}={val} outside [{min_val}, {max_val}], clamping")
            val = max(min_val, min(max_val, val))
        return val
    except (ValueError, TypeError):
        report.warn(f"Row {row_num}: Invalid {field_name}='{raw}', using default {default}")
        return default


def validate_int(raw: str, default: int, field_name: str, row_num: int,
                 report: ValidationReport, min_val: int = 0, max_val: int = 100) -> int:
    """Validate and convert to int with bounds checking."""
    if not raw or not str(raw).strip():
        return default
    try:
        val = int(float(str(raw).strip()))
        if val < min_val or val > max_val:
            report.warn(f"Row {row_num}: {field_name}={val} outside [{min_val}, {max_val}], clamping")
            val = max(min_val, min(max_val, val))
        return val
    except (ValueError, TypeError):
        report.warn(f"Row {row_num}: Invalid {field_name}='{raw}', using default {default}")
        return default


def validate_difficulty(raw: str, row_num: int, report: ValidationReport) -> int:
    """Validate content difficulty (1-5)."""
    if not raw or not str(raw).strip():
        report.error(f"Row {row_num}: Empty difficulty")
        return 3  # default mid-range
    try:
        diff = int(float(str(raw).strip()))
        if diff < MIN_DIFFICULTY or diff > MAX_DIFFICULTY:
            report.warn(f"Row {row_num}: difficulty={diff} outside [{MIN_DIFFICULTY}, {MAX_DIFFICULTY}], clamping")
            diff = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, diff))
        return diff
    except (ValueError, TypeError):
        report.error(f"Row {row_num}: Invalid difficulty='{raw}'")
        return 3


def validate_content_type(raw: str, row_num: int, report: ValidationReport) -> str:
    """Validate content type."""
    if not raw or not raw.strip():
        report.error(f"Row {row_num}: Empty content_type")
        return "reading"  # default
    ct = raw.strip().lower()
    if ct not in VALID_CONTENT_TYPES:
        report.warn(f"Row {row_num}: Unknown content_type='{raw}', using 'reading'")
        return "reading"
    return ct


def validate_topic(raw: str, row_num: int, report: ValidationReport) -> str:
    """Validate and clean topic."""
    if not raw or not raw.strip():
        report.error(f"Row {row_num}: Empty topic")
        return "General"
    return normalize_label(raw)


def parse_grade_history(row: Dict, row_num: int, report: ValidationReport) -> Dict[str, List[float]]:
    """Extract grade history from row columns."""
    history = {}
    topic_cols = [k for k in row.keys() if k.lower().startswith("grade_history_")]
    for col in topic_cols:
        topic = col.replace("grade_history_", "").replace("grade_history", "").strip()
        if not topic:
            topic = "General"
        raw_val = row.get(col, "")
        if raw_val and str(raw_val).strip():
            try:
                scores = [float(s.strip()) for s in str(raw_val).split(";") if s.strip()]
                scores = [max(0.0, min(1.0, s)) for s in scores]  # clamp to [0,1]
                if scores:
                    history[normalize_label(topic)] = scores
            except (ValueError, TypeError):
                report.warn(f"Row {row_num}: Could not parse grade_history for topic '{topic}'")
    return history


# ── Ingestion Logic ────────────────────────────────────────────────────────────

def ingest_students(
    filepath: str,
    registry: dict,
    brain_students: Dict[str, Student],
    school_id: Optional[str] = None,
    school_name: Optional[str] = None,
    dry_run: bool = False,
) -> ValidationReport:
    """
    Ingest student roster from CSV/Excel into the multi-tenant schema.

    Expected CSV columns:
        Required: student_id, name
        Optional: class_label, grade_level, arm, school_name,
                  performance_score, session_count, current_topic,
                  education_level, age_band, credits_studied, imd_band, region_code,
                  grade_history_math, grade_history_science, etc.
    """
    report = ValidationReport()
    rows = read_data_file(filepath)
    report.stats["students_read"] = len(rows)

    if not rows:
        report.warn("No rows found in student file")
        return report

    # Validate columns
    actual_cols = set(rows[0].keys())
    missing = [c for c in STUDENT_REQUIRED if c not in actual_cols]
    if missing:
        report.error(f"Missing required columns: {missing}")
        return report

    for i, row in enumerate(rows, start=2):  # row 1 = header
        sid = validate_student_id(row.get("student_id", ""), report, i)
        name = validate_name(row.get("name", ""), report, i)
        if not sid or not name:
            report.stats["students_skipped"] += 1
            continue

        # Determine school
        s_id = school_id
        s_name = school_name or row.get("school_name", "").strip()
        if not s_id and s_name:
            school = ensure_school(registry, s_name)
            s_id = school["school_id"]
            if school not in [s for s in registry["schools"] if s["school_id"] == s_id]:
                report.stats["schools_created"] += 1
        elif not s_id:
            # Use first school in registry or create default
            if registry["schools"]:
                s_id = registry["schools"][0]["school_id"]
            else:
                school = ensure_school(registry, "MY SCHOOL")
                s_id = school["school_id"]
                report.stats["schools_created"] += 1

        # Determine class
        class_label = row.get("class_label", "").strip()
        grade_level = row.get("grade_level", "").strip().upper()
        arm = row.get("arm", "").strip().upper()
        c_id = ""

        if class_label:
            # Try to find or create class
            cls = add_class(registry, s_id, class_label)
            if cls:
                c_id = cls["class_id"]
                report.stats["classes_created"] += 1
            else:
                # Class might already exist, find it
                from linucb_brain.registry import get_classes
                for c in get_classes(registry, s_id):
                    if c["label"] == normalize_label(class_label):
                        c_id = c["class_id"]
                        break

        # Validate numeric fields
        perf = validate_float(row.get("performance_score", ""), 0.5, "performance_score", i, report)
        sessions = validate_int(row.get("session_count", ""), 0, "session_count", i, report, min_val=0, max_val=10000)
        edu = validate_float(row.get("education_level", ""), DEFAULT_EDUCATION_LEVEL, "education_level", i, report, min_val=0, max_val=10)
        age = validate_float(row.get("age_band", ""), DEFAULT_AGE_BAND, "age_band", i, report, min_val=0, max_val=10)
        credits = validate_float(row.get("credits_studied", ""), DEFAULT_CREDITS, "credits_studied", i, report, min_val=0, max_val=100)
        imd = validate_float(row.get("imd_band", ""), DEFAULT_IMD_BAND, "imd_band", i, report, min_val=0, max_val=1)
        region = validate_float(row.get("region_code", ""), DEFAULT_REGION_CODE, "region_code", i, report, min_val=0, max_val=100)
        topic = normalize_label(row.get("current_topic", ""))

        # Parse grade history
        grade_history = parse_grade_history(row, i, report)

        # Build student kwargs
        kwargs = {
            "performance_score": perf,
            "session_count": sessions,
            "current_topic": topic,
            "education_level": edu,
            "age_band": age,
            "credits_studied": credits,
            "imd_band": imd,
            "region_code": region,
            "grade_history": grade_history,
            "school_id": s_id,
            "class_id": c_id,
        }

        if not dry_run:
            if sid in brain_students:
                # Update existing student
                s = brain_students[sid]
                for k, v in kwargs.items():
                    if k in ("school_id", "class_id"):
                        setattr(s, k, v)
                    elif k == "grade_history":
                        s.grade_history.update(v)
                    elif k != "session_count":  # don't overwrite session count on update
                        setattr(s, k, v)
            else:
                brain_students[sid] = Student(student_id=sid, name=name, **kwargs)

        report.stats["students_valid"] += 1

    return report


def ingest_content(
    filepath: str,
    brain_contents: Dict[str, Content],
    dry_run: bool = False,
) -> ValidationReport:
    """
    Ingest content catalog from CSV/Excel.

    Expected CSV columns:
        Required: content_id, title, topic, difficulty, content_type
    """
    report = ValidationReport()
    rows = read_data_file(filepath)
    report.stats["content_read"] = len(rows)

    if not rows:
        report.warn("No rows found in content file")
        return report

    # Validate columns
    actual_cols = set(rows[0].keys())
    missing = [c for c in CONTENT_REQUIRED if c not in actual_cols]
    if missing:
        report.error(f"Missing required columns: {missing}")
        return report

    for i, row in enumerate(rows, start=2):
        cid = row.get("content_id", "").strip()
        title = row.get("title", "").strip()
        topic = validate_topic(row.get("topic", ""), i, report)
        difficulty = validate_difficulty(row.get("difficulty", ""), i, report)
        content_type = validate_content_type(row.get("content_type", ""), i, report)

        if not cid:
            report.error(f"Row {i}: Empty content_id")
            report.stats["content_skipped"] += 1
            continue
        if not title:
            report.error(f"Row {i}: Empty title")
            report.stats["content_skipped"] += 1
            continue

        if not dry_run:
            if cid in brain_contents:
                # Update existing content
                c = brain_contents[cid]
                c.title = title
                c.topic = topic
                c.difficulty = difficulty
                c.content_type = content_type
            else:
                brain_contents[cid] = Content(
                    content_id=cid,
                    title=title,
                    topic=topic,
                    difficulty=difficulty,
                    content_type=content_type,
                )

        report.stats["content_valid"] += 1

    return report


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GradePulse Data Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest students and content
  python ingest.py --students students.csv --content content.csv --school "MY SCHOOL"

  # Validate only (no writes)
  python ingest.py --validate-only --students students.csv --content content.csv

  # Ingest with specific school ID
  python ingest.py --students students.xlsx --school-id 8aa6f66b

  # Dry run (parse but don't write)
  python ingest.py --dry-run --students students.csv --content content.csv
        """,
    )
    parser.add_argument("--students", "-s", help="Path to student roster CSV/Excel")
    parser.add_argument("--content", "-c", help="Path to content catalog CSV/Excel")
    parser.add_argument("--school", help="School name (creates if not exists)")
    parser.add_argument("--school-id", help="School ID (overrides --school)")
    parser.add_argument("--config", default="class_config.json", help="Config file path")
    parser.add_argument("--brain-state", default="brain_state.json", help="Brain state file path")
    parser.add_argument("--validate-only", action="store_true", help="Validate only, don't write")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate, but don't write to files")
    parser.add_argument("--no-lock", action="store_true", help="Skip BrainSynchronizer file locking (CLI-only, API not running)")
    parser.add_argument("--output-sample", help="Generate sample data CSV at this path")
    parser.add_argument("--output-large", help="Generate large sample dataset (50+ students) at this path")

    args = parser.parse_args()

    # Generate sample data if requested
    if args.output_sample:
        generate_sample_data(args.output_sample)
        return
    
    if args.output_large:
        generate_large_sample_data(args.output_large)
        return

    if not args.students and not args.content:
        parser.print_help()
        print("\nError: At least one of --students or --content is required")
        sys.exit(1)

    # Load existing state
    registry = load_registry(args.config)
    brain_instance = None

    if os.path.exists(args.brain_state) and not args.validate_only:
        try:
            from linucb_brain.brain import Brain
            brain_instance = Brain.load(args.brain_state)
        except Exception as e:
            print(f"Warning: Could not load brain state: {e}")

    # Use brain's dicts if loaded, otherwise empty dicts
    brain_students = brain_instance.students if brain_instance else {}
    brain_contents = brain_instance.contents if brain_instance else {}

    print(f"\nConfig: {args.config}")
    print(f"Brain state: {args.brain_state}")
    print(f"Mode: {'Validate only' if args.validate_only else 'Dry run' if args.dry_run else 'Live ingestion'}")
    print()

    all_reports = []

    # Ingest students
    if args.students:
        print(f"Ingesting students from: {args.students}")
        report = ingest_students(
            args.students, registry, brain_students,
            school_id=args.school_id, school_name=args.school,
            dry_run=args.dry_run or args.validate_only,
        )
        all_reports.append(("Students", report))
        print(report.summary())

    # Ingest content
    if args.content:
        print(f"\nIngesting content from: {args.content}")
        report = ingest_content(
            args.content, brain_contents,
            dry_run=args.dry_run or args.validate_only,
        )
        all_reports.append(("Content", report))
        print(report.summary())

    # Write results
    if not args.validate_only and not args.dry_run:
        if args.no_lock:
            # Direct write without file locking (CLI-only mode)
            save_registry(registry, args.config)
            print(f"\nRegistry saved to: {args.config}")

            if brain_instance is not None:
                brain_instance.save(args.brain_state)
                print(f"Brain state saved to: {args.brain_state}")
            elif brain_students or brain_contents:
                try:
                    from linucb_brain.brain import Brain
                    brain = Brain(model_type="hybrid")
                    brain.students = brain_students
                    brain.contents = brain_contents
                    brain.save(args.brain_state)
                    print(f"Brain state saved to: {args.brain_state}")
                except Exception as e:
                    print(f"Warning: Could not save brain state: {e}")
        else:
            # Use BrainSynchronizer for safe multi-worker writes
            synchronizer = BrainSynchronizer(
                brain_state_path=args.brain_state,
                config_path=args.config,
                auto_save_interval=0,  # No auto-save needed for one-shot ingestion
            )

            # Save registry with file lock
            with synchronizer._config_lock:
                save_registry(registry, args.config)
            print(f"\nRegistry saved to: {args.config} (with file lock)")

            # Save brain state with file lock
            if brain_instance is not None:
                synchronizer.set_brain(brain_instance)
                synchronizer.save_brain(brain_instance.save)
                print(f"Brain state saved to: {args.brain_state} (with file lock)")
            elif brain_students or brain_contents:
                try:
                    from linucb_brain.brain import Brain
                    brain = Brain(model_type="hybrid")
                    brain.students = brain_students
                    brain.contents = brain_contents
                    synchronizer.set_brain(brain)
                    synchronizer.save_brain(brain.save)
                    print(f"Brain state saved to: {args.brain_state} (with file lock)")
                except Exception as e:
                    print(f"Warning: Could not save brain state: {e}")

    # Final summary
    total_errors = sum(len(r.errors) for _, r in all_reports)
    total_warnings = sum(len(r.warnings) for _, r in all_reports)
    print(f"\n{'='*60}")
    print(f"FINAL: {total_errors} errors, {total_warnings} warnings")
    if total_errors > 0:
        print("Ingestion completed with errors. Review output above.")
        sys.exit(1)
    else:
        print("Ingestion completed successfully.")
        sys.exit(0)


def generate_sample_data(output_dir: str):
    """Generate sample CSV files for testing."""
    os.makedirs(output_dir, exist_ok=True)

    # Sample students
    students_path = os.path.join(output_dir, "sample_students.csv")
    student_fields = [
        "student_id", "name", "class_label", "school_name",
        "performance_score", "session_count", "current_topic",
        "education_level", "age_band", "credits_studied", "imd_band", "region_code",
        "grade_history_math", "grade_history_science", "grade_history_english", "grade_history_history",
    ]
    students = [
        {"student_id": "STU001", "name": "Adebayo Olawale", "class_label": "JSS1A", "school_name": "LAGOS MODEL SCHOOL",
         "performance_score": "0.65", "session_count": "12", "current_topic": "Math",
         "education_level": "1.0", "age_band": "2.0", "credits_studied": "5.0",
         "imd_band": "0.4", "region_code": "1.0", "grade_history_math": "0.55;0.60;0.65",
         "grade_history_science": "", "grade_history_english": "", "grade_history_history": ""},
        {"student_id": "STU002", "name": "Chidinma Eze", "class_label": "JSS1A", "school_name": "LAGOS MODEL SCHOOL",
         "performance_score": "0.78", "session_count": "15", "current_topic": "Science",
         "education_level": "1.0", "age_band": "2.0", "credits_studied": "5.0",
         "imd_band": "0.3", "region_code": "1.0", "grade_history_math": "",
         "grade_history_science": "0.70;0.75;0.78", "grade_history_english": "", "grade_history_history": ""},
        {"student_id": "STU003", "name": "Fatima Abubakar", "class_label": "JSS2B", "school_name": "LAGOS MODEL SCHOOL",
         "performance_score": "0.42", "session_count": "8", "current_topic": "English",
         "education_level": "2.0", "age_band": "3.0", "credits_studied": "10.0",
         "imd_band": "0.6", "region_code": "2.0", "grade_history_math": "",
         "grade_history_science": "", "grade_history_english": "0.35;0.38;0.42", "grade_history_history": ""},
        {"student_id": "STU004", "name": "Emeka Nnamdi", "class_label": "SSS1A", "school_name": "ABUJA PREP ACADEMY",
         "performance_score": "0.88", "session_count": "20", "current_topic": "Math",
         "education_level": "4.0", "age_band": "4.0", "credits_studied": "20.0",
         "imd_band": "0.2", "region_code": "3.0", "grade_history_math": "0.82;0.85;0.88",
         "grade_history_science": "", "grade_history_english": "", "grade_history_history": ""},
        {"student_id": "STU005", "name": "Grace Okonkwo", "class_label": "SSS2A", "school_name": "ABUJA PREP ACADEMY",
         "performance_score": "0.55", "session_count": "10", "current_topic": "History",
         "education_level": "5.0", "age_band": "5.0", "credits_studied": "25.0",
         "imd_band": "0.5", "region_code": "3.0", "grade_history_math": "",
         "grade_history_science": "", "grade_history_english": "", "grade_history_history": "0.48;0.52;0.55"},
    ]
    with open(students_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=student_fields)
        writer.writeheader()
        writer.writerows(students)

    # Sample content
    content_path = os.path.join(output_dir, "sample_content.csv")
    content = [
        {"content_id": "CONT001", "title": "Algebra Basics", "topic": "Math", "difficulty": "2", "content_type": "video"},
        {"content_id": "CONT002", "title": "Quadratic Equations Quiz", "topic": "Math", "difficulty": "3", "content_type": "quiz"},
        {"content_id": "CONT003", "title": "Cell Structure Reading", "topic": "Science", "difficulty": "2", "content_type": "reading"},
        {"content_id": "CONT004", "title": "Physics Lab Exercise", "topic": "Science", "difficulty": "4", "content_type": "exercise"},
        {"content_id": "CONT005", "title": "Grammar Fundamentals", "topic": "English", "difficulty": "1", "content_type": "video"},
        {"content_id": "CONT006", "title": "Creative Writing Practice", "topic": "English", "difficulty": "3", "content_type": "exercise"},
        {"content_id": "CONT007", "title": "Nigerian History Overview", "topic": "History", "difficulty": "2", "content_type": "reading"},
        {"content_id": "CONT008", "title": "Past Questions Quiz", "topic": "History", "difficulty": "4", "content_type": "quiz"},
    ]
    with open(content_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=content[0].keys())
        writer.writeheader()
        writer.writerows(content)

    print(f"Sample data generated in: {output_dir}")
    print(f"  - {students_path} ({len(students)} students)")
    print(f"  - {content_path} ({len(content)} content items)")


def generate_large_sample_data(output_dir: str):
    """Generate large sample dataset (50+ students) for stress testing."""
    import random
    random.seed(42)  # Reproducible
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Nigerian names pools
    first_names_male = [
        "Adebayo", "Chinedu", "Emeka", "Tunde", "Kola", "Femi", "Dapo", "Wale",
        "Segun", "Kayode", "Biodun", "Lanre", "Tobi", "Yemi", "Gbenga", "Sola",
        "Bankole", "Demola", "Funso", "Jide", "Kunle", "Niyi", "Obinna", "Uche",
        "Chidi", "Ikenna", "Chukwu", "Emeka", "Ifeanyi", "Kelechi",
    ]
    first_names_female = [
        "Chidinma", "Ngozi", "Adaeze", "Funke", "Bimpe", "Tolu", "Sade", "Bola",
        "Yetunde", "Folake", "Amara", "Nneka", "Chioma", "Obiageli", "Ifeoma",
        "Aisha", "Halima", "Zainab", "Fatima", "Amina", "Blessing", "Grace",
        "Mercy", "Esther", "Ruth", "Deborah", "Victoria", "Patience", "Joy", "Peace",
    ]
    last_names = [
        "Olawale", "Nnamdi", "Abubakar", "Okonkwo", "Adeyemi", "Balogun", "Okafor",
        "Ibrahim", "Ogundimu", "Chukwuemeka", "Afolabi", "Eze", "Aliyu", "Akinwale",
        "Nwosu", "Mohammed", "Olawuwo", "Igwe", "Adeleke", "Ogundele", "Ugwu",
        "Adebanjo", "Olaniyan", "Chidebe", "Ogundipe", "Suleiman", "Adekunle",
        "Obiora", "Ibekwe", "Adegoke",
    ]
    
    schools = [
        ("LAGOS MODEL SCHOOL", ["JSS1A", "JSS1B", "JSS2A", "JSS2B", "SSS1A", "SSS1B"]),
        ("ABUJA PREP ACADEMY", ["JSS1A", "JSS2A", "SSS1A", "SSS2A"]),
        ("PORT HARCOURT COLLEGE", ["JSS1A", "JSS2A", "JSS3A", "SSS1A", "SSS2A", "SSS3A"]),
    ]
    
    topics = ["Math", "Science", "English", "History"]
    content_types = ["video", "quiz", "exercise", "reading"]
    
    # Generate 60 students
    student_fields = [
        "student_id", "name", "class_label", "school_name",
        "performance_score", "session_count", "current_topic",
        "education_level", "age_band", "credits_studied", "imd_band", "region_code",
        "grade_history_math", "grade_history_science", "grade_history_english", "grade_history_history",
    ]
    
    students = []
    student_id = 1
    
    for school_name, class_labels in schools:
        for class_label in class_labels:
            # 3-4 students per class
            num_students = random.randint(3, 4)
            for _ in range(num_students):
                # Pick name
                if random.random() < 0.5:
                    first = random.choice(first_names_male)
                else:
                    first = random.choice(first_names_female)
                last = random.choice(last_names)
                name = f"{first} {last}"
                
                # Performance based on grade level
                if "JSS1" in class_label:
                    base_perf = random.uniform(0.3, 0.7)
                    edu_level = 1.0
                    age_band = random.uniform(1.0, 2.0)
                elif "JSS2" in class_label:
                    base_perf = random.uniform(0.4, 0.75)
                    edu_level = 2.0
                    age_band = random.uniform(2.0, 3.0)
                elif "JSS3" in class_label:
                    base_perf = random.uniform(0.45, 0.8)
                    edu_level = 3.0
                    age_band = random.uniform(3.0, 4.0)
                elif "SSS1" in class_label:
                    base_perf = random.uniform(0.5, 0.85)
                    edu_level = 4.0
                    age_band = random.uniform(4.0, 5.0)
                elif "SSS2" in class_label:
                    base_perf = random.uniform(0.55, 0.9)
                    edu_level = 5.0
                    age_band = random.uniform(5.0, 6.0)
                else:  # SSS3
                    base_perf = random.uniform(0.6, 0.95)
                    edu_level = 6.0
                    age_band = random.uniform(6.0, 7.0)
                
                # Add some variance
                perf = round(min(0.99, max(0.1, base_perf + random.uniform(-0.1, 0.1))), 2)
                sessions = random.randint(5, 30)
                topic = random.choice(topics)
                credits = round(edu_level * random.uniform(4, 6), 1)
                imd = round(random.uniform(0.2, 0.8), 2)
                region = round(random.uniform(1.0, 6.0), 1)
                
                # Grade history (3-5 data points)
                history_len = random.randint(3, 5)
                history_base = perf + random.uniform(-0.15, 0.15)
                history = [round(min(1.0, max(0.0, history_base + random.uniform(-0.1, 0.1) * i)), 2) 
                          for i in range(history_len)]
                history_str = ";".join([str(h) for h in history])
                
                # Build grade history for current topic
                grade_hist = {f"grade_history_{topic.lower()}": history_str}
                
                student = {
                    "student_id": f"STU{student_id:03d}",
                    "name": name,
                    "class_label": class_label,
                    "school_name": school_name,
                    "performance_score": str(perf),
                    "session_count": str(sessions),
                    "current_topic": topic,
                    "education_level": str(edu_level),
                    "age_band": str(round(age_band, 1)),
                    "credits_studied": str(credits),
                    "imd_band": str(imd),
                    "region_code": str(region),
                    "grade_history_math": grade_hist.get("grade_history_math", ""),
                    "grade_history_science": grade_hist.get("grade_history_science", ""),
                    "grade_history_english": grade_hist.get("grade_history_english", ""),
                    "grade_history_history": grade_hist.get("grade_history_history", ""),
                }
                students.append(student)
                student_id += 1
    
    # Write students
    students_path = os.path.join(output_dir, "large_students.csv")
    with open(students_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=student_fields)
        writer.writeheader()
        writer.writerows(students)
    
    # Generate 25 content items
    content_fields = ["content_id", "title", "topic", "difficulty", "content_type"]
    content = []
    
    content_titles = {
        "Math": [
            ("Algebra Fundamentals", 2, "video"),
            ("Quadratic Equations", 3, "quiz"),
            ("Geometry Basics", 2, "reading"),
            ("Trigonometry Practice", 4, "exercise"),
            ("Statistics Intro", 3, "video"),
            ("Calculus Preview", 5, "quiz"),
            ("Number Theory", 3, "reading"),
        ],
        "Science": [
            ("Cell Biology", 2, "video"),
            ("Chemical Reactions", 3, "quiz"),
            ("Physics Motion", 3, "exercise"),
            ("Ecology Systems", 2, "reading"),
            ("Lab Safety", 1, "video"),
            ("Genetics Basics", 4, "quiz"),
        ],
        "English": [
            ("Grammar Rules", 1, "video"),
            ("Essay Writing", 3, "exercise"),
            ("Literature Analysis", 4, "reading"),
            ("Comprehension Practice", 2, "quiz"),
            ("Vocabulary Builder", 2, "video"),
            ("Poetry Appreciation", 3, "reading"),
        ],
        "History": [
            ("Nigerian Independence", 2, "reading"),
            ("West African Empires", 3, "video"),
            ("Colonial Period", 3, "quiz"),
            ("Modern Nigeria", 2, "exercise"),
            ("World Wars Impact", 4, "reading"),
        ],
    }
    
    content_id = 1
    for topic, items in content_titles.items():
        for title, diff, ctype in items:
            content.append({
                "content_id": f"CONT{content_id:03d}",
                "title": title,
                "topic": topic,
                "difficulty": str(diff),
                "content_type": ctype,
            })
            content_id += 1
    
    # Write content
    content_path = os.path.join(output_dir, "large_content.csv")
    with open(content_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=content_fields)
        writer.writeheader()
        writer.writerows(content)
    
    # Generate README
    readme_path = os.path.join(output_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"# Large Sample Dataset\n\n")
        f.write(f"Generated for stress testing the GradePulse ingestion pipeline.\n\n")
        f.write(f"## Statistics\n\n")
        f.write(f"- **Students:** {len(students)}\n")
        f.write(f"- **Content items:** {len(content)}\n")
        f.write(f"- **Schools:** {len(schools)}\n")
        f.write(f"- **Grade levels:** JSS1-SSS3\n\n")
        f.write(f"## Schools\n\n")
        for school_name, class_labels in schools:
            f.write(f"- **{school_name}**: {', '.join(class_labels)}\n")
        f.write(f"\n## Usage\n\n")
        f.write(f"```bash\n")
        f.write(f"# Ingest all data\n")
        f.write(f"python ingest.py --students large_students.csv --content large_content.csv\n\n")
        f.write(f"# Validate only\n")
        f.write(f"python ingest.py --validate-only --students large_students.csv --content large_content.csv\n\n")
        f.write(f"# Dry run\n")
        f.write(f"python ingest.py --dry-run --students large_students.csv --content large_content.csv\n")
        f.write(f"```\n")
    
    print(f"Large sample dataset generated in: {output_dir}")
    print(f"  - {students_path} ({len(students)} students)")
    print(f"  - {content_path} ({len(content)} content items)")
    print(f"  - {readme_path}")


if __name__ == "__main__":
    main()
