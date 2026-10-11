import uuid
from datetime import date

from pydantic import BaseModel

from backend.db.models import Lift


class TrainingMax(BaseModel):
    id: uuid.UUID
    lift: Lift
    weight_lb: float
    weight_kg: float
    effective_date: date


class Program(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    weeks: int
    active: bool


class ProgramSet(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    week: int
    day: int
    lift: Lift
    sets: int
    reps: int
    percent: float
    # Computed from the training max in force on the session's date. Null when that lift has no max yet
    weight_lb: float | None
    weight_kg: float | None
    date: date


class LiftSet(BaseModel):
    id: uuid.UUID
    lift: Lift
    weight_lb: float
    weight_kg: float
    reps: int
    set_order: int
    estimated_1rm_lb: float
    estimated_1rm_kg: float
    program_set_id: uuid.UUID | None


class WorkoutSession(BaseModel):
    id: uuid.UUID
    date: date
    notes: str
    bodyweight_lb: float | None
    bodyweight_kg: float | None
    sets: list[LiftSet]


class E1RMPoint(BaseModel):
    date: date
    estimated_1rm_lb: float
    estimated_1rm_kg: float


class GymDay(BaseModel):
    """A day with a gym session: the logged one if there is one, otherwise the program's plan."""

    date: date
    logged: bool  # True when the session already happened, False when it is only planned
    lifts: list[str]  # e.g. ["Squat", "Bench"]
    sets: int
    details: list[str]  # one line per exercise, e.g. "Squat 3x5 at 80%"
