import asyncio
import asyncpg

async def check_db():
    try:
        conn = await asyncpg.connect(
            user='courtcase_admin', 
            password='=IG14U.Yt9Iea,aDdYvR-BTa=KW7z3', 
            database='courtcase_db_staging', 
            host='courtcasemanagementstack-courtcasedatabasef7bbe8d-g3dyfwj0ntc0.cv0iquw2k1to.us-east-1.rds.amazonaws.com'
        )
        val = await conn.fetchval('SELECT count(*) FROM cases')
        print(f'Total cases: {val}')
        await conn.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_db())
