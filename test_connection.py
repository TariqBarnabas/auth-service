import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

# Running from the terminal, not inside Docker — same reasoning as Alembic's env.py fix.
local_url = settings.DATABASE_URL.replace("@postgres:", "@localhost:")

async def test_connection():
    engine = create_async_engine(local_url, echo=True)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("Connected! SELECT 1 returned:", result.scalar())
    await engine.dispose()

asyncio.run(test_connection())