"""
DATA: REPOSITORY
The 'Librarian'. (Anatomy: Memory)
Encapsulates all CRUD operations. No business logic allowed. (Rule 11)
Fighting duplicates and ghost errors while the music plays.
"""
from sqlalchemy import select, delete
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

    async def update_session_string(self, user_id: int, session_string: str):
        """Action: Writes the Session String (Soul) into the User record."""
        user = await self.get_user(user_id)
        if user:
            user.session_string = session_string
            await self.session.commit()
            return True
        return False

    # --- REPOST PAIR METHODS ---

    async def add_repost_pair(self, user_id: int, source: str, destination: str):
        """Adds a new repost pair for the user. (With Duplicate Guard)"""
        # <REACTION: Check if this exact pair already exists before adding more clutter.>
        existing = await self.session.execute(
            select(RepostPair).where(
                RepostPair.user_id == user_id,
                RepostPair.source_id == source,
                RepostPair.destination_id == destination
            )
        )
        if existing.scalar_one_or_none():
            return

        new_pair = RepostPair(
            user_id=user_id,
            source_id=source,
            destination_id=destination
        )
        self.session.add(new_pair)
        await self.session.commit()

    async def delete_all_user_pairs(self, user_id: int) -> int:
        """The 'Burn Notice'. Deletes all pairs for a user."""
        result = await self.session.execute(
            delete(RepostPair).where(RepostPair.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount 

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

    # --- THE MISSING DNA STRAND ---
    async def get_all_active_users_with_pairs(self):
        """Fetches a unique list of user_ids who have at least one active repost pair."""
        # <THINK: This fixes the CRITICAL boot error. The Nervous System needs this list!>
        query = select(RepostPair.user_id).where(RepostPair.is_active == True).distinct()
        result = await self.session.execute(query)
        return [row[0] for row in result.all()]

    async def deactivate_pair(self, pair_id: int):
        """Marks a pair as inactive in the Vault."""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_active = False
            await self.session.commit()
        return pair