from collections.abc import Iterable

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langsmith import traceable
from pydantic import BaseModel

from backend.agents.llm import get_llm
from backend.config import settings


class AgentOutputError(Exception):
    """The model finished without producing the structured output that was asked for."""


async def load_tools(allowed: Iterable[str]):
    """Fetch tools from the MCP server, keeping only the allow-listed names.

    Raises if an allowed tool is missing so a renamed server tool fails loudly.
    """
    client = MultiServerMCPClient({"command_center": {"transport": "streamable_http", "url": settings.mcp_url}})
    by_name = {t.name: t for t in await client.get_tools()}
    missing = set(allowed) - by_name.keys()
    if missing:
        raise RuntimeError(f"MCP server is missing tools: {sorted(missing)}")
    return [by_name[name] for name in allowed]

@traceable(run_type="chain")
async def run_agent(
    name: str,
    system_prompt: str,
    allowed_tools: Iterable[str],
    message: str,
    response_format: type[BaseModel] | None = None,
) -> dict:
    """Run a tool-calling agent. Returns {"output": final text, "messages": full transcript}.

    With `response_format`, "output" is an instance of that model instead of text.
    An empty allow-list skips the MCP server entirely.
    """
    allowed = list(allowed_tools)
    tools = await load_tools(allowed) if allowed else []
    agent = create_agent(get_llm(name), tools, system_prompt=system_prompt, name=name, response_format=response_format)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
    messages = result["messages"]
    if response_format:
        output = result.get("structured_response")
        if output is None:
            raise AgentOutputError(f"{name} did not return the requested structure")
    else:
        output = messages[-1].content
    return {"output": output, "messages": messages}
