import math
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.crud.schemas.training import (
    CopyWeek,
    ProgramCreate,
    ProgramSetCreate,
    SessionSave,
    TrainingMaxSet,
)
from backend.db.models import Lift, LiftSet, Program, ProgramSet, TrainingMax, WorkoutSession
from backend.models import training as view

LB_PER_KG = 2.20462262185
PLATE_INCREMENT_LB = 5.0


class TrainingError(ValueError):
    """A request the data can't satisfy (bad week, taken date, missing row). Routes turn it into a 4xx."""


# Unit and strength maths. Weights are stored in lb; kg is for display only.

def lb_to_kg(lb: float) -> float:
    return round(float(lb) / LB_PER_KG, 1)


def round_to_increment(lb: float, increment: float = PLATE_INCREMENT_LB) -> float:
    """Nearest loadable weight, halves round up."""
    return math.floor(float(lb) / increment + 0.5) * increment


def working_weight(training_max_lb: float, percent: float) -> float:
    return round_to_increment(float(training_max_lb) * float(percent) / 100)


def estimated_1rm(weight_lb: float, reps: int) -> float:
    """Epley formula. A single is its own max."""
    weight = float(weight_lb)
    return round(weight if reps == 1 else weight * (1 + reps / 30), 1)


# Training maxes

def set_training_max(db: Session, data: TrainingMaxSet) -> TrainingMax:
    """Record a max. A second entry for the same lift and date replaces the first."""
    stmt = insert(TrainingMax).values(**data.model_dump())
    stmt = stmt.on_conflict_do_update(constraint="uq_training_maxes_lift_date", set_={"weight": stmt.excluded.weight})
    row = db.scalars(stmt.returning(TrainingMax), execution_options={"populate_existing": True}).one()
    db.commit()
    return row


def list_training_maxes(db: Session) -> list[TrainingMax]:
    return list(db.scalars(select(TrainingMax).order_by(TrainingMax.effective_date.desc(), TrainingMax.lift)))


def delete_training_max(db: Session, max_id: uuid.UUID) -> bool:
    deleted = db.execute(delete(TrainingMax).where(TrainingMax.id == max_id).returning(TrainingMax.id)).scalar_one_or_none()
    db.commit()
    return deleted is not None


def _maxes_as_of(rows: list[TrainingMax], as_of: date) -> dict[Lift, TrainingMax]:
    """`rows` must be oldest first, so later dates overwrite earlier ones."""
    return {row.lift: row for row in rows if row.effective_date <= as_of}


def _all_maxes(db: Session) -> list[TrainingMax]:
    return list(db.scalars(select(TrainingMax).order_by(TrainingMax.effective_date)))


def current_maxes(db: Session, as_of: date | None = None) -> dict[Lift, TrainingMax]:
    """The latest max per lift on or before `as_of` (today by default)."""
    return _maxes_as_of(_all_maxes(db), as_of or date.today())


def max_view(row: TrainingMax) -> view.TrainingMax:
    return view.TrainingMax(
        id=row.id, lift=row.lift, weight_lb=float(row.weight), weight_kg=lb_to_kg(row.weight), effective_date=row.effective_date
    )


# Programs

def _deactivate_others(db: Session, keep: uuid.UUID | None = None) -> None:
    stmt = update(Program).where(Program.active)
    if keep is not None:
        stmt = stmt.where(Program.id != keep)
    db.execute(stmt.values(active=False))


