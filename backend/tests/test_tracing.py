import os

import pytest

from backend.config import configure_tracing, settings


@pytest.fixture(autouse=True)
def _restore(monkeypatch):
    for key in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
        monkeypatch.setenv(key, "")
    yield
    configure_tracing()


def test_tracing_exported_when_key_set(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_tracing", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "lsv2_test")
    monkeypatch.setattr(settings, "langsmith_project", "proj")
    configure_tracing()
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2_test"
    assert os.environ["LANGSMITH_PROJECT"] == "proj"


def test_tracing_off_without_key(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_tracing", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "")
    configure_tracing()
    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_tracing_off_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_tracing", False)
    monkeypatch.setattr(settings, "langsmith_api_key", "lsv2_test")
    configure_tracing()
    assert os.environ["LANGSMITH_TRACING"] == "false"
