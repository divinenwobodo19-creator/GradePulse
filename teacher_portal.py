"""
Teacher Portal — Streamlit App
================================
For traditional schools: input weekly scores, get group recommendations.

Run: PYTHONPATH=. streamlit run teacher_portal.py
"""

import json, os, sys
import streamlit as st
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from linucb_brain import Brain
from linucb_brain.registry import (
    load_registry, save_registry, ensure_school, add_class, remove_class,
    get_schools, get_classes, get_school_by_id, get_class_by_id,
    DEFAULT_SCHOOL,
)
from linucb_brain.models import normalize_label

st.set_page_config(page_title="Teacher Portal", layout="wide")

CONFIG_FILE = "class_config.json"

# ── Helpers ──────────────────────────────────────────────────────────────────

def nigerian_grade(score: float) -> str:
    p = score * 100
    if p >= 75:  return "A"
    if p >= 70:  return "B"
    if p >= 65:  return "B"
    if p >= 60:  return "C"
    if p >= 55:  return "C"
    if p >= 50:  return "C"
    if p >= 45:  return "D"
    if p >= 40:  return "E"
    return "F"


def nigerian_grade_description(score: float) -> str:
    p = score * 100
    if p >= 75:  return "Excellent"
    if p >= 70:  return "Very Good"
    if p >= 65:  return "Good"
    if p >= 60:  return "Credit"
    if p >= 55:  return "Credit"
    if p >= 50:  return "Credit"
    if p >= 45:  return "Pass"
    if p >= 40:  return "Pass"
    return "Fail"


def load_class_config() -> dict:
    return load_registry(CONFIG_FILE)


def save_class_config(config: dict) -> None:
    save_registry(config, CONFIG_FILE)


TIER_LABELS = {
    "remediation": {"label": "Needs Extra Help", "icon": "\U0001F534",
        "note": "Scored below 40% (F). Give them remedial exercises before moving on.",
        "color": "#E74C3C"},
    "on_track": {"label": "At Expected Level", "icon": "\U0001F7E1",
        "note": "Scored 40-74% (E to B). Continue with standard curriculum materials.",
        "color": "#F1C40F"},
    "ahead": {"label": "Ahead of Class", "icon": "\U0001F7E2",
        "note": "Scored 75% or above (A). Give them advanced or challenge materials.",
        "color": "#27AE60"},
}

TIER_ORDER = ["remediation", "on_track", "ahead"]

# ── Config & Brain ───────────────────────────────────────────────────────────

class_config = load_class_config()

@st.cache_resource
def get_brain():
    if os.path.exists("brain_state.json"):
        return Brain.load("brain_state.json")
    elif os.path.exists("school_brain_state.json"):
        return Brain.load("school_brain_state.json")
    else:
        b = Brain(model_type="hybrid", alpha=1.5, n_clusters=3)
        return b

brain = get_brain()

# Seed session state
if "term_subjects" not in st.session_state:
    st.session_state.term_subjects = class_config.get("term_subjects", [])

# Programmatic selection changes are deferred via pending_* keys set by
# button handlers. They are applied HERE, before any widget with these keys
# is instantiated (Streamlit forbids writing to widget state after creation).
if "pending_school_id" in st.session_state:
    st.session_state.selected_school_id = st.session_state.pop("pending_school_id")
if "pending_class_id" in st.session_state:
    st.session_state.selected_class_id = st.session_state.pop("pending_class_id")

if "selected_school_id" not in st.session_state:
    schools = get_schools(class_config)
    st.session_state.selected_school_id = schools[0]["school_id"] if schools else ""
if "selected_class_id" not in st.session_state:
    schools = get_schools(class_config)
    first_classes = get_classes(class_config, st.session_state.selected_school_id)
    st.session_state.selected_class_id = first_classes[0]["class_id"] if first_classes and st.session_state.selected_school_id else ""

# ── Derived lists (filtered by selected school + class) ─────────────────────

selected_school_id = st.session_state.selected_school_id
selected_class_id = st.session_state.selected_class_id
selected_class_label = ""
if selected_class_id:
    cdef = get_class_by_id(class_config, selected_class_id, selected_school_id)
    if cdef:
        selected_class_label = cdef["label"]


