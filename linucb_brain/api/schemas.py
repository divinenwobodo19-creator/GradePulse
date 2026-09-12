from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

class StudentSchema(BaseModel):
    student_id: str
    name: str
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

class SignupRequest(BaseModel):
    email: str
    password: str
    school_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    school_id: str = ""
    school_name: str = ""
    token: str = ""

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

class TriageRequest(BaseModel):
    subject: str

class UpdateStudentRequest(BaseModel):
    name: Optional[str] = None
    current_topic: Optional[str] = None
    class_id: Optional[str] = None

class IngestResponse(BaseModel):
    status: str
    report: Dict[str, Any]
