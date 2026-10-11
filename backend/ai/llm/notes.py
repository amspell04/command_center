from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from backend.ai.llm.client import get_llm, load_prompt


@traceable(run_type="chain")
async def summarize_note(title: str, text: str) -> str:
    """One model call: no tools, no DB access. Returns the summary text; the caller saves it."""
    result = await get_llm("notes").ainvoke(
        [SystemMessage(load_prompt("summarize_note")), HumanMessage(f"title: {title}\n\n{text}")]
    )
    return result.content.strip()
