import asyncio
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from core.database import engine
from models import Base

async def init_db():
    print("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
