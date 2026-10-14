import re
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Any
from datetime import date, datetime

class StudentSchema(BaseModel):
    student_id: str
    name: str
    class_id: str = ""
    school_id: str = ""
    grade_history: Dict[str, List[float]] = {}
    performance_score: float = 0.5
    current_topic: str = ""
    metadata: Dict[str, Any] = {}

class ContentSchema(BaseModel):
    content_id: str
    title: str
    topic: str
    difficulty: int = Field(..., ge=1, le=5)
    content_type: str

class RecommendationRequest(BaseModel):
    student_id: str
    topic: Optional[str] = None
    top_n: int = 1

class UpdateRequest(BaseModel):
    student_id: str
    content_id: str
    reward: float = Field(..., ge=-1.0, le=1.0)

class RewardRequest(BaseModel):
    before_score: float
    after_score: float
    completed: bool
    time_spent_ratio: float = 1.0
    engaged: bool = True
    churned: bool = False

class NeuralScoreResponse(BaseModel):
    exploration_score: float
    convergence_score: float
    context_score: float
    precision_score: float
    grade_score: float
    purity_score: float = 5.0
    balance_score: float = 7.5
    neural_score: float

class BrainSummary(BaseModel):
    student_count: int
    content_count: int
    total_sessions: int
    model_type: str
    current_alpha: float
    current_gamma: float
    cumulative_regret: float
    last_neural_score: Optional[float]

PASSWORD_MIN_LENGTH = 8
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _valid_new_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    return value


class SignupRequest(BaseModel):
    email: str
    password: str
    school_name: Optional[str] = None
    invite_code: Optional[str] = None  # join an existing school as a teacher

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return _valid_new_password(value)

class LoginRequest(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _check_new = field_validator("new_password")(classmethod(lambda cls, v: _valid_new_password(v)))

class ResetPasswordRequest(BaseModel):
    code: str
    new_password: str

    _check_new = field_validator("new_password")(classmethod(lambda cls, v: _valid_new_password(v)))

class OperatorResetRequest(BaseModel):
    email: str

class PasswordResetLink(BaseModel):
    code: str
    expires_at: str

class MemberResponse(BaseModel):
    id: str
    email: str
    role: str
    class_ids: List[str] = []  # a teacher's classes; empty for admins

class ClassAssignment(BaseModel):
    class_ids: List[str] = Field(..., max_length=200)

class UserResponse(BaseModel):
    id: str
    email: str
    school_id: str = ""
    school_name: str = ""
    role: str = ""
    token: str = ""

class InviteResponse(BaseModel):
    code: str
    created_at: str
    expires_at: str

class SchoolResponse(BaseModel):
    school_id: str
    name: str
    classes: List[Dict[str, Any]] = []

class CreateSchoolRequest(BaseModel):
    name: str

class ClassResponse(BaseModel):
    class_id: str
    label: str
    grade_level: str
    arm: str

class CreateClassRequest(BaseModel):
    label: str

class BulkUpdateEntry(BaseModel):
    student_id: str
    subject: str
    score: float = Field(..., ge=0.0, le=1.0)

class BulkUpdateRequest(BaseModel):
    entries: List[BulkUpdateEntry]
    # One sitting: the day the test was taken (today if omitted) and an
    # optional name for it, e.g. "Week 4 test". Re-sending the same student,
    # subject, date and label corrects the earlier score.
    assessed_on: Optional[date] = None
    label: str = Field("", max_length=80)

class ScoreRecord(BaseModel):
    subject: str
    score: float
    assessed_on: str
    label: str = ""
    source: str = "teacher"

class SchoolScoreRecord(BaseModel):
    student_id: str
    subject: str
    score: float
    assessed_on: str
    label: str = ""

class SubjectsPayload(BaseModel):
    subjects: List[str] = Field(..., max_length=40)

    @field_validator("subjects")
    @classmethod
    def _check_names(cls, value: List[str]) -> List[str]:
        if any(len(subject.strip()) > 40 for subject in value):
            raise ValueError("A subject name can be at most 40 characters")
        return value

class TriageRequest(BaseModel):
    subject: str
    class_id: Optional[str] = None  # limit the report to one class

class UpdateStudentRequest(BaseModel):
    name: Optional[str] = None
    current_topic: Optional[str] = None
    class_id: Optional[str] = None

class IngestResponse(BaseModel):
    status: str
    report: Dict[str, Any]
