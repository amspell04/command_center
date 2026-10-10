from typing import Optional
from langchain_ollama import ChatOllama


def run_notes_agent(message: Optional[str]):
    agent = ChatOllama(
           model="qwen3.5:2b",
           temperature=0,
       )
   
    response = agent.invoke(message)
    return response.content_blocks