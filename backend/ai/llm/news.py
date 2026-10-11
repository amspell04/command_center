from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from backend.ai.llm.client import get_llm
from backend.crud.schemas.news import NewsCreate

# Keeps the prompt inside the 2B model's context window.
MAX_INPUT_CHARS = 8000

SYSTEM_PROMPT = """You write a short daily news briefing from the articles provided.
Use only the provided text. Return a title, a markdown summary, and 3 quiz questions with answers."""

@traceable(run_type="llm")
async def summarize_news(articles: str, sources: list[str]) -> NewsCreate:
    """One structured model call: no tools, no DB access. The caller (briefing service) stores the result."""
    llm = get_llm("news").with_structured_output(NewsCreate)
    result = await llm.ainvoke(
        [SystemMessage(SYSTEM_PROMPT), HumanMessage(articles[:MAX_INPUT_CHARS])]
    )
    return result.model_copy(update={"sources": sources})