def _commit_single_active(db: Session) -> None:
    """Commit, turning a lost race for the one active program into a TrainingError."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise TrainingError("Another program was just activated, try again")


def create_program(db: Session, data: ProgramCreate) -> Program:
    """Creating an active program deactivates the current one."""
    if data.active:
        _deactivate_others(db)
    program = Program(**data.model_dump())
    db.add(program)
    _commit_single_active(db)
    return program


def get_program(db: Session, program_id: uuid.UUID) -> Program | None:
    return db.get(Program, program_id)


def get_active_program(db: Session) -> Program | None:
    return db.scalars(select(Program).where(Program.active)).one_or_none()


def list_programs(db: Session) -> list[Program]:
    return list(db.scalars(select(Program).order_by(Program.start_date.desc(), Program.name)))


def update_program(db: Session, program_id: uuid.UUID, **fields) -> Program | None:
    """Partial update. `fields` must be JSON-mode values. Activating a program deactivates the current one."""
    program = db.get(Program, program_id)
    if program is None:
        return None
    if "weeks" in fields:
        last_week = db.scalar(select(func.max(ProgramSet.week)).where(ProgramSet.program_id == program_id))
        if last_week is not None and fields["weeks"] < last_week:
            raise TrainingError(f"Week {last_week} already has exercises, remove them before shortening the program")
    if "start_date" in fields:
        fields["start_date"] = date.fromisoformat(fields["start_date"])
    if fields.get("active"):
        _deactivate_others(db, keep=program_id)
    for key, value in fields.items():
        setattr(program, key, value)
    _commit_single_active(db)
    return program


def delete_program(db: Session, program_id: uuid.UUID) -> bool:
    deleted = db.execute(delete(Program).where(Program.id == program_id).returning(Program.id)).scalar_one_or_none()
    db.commit()
    return deleted is not None


# Program sets

def _check_week(program: Program, week: int) -> None:
    if week > program.weeks:
        raise TrainingError(f"Week {week} is past the end of a {program.weeks} week program")


def add_program_set(db: Session, program_id: uuid.UUID, data: ProgramSetCreate) -> ProgramSet | None:
    program = db.get(Program, program_id)
    if program is None:
        return None
    _check_week(program, data.week)
    program_set = ProgramSet(program_id=program_id, **data.model_dump())
    db.add(program_set)
    db.commit()
    return program_set


def get_program_set(db: Session, program_set_id: uuid.UUID) -> ProgramSet | None:
    return db.get(ProgramSet, program_set_id)


def list_program_sets(db: Session, program_id: uuid.UUID, week: int | None = None) -> list[ProgramSet]:
    stmt = select(ProgramSet).where(ProgramSet.program_id == program_id)
    if week is not None:
        stmt = stmt.where(ProgramSet.week == week)
    return list(db.scalars(stmt.order_by(ProgramSet.week, ProgramSet.day, ProgramSet.lift, ProgramSet.percent.desc())))


def update_program_set(db: Session, program_set_id: uuid.UUID, **fields) -> ProgramSet | None:
    program_set = db.get(ProgramSet, program_set_id)
    if program_set is None:
        return None
    if "week" in fields:
        _check_week(db.get(Program, program_set.program_id), fields["week"])
    for key, value in fields.items():
        setattr(program_set, key, Lift(value) if key == "lift" else value)
    db.commit()
    return program_set


def delete_program_set(db: Session, program_set_id: uuid.UUID) -> bool:
    deleted = db.execute(
        delete(ProgramSet).where(ProgramSet.id == program_set_id).returning(ProgramSet.id)
    ).scalar_one_or_none()
    db.commit()
    return deleted is not None


def copy_week(db: Session, program_id: uuid.UUID, data: CopyWeek) -> list[ProgramSet] | None:
    """Copy every exercise of one week into an empty week. Returns the new rows."""
    program = db.get(Program, program_id)
    if program is None:
        return None
    _check_week(program, data.from_week)
    _check_week(program, data.to_week)
    source = list_program_sets(db, program_id, data.from_week)
    if not source:
        raise TrainingError(f"Week {data.from_week} has no exercises to copy")
    if list_program_sets(db, program_id, data.to_week):
        raise TrainingError(f"Week {data.to_week} already has exercises")
    copies = [
        ProgramSet(program_id=program_id, week=data.to_week, day=s.day, lift=s.lift, sets=s.sets, reps=s.reps, percent=s.percent)
        for s in source
    ]
    db.add_all(copies)
    db.commit()
    return copies


def session_date(program: Program, week: int, day: int) -> date:
    return program.start_date + timedelta(days=(week - 1) * 7 + day - 1)


def planned_for_date(db: Session, on: date) -> list[view.ProgramSet]:
    """What the active program prescribes for `on`, with working weights from the max in force that day."""
    program = get_active_program(db)
    if program is None:
        return []
    offset = (on - program.start_date).days
    if offset < 0 or offset >= program.weeks * 7:
        return []
    week, day = offset // 7 + 1, offset % 7 + 1
    maxes = current_maxes(db, on)
    rows = db.scalars(
        select(ProgramSet)
        .where(ProgramSet.program_id == program.id, ProgramSet.week == week, ProgramSet.day == day)
        .order_by(ProgramSet.lift, ProgramSet.percent.desc())
    )
    return [program_set_view(row, program, maxes) for row in rows]


def program_set_views(db: Session, program: Program, rows: list[ProgramSet]) -> list[view.ProgramSet]:
    """Views for exercises of one program. Each weight uses the max in force on that exercise's date."""
    all_maxes = _all_maxes(db)
    return [program_set_view(r, program, _maxes_as_of(all_maxes, session_date(program, r.week, r.day))) for r in rows]


def program_set_view(row: ProgramSet, program: Program, maxes: dict[Lift, TrainingMax]) -> view.ProgramSet:
    top = maxes.get(row.lift)
    weight = working_weight(top.weight, row.percent) if top else None
    return view.ProgramSet(
        id=row.id, program_id=row.program_id, week=row.week, day=row.day, lift=row.lift, sets=row.sets,
        reps=row.reps, percent=float(row.percent), weight_lb=weight,
        weight_kg=lb_to_kg(weight) if weight is not None else None, date=session_date(program, row.week, row.day),
    )


# Logged sessions

