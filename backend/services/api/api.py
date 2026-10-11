import uuid
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.crud import goals as goals_crud
from backend.crud import news as news_crud
from backend.crud import notes as notes_crud
from backend.crud import tasks as tasks_crud
from backend.crud import weak_points as weak_points_crud
from backend.crud.training import TrainingError
from backend.db.session import get_db
from backend.models.goal import Goal
from backend.models.news import News
from backend.models.note import Note
from backend.models.task import Task, TaskType
from backend.models.weak_point import WeakPoint
from backend.crud.schemas.goal import GoalCreate, GoalUpdate
from backend.crud.schemas.note import NoteCreate, NoteUpdate
from backend.crud.schemas.task import TaskCreate, TaskUpdate
from backend.crud.schemas.weak_point import WeakPointUpdate
from backend.services.api.agent_routes import router as agents_router
from backend.services.api.study_buddy_routes import router as study_buddy_router
from backend.services.api.training_routes import router as training_router
from backend.services.helpers import _changes, _found, guarded
from backend.services.news.briefing import BriefingExists, NoArticles, generate_briefing


app = FastAPI(title="Command Center API")
app.include_router(agents_router)
app.include_router(study_buddy_router)
app.include_router(training_router)


@app.exception_handler(TrainingError)
def training_error(_: Request, exc: TrainingError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


# NEWS

@app.get("/news/today", response_model=list[News])
def get_todays_news(db: Session = Depends(get_db)):
    return news_crud.list_todays_news(db)

@app.get("/news/latest", response_model=News)
def get_latest_news(db: Session = Depends(get_db)):
    return _found(news_crud.get_latest_news(db), "Briefing")

@app.get("/news/{news_id}", response_model=News)
def get_news(news_id: uuid.UUID, db: Session = Depends(get_db)):
    return _found(news_crud.get_news(db, news_id), "Briefing")

@app.post("/news/refresh", response_model=News, status_code=status.HTTP_201_CREATED)
async def refresh_news(replace: bool = False, db: Session = Depends(get_db)):
    """Generate today's briefing. Once it exists, only allowed with replace=true, which swaps it for a new one."""
    try:
        return await guarded("news", generate_briefing(db, replace), (BriefingExists, NoArticles))
    except BriefingExists as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except NoArticles as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))

# TASKS

@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    return tasks_crud.create_task(db, body)

@app.get("/tasks", response_model=list[Task])
def list_tasks(
    due_date: date | None = None,
    completed: bool | None = None,
    type: TaskType | None = None,
    db: Session = Depends(get_db),
):
    return tasks_crud.list_tasks(db, due_date, completed, type)

@app.patch("/tasks/{task_id}/complete", response_model=Task)
def mark_task_complete(task_id: uuid.UUID, db: Session = Depends(get_db)):
    return _found(tasks_crud.complete_task(db, task_id), "Task")

@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: uuid.UUID, body: TaskUpdate, db: Session = Depends(get_db)):
    return _found(tasks_crud.update_task(db, task_id, **_changes(body)), "Task")

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(tasks_crud.delete_task(db, task_id) or None, "Task")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# NOTES

@app.post("/notes", response_model=Note, status_code=status.HTTP_201_CREATED)
def create_note(body: NoteCreate, db: Session = Depends(get_db)):
    return notes_crud.create_note(db, body)

@app.get("/notes", response_model=list[Note])
def list_notes(q: str | None = None, db: Session = Depends(get_db)):
    return notes_crud.list_notes(db, q)

@app.get("/notes/{note_id}", response_model=Note)
def get_note(note_id: uuid.UUID, db: Session = Depends(get_db)):
    return _found(notes_crud.get_note(db, note_id), "Note")

@app.patch("/notes/{note_id}", response_model=Note)
def update_notes(note_id: uuid.UUID, body: NoteUpdate, db: Session = Depends(get_db)):
    return _found(notes_crud.update_note(db, note_id, **_changes(body)), "Note")

@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(notes_crud.delete_note(db, note_id) or None, "Note")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# WEAK POINTS

@app.get("/weak_points", response_model=list[WeakPoint])
def list_all_weak_points(resolved: bool | None = None, db: Session = Depends(get_db)):
    return weak_points_crud.list_all_weak_points(db, resolved)

@app.get("/notes/{note_id}/weak_points", response_model=list[WeakPoint])
def list_weak_points(note_id: uuid.UUID, resolved: bool | None = None, db: Session = Depends(get_db)):
    _found(notes_crud.get_note(db, note_id), "Note")
    return weak_points_crud.list_weak_points(db, note_id, resolved)

@app.patch("/weak_points/{weak_point_id}", response_model=WeakPoint)
def update_weak_point(weak_point_id: uuid.UUID, body: WeakPointUpdate, db: Session = Depends(get_db)):
    return _found(weak_points_crud.update_weak_point(db, weak_point_id, **_changes(body)), "Weak point")

@app.delete("/weak_points/{weak_point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weak_point(weak_point_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(weak_points_crud.delete_weak_point(db, weak_point_id) or None, "Weak point")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# GOALS

@app.post("/goals", response_model=Goal, status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalCreate, db: Session = Depends(get_db)):
    return goals_crud.create_goal(db, body)

@app.get("/goals", response_model=list[Goal])
def list_goals(db: Session = Depends(get_db)):
    return goals_crud.list_goals(db)

@app.patch("/goals/{goal_id}", response_model=Goal)
def update_goal(goal_id: uuid.UUID, body: GoalUpdate, db: Session = Depends(get_db)):
    return _found(goals_crud.update_goal(db, goal_id, **_changes(body, nullable=("target_date",))), "Goal")

@app.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(goals_crud.delete_goal(db, goal_id) or None, "Goal")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
