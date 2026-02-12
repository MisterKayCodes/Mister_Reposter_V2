"""
SERVICES: SESSION MANAGER
The 'Nervous System'. (Anatomy: Nervous System)
Orchestrates input type detection, validation, and storage. (Rule 11)
"""
import os
import aiofiles
import logging
from aiogram import types
from providers.telethon_client import TelethonProvider
from data.database import async_session
from data.repository import UserRepository
from config import config

SESSIONS_DIR = "data/sessions"
logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self):
        # Same here—matching the DNA perfectly
        self.telethon = TelethonProvider(
            api_id=config.API_ID, 
            api_hash=config.API_HASH
        )

    async def handle_session_input(self, message: types.Message):
        """The Orchestrator. (Tasks.md 1.1)"""
        user_id = message.from_user.id

        if message.document:
            # 1. Action: Extract bytes from the Mouth
            file_bytes = await message.bot.download(message.document)
            content = file_bytes.read()
            
            # 2. Storage: Save to disk and update Vault via Librarian
            await self._save_to_disk(user_id, content)
            await message.answer("✅ .session file stored in the Vault.")

        elif message.text:
            session_str = message.text.strip()
            # The Eyes validate the string
            is_valid = await self.telethon.validate_session(session_str)
            
            if is_valid:
                # Rule 11: Ask the Librarian to update the memory
                async with async_session() as db_session:
                    repo = UserRepository(db_session)
                    await repo.update_session_string(user_id, session_str)
                await message.answer("✅ Session string validated and linked!")
            else:
                await message.answer("❌ Invalid session string. Please try again.")

    async def _save_to_disk(self, user_id: int, content: bytes):
        """Private helper for disk I/O. (Rule 3)"""
        file_path = f"{SESSIONS_DIR}/{user_id}.session"
        
        # Physical Storage
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Logical Storage: Inform the Librarian
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            # We store the file path as the 'string' so the engine knows it's a file
            await repo.update_session_string(user_id, file_path)
            logger.info(f"User {user_id} session file path saved to DB.")