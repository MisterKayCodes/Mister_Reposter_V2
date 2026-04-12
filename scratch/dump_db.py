import asyncio
from data.database import async_session
from data.repository import UserRepository
from data.models import User, RepostPair

async def dump_db():
    async with async_session() as session:
        result = await session.execute(UserRepository(session).select(User))
        users = result.scalars().all()
        print("--- USERS ---")
        for u in users:
            print(f"ID: {u.id}, Username: {u.username}, Session: {bool(u.session_string)}")

        result = await session.execute(UserRepository(session).select(RepostPair))
        pairs = result.scalars().all()
        print("\n--- REPOST PAIRS ---")
        for p in pairs:
            print(f"ID: {p.id}, Source: {p.source_id}, Dest: {p.destination_id}, Active: {p.is_active}, Status: {p.status}, ErrorCount: {p.error_count}")

if __name__ == "__main__":
    asyncio.run(dump_db())
