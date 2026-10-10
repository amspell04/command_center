import uuid
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.crud import news as news_crud
from backend.crud import notes as notes_crud
from backend.crud import tasks as tasks_crud
from backend.db.session import get_db
from backend.models.news import News
from backend.models.note import Note
from backend.models.task import Task, TaskType
from backend.crud.schemas.note import NoteCreate, NoteUpdate
from backend.crud.schemas.task import TaskCreate, TaskUpdate
from backend.services.api.agent_routes import router as agents_router
from backend.services.helpers import _changes, _found, guarded
from backend.services.news.briefing import BriefingExists, NoArticles, generate_briefing


app = FastAPI(title="Command Center API")
app.include_router(agents_router)

# NEWS

@app.get("/news/today", response_model=list[News])
def get_todays_news(db: Session = Depends(get_db)):
    return news_crud.list_todays_news(db)

@app.post("/news/refresh", response_model=News, status_code=status.HTTP_201_CREATED)
async def refresh_news(db: Session = Depends(get_db)):
    """Generate today's briefing. Allowed once per day."""
    try:
        return await guarded("news", generate_briefing(db), (BriefingExists, NoArticles))
    except BriefingExists as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
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

@app.patch("/notes/{note_id}", response_model=Note)
def update_notes(note_id: uuid.UUID, body: NoteUpdate, db: Session = Depends(get_db)):
    return _found(notes_crud.update_note(db, note_id, **_changes(body)), "Note")

@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: uuid.UUID, db: Session = Depends(get_db)):
    _found(notes_crud.delete_note(db, note_id) or None, "Note")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
