
import asyncio
import logging
from collections.abc import Awaitable

from fastapi import HTTPException, status
from langchain.agents.structured_output import StructuredOutputError
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, ValidationError

from backend.agents.runner import AgentOutputError
from backend.config import settings

logger = logging.getLogger(__name__)


def _changes(body: BaseModel) -> dict:
    """Fields the client actually sent. Rejects empty bodies and explicit nulls."""
    changes = body.model_dump(exclude_unset=True, mode="json")
    if not changes or any(v is None for v in changes.values()):
        raise HTTPException(422, "Send at least one field, none may be null")
    return changes


def _found(item, name: str):
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{name} not found")
    return item


async def guarded(label: str, work: Awaitable, passthrough: tuple[type[Exception], ...] = ()):
    """Await an agent call, mapping its failures to HTTP errors a client can act on.

    `passthrough` exceptions are the caller's own and are re-raised untouched.
    """
    try:
        return await asyncio.wait_for(work, settings.agent_timeout_seconds)
    except passthrough:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(504, "The agent timed out")
    except (StructuredOutputError, AgentOutputError, ValidationError, GraphRecursionError):
        logger.exception("agent %s returned unusable output", label)
        raise HTTPException(502, "The agent returned an unusable response, try again")
    except Exception:
        logger.exception("agent %s failed", label)
        raise HTTPException(503, "Agent unavailable: check that the MCP server and Ollama are running")