def save_session(db: Session, data: SessionSave) -> WorkoutSession:
    """Create the day's session, or replace its sets if the date already has one."""
    program_set_ids = {s.program_set_id for s in data.sets if s.program_set_id}
    if program_set_ids:
        found = set(db.scalars(select(ProgramSet.id).where(ProgramSet.id.in_(program_set_ids))))
        if missing := program_set_ids - found:
            raise TrainingError(f"Unknown program set: {sorted(map(str, missing))[0]}")
    session = db.scalars(select(WorkoutSession).where(WorkoutSession.date == data.date)).one_or_none()
    if session is None:
        session = WorkoutSession(date=data.date)
        db.add(session)
        db.flush()
    else:
        db.execute(delete(LiftSet).where(LiftSet.session_id == session.id))
    session.notes = data.notes
    session.bodyweight = data.bodyweight
    db.add_all(
        LiftSet(session_id=session.id, set_order=i, **s.model_dump()) for i, s in enumerate(data.sets, start=1)
    )
    try:
        db.commit()
    except IntegrityError:  # two requests racing on the same new date
        db.rollback()
        raise TrainingError("A session for that date was just saved, try again")
    return session


def get_session(db: Session, session_id: uuid.UUID) -> WorkoutSession | None:
    return db.get(WorkoutSession, session_id)


def get_session_by_date(db: Session, on: date) -> WorkoutSession | None:
    return db.scalars(select(WorkoutSession).where(WorkoutSession.date == on)).one_or_none()


def list_sessions(db: Session, start: date | None = None, end: date | None = None) -> list[WorkoutSession]:
    stmt = select(WorkoutSession).order_by(WorkoutSession.date.desc())
    if start is not None:
        stmt = stmt.where(WorkoutSession.date >= start)
    if end is not None:
        stmt = stmt.where(WorkoutSession.date <= end)
    return list(db.scalars(stmt))


def list_session_sets(db: Session, session_id: uuid.UUID) -> list[LiftSet]:
    return list(db.scalars(select(LiftSet).where(LiftSet.session_id == session_id).order_by(LiftSet.set_order)))


def delete_session(db: Session, session_id: uuid.UUID) -> bool:
    deleted = db.execute(
        delete(WorkoutSession).where(WorkoutSession.id == session_id).returning(WorkoutSession.id)
    ).scalar_one_or_none()
    db.commit()
    return deleted is not None


def set_view(row: LiftSet) -> view.LiftSet:
    e1rm = estimated_1rm(row.weight, row.reps)
    return view.LiftSet(
        id=row.id, lift=row.lift, weight_lb=float(row.weight), weight_kg=lb_to_kg(row.weight), reps=row.reps,
        set_order=row.set_order, estimated_1rm_lb=e1rm, estimated_1rm_kg=lb_to_kg(e1rm), program_set_id=row.program_set_id,
    )


def gym_day(db: Session, on: date) -> view.GymDay | None:
    """The gym session for `on`: what was logged if anything was, otherwise what the active program prescribes."""
    session = get_session_by_date(db, on)
    if session is not None:
        rows = list_session_sets(db, session.id)
        lifts = list(dict.fromkeys(r.lift.value.title() for r in rows))
        details = [f"{len(rows)} sets of {', '.join(lifts)}, already logged"]
        return view.GymDay(date=on, logged=True, lifts=lifts, sets=len(rows), details=details)
    plan = planned_for_date(db, on)
    if not plan:
        return None
    lifts = list(dict.fromkeys(p.lift.value.title() for p in plan))
    details = [f"{p.lift.value.title()} {p.sets}x{p.reps} at {p.percent:g}%" for p in plan]
    return view.GymDay(date=on, logged=False, lifts=lifts, sets=sum(p.sets for p in plan), details=details)


def gym_week(db: Session, on: date) -> list[view.GymDay]:
    """The gym days of the Monday to Sunday week containing `on`."""
    start = on - timedelta(days=on.weekday())
    days = (gym_day(db, start + timedelta(days=i)) for i in range(7))
    return [d for d in days if d is not None]


def session_view(db: Session, session: WorkoutSession) -> view.WorkoutSession:
    bodyweight = float(session.bodyweight) if session.bodyweight is not None else None
    return view.WorkoutSession(
        id=session.id, date=session.date, notes=session.notes, bodyweight_lb=bodyweight,
        bodyweight_kg=lb_to_kg(bodyweight) if bodyweight is not None else None,
        sets=[set_view(s) for s in list_session_sets(db, session.id)],
    )


def e1rm_history(db: Session, lift: Lift) -> list[view.E1RMPoint]:
    """The best estimated 1RM per session date for one lift, oldest first."""
    rows = db.execute(
        select(WorkoutSession.date, LiftSet.weight, LiftSet.reps)
        .join(LiftSet, LiftSet.session_id == WorkoutSession.id)
        .where(LiftSet.lift == lift)
        .order_by(WorkoutSession.date)
    )
    best: dict[date, float] = {}
    for day, weight, reps in rows:
        best[day] = max(best.get(day, 0.0), estimated_1rm(weight, reps))
    return [view.E1RMPoint(date=d, estimated_1rm_lb=v, estimated_1rm_kg=lb_to_kg(v)) for d, v in best.items()]
