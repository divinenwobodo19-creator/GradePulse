#!/usr/bin/env python3
"""
Generate pilot-grade validation dataset for GradePulse.
Exercises all edge cases the pipeline will face in production.
"""
import csv
import os
import random

random.seed(2026)  # Reproducible

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sample_data", "pilot_grade")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Name pools ────────────────────────────────────────────────────────────────

FIRST_MALE = [
    "Adebayo", "Chinedu", "Emeka", "Tunde", "Kola", "Femi", "Dapo", "Wale",
    "Segun", "Kayode", "Biodun", "Lanre", "Tobi", "Yemi", "Gbenga", "Sola",
    "Bankole", "Demola", "Jide", "Kunle", "Niyi", "Obinna", "Uche", "Chidi",
    "Ikenna", "Chukwuemeka", "Ifeanyi", "Kelechi", "Olumide", "Akin",
    "Babatunde", "Oluwaseun", "Adewale", "Taiwo", "Kehinde", "Ayomide",
    "Joshua", "Daniel", "Ibrahim", "Abdulrahman",
]
FIRST_FEMALE = [
    "Chidinma", "Ngozi", "Adaeze", "Funke", "Bimpe", "Tolu", "Sade", "Bola",
    "Yetunde", "Folake", "Amara", "Nneka", "Chioma", "Obiageli", "Ifeoma",
    "Aisha", "Halima", "Zainab", "Fatima", "Amina", "Blessing", "Grace",
    "Mercy", "Esther", "Ruth", "Deborah", "Victoria", "Patience", "Joy", "Peace",
    "Oluwadamilola", "Titilayo", "Modupe", "Titilope", "Aanu", "Busayo",
]
LAST_NAMES = [
    "Olawale", "Nnamdi", "Abubakar", "Okonkwo", "Adeyemi", "Balogun", "Okafor",
    "Ibrahim", "Ogundimu", "Chukwuemeka", "Afolabi", "Eze", "Aliyu", "Akinwale",
    "Nwosu", "Mohammed", "Olawuwo", "Igwe", "Adeleke", "Ogundele", "Ugwu",
    "Adebanjo", "Olaniyan", "Chidebe", "Ogundipe", "Suleiman", "Adekunle",
    "Obiora", "Ibekwe", "Adegoke", "Olatunji", "Adebisi", "Onwueme",
    "Osagie", "Emenike", "Uchechukwu", "Akande", "Oyewole", "Adesanya",
]

# ── Schools and classes ───────────────────────────────────────────────────────

SCHOOLS = {
    "LAGOS MODEL SCHOOL": {
        "classes": ["JSS1A", "JSS1B", "JSS2A", "JSS2B", "JSS3A", "SSS1A", "SSS1B", "SSS2A", "SSS2B", "SSS3A"],
        "region": 1.0,
    },
    "ABUJA PREP ACADEMY": {
        "classes": ["JSS1A", "JSS2A", "JSS3A", "SSS1A", "SSS2A", "SSS3A"],
        "region": 3.0,
    },
    "PORT HARCOURT COLLEGE": {
        "classes": ["JSS1A", "JSS2A", "JSS3A", "SSS1A", "SSS2A", "SSS3A"],
        "region": 5.0,
    },
    "KANO GRAMMAR SCHOOL": {
        "classes": ["JSS1A", "JSS2A", "SSS1A", "SSS2A", "SSS3A"],
        "region": 7.0,
    },
}

TOPICS = ["Math", "Science", "English", "History"]
CONTENT_TYPES = ["video", "quiz", "exercise", "reading"]

GRADE_LEVELS = {
    "JSS1": (1.0, (1.0, 2.0), (0.30, 0.70)),
    "JSS2": (2.0, (2.0, 3.0), (0.35, 0.75)),
    "JSS3": (3.0, (3.0, 4.0), (0.40, 0.80)),
    "SSS1": (4.0, (4.0, 5.0), (0.45, 0.85)),
    "SSS2": (5.0, (5.0, 6.0), (0.50, 0.90)),
    "SSS3": (6.0, (6.0, 7.0), (0.55, 0.95)),
}


def make_name():
    first = random.choice(FIRST_MALE if random.random() < 0.5 else FIRST_FEMALE)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"


