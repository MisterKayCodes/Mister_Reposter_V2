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
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self.telethon = TelethonProvider(
            api_id=config.API_ID, 
            api_hash=config.API_HASH
        )

    async def handle_session_input(self, message: types.Message) -> bool:
        """The Orchestrator. (Tasks.md 1.1)"""
        user_id = message.from_user.id

        if message.document:
            file_path = f"{SESSIONS_DIR}/{user_id}.session"
            
            # Action: Download directly to destination
            await message.bot.download(message.document, destination=file_path)
            
            # The Eyes validate the file path
            is_valid = await self.telethon.validate_session(file_path)
            
            if is_valid:
                # Logical Storage: Inform the Librarian
                async with async_session() as db_session:
                    repo = UserRepository(db_session)
                    await repo.update_session_string(user_id, file_path)
                    logger.info(f"User {user_id} session file path saved to DB.")
                await message.answer("✅ .session file validated and saved in the Vault.")
                return True
            else:
                if os.path.exists(file_path):
                    os.remove(file_path)
                await message.answer("❌ Invalid or corrupted .session file. Please try again.")
                return False

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
                return True
            else:
                await message.answer("❌ Invalid session string. Please try again.")
                return False
                
        return False