def get_class_students():
    all_students = sorted(brain.students.values(), key=lambda s: s.name)
    if selected_school_id and selected_class_id:
        return [s for s in all_students
                if s.school_id == selected_school_id and s.class_id == selected_class_id]
    if selected_school_id:
        return [s for s in all_students if s.school_id == selected_school_id]
    return all_students


def get_class_subjects():
    students = get_class_students()
    return sorted(set(
        subj for s in students
        for subj in s.grade_history.keys()
    ))


def persist_registry():
    save_class_config({
        "term_subjects": st.session_state.term_subjects,
        "schools": class_config["schools"],
    })

# ── Sidebar: School & Class management ──────────────────────────────────────

with st.sidebar:
    st.header("School & Class")

    school_options = get_schools(class_config)
    school_labels = {s["school_id"]: s["name"] for s in school_options}
    sel_school = st.selectbox(
        "School",
        [s["school_id"] for s in school_options],
        index=([s["school_id"] for s in school_options].index(selected_school_id)
               if selected_school_id in [s["school_id"] for s in school_options] else 0),
        format_func=lambda x: school_labels.get(x, x),
        key="selected_school_id",
    )

    class_options = get_classes(class_config, selected_school_id)
    class_labels = {}
    for c in class_options:
        count = sum(1 for s in brain.students.values()
                    if s.school_id == selected_school_id and s.class_id == c["class_id"])
        class_labels[c["class_id"]] = f"{c['label']} ({count} students)"
    sel_class = st.selectbox(
        "Class",
        [c["class_id"] for c in class_options],
        index=([c["class_id"] for c in class_options].index(selected_class_id)
               if selected_class_id in [c["class_id"] for c in class_options] else 0),
        format_func=lambda x: class_labels.get(x, x),
        key="selected_class_id",
    )

    with st.expander("Manage Schools"):
        st.caption("Create a new school. Each school gets its own classes.")
        new_school = st.text_input("New school name", placeholder="e.g. Enugu High School",
                                   key="new_school_input")
        if st.button("Create School"):
            name = new_school.strip().upper()
            if name:
                school = ensure_school(class_config, name)
                st.session_state.pending_school_id = school["school_id"]
                st.session_state.pending_class_id = ""
                persist_registry()
                st.rerun()

    with st.expander("Manage Classes"):
        st.caption("Create or remove classes inside the selected school.")
        new_class = st.text_input("New class name", placeholder="e.g. JSS1A",
                                   key="new_class_input")
        if st.button("Create Class"):
            label = new_class.strip().upper()
            if label and selected_school_id:
                cls = add_class(class_config, selected_school_id, label)
                if cls:
                    st.session_state.pending_class_id = cls["class_id"]
                    persist_registry()
                    st.rerun()
                else:
                    st.warning("Class already exists in this school.")

        if class_options:
            st.markdown("**Remove class**")
            class_to_del = st.selectbox(
                "Select class to remove",
                [c["class_id"] for c in class_options],
                format_func=lambda x: class_labels.get(x, x),
                key="del_class_sel")
            if class_to_del and st.button("Delete Class", type="primary"):
                remove_class(class_config, selected_school_id, class_to_del)
                if st.session_state.selected_class_id == class_to_del:
                    st.session_state.pending_class_id = ""
                persist_registry()
                st.rerun()

        if selected_school_id and selected_class_id:
            st.markdown("**Move students to another class**")
            students_in_class = [s for s in brain.students.values()
                                 if s.school_id == selected_school_id
                                 and s.class_id == selected_class_id]
            if students_in_class:
                other_classes = [c for c in class_options if c["class_id"] != selected_class_id]
                if other_classes:
                    target = st.selectbox(
                        "Move to",
                        [c["class_id"] for c in other_classes],
                        format_func=lambda x: class_labels.get(x, x),
                        key="move_target")
                    if st.button("Move All"):
                        for s in students_in_class:
                            brain.students[s.student_id].class_id = target
                            brain.students[s.student_id].school_id = selected_school_id
                            brain.students[s.student_id].touch()
                        brain.save("brain_state.json")
                        st.rerun()
                else:
                    st.caption("No other classes in this school yet.")
            else:
                st.caption("No students in this class.")

