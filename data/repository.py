"""
DATA: REPOSITORY
Handles all database operations for users and repost pairs.
This layer is strictly for reading and writing to the Vault.
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
        """Ensures the user exists in the database."""
        user = await self.get_user(user_id)
        if not user:
            user = User(id=user_id, username=username)
            self.session.add(user)
        else:
            user.username = username
        
        await self.session.commit()
        return user

    async def update_session_string(self, user_id: int, session_string: str):
        """Updates the stored session string for a user."""
        user = await self.get_user(user_id)
        if user:
            user.session_string = session_string
            await self.session.commit()
            return True
        return False

    # --- REPOST PAIR METHODS ---

    async def add_repost_pair(self, user_id: int, source: str, destination: str, filter_type: int = 1, replacement_link: str = None):
        """Adds a new repost pair with duplicate protection and filter settings."""
        # Check if this exact pair already exists to avoid duplicate messages
        existing = await self.session.execute(
            select(RepostPair).where(
                RepostPair.user_id == user_id,
                RepostPair.source_id == source,
                RepostPair.destination_id == destination
            )
        )
        if existing.scalar_one_or_none():
            return

        # Added filter_type and replacement_link to the storage logic
        new_pair = RepostPair(
            user_id=user_id,
            source_id=source,
            destination_id=destination,
            filter_type=filter_type,
            replacement_link=replacement_link
        )
        self.session.add(new_pair)
        await self.session.commit()

    async def delete_pair_by_id(self, user_id: int, pair_id: int) -> bool:
        """Deletes a specific pair after verifying ownership."""
        query = select(RepostPair).where(
            RepostPair.id == pair_id, 
            RepostPair.user_id == user_id
        )
        result = await self.session.execute(query)
        pair = result.scalar_one_or_none()

        if pair:
            await self.session.delete(pair)
            await self.session.commit()
            return True
        return False

    async def delete_all_user_pairs(self, user_id: int) -> int:
        """Removes all pairs for a specific user."""
        result = await self.session.execute(
            delete(RepostPair).where(RepostPair.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount 

    async def get_user_pairs(self, user_id: int):
        """Fetches all repost pairs for a user."""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.user_id == user_id)
        )
        return result.scalars().all()

    async def get_all_active_pairs(self):
        """Fetches all active pairs across all users for system recovery."""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.is_active == True)
        )
        return result.scalars().all()

    async def get_all_active_users_with_pairs(self):
        """Returns a list of unique user IDs who have active reposts running."""
        query = select(RepostPair.user_id).where(RepostPair.is_active == True).distinct()
        result = await self.session.execute(query)
        return [row[0] for row in result.all()]

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        """Pauses a repost pair."""
        result = await self.session.execute(
            select(RepostPair).where(
                RepostPair.id == pair_id, 
                RepostPair.user_id == user_id
            )
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_active = False
            await self.session.commit()
            return True
        return False

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        """Resumes a repost pair."""
        result = await self.session.execute(
            select(RepostPair).where(
                RepostPair.id == pair_id, 
                RepostPair.user_id == user_id
            )
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_active = True
            await self.session.commit()
            return True
        return False