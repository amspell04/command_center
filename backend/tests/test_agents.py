import asyncio
from types import SimpleNamespace

import pytest

from backend.agents import runner
from backend.agents.news_agent import agent as news_agent
from backend.agents.notes_agent.agent import ALLOWED_TOOLS as NOTES_TOOLS
from backend.agents.task_agent.agent import ALLOWED_TOOLS as TASK_TOOLS
from backend.crud.schemas.news import NewsCreate
from backend.services.mcp.server import mcp


def fake_client(tool_names):
    class FakeClient:
        def __init__(self, config):
            self.config = config

        async def get_tools(self):
            return [SimpleNamespace(name=n) for n in tool_names]

    return FakeClient


# allow-lists

def test_allow_lists_are_real_server_tools():
    server_tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert set(TASK_TOOLS) <= server_tools
    assert set(NOTES_TOOLS) <= server_tools


def test_allow_lists_have_no_delete_and_do_not_overlap():
    assert not any("delete" in n for n in TASK_TOOLS + NOTES_TOOLS)
    assert not set(TASK_TOOLS) & set(NOTES_TOOLS)


# load_tools

@pytest.mark.asyncio
async def test_load_tools_filters_to_allow_list(monkeypatch):
    monkeypatch.setattr(runner, "MultiServerMCPClient", fake_client(["a", "b", "secret"]))
    tools = await runner.load_tools(["a", "b"])
    assert [t.name for t in tools] == ["a", "b"]


@pytest.mark.asyncio
async def test_load_tools_uses_streamable_http(monkeypatch):
    seen = {}
    base = fake_client(["a"])

    class Spy(base):
        def __init__(self, config):
            seen.update(config)

    monkeypatch.setattr(runner, "MultiServerMCPClient", Spy)
    await runner.load_tools(["a"])
    assert seen["command_center"]["transport"] == "streamable_http"


@pytest.mark.asyncio
async def test_load_tools_missing_tool_raises(monkeypatch):
    monkeypatch.setattr(runner, "MultiServerMCPClient", fake_client(["a"]))
    with pytest.raises(RuntimeError, match="missing tools.*'b'"):
        await runner.load_tools(["a", "b"])


# news agent

class FakeLLM:
    def __init__(self):
        self.prompt = None

    def with_structured_output(self, schema):
        assert schema is NewsCreate
        return self

    async def ainvoke(self, messages):
        self.prompt = messages
        return NewsCreate(title="t", summary="s", sources=["model-made-up"])


@pytest.mark.asyncio
async def test_summarize_news_overrides_sources(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(news_agent, "get_llm", lambda name: llm)
    result = await news_agent.summarize_news("articles", ["https://a.example"])
    assert result.sources == ["https://a.example"]
    assert result.title == "t"


@pytest.mark.asyncio
async def test_summarize_news_truncates_input(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(news_agent, "get_llm", lambda name: llm)
    await news_agent.summarize_news("x" * (news_agent.MAX_INPUT_CHARS + 500), [])
    assert len(llm.prompt[1].content) == news_agent.MAX_INPUT_CHARS


@pytest.mark.asyncio
async def test_summarize_news_uses_no_tools(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(news_agent, "get_llm", lambda name: llm)
    assert not hasattr(llm, "bind_tools")
    await news_agent.summarize_news("a", [])
