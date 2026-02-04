"""
SERVICES: SESSION MANAGER
The 'Nervous System'. (Anatomy: Nervous System)
Orchestrates input type detection, validation, and storage. (Rule 11)
"""
import os
import aiofiles
from aiogram import types
from providers.telethon_client import TelethonProvider
from data.database import async_session
from data.repository import UserRepository
from config import config

SESSIONS_DIR = "data/sessions"

class SessionService:
    def __init__(self):
        # The Nervous System controls the Eyes (Telethon)
        self.telethon = TelethonProvider(
            api_id=config.API_ID, 
            api_hash=config.API_HASH
        )
        if not os.path.exists(SESSIONS_DIR):
            os.makedirs(SESSIONS_DIR)

    async def handle_session_input(self, message: types.Message):
        """
        The Orchestrator. (Tasks.md 1.1)
        Decides if input is a file or string and directs it.
        """
        user_id = message.from_user.id

        if message.document:
            # 1. Action: Get file from Telegram
            file_bytes = await message.bot.download(message.document)
            content = file_bytes.read()
            
            # 2. Storage: Save to disk
            await self._save_to_disk(user_id, content)
            await message.answer("✅ .session file stored in the Vault.")

        elif message.text:
            # 1. Action: Validate string (Rule 5: Idempotency)
            session_str = message.text.strip()
            is_valid = await self.telethon.validate_session(session_str)
            
            if is_valid:
                # 2. Storage: Update Librarian (Memory)
                async with async_session() as db_session:
                    repo = UserRepository(db_session)
                    await repo.update_session_status(user_id, active=True)
                await message.answer("✅ Session string validated and linked!")
            else:
                await message.answer("❌ Invalid session string. Please try again.")

    async def _save_to_disk(self, user_id: int, content: bytes):
        """Private helper for disk I/O. (Rule 3)"""
        file_path = f"{SESSIONS_DIR}/{user_id}.session"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        async with async_session() as db_session:
            repo = UserRepository(db_session)
            # We store the path so the recovery service knows where to look
            user = await repo.get_user(user_id)
            if user:
                user.session_string = file_path # Point to the file
                user.has_active_session = True
                await db_session.commit()



