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

    async def validate_and_save_file(self, user_id: int, file_path: str) -> tuple[bool, int | None]:
        """Rule 11: Logic for validating a pre-downloaded file."""
        is_valid, target_id, username = await self.telethon.validate_session(file_path)
        
        if is_valid:
            async with async_session() as db_session:
                repo = UserRepository(db_session)
                # Identity Sync: Link the file to the actual account inside the session
                await repo.import_session_identity(target_id, username, file_path)
                logger.info(f"Session file for '{username}' ({target_id}) saved.")
            return True, target_id
        else:
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except Exception: pass
            return False, None

    async def validate_and_save_string(self, user_id: int, session_str: str) -> tuple[bool, int | None]:
        """Rule 11: Logic for validating a raw session string."""
        is_valid, target_id, username = await self.telethon.validate_session(session_str)
        
        if is_valid:
            async with async_session() as db_session:
                repo = UserRepository(db_session)
                # Identity Sync: Link the string to the actual account inside the session
                await repo.import_session_identity(target_id, username, session_str)
            return True, target_id
        return False, None