def make_grade_history(base_perf, trend="stable", length=None):
    """Generate a realistic grade history list."""
    if length is None:
        length = random.randint(3, 7)

    if trend == "improving":
        start = max(0.1, base_perf - 0.2)
        history = [round(min(1.0, start + i * 0.05 + random.uniform(-0.03, 0.03)), 2) for i in range(length)]
    elif trend == "declining":
        start = min(1.0, base_perf + 0.2)
        history = [round(max(0.05, start - i * 0.05 + random.uniform(-0.03, 0.03)), 2) for i in range(length)]
    elif trend == "volatile":
        history = [round(max(0.05, min(1.0, base_perf + random.uniform(-0.25, 0.25))), 2) for _ in range(length)]
    else:  # stable
        history = [round(max(0.05, min(1.0, base_perf + random.uniform(-0.05, 0.05))), 2) for _ in range(length)]

    return history


def history_str(history):
    return ";".join(str(h) for h in history) if history else ""


# ── Generate students ─────────────────────────────────────────────────────────

students = []
student_id = 1

# Edge case categories
EDGE_CASES = [
    # (count, trend, description)
    (8, "stable", "normal students"),
    (5, "improving", "improving students"),
    (5, "declining", "declining students"),
    (4, "volatile", "volatile students"),
    (6, None, "brand new students (no history, session=0)"),
    (3, None, "high performers (perf > 0.9)"),
    (3, None, "low performers (perf < 0.2)"),
    (2, None, "students with very few sessions (1-2)"),
    (2, None, "students with many sessions (50+)"),
    (2, None, "students with missing class_label"),
    (2, None, "students with missing performance_score"),
]

# Distribute edge cases across schools/classes
student_id = 1
student_rows = []

for school_name, school_info in SCHOOLS.items():
    region = school_info["region"]
    for class_label in school_info["classes"]:
        # Determine grade level from class label
        grade_key = ""
        for gl in GRADE_LEVELS:
            if class_label.startswith(gl):
                grade_key = gl
                break

        if not grade_key:
            continue

        edu_level, age_range, perf_range = GRADE_LEVELS[grade_key]

        # Generate 2-4 students per class
        num_students = random.randint(2, 4)
        for _ in range(num_students):
            name = make_name()
            perf = round(random.uniform(*perf_range), 2)
            sessions = random.randint(0, 40)
            topic = random.choice(TOPICS)
            credits = round(edu_level * random.uniform(3, 6), 1)
            imd = round(random.uniform(0.15, 0.85), 2)
            age = round(random.uniform(*age_range), 1)

            # Grade history for current topic
            trend = random.choice(["stable", "improving", "declining", "volatile"])
            hist = make_grade_history(perf, trend)

            row = {
                "student_id": f"STU{student_id:03d}",
                "name": name,
                "class_label": class_label,
                "school_name": school_name,
                "performance_score": str(perf),
                "session_count": str(sessions),
                "current_topic": topic,
                "education_level": str(edu_level),
                "age_band": str(age),
                "credits_studied": str(credits),
                "imd_band": str(imd),
                "region_code": str(region),
                "grade_history_math": history_str(hist if topic == "Math" else []),
                "grade_history_science": history_str(hist if topic == "Science" else []),
                "grade_history_english": history_str(hist if topic == "English" else []),
                "grade_history_history": history_str(hist if topic == "History" else []),
            }
            student_rows.append(row)
            student_id += 1

# ── Inject edge cases ─────────────────────────────────────────────────────────

