"""
SERVICES: SESSION MANAGER
The 'Nervous System'. (Anatomy: Nervous System)
Orchestrates input type detection, validation, and storage. (Rule 11)
"""
import uuid
import os
import aiofiles
import logging
from app.providers.telethon_client import TelethonProvider
from app.data.database import async_session
from app.data.repository import UserRepository
from app.core.config import config

SESSIONS_DIR = "data/sessions"
logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self.telethon = TelethonProvider(
            api_id=config.API_ID, 
            api_hash=config.API_HASH
        )

    async def validate_and_save_file(self, user_id: int, file_path: str) -> bool:
        """Rule 11: Logic for validating a pre-downloaded file."""
        is_valid = await self.telethon.validate_session(file_path)
        
        if is_valid:
            async with async_session() as db_session:
                repo = UserRepository(db_session)
                await repo.update_session_string(user_id, file_path)
                logger.info(f"User {user_id} session file path saved to DB.")
            return True
        else:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup invalid session file: {e}")
            return False

    async def validate_and_save_string(self, user_id: int, session_str: str) -> bool:
        """Rule 11: Logic for validating a raw session string."""
        is_valid = await self.telethon.validate_session(session_str)
        
        if is_valid:
            async with async_session() as db_session:
                repo = UserRepository(db_session)
                await repo.update_session_string(user_id, session_str)
            return True
        return False
