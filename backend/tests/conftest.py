import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.db import models  # noqa: F401  (registers tables)
from backend.db.base import Base
from backend.db.session import get_db
from backend.services.api.api import app

# Throwaway database: create it once with `CREATE DATABASE command_center_test`.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", settings.database_url.rsplit("/", 1)[0] + "/command_center_test")

engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean():
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE tasks, notes, news, goals"))


@pytest.fixture
def db():
    with TestSession() as session:
        yield session


@pytest.fixture
def client():
    def override():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
