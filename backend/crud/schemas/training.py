import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.db.models import Lift

Weight = Field(gt=0, le=2000)


class TrainingMaxSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lift: Lift
    weight: float = Weight
    effective_date: date


class ProgramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    start_date: date
    weeks: int = Field(ge=1, le=52)
    active: bool = False


class ProgramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    weeks: int | None = Field(default=None, ge=1, le=52)
    active: bool | None = None


class ProgramSetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: int = Field(ge=1, le=52)
    day: int = Field(ge=1, le=7)
    lift: Lift
    sets: int = Field(ge=1, le=20)
    reps: int = Field(ge=1, le=30)
    percent: float = Field(gt=0, le=150)


class ProgramSetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: int | None = Field(default=None, ge=1, le=52)
    day: int | None = Field(default=None, ge=1, le=7)
    lift: Lift | None = None
    sets: int | None = Field(default=None, ge=1, le=20)
    reps: int | None = Field(default=None, ge=1, le=30)
    percent: float | None = Field(default=None, gt=0, le=150)


class CopyWeek(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_week: int = Field(ge=1, le=52)
    to_week: int = Field(ge=1, le=52)

    @model_validator(mode="after")
    def _different_weeks(self):
        if self.from_week == self.to_week:
            raise ValueError("from_week and to_week must differ")
        return self


class LiftSetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lift: Lift
    weight: float = Weight
    reps: int = Field(ge=1, le=30)
    program_set_id: uuid.UUID | None = None


class SessionSave(BaseModel):
    """A day's workout. Saving a date that already has a session replaces its sets."""

    model_config = ConfigDict(extra="forbid")

    date: date
    notes: str = ""
    bodyweight: float | None = Field(default=None, gt=0, le=1000)
    sets: list[LiftSetInput] = Field(min_length=1, max_length=100)