st.title("Teacher Portal")
st.markdown("Enter weekly test scores -- see which students need extra help and what to give them.")

# ── Onboarding for brand-new users ──────────────────────────────────────────
total_students = len(brain.students)
if total_students == 0 and not get_schools(class_config):
    st.info(
        "\U0001f4ac **Welcome! Let's get you started in 3 quick steps:**\n\n"
        "1️⃣ **Create a school** — use the sidebar (click _Manage Schools_ → type a name → _Create School_)\n"
        "2️⃣ **Create a class** — sidebar → _Manage Classes_ → e.g. _JSS1A_\n"
        "3️⃣ **Add students** — use the _Add Student_ form below, then enter scores\n\n"
        "Or click the button below to load demo data and explore right away:"
    )
    if st.button("\U0001f680 Load demo data (school + class + students)", use_container_width=True):
        school = ensure_school(class_config, "Demo School")
        cls = None
        for c in school["classes"]:
            if c["label"] == "JSS1A":
                cls = c
                break
        if cls is None:
            cls = add_class(class_config, school["school_id"], "JSS1A")
        demo_data = [
            ("S01", "Chinwe", 0.82, "Maths"), ("S02", "Emeka", 0.55, "Maths"),
            ("S03", "Amina", 0.91, "Maths"), ("S04", "Tunde", 0.63, "Maths"),
            ("S05", "Ngozi", 0.76, "English"), ("S06", "Chidi", 0.44, "English"),
            ("S07", "Zainab", 0.88, "English"), ("S08", "Efe", 0.59, "English"),
            ("S09", "Adaeze", 0.71, "Science"), ("S10", "Kelechi", 0.48, "Science"),
            ("S11", "Fatima", 0.93, "Science"), ("S12", "Obinna", 0.37, "Science"),
            ("S13", "Chioma", 0.79, "History"), ("S14", "Segun", 0.52, "History"),
            ("S15", "Yetunde", 0.85, "History"), ("S16", "Musa", 0.41, "History"),
        ]
        for sid, name, grade, topic in demo_data:
            brain.add_student(sid, name, performance_score=grade,
                              current_topic=topic,
                              school_id=school["school_id"], class_id=cls["class_id"])
        brain.save("brain_state.json")
        persist_registry()
        st.session_state.pending_school_id = school["school_id"]
        st.session_state.pending_class_id = cls["class_id"]
        st.rerun()

# ── Add Student form (always visible when data is low) ─────────────────────
total_students = len(brain.students)
if total_students < 30:
    with st.expander("\u2795 Add a new student", expanded=total_students == 0):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_id = st.text_input("Student ID", placeholder="e.g. S17",
                                   key="global_new_id")
        with c2:
            new_name = st.text_input("Full Name", placeholder="e.g. John Doe",
                                     key="global_new_name")
        with c3:
            new_subject = st.text_input("Main Subject", placeholder="e.g. Maths",
                                        key="global_new_subj")
        c4, c5 = st.columns(2)
        with c4:
            all_schools = get_schools(class_config)
            new_school = st.selectbox(
                "School", [s["school_id"] for s in all_schools],
                format_func=lambda x: next((s["name"] for s in all_schools if s["school_id"] == x), x),
                key="global_new_school")
        with c5:
            sel_classes = get_classes(class_config, new_school)
            new_class = st.selectbox(
                "Class", [c["class_id"] for c in sel_classes],
                format_func=lambda x: next((c["label"] for c in sel_classes if c["class_id"] == x), x),
                key="global_new_class")
        if st.button("Add Student", key="global_add_btn", use_container_width=True):
            if new_id and new_name and new_class:
                brain.add_student(new_id, normalize_label(new_name),
                                  performance_score=0.5,
                                  current_topic=new_subject.strip() or "",
                                  school_id=new_school, class_id=new_class)
                brain.save("brain_state.json")
                st.success(f"Added {normalize_label(new_name)}!")
                st.rerun()
            else:
                st.warning("Student ID, name, and a class are required.")

# Fresh copies filtered by selected class
student_list = get_class_students()
subjects_with_scores = get_class_subjects()

tab1, tab2, tab3, tab4 = st.tabs(["Enter Scores", "Class Groups", "Student Progress", "Print Report"])

