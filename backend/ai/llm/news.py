from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from backend.ai.llm.client import get_llm
from backend.crud.schemas.news import NewsCreate

# Keeps the prompt inside the 2B model's context window.
MAX_INPUT_CHARS = 8000

SYSTEM_PROMPT = """You write a daily news briefing from the articles provided.
Use only the provided text. Do not invent details.

Pick the 3 most significant events. Favor events covered by several articles or sources.

Return these fields:
- title: a short headline.
- summary: 2-3 plain sentences naming the 3 events. It is shown on its own, so do not repeat it in the body.
- body: 2-3 markdown paragraphs of plain prose (no bullet lists, no headings) covering all 3 events.
  Say what happened, then explain why it matters. Put the most important event first.
- quiz_section: 3 questions with answers, based on those events."""

@traceable(run_type="chain")
async def summarize_news(articles: str, sources: list[str]) -> NewsCreate:
    """One structured model call: no tools, no DB access. The caller (briefing service) stores the result."""
    llm = get_llm("news").with_structured_output(NewsCreate, method="json_schema")
    result = await llm.ainvoke(
        [SystemMessage(SYSTEM_PROMPT), HumanMessage(articles[:MAX_INPUT_CHARS])]
    )
    return result.model_copy(update={"sources": sources})
