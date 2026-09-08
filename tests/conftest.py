import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://authuser:changeme@localhost:5432/authdb_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import engine
from app.models.db import Base


@pytest_asyncio.fixture
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(setup_test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac