"""
DATA: REPOSITORY
Handles all database operations for users and repost pairs.
Strictly for reading and writing to the Vault.
"""
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, RepostPair


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_or_update_user(self, user_id: int, username: str | None = None) -> User:
        user = await self.get_user(user_id)
        if not user:
            user = User(id=user_id, username=username)
            self.session.add(user)
        else:
            user.username = username
        await self.session.commit()
        return user

    async def update_session_string(self, user_id: int, session_string: str):
        user = await self.get_user(user_id)
        if user:
            user.session_string = session_string
            user.has_active_session = True
            await self.session.commit()
            return True
        return False

    async def add_repost_pair(
        self, user_id: int, source: str, destination: str,
        filter_type: int = 1, replacement_link: str = None,
        schedule_interval: int = None, start_from_msg_id: int = None
    ):
        # Rule 5: Check for existing pairs to prevent duplicates
        existing = await self.session.execute(
            select(RepostPair).where(
                RepostPair.user_id == user_id,
                RepostPair.source_id == source,
                RepostPair.destination_id == destination
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

        new_pair = RepostPair(
            user_id=user_id,
            source_id=source,
            destination_id=destination,
            filter_type=filter_type,
            replacement_link=replacement_link,
            schedule_interval=schedule_interval,
            start_from_msg_id=start_from_msg_id,
            status="active",
            is_active=True
        )
        self.session.add(new_pair)
        await self.session.commit()
        await self.session.refresh(new_pair)
        return new_pair

    async def update_pair_start_id(self, pair_id: int, new_msg_id: int):
        """Rule 11: Moves the pointer forward for scheduled backfills."""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.start_from_msg_id = new_msg_id
            await self.session.commit()
            return True
        return False

    async def delete_pair_by_id(self, user_id: int, pair_id: int) -> bool:
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
        result = await self.session.execute(
            delete(RepostPair).where(RepostPair.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount

    async def get_user_pairs(self, user_id: int):
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.user_id == user_id)
        )
        return result.scalars().all()

    async def get_all_active_pairs(self):
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.is_active == True)
        )
        return result.scalars().all()

    async def get_all_active_users_with_pairs(self):
        # Optimized for performance
        query = select(RepostPair.user_id).where(RepostPair.is_active == True).distinct()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        result = await self.session.execute(
            select(RepostPair).where(
                RepostPair.id == pair_id,
                RepostPair.user_id == user_id
            )
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_active = False
            pair.status = "paused"
            await self.session.commit()
            return True
        return False

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        result = await self.session.execute(
            select(RepostPair).where(
                RepostPair.id == pair_id,
                RepostPair.user_id == user_id
            )
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_active = True
            pair.status = "active"
            pair.error_count = 0
            await self.session.commit()
            return True
        return False

    async def deactivate_pair_as_error(self, pair_id: int) -> bool:
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_active = False
            pair.status = "error"
            await self.session.commit()
            return True
        return False

    async def increment_error_count(self, pair_id: int) -> int:
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.error_count = (pair.error_count or 0) + 1
            current_count = pair.error_count
            await self.session.commit()
            return current_count
        return 0

    async def reset_error_count(self, pair_id: int):
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.error_count = 0
            if pair.status == "error":
                pair.status = "active"
            await self.session.commit()