# Brand new students (no history, session=0)
for i in range(6):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(list(GRADE_LEVELS.keys()))
    edu, age_r, _ = GRADE_LEVELS[grade]
    class_label = f"{grade}{random.choice(['A', 'B'])}"
    student_id_num = student_id + i
    student_rows.append({
        "student_id": f"STU{student_id_num:03d}",
        "name": make_name(),
        "class_label": class_label,
        "school_name": school,
        "performance_score": "0.5",
        "session_count": "0",
        "current_topic": random.choice(TOPICS),
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": "0.0",
        "imd_band": str(round(random.uniform(0.2, 0.8), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": "",
        "grade_history_science": "",
        "grade_history_english": "",
        "grade_history_history": "",
    })
student_id += 6

# High performers (perf > 0.9)
for i in range(3):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(["SSS2", "SSS3"])
    edu, age_r, _ = GRADE_LEVELS[grade]
    perf = round(random.uniform(0.91, 0.99), 2)
    hist = make_grade_history(perf, "improving")
    student_rows.append({
        "student_id": f"STU{student_id:03d}",
        "name": make_name(),
        "class_label": f"{grade}A",
        "school_name": school,
        "performance_score": str(perf),
        "session_count": str(random.randint(25, 50)),
        "current_topic": "Math",
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": str(round(edu * 5, 1)),
        "imd_band": str(round(random.uniform(0.2, 0.6), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": history_str(hist),
        "grade_history_science": "",
        "grade_history_english": "",
        "grade_history_history": "",
    })
    student_id += 1

# Low performers (perf < 0.2)
for i in range(3):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(["JSS1", "JSS2"])
    edu, age_r, _ = GRADE_LEVELS[grade]
    perf = round(random.uniform(0.08, 0.19), 2)
    hist = make_grade_history(perf, "declining")
    student_rows.append({
        "student_id": f"STU{student_id:03d}",
        "name": make_name(),
        "class_label": f"{grade}A",
        "school_name": school,
        "performance_score": str(perf),
        "session_count": str(random.randint(5, 15)),
        "current_topic": "Science",
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": str(round(edu * 4, 1)),
        "imd_band": str(round(random.uniform(0.4, 0.9), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": "",
        "grade_history_science": history_str(hist),
        "grade_history_english": "",
        "grade_history_history": "",
    })
    student_id += 1

# Very few sessions (1-2)
for i in range(2):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(list(GRADE_LEVELS.keys()))
    edu, age_r, _ = GRADE_LEVELS[grade]
    student_rows.append({
        "student_id": f"STU{student_id:03d}",
        "name": make_name(),
        "class_label": f"{grade}A",
        "school_name": school,
        "performance_score": str(round(random.uniform(0.4, 0.7), 2)),
        "session_count": str(random.randint(1, 2)),
        "current_topic": random.choice(TOPICS),
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": str(round(edu * 3, 1)),
        "imd_band": str(round(random.uniform(0.2, 0.7), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": "",
        "grade_history_science": "",
        "grade_history_english": "",
        "grade_history_history": "",
    })
    student_id += 1

# Many sessions (50+)
for i in range(2):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(["SSS2", "SSS3"])
    edu, age_r, _ = GRADE_LEVELS[grade]
    perf = round(random.uniform(0.6, 0.85), 2)
    hist = make_grade_history(perf, "stable", length=8)
    student_rows.append({
        "student_id": f"STU{student_id:03d}",
        "name": make_name(),
        "class_label": f"{grade}A",
        "school_name": school,
        "performance_score": str(perf),
        "session_count": str(random.randint(50, 80)),
        "current_topic": "English",
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": str(round(edu * 5, 1)),
        "imd_band": str(round(random.uniform(0.3, 0.7), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": "",
        "grade_history_science": "",
        "grade_history_english": history_str(hist),
        "grade_history_history": "",
    })
    student_id += 1

# Missing class_label
for i in range(2):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(list(GRADE_LEVELS.keys()))
    edu, age_r, _ = GRADE_LEVELS[grade]
    student_rows.append({
        "student_id": f"STU{student_id:03d}",
        "name": make_name(),
        "class_label": "",
        "school_name": school,
        "performance_score": str(round(random.uniform(0.4, 0.8), 2)),
        "session_count": str(random.randint(5, 20)),
        "current_topic": random.choice(TOPICS),
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": str(round(edu * 4, 1)),
        "imd_band": str(round(random.uniform(0.2, 0.8), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": "",
        "grade_history_science": "",
        "grade_history_english": "",
        "grade_history_history": "",
    })
    student_id += 1

# Missing performance_score
for i in range(2):
    school = random.choice(list(SCHOOLS.keys()))
    grade = random.choice(list(GRADE_LEVELS.keys()))
    edu, age_r, _ = GRADE_LEVELS[grade]
    student_rows.append({
        "student_id": f"STU{student_id:03d}",
        "name": make_name(),
        "class_label": f"{grade}A",
        "school_name": school,
        "performance_score": "",
        "session_count": str(random.randint(5, 20)),
        "current_topic": random.choice(TOPICS),
        "education_level": str(edu),
        "age_band": str(round(random.uniform(*age_r), 1)),
        "credits_studied": str(round(edu * 4, 1)),
        "imd_band": str(round(random.uniform(0.2, 0.8), 2)),
        "region_code": str(SCHOOLS[school]["region"]),
        "grade_history_math": "",
        "grade_history_science": "",
        "grade_history_english": "",
        "grade_history_history": "",
    })
    student_id += 1

# ── Write students CSV ────────────────────────────────────────────────────────

STUDENT_FIELDS = [
    "student_id", "name", "class_label", "school_name",
    "performance_score", "session_count", "current_topic",
    "education_level", "age_band", "credits_studied", "imd_band", "region_code",
    "grade_history_math", "grade_history_science", "grade_history_english", "grade_history_history",
]

students_path = os.path.join(OUTPUT_DIR, "pilot_students.csv")
with open(students_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=STUDENT_FIELDS)
    writer.writeheader()
    writer.writerows(student_rows)

print(f"Students: {len(student_rows)} written to {students_path}")

# ── Generate content catalog ──────────────────────────────────────────────────

content_items = []
content_id = 1

CONTENT_CATALOG = {
    "Math": [
        ("Number Operations", 1, "video"),
        ("Fractions and Decimals", 2, "reading"),
        ("Algebraic Expressions", 3, "exercise"),
        ("Quadratic Equations", 4, "quiz"),
        ("Trigonometry Fundamentals", 3, "video"),
        ("Statistics and Probability", 2, "quiz"),
        ("Geometry Proofs", 5, "exercise"),
        ("Matrices and Determinants", 4, "reading"),
        ("Calculus Introduction", 5, "video"),
        ("Logarithms and Indices", 3, "quiz"),
    ],
    "Science": [
        ("Cell Biology Basics", 1, "video"),
        ("Chemical Bonding", 2, "reading"),
        ("Newton's Laws of Motion", 3, "exercise"),
        ("Acids and Bases", 2, "quiz"),
        ("Electromagnetic Waves", 4, "video"),
        ("Organic Chemistry", 5, "reading"),
        ("Ecology and Ecosystems", 2, "exercise"),
        ("Genetics and Heredity", 4, "quiz"),
        ("Energy Transformations", 3, "video"),
        ("Lab Safety Procedures", 1, "reading"),
    ],
    "English": [
        ("Parts of Speech", 1, "video"),
        ("Sentence Construction", 2, "exercise"),
        ("Comprehension Strategies", 3, "quiz"),
        ("Essay Writing Structure", 4, "reading"),
        ("Figurative Language", 3, "video"),
        ("Grammar and Punctuation", 2, "quiz"),
        ("Literary Devices", 4, "exercise"),
        ("Summary Writing", 2, "reading"),
        ("Formal Letter Writing", 3, "video"),
        ("Debate and Argumentation", 5, "exercise"),
    ],
    "History": [
        ("Pre-Colonial Nigeria", 1, "reading"),
        ("The Sokoto Caliphate", 2, "video"),
        ("British Colonial Rule", 3, "quiz"),
        ("Nigerian Independence", 2, "exercise"),
        ("First Republic and Civil War", 4, "reading"),
        ("Modern Nigerian Democracy", 3, "video"),
        ("West African Trade Routes", 2, "reading"),
        ("Ancient Benin Kingdom", 3, "video"),
        ("Women in Nigerian History", 4, "exercise"),
        ("Pan-Africanism Movement", 5, "quiz"),
    ],
}

for topic, items in CONTENT_CATALOG.items():
    for title, difficulty, ctype in items:
        content_items.append({
            "content_id": f"PC{content_id:03d}",
            "title": title,
            "topic": topic,
            "difficulty": str(difficulty),
            "content_type": ctype,
        })
        content_id += 1

CONTENT_FIELDS = ["content_id", "title", "topic", "difficulty", "content_type"]
content_path = os.path.join(OUTPUT_DIR, "pilot_content.csv")
with open(content_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=CONTENT_FIELDS)
    writer.writeheader()
    writer.writerows(content_items)

print(f"Content: {len(content_items)} written to {content_path}")

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"PILOT-GRADE DATASET SUMMARY")
print(f"{'='*60}")
print(f"Students: {len(student_rows)}")
print(f"Content items: {len(content_items)}")
print(f"Schools: {len(SCHOOLS)}")
for name, info in SCHOOLS.items():
    count = sum(1 for s in student_rows if s["school_name"] == name)
    print(f"  - {name}: {count} students, {len(info['classes'])} classes")
print(f"Edge cases included:")
print(f"  - Brand new students (session=0, no history): 6")
print(f"  - High performers (perf > 0.9): 3")
print(f"  - Low performers (perf < 0.2): 3")
print(f"  - Very few sessions (1-2): 2")
print(f"  - Many sessions (50+): 2")
print(f"  - Missing class_label: 2")
print(f"  - Missing performance_score: 2")
print(f"Grade levels: JSS1-SSS3")
print(f"Content difficulty range: 1-5")
print(f"Content types: video, quiz, exercise, reading")
print(f"{'='*60}")
