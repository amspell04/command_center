
from fastapi import FastAPI


app = FastAPI(title="Command Center API")

# NEWS

@app.get("/news/today")
def get_todays_news():
    return 

# TASKS

@app.get("/tasks")
def list_tasks():
    return 

@app.patch("/tasks/{task_id}/complete")
def mark_task_complete():
    return 

@app.patch("/tasks/{task_id}")
def update_task():
    return 

@app.delete("/tasks/{task_id}")
def delete_task():
    return 

# NOTES

@app.get("/notes")
def list_notes():
    return 

@app.patch("/notes/{note_id}")
def update_notes():
    return 

@app.delete("/notes/{note_id}")
def delete_note():
    return 


