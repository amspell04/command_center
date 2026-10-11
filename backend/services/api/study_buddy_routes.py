"""Streaming quiz on one note. The client keeps the conversation and resends it each turn; the reply streams
back as server-sent events: token, weak_point (the agent added one), weak_point_resolved (a review resolved one),
then done or error. `mode` is "quiz" (default) or "review" of the note's open weak points."""
import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from backend.ai.agents.study_buddy.agent import study_buddy_events
from backend.config import settings
from backend.crud import weak_points as weak_points_crud
from backend.db.session import get_db
from backend.services.api.agent_routes import _note_or_404, _note_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents/notes", tags=["agents"])

# Only the latest turns are sent to the model, to stay inside its context window.
MAX_HISTORY = 20


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class StudyBuddyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_id: uuid.UUID
    mode: Literal["quiz", "review"] = "quiz"
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _ends_with_the_user(self):
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


def _frame(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def _sse(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Frame events for the wire. Headers are already sent, so failures become an `error` event, not a status."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.agent_timeout_seconds
    try:
        while True:
            try:
                event = await asyncio.wait_for(events.__anext__(), max(deadline - loop.time(), 0.001))
            except StopAsyncIteration:
                break
            yield _frame(event)
        yield _frame({"type": "done"})
    except asyncio.TimeoutError:
        yield _frame({"type": "error", "message": "The agent timed out"})
    except GraphRecursionError:
        logger.exception("study_buddy ran too many steps")
        yield _frame({"type": "error", "message": "The agent returned an unusable response, try again"})
    except Exception:
        logger.exception("study_buddy failed")
        yield _frame({"type": "error", "message": "Agent unavailable: check that Ollama is running"})
    finally:
        await events.aclose()


@router.post("/study_buddy/stream")
async def study_buddy_stream(params: StudyBuddyParams, db: Session = Depends(get_db)):
    note = _note_or_404(db, params.note_id)
    text = _note_text(note)
    open_topics = [w.topic for w in weak_points_crud.list_weak_points(db, note.id, resolved=False)]
    history = [m.model_dump() for m in params.messages[-MAX_HISTORY:]]
    if params.mode == "review" and not open_topics:
        raise HTTPException(status_code=400, detail="This note has no open weak points to review")
    events = study_buddy_events(note.id, note.title, text, open_topics, history, params.mode)
    return StreamingResponse(
        _sse(events), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
