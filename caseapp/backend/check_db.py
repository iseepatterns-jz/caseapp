
import asyncio
from core.database import AsyncSessionLocal
from sqlalchemy import text
from models.case import Case
from models.user import User

async def check():
    async with AsyncSessionLocal() as session:
        try:
            case_count = await session.execute(text("SELECT count(*) FROM cases"))
            user_count = await session.execute(text("SELECT count(*) FROM users"))
            print(f"Cases in DB: {case_count.scalar()}")
            print(f"Users in DB: {user_count.scalar()}")
            
            # List all cases
            result = await session.execute(text("SELECT case_number, title FROM cases"))
            for row in result:
                print(f"Case: {row.case_number} - {row.title}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(check())
