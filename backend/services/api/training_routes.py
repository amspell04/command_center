import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.crud import training as crud
from backend.crud.schemas.training import (
    CopyWeek,
    ProgramCreate,
    ProgramSetCreate,
    ProgramSetUpdate,
    ProgramUpdate,
    SessionSave,
    TrainingMaxSet,
)
from backend.db.models import Lift
from backend.db.session import get_db
from backend.models import training as view
from backend.services.helpers import _changes, _found

router = APIRouter(prefix="/training", tags=["training"])


def _program(db: Session, program_id: uuid.UUID):
    return _found(crud.get_program(db, program_id), "Program")


# Training maxes

@router.get("/maxes", response_model=list[view.TrainingMax])
def list_maxes(db: Session = Depends(get_db)):
    return [crud.max_view(m) for m in crud.list_training_maxes(db)]


@router.put("/maxes", response_model=view.TrainingMax)
def set_max(body: TrainingMaxSet, db: Session = Depends(get_db)):
    return crud.max_view(crud.set_training_max(db, body))


@router.delete("/maxes/{max_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_max(max_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(crud.delete_training_max(db, max_id) or None, "Training max")


# Programs

@router.post("/programs", response_model=view.Program, status_code=status.HTTP_201_CREATED)
def create_program(body: ProgramCreate, db: Session = Depends(get_db)):
    return crud.create_program(db, body)


@router.get("/programs", response_model=list[view.Program])
def list_programs(db: Session = Depends(get_db)):
    return crud.list_programs(db)


@router.get("/programs/{program_id}", response_model=view.Program)
def get_program(program_id: uuid.UUID, db: Session = Depends(get_db)):
    return _program(db, program_id)


@router.patch("/programs/{program_id}", response_model=view.Program)
def update_program(program_id: uuid.UUID, body: ProgramUpdate, db: Session = Depends(get_db)):
    return _found(crud.update_program(db, program_id, **_changes(body)), "Program")


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(program_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(crud.delete_program(db, program_id) or None, "Program")


# Program exercises

@router.get("/programs/{program_id}/sets", response_model=list[view.ProgramSet])
def list_program_sets(program_id: uuid.UUID, week: int | None = None, db: Session = Depends(get_db)):
    program = _program(db, program_id)
    return crud.program_set_views(db, program, crud.list_program_sets(db, program_id, week))


@router.post("/programs/{program_id}/sets", response_model=view.ProgramSet, status_code=status.HTTP_201_CREATED)
def add_program_set(program_id: uuid.UUID, body: ProgramSetCreate, db: Session = Depends(get_db)):
    program = _program(db, program_id)
    row = crud.add_program_set(db, program_id, body)
    return crud.program_set_views(db, program, [row])[0]


@router.post("/programs/{program_id}/copy_week", response_model=list[view.ProgramSet], status_code=status.HTTP_201_CREATED)
def copy_week(program_id: uuid.UUID, body: CopyWeek, db: Session = Depends(get_db)):
    program = _program(db, program_id)
    return crud.program_set_views(db, program, crud.copy_week(db, program_id, body))


@router.patch("/sets/{program_set_id}", response_model=view.ProgramSet)
def update_program_set(program_set_id: uuid.UUID, body: ProgramSetUpdate, db: Session = Depends(get_db)):
    row = _found(crud.update_program_set(db, program_set_id, **_changes(body)), "Exercise")
    return crud.program_set_views(db, crud.get_program(db, row.program_id), [row])[0]


@router.delete("/sets/{program_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program_set(program_set_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(crud.delete_program_set(db, program_set_id) or None, "Exercise")


@router.get("/planned", response_model=list[view.ProgramSet])
def planned(on: date | None = Query(default=None, alias="date"), db: Session = Depends(get_db)):
    """What the active program prescribes for a date (today by default)."""
    return crud.planned_for_date(db, on or date.today())


@router.get("/week", response_model=list[view.GymDay])
def gym_week(on: date | None = Query(default=None, alias="date"), db: Session = Depends(get_db)):
    """The gym days (logged, or planned by the active program) in the Monday to Sunday week of a date (today by default)."""
    return crud.gym_week(db, on or date.today())


# Logged sessions

@router.put("/sessions", response_model=view.WorkoutSession)
def save_session(body: SessionSave, db: Session = Depends(get_db)):
    """Log a day. A date that already has a session has its sets replaced."""
    return crud.session_view(db, crud.save_session(db, body))


@router.get("/sessions", response_model=list[view.WorkoutSession])
def list_sessions(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    return [crud.session_view(db, s) for s in crud.list_sessions(db, start, end)]


@router.get("/sessions/{session_id}", response_model=view.WorkoutSession)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return crud.session_view(db, _found(crud.get_session(db, session_id), "Session"))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(crud.delete_session(db, session_id) or None, "Session")


# Progress

@router.get("/progress/{lift}", response_model=list[view.E1RMPoint])
def progress(lift: Lift, db: Session = Depends(get_db)):
    """Best estimated 1RM per session date for one lift, oldest first."""
    return crud.e1rm_history(db, lift)