# ============================================================================
# TAB 1 — Enter Scores
# ============================================================================
with tab1:
    st.subheader("Step 1: What subject are you teaching?")

    # ── Term subjects chips ─────────────────────────────────────────────────
    if st.session_state.term_subjects:
        subject_counts = {}
        for subj in st.session_state.term_subjects:
            count = 0
            for student in get_class_students():
                g = student.grade_history.get(subj, [])
                if len(g) > count:
                    count = len(g)
            subject_counts[subj] = count

        st.markdown("**This term's subjects:**")
        chip_cols = st.columns(6)
        for i, subj in enumerate(st.session_state.term_subjects):
            cnt = subject_counts[subj]
            label = f"{subj} x{cnt}" if cnt else subj
            with chip_cols[i % 6]:
                if st.button(label, key=f"chip_{i}", use_container_width=True):
                    st.session_state["subject_input"] = subj
                    st.rerun()

        with st.expander("Manage subjects"):
            st.caption("Remove subjects added by mistake, or add new ones.")
            for i, subj in enumerate(st.session_state.term_subjects):
                c1, c2 = st.columns([5, 1])
                cnt = subject_counts[subj]
                label = f"{subj}  ({cnt} entries)" if cnt else subj
                c1.markdown(f"**{label}**")
                if c2.button("Delete", key=f"del_subj_{i}", help=f"Remove {subj}"):
                    st.session_state.term_subjects.pop(i)
                    persist_registry()
                    st.rerun()
            st.text_input("Add a subject", key="add_subj_input",
                          placeholder="Subject name", label_visibility="collapsed")
            if st.button("Add"):
                new_s = normalize_label(st.session_state.get("add_subj_input", ""))
                if new_s and new_s not in st.session_state.term_subjects:
                    st.session_state.term_subjects.append(new_s)
                    persist_registry()
                    st.rerun()

    subject = st.text_input("Subject name (e.g. Basic Science - Week 4, Algebra - Week 1)",
                            placeholder="Type the subject or topic name", key="subject_input")
    subject = normalize_label(subject)

    # ── Score entry table ────────────────────────────────────────────────────
    if not student_list:
        st.warning("No students in this class. Create a class in the sidebar and add students.")
    elif not subject.strip():
        st.info("Type a subject name above to begin.")
    else:
        st.subheader(f"Step 2: Enter scores for \"{subject}\" (0-100)")

        rows = []
        for student in student_list:
            grades = student.grade_history.get(subject, [])
            last_score = int(grades[-1] * 100) if grades else int(student.performance_score * 100)
            rows.append({
                "Student": student.name,
                "Score (0-100)": last_score,
                "Absent": False,
            })

        df = pd.DataFrame(rows)
        edited_df = st.data_editor(
            df,
            column_config={
                "Student": st.column_config.TextColumn(
                    "Student", help="Edit student name if needed",
                ),
                "Score (0-100)": st.column_config.NumberColumn(
                    "Score (0-100)", min_value=0, max_value=100, step=1,
                    help="Enter score from 0 to 100",
                ),
                "Absent": st.column_config.CheckboxColumn(
                    "Absent", help="Check if student was absent",
                ),
            },
            hide_index=True,
            use_container_width=True,
            key=f"score_editor_{subject}_{selected_class_id}",
        )

        # ── Quick preview bar ────────────────────────────────────────────────
        absent_count = int(edited_df["Absent"].sum())
        present_df = edited_df[~edited_df["Absent"]]
        total_present = len(present_df)
        if total_present > 0:
            scores_pct = present_df["Score (0-100)"].values
            rem = int((scores_pct < 40).sum())
            on_tr = int(((scores_pct >= 40) & (scores_pct < 75)).sum())
            ahead = int((scores_pct >= 75).sum())
        else:
            rem = on_tr = ahead = 0

        preview_parts = [
            f"<b>Preview</b>"
        ]
        if total_present:
            preview_parts.append(
                f"\U0001F534 Needs Extra Help: {rem}"
                f"  \U0001F7E1 At Expected Level: {on_tr}"
                f"  \U0001F7E2 Ahead of Class: {ahead}"
            )
        if absent_count:
            preview_parts.append(f"Absent: {absent_count}")

        st.markdown(
            f"<div style='padding:8px 12px;background:#f0f2f6;border-radius:6px;font-size:14px;'>"
            f"{' | '.join(preview_parts)}"
            f"</div>",
            unsafe_allow_html=True,
        )

        if st.button("Submit Scores", type="primary", use_container_width=True):
            entries = []
            name_changed = False
            for i, student in enumerate(student_list):
                row = edited_df.iloc[i]
                if row["Absent"]:
                    continue
                new_name = " ".join(row["Student"].split())
                if new_name and new_name != student.name:
                    brain.students[student.student_id].name = new_name
                    name_changed = True
                score = row["Score (0-100)"]
                entries.append({"student_id": student.student_id, "subject": subject, "score": score / 100.0})

            if subject not in st.session_state.term_subjects:
                st.session_state.term_subjects.append(subject)

            with st.spinner("Saving scores to model..."):
                result = brain.bulk_update(entries)
                brain.save("brain_state.json")
                persist_registry()
            parts = [f"Scores saved for {result['processed']} students in \"{subject}\"."]
            if absent_count:
                parts.append(f"{absent_count} student(s) marked absent.")
            if name_changed:
                parts.append("Student names also updated.")
            st.success(" ".join(parts))
            st.rerun()

    with st.expander("Load demo students (Nigerian names)"):
        demo_data = [
            ("S01", "Chinwe", 0.82, "Maths"), ("S02", "Emeka", 0.55, "Maths"),
            ("S03", "Amina", 0.91, "Maths"), ("S04", "Tunde", 0.63, "Maths"),
            ("S05", "Ngozi", 0.76, "English"), ("S06", "Chidi", 0.44, "English"),
            ("S07", "Zainab", 0.88, "English"), ("S08", "Efe", 0.59, "English"),
            ("S09", "Adaeze", 0.71, "Science"), ("S10", "Kelechi", 0.48, "Science"),
            ("S11", "Fatima", 0.93, "Science"), ("S12", "Obinna", 0.37, "Science"),
            ("S13", "Chioma", 0.79, "History"), ("S14", "Segun", 0.52, "History"),
            ("S15", "Yetunde", 0.85, "History"), ("S16", "Musa", 0.41, "History"),
        ]
        load_schools = get_schools(class_config)
        if not load_schools:
            st.warning("Create a school in the sidebar first.")
        else:
            target_school = st.selectbox(
                "School", [s["school_id"] for s in load_schools],
                format_func=lambda x: next((s["name"] for s in load_schools if s["school_id"] == x), x),
                key="demo_school")
            t_classes = get_classes(class_config, target_school)
            target_class = st.selectbox(
                "Assign all to class", [c["class_id"] for c in t_classes],
                format_func=lambda x: next((c["label"] for c in t_classes if c["class_id"] == x), x),
                key="demo_class_target")
            if st.button("Load 16 demo students"):
                cid = target_class if target_class else ""
                for sid, name, grade, topic in demo_data:
                    brain.add_student(sid, name, performance_score=grade,
                                      current_topic=topic,
                                      school_id=target_school, class_id=cid)
                brain.save("brain_state.json")
                st.success("Demo students loaded! Select the class in the sidebar to see them.")
                st.rerun()

