import uuid
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from backend.crud import training as crud
from backend.crud.schemas.training import (
    CopyWeek,
    LiftSetInput,
    ProgramCreate,
    ProgramSetCreate,
    SessionSave,
    TrainingMaxSet,
)
from backend.db.models import Lift

START = date(2026, 10, 12)  # a Monday


def program(db, **over):
    return crud.create_program(db, ProgramCreate(**{"name": "Peak", "start_date": START, "weeks": 10, "active": True, **over}))


def prescribe(db, program_id, **over):
    data = {"week": 1, "day": 1, "lift": Lift.squat, "sets": 3, "reps": 5, "percent": 80, **over}
    return crud.add_program_set(db, program_id, ProgramSetCreate(**data))


def set_max(db, lift=Lift.squat, weight=400, on=START - timedelta(days=30)):
    return crud.set_training_max(db, TrainingMaxSet(lift=lift, weight=weight, effective_date=on))


# maths

def test_lb_to_kg():
    assert crud.lb_to_kg(225) == 102.1
    assert crud.lb_to_kg(0) == 0


def test_round_to_increment_rounds_to_nearest_five_and_halves_up():
    assert crud.round_to_increment(322) == 320
    assert crud.round_to_increment(323) == 325
    assert crud.round_to_increment(322.5) == 325


def test_working_weight_is_percent_of_max_rounded():
    assert crud.working_weight(400, 80) == 320
    assert crud.working_weight(405, 72.5) == 295  # 293.6 -> 295


def test_estimated_1rm_uses_epley_and_a_single_is_itself():
    assert crud.estimated_1rm(300, 1) == 300
    assert crud.estimated_1rm(300, 5) == 350
    assert crud.estimated_1rm(200, 10) == 266.7


# training maxes

def test_setting_a_max_twice_on_one_date_replaces_it(db):
    set_max(db, weight=400)
    set_max(db, weight=410)
    maxes = crud.list_training_maxes(db)
    assert len(maxes) == 1 and float(maxes[0].weight) == 410


def test_replacing_a_max_keeps_one_row_with_the_new_weight(db):
    first = set_max(db, weight=400)
    second = set_max(db, weight=425)
    assert first.id == second.id and float(second.weight) == 425
    assert len(crud.list_training_maxes(db)) == 1


def test_current_max_is_latest_on_or_before_the_date(db):
    set_max(db, weight=400, on=date(2026, 8, 1))
    set_max(db, weight=420, on=date(2026, 10, 1))
    set_max(db, weight=440, on=date(2026, 12, 1))
    assert float(crud.current_maxes(db, date(2026, 9, 1))[Lift.squat].weight) == 400
    assert float(crud.current_maxes(db, date(2026, 10, 15))[Lift.squat].weight) == 420
    assert crud.current_maxes(db, date(2026, 7, 1)) == {}


def test_training_max_rejects_bad_input():
    with pytest.raises(ValidationError):
        TrainingMaxSet(lift=Lift.squat, weight=0, effective_date=START)
    with pytest.raises(ValidationError):
        TrainingMaxSet(lift="OHP", weight=100, effective_date=START)


# programs

def test_only_one_program_is_active(db):
    first = program(db, name="One")
    second = program(db, name="Two")
    db.refresh(first)
    assert first.active is False and second.active is True
    assert crud.get_active_program(db).id == second.id


