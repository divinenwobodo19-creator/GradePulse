__version__ = "0.2.1"

from .brain import Brain
from .models.student import Student
from .models.content import Content
from .models.session import Session
from .models.school import School, SchoolClass, GRADE_LEVELS, normalize_label
from .core.linucb import LinUCBDisjoint
from .core.context import build_context
from .core.reward import calculate_reward

__all__ = ["Brain", "Student", "Content", "Session", "School", "SchoolClass",
           "GRADE_LEVELS", "normalize_label", "LinUCBDisjoint", "build_context", "calculate_reward"]