# ============================================================================
# TAB 2 — Class Groups
# ============================================================================
with tab2:
    st.subheader("Class Groups by Subject")

    if not subjects_with_scores:
        st.info("No scores entered yet for this class.")
    else:
        subj = st.selectbox("Select subject to view groups",
                            subjects_with_scores, key="triage_subject")
        result = brain.triage(subj)
        st.metric("Total Students Assessed", result["total_students"])

        t1, t2, t3 = st.columns(3)
        for col, tier_name in zip([t1, t2, t3], TIER_ORDER):
            tier = result["tiers"][tier_name]
            info = TIER_LABELS[tier_name]
            with col:
                st.markdown(f"### {info['icon']} {info['label']}")
                st.markdown(f"**{tier['count']} students**")
                st.caption(info["note"])
                names = [(s["name"], s["predicted_score"]) for s in tier["students"]]
                if names:
                    for name, pscore in names:
                        grade = nigerian_grade(pscore)
                        st.markdown(f"- {name} ({grade})")
                else:
                    st.markdown("_No students in this group._")

        not_assessed = [s.name for s in student_list
                        if not s.grade_history.get(subj)]
        with st.expander(f"Not yet assessed: {len(not_assessed)} students"):
            if not_assessed:
                for name in not_assessed:
                    st.markdown(f"- {name}")
            else:
                st.caption("Everyone in this class has at least one score for this subject.")