def test_losing_the_race_for_the_active_program_is_a_training_error(db, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    program(db, name="One")

    def boom():
        raise IntegrityError("stmt", {}, Exception("uq_programs_one_active"))

    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(crud.TrainingError, match="try again"):
        program(db, name="Two")


def test_activating_a_program_deactivates_the_other(db):
    first = program(db, name="One")
    second = program(db, name="Two", active=False)
    crud.update_program(db, second.id, active=True)
    db.refresh(first)
    assert first.active is False and crud.get_active_program(db).id == second.id


def test_cannot_shorten_a_program_below_its_last_exercise(db):
    p = program(db)
    prescribe(db, p.id, week=8)
    with pytest.raises(crud.TrainingError):
        crud.update_program(db, p.id, weeks=6)
    assert crud.update_program(db, p.id, weeks=8).weeks == 8


def test_program_rejects_bad_weeks():
    for weeks in (0, 53):
        with pytest.raises(ValidationError):
            ProgramCreate(name="x", start_date=START, weeks=weeks)


def test_unknown_program_returns_none(db):
    assert crud.update_program(db, uuid.uuid4(), name="x") is None
    assert crud.add_program_set(db, uuid.uuid4(), ProgramSetCreate(week=1, day=1, lift=Lift.squat, sets=3, reps=5, percent=80)) is None
    assert crud.delete_program(db, uuid.uuid4()) is False


def test_deleting_a_program_deletes_its_exercises(db):
    p = program(db)
    row_id = prescribe(db, p.id).id
    assert crud.delete_program(db, p.id) is True
    db.expire_all()  # the session still holds the deleted row
    assert crud.get_program_set(db, row_id) is None


# program sets

def test_exercise_past_the_last_week_is_rejected(db):
    p = program(db, weeks=4)
    with pytest.raises(crud.TrainingError):
        prescribe(db, p.id, week=5)
    assert crud.list_program_sets(db, p.id) == []


def test_exercise_rejects_bad_values():
    base = {"week": 1, "day": 1, "lift": Lift.squat, "sets": 3, "reps": 5, "percent": 80}
    for bad in ({"day": 0}, {"day": 8}, {"week": 0}, {"sets": 0}, {"reps": 0}, {"percent": 0}, {"percent": 151}, {"lift": "OHP"}):
        with pytest.raises(ValidationError):
            ProgramSetCreate(**{**base, **bad})


def test_update_exercise_checks_week_and_converts_lift(db):
    p = program(db, weeks=4)
    row = prescribe(db, p.id)
    with pytest.raises(crud.TrainingError):
        crud.update_program_set(db, row.id, week=5)
    updated = crud.update_program_set(db, row.id, lift="BENCH", percent=72.5)
    assert updated.lift == Lift.bench and float(updated.percent) == 72.5
    assert crud.update_program_set(db, uuid.uuid4(), reps=3) is None


def test_exercises_list_in_week_day_order(db):
    p = program(db)
    prescribe(db, p.id, week=2, day=1)
    prescribe(db, p.id, week=1, day=3)
    prescribe(db, p.id, week=1, day=1)
    assert [(r.week, r.day) for r in crud.list_program_sets(db, p.id)] == [(1, 1), (1, 3), (2, 1)]
    assert [r.week for r in crud.list_program_sets(db, p.id, week=2)] == [2]


def test_copy_week_duplicates_exercises(db):
    p = program(db)
    prescribe(db, p.id, day=1, percent=80)
    prescribe(db, p.id, day=3, lift=Lift.bench, percent=70)
    copies = crud.copy_week(db, p.id, CopyWeek(from_week=1, to_week=2))
    assert len(copies) == 2
    assert [(r.day, r.lift, float(r.percent)) for r in crud.list_program_sets(db, p.id, week=2)] == [
        (1, Lift.squat, 80.0),
        (3, Lift.bench, 70.0),
    ]


def test_copy_week_rejects_bad_requests(db):
    p = program(db, weeks=4)
    prescribe(db, p.id, week=1)
    prescribe(db, p.id, week=2)
    with pytest.raises(crud.TrainingError):  # target not empty
        crud.copy_week(db, p.id, CopyWeek(from_week=1, to_week=2))
    with pytest.raises(crud.TrainingError):  # source empty
        crud.copy_week(db, p.id, CopyWeek(from_week=3, to_week=4))
    with pytest.raises(crud.TrainingError):  # past the end
        crud.copy_week(db, p.id, CopyWeek(from_week=1, to_week=5))
    with pytest.raises(ValidationError):  # same week
        CopyWeek(from_week=1, to_week=1)
    assert crud.copy_week(db, uuid.uuid4(), CopyWeek(from_week=1, to_week=2)) is None


# planned for a date

def test_planned_for_date_computes_weights_in_lb_and_kg(db):
    set_max(db, weight=400)
    p = program(db)
    prescribe(db, p.id, week=2, day=3, percent=80)  # START + 7 + 2 days
    planned = crud.planned_for_date(db, START + timedelta(days=9))
    assert len(planned) == 1
    assert planned[0].weight_lb == 320 and planned[0].weight_kg == 145.1 and planned[0].date == START + timedelta(days=9)


def test_planned_weight_uses_the_max_in_force_that_day(db):
    p = program(db)
    prescribe(db, p.id, week=1, day=1, percent=80)
    prescribe(db, p.id, week=3, day=1, percent=80)
    set_max(db, weight=400, on=START - timedelta(days=5))
    set_max(db, weight=500, on=START + timedelta(days=10))
    assert crud.planned_for_date(db, START)[0].weight_lb == 320
    assert crud.planned_for_date(db, START + timedelta(days=14))[0].weight_lb == 400


def test_planned_weight_is_null_without_a_max(db):
    p = program(db)
    prescribe(db, p.id)
    planned = crud.planned_for_date(db, START)
    assert planned[0].weight_lb is None and planned[0].weight_kg is None


def test_planned_for_date_is_empty_outside_the_program_or_without_one(db):
    assert crud.planned_for_date(db, START) == []
    p = program(db, weeks=2)
    prescribe(db, p.id)
    assert crud.planned_for_date(db, START - timedelta(days=1)) == []
    assert crud.planned_for_date(db, START + timedelta(days=14)) == []
    assert crud.planned_for_date(db, START + timedelta(days=1)) == []  # a rest day


def test_inactive_program_is_not_planned(db):
    p = program(db, active=False)
    prescribe(db, p.id)
    assert crud.planned_for_date(db, START) == []


# sessions

def save(db, on=START, sets=None, **over):
    sets = sets if sets is not None else [LiftSetInput(lift=Lift.squat, weight=315, reps=5)]
    return crud.save_session(db, SessionSave(date=on, sets=sets, **over))


def test_save_session_stores_ordered_sets_with_both_units(db):
    session = save(db, sets=[
        LiftSetInput(lift=Lift.squat, weight=315, reps=5),
        LiftSetInput(lift=Lift.squat, weight=335, reps=3),
    ], bodyweight=200)
    shown = crud.session_view(db, session)
    assert [s.set_order for s in shown.sets] == [1, 2]
    assert shown.sets[0].weight_lb == 315 and shown.sets[0].weight_kg == 142.9
    assert shown.sets[0].estimated_1rm_lb == 367.5
    assert shown.bodyweight_lb == 200 and shown.bodyweight_kg == 90.7


def test_saving_the_same_date_replaces_the_sets(db):
    first = save(db, sets=[LiftSetInput(lift=Lift.squat, weight=315, reps=5)] * 3)
    second = save(db, sets=[LiftSetInput(lift=Lift.bench, weight=225, reps=5)], notes="redo")
    assert second.id == first.id and second.notes == "redo"
    sets = crud.list_session_sets(db, second.id)
    assert [(s.lift, float(s.weight)) for s in sets] == [(Lift.bench, 225.0)]
    assert len(crud.list_sessions(db)) == 1


def test_session_links_to_a_real_exercise_only(db):
    p = program(db)
    row = prescribe(db, p.id)
    linked = save(db, sets=[LiftSetInput(lift=Lift.squat, weight=320, reps=5, program_set_id=row.id)])
    assert crud.list_session_sets(db, linked.id)[0].program_set_id == row.id
    with pytest.raises(crud.TrainingError):
        save(db, on=START + timedelta(days=1), sets=[LiftSetInput(lift=Lift.squat, weight=320, reps=5, program_set_id=uuid.uuid4())])
    assert len(crud.list_sessions(db)) == 1


def test_deleting_an_exercise_keeps_the_logged_set(db):
    p = program(db)
    row = prescribe(db, p.id)
    session = save(db, sets=[LiftSetInput(lift=Lift.squat, weight=320, reps=5, program_set_id=row.id)])
    crud.delete_program_set(db, row.id)
    logged = crud.list_session_sets(db, session.id)
    assert len(logged) == 1 and logged[0].program_set_id is None


def test_session_rejects_bad_input():
    with pytest.raises(ValidationError):
        SessionSave(date=START, sets=[])
    for bad in ({"weight": 0}, {"weight": -5}, {"reps": 0}, {"reps": 31}, {"lift": "OHP"}):
        with pytest.raises(ValidationError):
            LiftSetInput(**{"lift": Lift.squat, "weight": 300, "reps": 5, **bad})


def test_list_sessions_filters_by_range_newest_first(db):
    for offset in (0, 3, 7):
        save(db, on=START + timedelta(days=offset))
    assert [s.date for s in crud.list_sessions(db)] == [START + timedelta(days=d) for d in (7, 3, 0)]
    in_range = crud.list_sessions(db, start=START + timedelta(days=1), end=START + timedelta(days=5))
    assert [s.date for s in in_range] == [START + timedelta(days=3)]


def test_delete_session_deletes_its_sets(db):
    session = save(db)
    assert crud.delete_session(db, session.id) is True
    assert crud.list_session_sets(db, session.id) == []
    assert crud.delete_session(db, session.id) is False


def test_e1rm_history_is_best_set_per_date_for_one_lift(db):
    save(db, on=START, sets=[
        LiftSetInput(lift=Lift.squat, weight=300, reps=5),   # 350
        LiftSetInput(lift=Lift.squat, weight=330, reps=1),   # 330
        LiftSetInput(lift=Lift.bench, weight=225, reps=5),
    ])
    save(db, on=START + timedelta(days=7), sets=[LiftSetInput(lift=Lift.squat, weight=320, reps=5)])  # 373.3
    history = crud.e1rm_history(db, Lift.squat)
    assert [(p.date, p.estimated_1rm_lb) for p in history] == [(START, 350.0), (START + timedelta(days=7), 373.3)]
    assert history[0].estimated_1rm_kg == 158.8
    assert crud.e1rm_history(db, Lift.deadlift) == []
