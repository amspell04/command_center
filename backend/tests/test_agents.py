import asyncio
from types import SimpleNamespace

import pytest

from backend.ai.agents import runner
from backend.ai.llm import news as news_llm
from backend.ai.llm import notes as notes_llm
from backend.ai.llm import tasks as tasks_llm
from backend.ai.llm.client import load_prompt
from backend.crud.schemas.news import NewsCreate


def fake_client(tool_names):
    class FakeClient:
        def __init__(self, config):
            self.config = config

        async def get_tools(self):
            return [SimpleNamespace(name=n) for n in tool_names]

    return FakeClient


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


# news

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
    monkeypatch.setattr(news_llm, "get_llm", lambda name: llm)
    result = await news_llm.summarize_news("articles", ["https://a.example"])
    assert result.sources == ["https://a.example"]
    assert result.title == "t"


@pytest.mark.asyncio
async def test_summarize_news_truncates_input(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(news_llm, "get_llm", lambda name: llm)
    await news_llm.summarize_news("x" * (news_llm.MAX_INPUT_CHARS + 500), [])
    assert len(llm.prompt[1].content) == news_llm.MAX_INPUT_CHARS


@pytest.mark.asyncio
async def test_summarize_news_uses_no_tools(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(news_llm, "get_llm", lambda name: llm)
    assert not hasattr(llm, "bind_tools")
    await news_llm.summarize_news("a", [])


# notes

class FakeChat:
    def __init__(self, content):
        self.content, self.prompt = content, None

    async def ainvoke(self, messages):
        self.prompt = messages
        return SimpleNamespace(content=self.content)


@pytest.mark.asyncio
async def test_summarize_note_sends_title_and_text_and_strips_the_reply(monkeypatch):
    llm = FakeChat("  A summary.\n")
    monkeypatch.setattr(notes_llm, "get_llm", lambda name: llm)
    assert await notes_llm.summarize_note("Cells", "body text") == "A summary."
    system, human = llm.prompt
    assert "summary" in system.content and not hasattr(llm, "bind_tools")
    assert human.content == "title: Cells\n\nbody text"


def test_summarize_note_prompt_does_not_ask_for_tool_calls():
    prompt = load_prompt("summarize_note")
    assert "append_note_content" not in prompt and "tool" not in prompt


# tasks

class FakeStructured:
    def __init__(self):
        self.schema = self.prompt = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    async def ainvoke(self, messages):
        self.prompt = messages
        return "plan"


@pytest.mark.asyncio
async def test_plan_day_uses_structured_output_and_fills_in_today(monkeypatch):
    llm = FakeStructured()
    monkeypatch.setattr(tasks_llm, "get_llm", lambda name: llm)
    assert await tasks_llm.plan_day("Plan my day.") == "plan"
    system, human = llm.prompt
    assert llm.schema is tasks_llm.DayPlan and human.content == "Plan my day."
    assert "{today}" not in system.content and tasks_llm.date.today().isoformat() in system.content


def test_load_prompt_unknown_name_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("nope")
