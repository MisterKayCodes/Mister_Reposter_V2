"""
DATA: REPOSITORY
The 'Librarian'. (Anatomy: Memory)
Encapsulates all CRUD operations. No business logic allowed. (Rule 11)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, RepostPair

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> User | None:
        """Fetches a user by their Telegram ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_or_update_user(self, user_id: int, username: str | None = None) -> User:
        """Ensures the user exists in the Vault. (Rule 1: Known State)"""
        user = await self.get_user(user_id)
        if not user:
            user = User(id=user_id, username=username)
            self.session.add(user)
        else:
            user.username = username
        
        await self.session.commit()
        return user

    async def update_session_status(self, user_id: int, active: bool):
        """Updates the session status for a user."""
        user = await self.get_user(user_id)
        if user:
            user.has_active_session = active
            await self.session.commit()

    # --- REPOST PAIR METHODS ---

    async def add_repost_pair(self, user_id: int, source: str, destination: str):
        """Adds a new repost pair for the user."""
        new_pair = RepostPair(
            user_id=user_id,
            source_id=source,
            destination_id=destination
        )
        self.session.add(new_pair)
        await self.session.commit()

    async def get_user_pairs(self, user_id: int):
        """Fetches all repost pairs for a specific user."""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.user_id == user_id)
        )
        return result.scalars().all()

    async def get_all_active_pairs(self):
        """Fetches every active pair for Startup Recovery. (Rule 7)"""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.is_active == True)
        )
        return result.scalars().all()