# ============================================================================
# TAB 3 — Student Progress
# ============================================================================
with tab3:
    st.subheader("Student Progress by Subject")

    if not subjects_with_scores:
        st.info("No scores recorded yet for this class.")
    else:
        selected_subj = st.selectbox("Select subject to view",
                                     subjects_with_scores, key="progress_subj")

        rows = []
        for student in student_list:
            grades = student.grade_history.get(selected_subj, [])
            if grades:
                latest = grades[-1]
                avg = sum(grades) / len(grades)
                numbered = "  ".join(
                    f"{i+1}: {g*100:.0f}" for i, g in enumerate(grades)
                )
                rows.append({
                    "Student": student.name,
                    "Latest": f"{latest*100:.0f}",
                    "Average": f"{avg*100:.0f}",
                    "Grade": nigerian_grade(avg),
                    "Tests Taken": len(grades),
                    "Scores Over Time": numbered,
                })
            else:
                rows.append({
                    "Student": student.name,
                    "Latest": "-",
                    "Average": "-",
                    "Grade": "-",
                    "Tests Taken": 0,
                    "Scores Over Time": "No scores yet",
                })

        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    with st.expander("Register a new student"):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_id = st.text_input("Student ID", placeholder="e.g. S17",
                                   key="tab3_new_id")
        with c2:
            new_name = st.text_input("Full Name", placeholder="e.g. John Doe",
                                     key="tab3_new_name")
        with c3:
            new_subject = st.text_input("Main Subject", placeholder="e.g. Maths",
                                        key="tab3_new_subj")
        c4, c5 = st.columns(2)
        with c4:
            tab3_schools = get_schools(class_config)
            new_school = st.selectbox(
                "School", [s["school_id"] for s in tab3_schools],
                format_func=lambda x: next((s["name"] for s in tab3_schools if s["school_id"] == x), x),
                key="tab3_new_school")
        with c5:
            tab3_classes = get_classes(class_config, new_school)
            new_class = st.selectbox(
                "Class", [c["class_id"] for c in tab3_classes],
                format_func=lambda x: next((c["label"] for c in tab3_classes if c["class_id"] == x), x),
                key="tab3_new_class")
        if st.button("Add Student", key="tab3_add_btn", use_container_width=True):
            if new_id and new_name and new_class:
                brain.add_student(new_id, normalize_label(new_name),
                                  performance_score=0.5,
                                  current_topic=new_subject.strip() or "",
                                  school_id=new_school, class_id=new_class)
                brain.save("brain_state.json")
                st.success(f"Added {normalize_label(new_name)}!")
                st.rerun()
            else:
                st.warning("Student ID, name, and a class are required.")

