"""
GradePulse API — FastAPI backend with JWT auth, multi-tenant CRUD, and brain operations.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Query, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
import os
import glob
import uuid
import tempfile
import numpy as np

from ..brain import Brain
from ..core.reward import calculate_reward
from ..sync import BrainSynchronizer
from ..backup import BackupManager
from ..registry import (
    load_registry, save_registry, ensure_school, add_class, remove_class,
    get_schools, get_classes, get_school_by_id, get_class_by_id,
)
from .auth import (
    create_user, authenticate_user, create_access_token,
    get_current_user, optional_user, update_user_school, get_user_by_id,
)
from .schemas import (
    StudentSchema, ContentSchema, RecommendationRequest, UpdateRequest,
    RewardRequest, NeuralScoreResponse, BrainSummary, SchoolResponse,
    ClassResponse, SignupRequest, LoginRequest, UserResponse,
    BulkUpdateRequest, TriageRequest, CreateSchoolRequest, CreateClassRequest,
    UpdateStudentRequest, IngestResponse,
)

BRAIN_STATE_PATH = os.getenv("BRAIN_STATE_PATH", "brain_state.json")
CONFIG_PATH = os.getenv("CONFIG_PATH", "class_config.json")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Auto-save every 30 seconds to keep workers synchronized
AUTO_SAVE_INTERVAL = float(os.getenv("AUTO_SAVE_INTERVAL", "30.0"))

# Backup configuration
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() == "true"
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
BACKUP_MAX_COUNT = int(os.getenv("BACKUP_MAX_COUNT", "24"))
BACKUP_INTERVAL = float(os.getenv("BACKUP_INTERVAL", "21600"))  # 6 hours

brain_instance: Optional[Brain] = None
synchronizer: Optional[BrainSynchronizer] = None
backup_manager: Optional[BackupManager] = None


def _load_brain() -> Brain:
    """
    Load brain state from disk with file locking.
    
    Each worker loads its own copy from disk, ensuring they all start
    with the same state. This prevents forked copies from diverging.
    """
    global synchronizer
    
    # Initialize synchronizer if not done yet
    if synchronizer is None:
        synchronizer = BrainSynchronizer(
            brain_state_path=BRAIN_STATE_PATH,
            config_path=CONFIG_PATH,
            auto_save_interval=AUTO_SAVE_INTERVAL,
        )
    
    # Try loading from main state file
    if os.path.exists(BRAIN_STATE_PATH):
        try:
            print(f"Worker {os.getpid()}: Loading Brain from {BRAIN_STATE_PATH}")
            brain = synchronizer.load_brain(Brain.load)
            if brain is not None:
                print(f"Worker {os.getpid()}: Brain loaded successfully")
                return brain
        except Exception as e:
            print(f"  Warning: Could not load {BRAIN_STATE_PATH}: {e}")
    
    # Try loading from checkpoints
    checkpoints = sorted(
        glob.glob("*_checkpoint_*.json") + glob.glob("oulad_checkpoint_*.json"),
        key=os.path.getmtime, reverse=True,
    )
    for cp in checkpoints:
        try:
            print(f"Worker {os.getpid()}: Loading Brain from checkpoint: {cp}")
            brain = synchronizer.load_brain(lambda path: Brain.load(cp))
            if brain is not None:
                print(f"Worker {os.getpid()}: Brain loaded from checkpoint")
                return brain
        except Exception as e:
            print(f"  Warning: Could not load {cp}: {e}")
    
    # Initialize new brain with demo data
    print(f"Worker {os.getpid()}: Initializing demo Brain with sample students and content...")
    brain = Brain(model_type="hybrid")
    _seed_demo_data(brain)
    synchronizer.set_brain(brain)
    # Save initial state so other workers can load it
    synchronizer.save_brain(brain.save)
    return brain


def _seed_demo_data(brain: Brain):
    students = [
        ("608041", "Alice", 0.72, "Math"), ("573152", "Bob", 0.45, "Science"),
        ("291018", "Charlie", 0.88, "History"), ("834729", "Diana", 0.61, "Math"),
        ("115503", "Eve", 0.93, "Science"),
    ]
    for sid, name, perf, topic in students:
        brain.add_student(sid, name, performance_score=perf, current_topic=topic)

    content_items = [
        ("C001", "Algebra Fundamentals", "Math", 2, "video"),
        ("C002", "Advanced Calculus", "Math", 5, "quiz"),
        ("C003", "Cell Biology", "Science", 3, "reading"),
        ("C004", "Quantum Physics", "Science", 5, "video"),
        ("C005", "World War II Overview", "History", 2, "reading"),
        ("C006", "Ancient Civilizations", "History", 4, "quiz"),
        ("C007", "Grammar Essentials", "English", 1, "video"),
        ("C008", "Creative Writing", "English", 3, "exercise"),
    ]
    for cid, title, topic, diff, ctype in content_items:
        brain.add_content(cid, title, topic, diff, ctype)

    for sid, _, _, _ in students:
        for _ in range(3):
            rec = brain.recommend(sid, top_n=1)
            brain.update(sid, rec.content_id, 0.5 + 0.5 * np.random.random())


def _get_registry():
    return load_registry(CONFIG_PATH)


def _save_registry(registry):
    save_registry(registry, CONFIG_PATH)


def _get_class_students(school_id: str = "", class_id: str = "") -> list:
    all_students = sorted(brain_instance.students.values(), key=lambda s: s.name)
    if school_id and class_id:
        return [s for s in all_students if s.school_id == school_id and s.class_id == class_id]
    if school_id:
        return [s for s in all_students if s.school_id == school_id]
    return all_students


@asynccontextmanager
async def lifespan(app: FastAPI):
    global brain_instance, synchronizer, backup_manager
    
    # Load brain state for this worker
    brain_instance = _load_brain()
    
    # Set brain in synchronizer and start auto-save
    if synchronizer is not None:
        synchronizer.set_brain(brain_instance)
        synchronizer.start_auto_save(lambda path: brain_instance.save(path))
        print(f"Worker {os.getpid()}: Auto-save started (every {AUTO_SAVE_INTERVAL}s)")
    
    # Initialize backup manager
    if BACKUP_ENABLED:
        backup_manager = BackupManager(
            backup_dir=BACKUP_DIR,
            max_backups=BACKUP_MAX_COUNT,
            backup_interval=BACKUP_INTERVAL,
        )
        # Register files for backup
        backup_manager.register_file(BRAIN_STATE_PATH)
        backup_manager.register_file(CONFIG_PATH)
        # Create initial backup
        backup_manager.create_backup("startup")
        # Start periodic backups
        backup_manager.start()
        print(f"Worker {os.getpid()}: Backups enabled (every {BACKUP_INTERVAL}s, max {BACKUP_MAX_COUNT})")
    
    yield
    
    # Shutdown: save brain state, stop auto-save, stop backups
    if backup_manager is not None:
        backup_manager.stop()
        backup_manager.create_backup("shutdown")
        print(f"Worker {os.getpid()}: Final backup created on shutdown")
    
    if synchronizer is not None:
        synchronizer.stop_auto_save()
        synchronizer.save_brain(brain_instance.save)
        print(f"Worker {os.getpid()}: Brain saved on shutdown")


app = FastAPI(title="GradePulse API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/signup", response_model=UserResponse)
def signup(request: SignupRequest):
    user = create_user(request.email, request.password)
    school = ensure_school(_get_registry(), f"{request.school_name.strip().upper()}" if request.school_name else "MY SCHOOL")
    update_user_school(user["id"], school["school_id"])
    _save_registry(_get_registry())
    token = create_access_token({"sub": user["id"]})
    return {"id": user["id"], "email": user["email"], "school_id": school["school_id"],
            "school_name": school["name"], "token": token}


@app.post("/auth/login", response_model=UserResponse)
def login(request: LoginRequest):
    user = authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    school = None
    if user.get("school_id"):
        school = get_school_by_id(_get_registry(), user["school_id"])
    token = create_access_token({"sub": user["id"]})
    return {"id": user["id"], "email": user["email"],
            "school_id": user.get("school_id", ""),
            "school_name": school["name"] if school else "",
            "token": token}


@app.get("/auth/me", response_model=UserResponse)
def me(user: dict = Depends(get_current_user)):
    school = None
    if user.get("school_id"):
        school = get_school_by_id(_get_registry(), user["school_id"])
    return {"id": user["id"], "email": user["email"],
            "school_id": user.get("school_id", ""),
            "school_name": school["name"] if school else ""}


# ══════════════════════════════════════════════════════════════════════════════
# SCHOOLS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/schools", response_model=List[SchoolResponse])
def list_schools(user: dict = Depends(get_current_user)):
    registry = _get_registry()
    schools = get_schools(registry)
    if user.get("school_id"):
        return [s for s in schools if s["school_id"] == user["school_id"]]
    return schools


@app.post("/schools", response_model=SchoolResponse)
def create_school(request: CreateSchoolRequest, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    school = ensure_school(registry, request.name.strip().upper())
    _save_registry(registry)
    if not user.get("school_id"):
        update_user_school(user["id"], school["school_id"])
    return school


@app.put("/schools/{school_id}", response_model=SchoolResponse)
def update_school(school_id: str, request: CreateSchoolRequest, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    school = get_school_by_id(registry, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school["name"] = request.name.strip().upper()
    _save_registry(registry)
    return school


@app.delete("/schools/{school_id}")
def delete_school(school_id: str, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    school = get_school_by_id(registry, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    class_ids = {c["class_id"] for c in school.get("classes", [])}
    for sid, student in list(brain_instance.students.items()):
        if student.school_id == school_id or student.class_id in class_ids:
            del brain_instance.students[sid]
    registry["schools"] = [s for s in registry["schools"] if s["school_id"] != school_id]
    _save_registry(registry)
    synchronizer.save_brain(brain_instance.save)
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/classes/{school_id}", response_model=List[ClassResponse])
def list_classes(school_id: str, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    classes = get_classes(registry, school_id=school_id)
    return classes


@app.post("/classes/{school_id}", response_model=ClassResponse)
def create_class(school_id: str, request: CreateClassRequest, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    cls = add_class(registry, school_id, request.label.strip().upper())
    if not cls:
        raise HTTPException(status_code=400, detail="Class already exists in this school")
    _save_registry(registry)
    return cls


@app.put("/classes/{school_id}/{class_id}", response_model=ClassResponse)
def update_class(school_id: str, class_id: str, request: CreateClassRequest, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    cls = get_class_by_id(registry, class_id, school_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    cls["label"] = request.label.strip().upper()
    _save_registry(registry)
    return cls


@app.delete("/classes/{school_id}/{class_id}")
def delete_class(school_id: str, class_id: str, user: dict = Depends(get_current_user)):
    registry = _get_registry()
    cls = get_class_by_id(registry, class_id, school_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    for sid, student in list(brain_instance.students.items()):
        if student.class_id == class_id:
            del brain_instance.students[sid]
    remove_class(registry, school_id, class_id)
    _save_registry(registry)
    synchronizer.save_brain(brain_instance.save)
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# STUDENTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/students", response_model=List[StudentSchema])
def list_students(
    school_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    sid = school_id or user.get("school_id", "")
    students = _get_class_students(school_id=sid, class_id=class_id or "")
    return [StudentSchema(
        student_id=s.student_id, name=s.name, grade_history=s.grade_history,
        performance_score=s.performance_score,
        current_topic=getattr(s, "current_topic", ""), metadata=s.metadata,
    ) for s in students]


@app.post("/students", response_model=StudentSchema)
def add_student(student: StudentSchema, user: dict = Depends(get_current_user)):
    try:
        brain_instance.add_student(
            student.student_id, student.name,
            grade_history=student.grade_history,
            performance_score=student.performance_score,
            current_topic=student.current_topic,
            metadata=student.metadata,
            school_id=user.get("school_id", ""),
            class_id=student.metadata.get("class_id", ""),
        )
        synchronizer.save_brain(brain_instance.save)
        return student
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/students/{student_id}", response_model=StudentSchema)
def update_student(student_id: str, request: UpdateStudentRequest, user: dict = Depends(get_current_user)):
    if student_id not in brain_instance.students:
        raise HTTPException(status_code=404, detail="Student not found")
    s = brain_instance.students[student_id]
    if request.name is not None:
        s.name = request.name
    if request.current_topic is not None:
        s.current_topic = request.current_topic
    if request.class_id is not None:
        s.class_id = request.class_id
    s.touch()
    synchronizer.save_brain(brain_instance.save)
    return StudentSchema(student_id=s.student_id, name=s.name, grade_history=s.grade_history,
                         performance_score=s.performance_score,
                         current_topic=getattr(s, "current_topic", ""), metadata=s.metadata)


@app.delete("/students/{student_id}")
def delete_student(student_id: str, user: dict = Depends(get_current_user)):
    if student_id not in brain_instance.students:
        raise HTTPException(status_code=404, detail="Student not found")
    del brain_instance.students[student_id]
    synchronizer.save_brain(brain_instance.save)
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/content", response_model=ContentSchema)
def add_content(content: ContentSchema, user: dict = Depends(get_current_user)):
    try:
        brain_instance.add_content(
            content.content_id, content.title, content.topic,
            content.difficulty, content.content_type,
        )
        return content
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# BRAIN OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/recommend")
def recommend(request: RecommendationRequest, user: dict = Depends(get_current_user)):
    try:
        result = brain_instance.recommend(request.student_id, topic=request.topic, top_n=request.top_n)
        if request.top_n == 1:
            return result.__dict__ if result else {}
        return [r.__dict__ for r in result]
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/update")
def update(request: UpdateRequest, user: dict = Depends(get_current_user)):
    try:
        brain_instance.update(request.student_id, request.content_id, request.reward)
        synchronizer.save_brain(brain_instance.save)
        return {"status": "success"}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/bulk-update")
def bulk_update(request: BulkUpdateRequest, user: dict = Depends(get_current_user)):
    entries = [{"student_id": e.student_id, "subject": e.subject, "score": e.score} for e in request.entries]
    result = brain_instance.bulk_update(entries)
    synchronizer.save_brain(brain_instance.save)
    return result


@app.post("/triage")
def triage(request: TriageRequest, user: dict = Depends(get_current_user)):
    result = brain_instance.triage(request.subject)
    return result


@app.post("/calculate-reward")
def get_reward(request: RewardRequest, user: dict = Depends(get_current_user)):
    reward = calculate_reward(
        request.before_score, request.after_score, request.completed,
        request.time_spent_ratio, request.engaged, request.churned,
    )
    return {"reward": reward}


@app.get("/summary", response_model=BrainSummary)
def get_summary(user: dict = Depends(get_current_user)):
    score = brain_instance.last_neural_score
    return {
        "student_count": len(brain_instance.students),
        "content_count": len(brain_instance.contents),
        "total_sessions": brain_instance.update_count,
        "model_type": brain_instance.model_type,
        "current_alpha": brain_instance.alpha,
        "current_gamma": brain_instance.gamma,
        "cumulative_regret": brain_instance.cumulative_regret,
        "last_neural_score": score.get("neural_score") if score else 0.0,
    }


@app.post("/save")
def save_brain_state(user: dict = Depends(get_current_user)):
    synchronizer.save_brain(brain_instance.save)
    return {"status": "saved", "path": BRAIN_STATE_PATH}


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/backup")
def create_backup(user: dict = Depends(get_current_user)):
    """Create an immediate backup of brain state and config."""
    if backup_manager is None:
        raise HTTPException(status_code=503, detail="Backup system not enabled")
    
    backup_info = backup_manager.create_backup("manual")
    if backup_info is None:
        raise HTTPException(status_code=500, detail="Backup creation failed")
    
    return {
        "status": "created",
        "path": backup_info.path,
        "timestamp": backup_info.timestamp.isoformat(),
        "files": backup_info.files,
        "size_bytes": backup_info.size_bytes,
    }


@app.get("/backups")
def list_backups(user: dict = Depends(get_current_user)):
    """List all available backups."""
    if backup_manager is None:
        raise HTTPException(status_code=503, detail="Backup system not enabled")
    
    backups = backup_manager.list_backups()
    return {
        "backups": [
            {
                "path": b.path,
                "timestamp": b.timestamp.isoformat(),
                "files": b.files,
                "size_bytes": b.size_bytes,
            }
            for b in sorted(backups, key=lambda x: x.timestamp, reverse=True)
        ],
        "total": len(backups),
    }


@app.post("/backup/restore")
def restore_backup(backup_path: str, user: dict = Depends(get_current_user)):
    """Restore brain state from a backup. Requires server restart after."""
    if backup_manager is None:
        raise HTTPException(status_code=503, detail="Backup system not enabled")
    
    # Stop auto-save before restoring
    if synchronizer is not None:
        synchronizer.stop_auto_save()
    
    success = backup_manager.restore_backup(backup_path)
    
    if not success:
        # Restart auto-save if restore failed
        if synchronizer is not None:
            synchronizer.start_auto_save(lambda path: brain_instance.save(path))
        raise HTTPException(status_code=500, detail="Backup restoration failed")
    
    # Save current state to ensure consistency
    if synchronizer is not None:
        synchronizer.save_brain(brain_instance.save)
        synchronizer.start_auto_save(lambda path: brain_instance.save(path))
    
    return {
        "status": "restored",
        "backup_path": backup_path,
        "message": "Brain state restored. Reload may be required.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATA INGESTION
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/ingest", response_model=IngestResponse)
async def ingest_data(
    file: UploadFile = File(...),
    type: str = Form(...),
    school: Optional[str] = Form(None),
    school_id: Optional[str] = Form(None),
    dry_run: bool = Form(False),
    user: dict = Depends(get_current_user),
):
    """
    Ingest student roster or content catalog from CSV/Excel upload.
    
    Args:
        file: CSV or Excel file to upload
        type: "students" or "content"
        school: School name (creates if not exists)
        school_id: School ID (overrides school name)
        dry_run: If true, validate only without writing
    """
    # Validate type parameter
    if type not in ("students", "content"):
        raise HTTPException(status_code=400, detail="type must be 'students' or 'content'")
    
    # Validate file extension
    filename = file.filename or "upload.csv"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel (.csv, .xlsx, .xls)")
    
    # Save uploaded file to temp location
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")
    
    try:
        # Import ingestion functions
        from ...ingest import ingest_students, ingest_content, ValidationReport
        
        # Load existing state
        registry = _get_registry()
        
        # Run ingestion
        if type == "students":
            report = ingest_students(
                tmp_path, registry, brain_instance.students,
                school_id=school_id or user.get("school_id"),
                school_name=school,
                dry_run=dry_run,
            )
        else:
            report = ingest_content(
                tmp_path, brain_instance.contents,
                dry_run=dry_run,
            )
        
        # Save if not dry run
        if not dry_run:
            # Save registry with file lock
            with synchronizer._config_lock:
                _save_registry(registry)
            
            # Save brain state with file lock
            synchronizer.save_brain(brain_instance.save)
        
        return IngestResponse(
            status="success" if report.errors == [] else "completed_with_errors",
            report=report.to_dict(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass


@app.get("/health")
def health_check():
    """Health check endpoint with backup status."""
    worker_count = int(os.getenv("WEB_CONCURRENCY", "1"))
    backup_status = "disabled"
    backup_count = 0
    
    if backup_manager is not None:
        backup_status = "enabled"
        backup_count = len(backup_manager.list_backups())
    
    return {
        "status": "alive",
        "engine": "GradePulse",
        "version": "1.0.0",
        "worker_pid": os.getpid(),
        "expected_workers": worker_count,
        "backup_status": backup_status,
        "backup_count": backup_count,
    }


@app.get("/")
def root_health_check():
    """Root health check endpoint (backward compatible)."""
    return health_check()
