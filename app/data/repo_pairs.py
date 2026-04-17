"""
DATA: PAIR REPOSITORY (BASE)
Separated from repository.py to satisfy line limits (Rule 3).
Handles all logic specific to RepostPair models.
"""
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from .models import RepostPair


class PairRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_repost_pair(
        self, user_id: int, source: str, destination: str,
        filter_type: int = 1, replacement_link: str = None,
        schedule_interval: int = None, start_from_msg_id: int = None,
        is_protected: bool = False,
        source_display: str = None, destination_display: str = None
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
            is_active=True,
            is_protected=is_protected,
            source_display=source_display,
            destination_display=destination_display
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

    async def delete_all_pairs(self, user_id: int) -> int:
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

    async def get_all_pairs(self):
        result = await self.session.execute(select(RepostPair))
        return result.scalars().all()

    async def get_pair_by_id(self, pair_id: int):
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        return result.scalar_one_or_none()

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

    async def update_pair_total_posts(self, pair_id: int, total: int):
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.total_posts_source = total
            await self.session.commit()
            return True
        return False

    async def update_next_post_time(self, pair_id: int, next_time):
        """Rule 11: Persists the timer for restart resilience."""
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.next_allowed_post_at = next_time
            await self.session.commit()
            return True
        return False

    async def toggle_pair_loop(self, user_id: int, pair_id: int) -> bool:
        result = await self.session.execute(
            select(RepostPair).where(
                RepostPair.id == pair_id,
                RepostPair.user_id == user_id
            )
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.loop_history = not pair.loop_history
            await self.session.commit()
            return pair.loop_history
        return False

    async def update_alert_3d(self, pair_id: int, status: bool):
        result = await self.session.execute(
            select(RepostPair).where(RepostPair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.alerted_3d = status
            await self.session.commit()
            return True
        return False
    async def toggle_pair_protection(self, user_id: int, pair_id: int) -> bool:
        """Rule 11: Toggles physical downloading for protected content."""
        result = await self.session.execute(
            select(RepostPair).where(
                RepostPair.id == pair_id,
                RepostPair.user_id == user_id
            )
        )
        pair = result.scalar_one_or_none()
        if pair:
            pair.is_protected = not pair.is_protected
            await self.session.commit()
            return pair.is_protected
        return False
