import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional, Any
from datetime import date, datetime

# Upper bounds on what one request may carry. Without them a single request
# with a 500,000-character name or 100,000 score entries could stall the API.
ID_MAX = 64
NAME_MAX = 120
TOPIC_MAX = 120
SUBJECT_MAX = 40
BULK_MAX_ENTRIES = 2000
METADATA_MAX_BYTES = 4096


class StudentSchema(BaseModel):
    student_id: str = Field(..., max_length=ID_MAX)
    name: str = Field(..., max_length=NAME_MAX)
    class_id: str = Field("", max_length=ID_MAX)
    school_id: str = Field("", max_length=ID_MAX)
    grade_history: Dict[str, List[float]] = Field(default_factory=dict, max_length=40)
    performance_score: float = 0.5
    current_topic: str = Field("", max_length=TOPIC_MAX)
    metadata: Dict[str, Any] = Field(default_factory=dict, max_length=20)

    @field_validator("grade_history")
    @classmethod
    def _check_history(cls, value: Dict[str, List[float]]) -> Dict[str, List[float]]:
        if any(len(subject) > SUBJECT_MAX or len(scores) > 200 for subject, scores in value.items()):
            raise ValueError("grade_history is too large")
        return value

    @field_validator("metadata")
    @classmethod
    def _check_metadata(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        import json
        if len(json.dumps(value, default=str)) > METADATA_MAX_BYTES:
            raise ValueError("metadata is too large")
        return value

class ContentSchema(BaseModel):
    content_id: str
    title: str
    topic: str
    difficulty: int = Field(..., ge=1, le=5)
    content_type: str

class RecommendationRequest(BaseModel):
    student_id: str
    topic: Optional[str] = Field(None, max_length=TOPIC_MAX)
    top_n: int = Field(1, ge=1, le=20)

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

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 256
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Passwords that are guessed first. A new password is refused when it is one of
# these, or one of these words padded with digits and symbols ("Password2026!").
_COMMON_PASSWORDS = frozenset("""
1234567890 12345678910 0123456789 0987654321 1111111111 0000000000 1122334455 1q2w3e4r5t
qwertyuiop asdfghjkl zxcvbnm1234 1qaz2wsx3edc abcdefghij abc1234567 abcd123456
password1234 iloveyou123 letmein123 welcome123 trustno1234
""".split())
_COMMON_WORDS = frozenset("""
password passw0rd pass qwerty asdf admin administrator welcome letmein iloveyou login abc
gradepulse nlibrary school schools teacher teachers student students principal proprietor
nigeria naija enugu lagos abuja jesus god godisgood blessed blessing football chelsea arsenal
""".split())


def _valid_new_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password can be at most {PASSWORD_MAX_LENGTH} characters")
    lowered = value.lower()
    letters = re.sub(r"[^a-z]", "", lowered)
    if lowered in _COMMON_PASSWORDS or letters in _COMMON_WORDS or len(set(lowered)) < 4:
        raise ValueError("That password is too easy to guess. Use a few unrelated words or a longer mix of characters.")
    return value


def password_mentions_email(password: str, email: str) -> bool:
    """True when the password contains the email's name part (4+ characters)."""
    name = email.split("@", 1)[0].lower()
    return len(name) >= 4 and name in password.lower()


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str
    school_name: Optional[str] = Field(None, max_length=NAME_MAX)
    invite_code: Optional[str] = Field(None, max_length=128)  # join an existing school as a teacher

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

    @model_validator(mode="after")
    def _password_not_email(self):
        if password_mentions_email(self.password, self.email):
            raise ValueError("Your password must not contain your email address")
        return self

class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=1024)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=1024)
    new_password: str

    _check_new = field_validator("new_password")(classmethod(lambda cls, v: _valid_new_password(v)))

class ResetPasswordRequest(BaseModel):
    code: str = Field(..., max_length=128)
    new_password: str

    _check_new = field_validator("new_password")(classmethod(lambda cls, v: _valid_new_password(v)))

class OperatorResetRequest(BaseModel):
    email: str = Field(..., max_length=254)

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
    id: str = ""      # for listing and revoking
    code: str = ""    # the code itself: only in the response that creates it
    hint: str = ""    # its last 4 characters, to tell invites apart
    created_at: str
    expires_at: str
    class_ids: List[str] = []  # classes the teacher joins

class InviteRequest(BaseModel):
    class_ids: List[str] = Field(default_factory=list, max_length=200)

class SchoolResponse(BaseModel):
    school_id: str
    name: str
    classes: List[Dict[str, Any]] = []

class CreateSchoolRequest(BaseModel):
    name: str = Field(..., max_length=NAME_MAX)

class ClassResponse(BaseModel):
    class_id: str
    label: str
    grade_level: str
    arm: str

class CreateClassRequest(BaseModel):
    label: str = Field(..., max_length=60)

class BulkUpdateEntry(BaseModel):
    student_id: str = Field(..., max_length=ID_MAX)
    subject: str = Field(..., max_length=SUBJECT_MAX)
    score: float = Field(..., ge=0.0, le=1.0)

class BulkUpdateRequest(BaseModel):
    # A class is under 100 students; 2,000 covers a whole school sheet.
    entries: List[BulkUpdateEntry] = Field(..., max_length=BULK_MAX_ENTRIES)
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
    subject: str = Field(..., max_length=SUBJECT_MAX)
    class_id: Optional[str] = Field(None, max_length=ID_MAX)  # limit the report to one class
    as_of: Optional[date] = None  # report as of this day; default: the latest test in the subject

class UpdateStudentRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=NAME_MAX)
    current_topic: Optional[str] = Field(None, max_length=TOPIC_MAX)
    class_id: Optional[str] = Field(None, max_length=ID_MAX)

class IngestResponse(BaseModel):
    status: str
    report: Dict[str, Any]