# ============================================================================
# TAB 4 — Printable Report
# ============================================================================
with tab4:
    st.subheader("Printable Class Report")

    if not subjects_with_scores:
        st.info("No scores entered yet.")
    else:
        report_subj = st.selectbox("Subject for report", subjects_with_scores, key="report_subj")

        if st.button("Generate Report", type="primary"):
            result = brain.triage(report_subj)

            waec_legend = """
            <h3 style="margin-top:30px;">WAEC Grading Scale Reference</h3>
            <table style="width:auto; border-collapse:collapse; font-size:11pt;">
              <tr style="background:#2C3E50;color:white;">
                <th style="padding:6px 12px;">Grade</th>
                <th style="padding:6px 12px;">Score Range</th>
                <th style="padding:6px 12px;">Meaning</th>
              </tr>
              <tr style="background:#E8F8F5;"><td>A1</td><td>75-100%</td><td>Excellent</td></tr>
              <tr><td>B2</td><td>70-74%</td><td>Very Good</td></tr>
              <tr style="background:#FEF9E7;"><td>B3</td><td>65-69%</td><td>Good</td></tr>
              <tr><td>C4</td><td>60-64%</td><td>Credit</td></tr>
              <tr style="background:#FEF9E7;"><td>C5</td><td>55-59%</td><td>Credit</td></tr>
              <tr><td>C6</td><td>50-54%</td><td>Credit</td></tr>
              <tr style="background:#FEF9E7;"><td>D7</td><td>45-49%</td><td>Pass</td></tr>
              <tr><td>E8</td><td>40-44%</td><td>Pass</td></tr>
              <tr style="background:#FDEDEC;"><td>F9</td><td>0-39%</td><td>Fail</td></tr>
            </table>"""

            html = f"""
            <html><head><meta charset="utf-8">
            <style>
              body {{ font-family: Arial, sans-serif; font-size: 12pt; padding: 20px; }}
              h1 {{ color: #2C3E50; border-bottom: 3px solid #3498DB; padding-bottom: 8px; }}
              h2 {{ margin-top: 24px; }}
              .students {{ font-size: 12pt; line-height: 1.8; }}
              .box {{ padding: 12px 16px; border-radius: 6px; margin: 12px 0; }}
              .box-red {{ background: #FDEDEC; border-left: 5px solid #E74C3C; }}
              .box-yellow {{ background: #FEF9E7; border-left: 5px solid #F1C40F; }}
              .box-green {{ background: #E8F8F5; border-left: 5px solid #27AE60; }}
              .note {{ font-size: 11pt; color: #555; font-style: italic; }}
              .footer {{ margin-top: 30px; font-size: 10pt; color: #999; border-top: 1px solid #ccc; padding-top: 10px; }}
              .grade {{ font-weight: bold; }}
            </style></head>
            <body>
            <h1>Class Report -- {report_subj}</h1>
            <p><strong>Class:</strong> {selected_class_label or "All Students"}</p>
            <p><strong>Total students assessed:</strong> {result['total_students']}</p>
            """

            tier_css = {"remediation": "box-red", "on_track": "box-yellow", "ahead": "box-green"}
            for tier_name in TIER_ORDER:
                tier = result["tiers"][tier_name]
                info = TIER_LABELS[tier_name]
                names = [(s["name"], s["predicted_score"]) for s in tier["students"]]
                html += f"<div class='box {tier_css[tier_name]}'>"
                html += f"<h2>{info['icon']} {info['label']} - {tier['count']} students</h2>"
                html += f"<p class='note'>{info['note']}</p>"
                if names:
                    for name, pscore in names:
                        grade = nigerian_grade(pscore)
                        desc = nigerian_grade_description(pscore)
                        html += f"<div class='students'>- {name} <span class='grade'>({grade} - {desc})</span></div>"
                else:
                    html += "<p>_No students in this group._</p>"
                html += "</div>"

            not_assessed = [s.name for s in student_list
                            if not s.grade_history.get(report_subj)]
            if not_assessed:
                html += "<h2>\u23f3 Not yet assessed</h2>"
                html += "<p class='note'>These students have no scores for this subject yet.</p>"
                html += "<div class='students'>"
                for name in not_assessed:
                    html += f"<div class='students'>- {name}</div>"
                html += "</div>"

            html += waec_legend
            html += f'<div class="footer">Generated by Smart Content Recommender - {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}</div>'
            html += "</body></html>"

            st.download_button(
                "Download HTML Report (print from browser)",
                html,
                file_name=f"class_report_{report_subj}.html",
                mime="text/html",
                use_container_width=True,
            )

            st.divider()
            st.markdown("### Preview")
            st.components.v1.html(html, height=600, scrolling=True)

# ============================================================================
# FOOTER — Run Tests
# ============================================================================
with st.expander("\u2699\ufe0f Diagnostics — Run Tests"):
    if st.button("Run all 20 tests", type="secondary", use_container_width=True):
        import subprocess, sys
        with st.spinner("Running tests..."):
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True, text=True, timeout=120,
            )
        out = r.stdout + r.stderr
        st.code(out, language="bash")
        if r.returncode == 0:
            st.success(f"All tests passed! (exit code {r.returncode})")
        else:
            st.error(f"Some tests failed (exit code {r.returncode})")
