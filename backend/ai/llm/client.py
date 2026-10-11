from pathlib import Path

from langchain_ollama import ChatOllama

from backend.config import settings

_PROMPTS = Path(__file__).parent / "prompts"


def get_llm(name: str) -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        reasoning=False,
        tags=[name],
        metadata={"name": name, "model": settings.ollama_model},
    )


def load_prompt(name: str) -> str:
    """System prompt text from `prompts/<name>.md`."""
    return (_PROMPTS / f"{name}.md").read_text().strip()
