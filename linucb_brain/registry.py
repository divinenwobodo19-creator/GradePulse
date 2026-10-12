"""
School/Class registry backed by class_config.json.

Schema (school-scoped so labels never collide across institutions):
{
  "term_subjects": ["Maths", ...],
  "schools": [
    {
      "school_id": "a1b2c3d4",
      "name": "MY SCHOOL",
      "classes": [
        {"class_id": "e5f6a7b8", "label": "JSS1A", "grade_level": "JSS1", "arm": "A"}
      ]
    }
  ]
}

Backwards compatibility: the old flat schema {"term_subjects": [...], "classes": ["JSS1A", ...]}
is auto-migrated to the school-scoped schema on load (legacy classes land in a default school).
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from .models.school import School, SchoolClass, normalize_label, GRADE_LEVELS

DEFAULT_CONFIG_FILE = "class_config.json"
DEFAULT_SCHOOL = "MY SCHOOL"


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def default_config() -> dict:
    return {"term_subjects": [], "schools": []}


def load_registry(config_file: str = DEFAULT_CONFIG_FILE) -> dict:
    if os.path.exists(config_file):
        with open(config_file) as f:
            raw = json.load(f)
        return _migrate(raw)
    return default_config()


def save_registry(registry: dict, config_file: str = DEFAULT_CONFIG_FILE) -> None:
    with open(config_file, "w") as f:
        json.dump(registry, f, indent=2)


def _migrate(raw: dict) -> dict:
    """Upgrade legacy flat config to school-scoped schema (idempotent, in memory)."""
    if "schools" in raw and "classes" not in raw:
        return raw

    term_subjects = raw.get("term_subjects", [])
    flat_classes = raw.get("classes", [])

    if "schools" in raw:
        registry = raw
        # Merge any flat legacy classes into the default school
        schools = registry.setdefault("schools", [])
        default = None
        for s in schools:
            if s.get("name", "").upper() == DEFAULT_SCHOOL:
                default = s
                break
        if default is None:
            default = {"school_id": _new_id(), "name": DEFAULT_SCHOOL, "classes": []}
            schools.insert(0, default)
        existing_labels = {c.get("label", "") for s in schools for c in s.get("classes", [])}
        for label in flat_classes:
            label = normalize_label(label)
            if label and label not in existing_labels:
                gl, arm = SchoolClass.split_label(label)
                default["classes"].append({
                    "class_id": _new_id(), "label": label,
                    "grade_level": gl, "arm": arm,
                })
        return registry

    return {
        "term_subjects": term_subjects,
        "schools": [{
            "school_id": _new_id(),
            "name": DEFAULT_SCHOOL,
            "classes": [
                {"class_id": _new_id(), "label": normalize_label(c),
                 "grade_level": SchoolClass.split_label(c)[0],
                 "arm": SchoolClass.split_label(c)[1]}
                for c in flat_classes
            ],
        }],
    }


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_schools(registry: dict) -> List[dict]:
    return registry.get("schools", [])


def get_classes(registry: dict, school_id: str = "") -> List[dict]:
    for school in get_schools(registry):
        if not school_id or school.get("school_id") == school_id:
            return school.get("classes", [])
    return []


def get_school_by_id(registry: dict, school_id: str) -> Optional[dict]:
    return next((s for s in get_schools(registry) if s.get("school_id") == school_id), None)


def get_class_by_id(registry: dict, class_id: str, school_id: str = "") -> Optional[dict]:
    for c in get_classes(registry, school_id):
        if c.get("class_id") == class_id:
            return c
    return None


def ensure_school(registry: dict, name: str = DEFAULT_SCHOOL) -> dict:
    """Get or create a school by name (normalized). Returns the school dict."""
    name = normalize_label(name) or DEFAULT_SCHOOL
    for s in registry["schools"]:
        if s.get("name") == name:
            return s
    school = {"school_id": _new_id(), "name": name, "classes": []}
    registry["schools"].append(school)
    return school


def create_school(registry: dict, name: str = DEFAULT_SCHOOL) -> dict:
    """Always create a new school. Names are labels, not identifiers, so two
    schools may share one; membership is never granted by matching a name."""
    school = {"school_id": _new_id(), "name": normalize_label(name) or DEFAULT_SCHOOL, "classes": []}
    registry["schools"].append(school)
    return school


def add_class(registry: dict, school_id: str, label: str) -> Optional[dict]:
    """Add a class to a school if the label doesn't already collide within that school."""
    school = get_school_by_id(registry, school_id)
    if school is None:
        return None
    label = normalize_label(label)
    if not label:
        return None
    existing = {c.get("label") for c in school["classes"]}
    if label in existing:
        return None
    gl, arm = SchoolClass.split_label(label)
    cls = {"class_id": _new_id(), "label": label, "grade_level": gl, "arm": arm}
    school["classes"].append(cls)
    return cls


def remove_class(registry: dict, school_id: str, class_id: str) -> bool:
    school = get_school_by_id(registry, school_id)
    if school is None:
        return False
    before = len(school["classes"])
    school["classes"] = [c for c in school["classes"] if c.get("class_id") != class_id]
    return len(school["classes"]) < before


def rename_class(registry: dict, school_id: str, class_id: str, new_label: str) -> bool:
    school = get_school_by_id(registry, school_id)
    cls = get_class_by_id(registry, class_id, school_id)
    if school is None or cls is None:
        return False
    new_label = normalize_label(new_label)
    if not new_label or new_label in {c.get("label") for c in school["classes"]}:
        return False
    cls["label"] = new_label
    gl, arm = SchoolClass.split_label(new_label)
    cls["grade_level"], cls["arm"] = gl, arm
    return True