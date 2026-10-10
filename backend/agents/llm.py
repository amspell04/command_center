from langchain_ollama import ChatOllama

from backend.config import settings


def get_llm(agent: str) -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        tags=[agent],
        metadata={"agent": agent, "model": settings.ollama_model},
    )
