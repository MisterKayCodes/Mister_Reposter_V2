"""
SERVICES: REPOST ENGINE
The 'Nervous System'. (Anatomy: Nervous System)
Bridges the Brain (Core) and the Eyes (Telethon).
"""
import logging
from providers.telethon_client import TelethonProvider
from core.repost.logic import clean_message_text
from data.database import async_session
from data.repository import UserRepository
from config import config

logger = logging.getLogger(__name__)

class RepostService:
    def __init__(self):
        self.telethon = TelethonProvider(config.API_ID, config.API_HASH)

    async def add_new_pair(self, user_id: int, source: str, destination: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.add_repost_pair(user_id, source, destination)
            user = await repo.get_user(user_id)
            session_str = user.session_string

        if session_str:
            await self.telethon.start_listener(
                user_id, 
                session_str, 
                source, 
                self._handle_new_message
            )

    async def _handle_new_message(self, message, user_id):
        """Callback triggered by the Eyes."""
        if not message.text:
            return

        # Fetch destination from Vault (Since lambda can be messy)
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pairs = await repo.get_user_pairs(user_id)
            user = await repo.get_user(user_id)
            
            # Simple MVP logic: Repost to the first active pair found
            if not pairs or not user: return
            dest = pairs[0].destination_id 

        # Brain: Clean text
        final_text = clean_message_text(message.text)
        
        # Eyes: Send using active client
        await self.telethon.send_message(user_id, user.session_string, dest, final_text)

    async def recover_all_listeners(self):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            active_pairs = await repo.get_all_active_pairs() 
            
            for pair in active_pairs:
                user = await repo.get_user(pair.user_id)
                if user and user.session_string:
                    logger.info(f"Recovering listener: User {user.id} | {pair.source_id}")
                    await self.telethon.start_listener(
                        user.id, 
                        user.session_string, 
                        pair.source_id, 
                        self._handle_new_message
                    )

    async def stop_repost_pair(self, user_id: int, pair_id: int):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.deactivate_pair(pair_id)
        return await self.telethon.stop_listener(user_id)
