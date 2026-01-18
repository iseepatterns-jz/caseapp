import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def fix_schema():
    # Construct database URL from environment variables
    # Matches the backend's logic
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "courtcase_db")
    
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    print(f"Connecting to database: {host}/{db_name}")
    
    engine = create_async_engine(db_url)
    
    async with engine.begin() as conn:
        print("Checking if column entity_name exists...")
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='audit_logs' AND column_name='entity_name';
        """))
        exists = result.fetchone()
        
        if not exists:
            print("Column entity_name does not exist. Adding it...")
            await conn.execute(text("ALTER TABLE audit_logs ADD COLUMN entity_name VARCHAR(200);"))
            print("Column added successfully.")
        else:
            print("Column entity_name already exists.")
            
        # Also ensure alembic_version is stamped if we are doing this manually
        # This keeps alembic in sync
        print("Ensuring alembic_version is up to date (0f087aba17ae)...")
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0f087aba17ae') ON CONFLICT DO NOTHING;"))
        await conn.execute(text("UPDATE alembic_version SET version_num = '0f087aba17ae';"))
        print("Alembic version updated.")

    await engine.dispose()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(fix_schema())
