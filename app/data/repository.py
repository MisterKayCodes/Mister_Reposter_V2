"""
DATA: REPOSITORY
Handles user-related database operations and orchestrates PairRepository logic.
Inherits from PairRepository to maintain a unified interface.
"""
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User
from .repo_pairs import PairRepository
from app.core.config import ADMIN_IDS

logger = logging.getLogger(__name__)

class UserRepository(PairRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def ensure_schema_healed(self):
        """Rule 11: Self-healing schema for dynamic additions."""
        try:
            from sqlalchemy import text
            # SQLite specific column addition checks
            for col in ["is_admin", "is_premium", "premium_until"]:
                try:
                    await self.session.execute(text(f"SELECT {col} FROM users LIMIT 1"))
                except Exception:
                    logger.warning(f"Healing Schema: Adding {col} to users table.")
                    await self.session.execute(text(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT 0"))
            await self.session.commit()
        except Exception as e:
            logger.error(f"Schema healing failed: {e}")

    async def get_user(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_or_update_user(self, user_id: int, username: str | None = None) -> User:
        user = await self.get_user(user_id)
        if not user:
            user = User(id=user_id, username=username)
            if user_id in ADMIN_IDS:
                user.is_admin = True
            self.session.add(user)
        else:
            if username: user.username = username
            if user_id in ADMIN_IDS and not user.is_admin:
                user.is_admin = True
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

    async def get_all_users(self):
        result = await self.session.execute(select(User).order_by(User.created_at.desc()))
        return result.scalars().all()

    async def promote_user(self, user_id: int, status: bool = True) -> bool:
        user = await self.get_user(user_id)
        if user:
            user.is_admin = status
            await self.session.commit()
            return True
        return False

    async def grant_premium(self, user_id: int, months: int = 1) -> bool:
        user = await self.get_user(user_id)
        if user:
            from datetime import timedelta
            user.is_premium = True
            if not user.premium_until or user.premium_until < datetime.utcnow():
                user.premium_until = datetime.utcnow() + timedelta(days=30 * months)
            else:
                user.premium_until += timedelta(days=30 * months)
            await self.session.commit()
            return True
        return False