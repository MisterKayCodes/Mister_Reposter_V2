"""
DATA: REPOSITORY
Handles user-related database operations and orchestrates PairRepository logic.
Inherits from PairRepository to maintain a unified interface.
"""
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, SystemSetting
from .repo_pairs import PairRepository
from app.core.config import ADMIN_IDS, config

logger = logging.getLogger(__name__)

class UserRepository(PairRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def ensure_schema_healed(self):
        """Rule 11: Self-healing schema for dynamic additions."""
        try:
            from sqlalchemy import text
            # SQLite specific column addition checks
            user_cols = ["is_admin", "is_premium", "premium_until"]
            for col in user_cols:
                try:
                    await self.session.execute(text(f"SELECT {col} FROM users LIMIT 1"))
                except Exception:
                    logger.warning(f"Healing Schema: Adding {col} to users table.")
                    col_type = "DATETIME" if col == "premium_until" else "BOOLEAN"
                    await self.session.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
            
            # Pair table healing
            pair_cols = ["is_protected", "alerted_caught_up", "source_display", "destination_display", "last_reposted_at", "consecutive_heals"]
            for col in pair_cols:
                try:
                    await self.session.execute(text(f"SELECT {col} FROM repost_pairs LIMIT 1"))
                except Exception:
                    logger.warning(f"Healing Schema: Adding {col} to repost_pairs table.")
                    if col == "last_reposted_at": col_type = "DATETIME"
                    elif col == "consecutive_heals": col_type = "INTEGER"
                    elif "alerted" in col or "protected" in col: col_type = "BOOLEAN"
                    else: col_type = "VARCHAR"
                    await self.session.execute(text(f"ALTER TABLE repost_pairs ADD COLUMN {col} {col_type}"))
            
            # Seed default settings
            owner = await self.get_setting("owner_username")
            if not owner:
                await self.set_setting("owner_username", config.OWNER_USERNAME)

            # Data Migration: SQLite sets defaults to '0' if added as BOOLEAN. Clean it for DATETIME.
            await self.session.execute(text("UPDATE users SET premium_until = NULL WHERE premium_until = '0' OR premium_until = 0"))
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

    async def import_session_identity(self, target_user_id: int, username: str | None, session_string: str) -> User:
        """Rule 11: Imports/Syncs an external Telegram account via session string."""
        user = await self.get_user(target_user_id)
        if not user:
            user = User(id=target_user_id, username=username)
            self.session.add(user)
        else:
            if username: user.username = username
            
        user.session_string = session_string
        user.has_active_session = True
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

    async def get_setting(self, key: str, default: str = None) -> str | None:
        result = await self.session.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        return setting.value if setting else default

    async def set_setting(self, key: str, value: str):
        result = await self.session.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if not setting:
            setting = SystemSetting(key=key, value=value)
            self.session.add(setting)
        else:
            setting.value = value
        await self.session.commit()
        return setting