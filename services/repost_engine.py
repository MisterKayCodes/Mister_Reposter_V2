"""
SERVICES: REPOST ENGINE
The 'Nervous System'. (Anatomy: Nervous System)
Bridges the Brain (Core) and the Eyes (Telethon).
"""
import logging
import os
from providers.telethon_client import TelethonProvider
from data.database import async_session
from data.repository import UserRepository
from config import config

logger = logging.getLogger(__name__)

class RepostService:
    def __init__(self):
        self.telethon = TelethonProvider(
            config.API_ID, 
            config.API_HASH
        )

    # --- VAULT OPERATIONS ---

    async def register_user(self, user_id: int, username: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.create_or_update_user(user_id, username)

    async def get_user_pairs(self, user_id: int):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.get_user_pairs(user_id)

    async def delete_all_user_pairs(self, user_id: int):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.delete_all_user_pairs(user_id)

    async def delete_single_pair(self, user_id: int, pair_id: int) -> bool:
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.delete_pair_by_id(user_id, pair_id)

    # --- TOGGLE LOGIC (FIXED) ---

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        """Action: Flip the switch to OFF in the Vault."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.deactivate_pair(user_id, pair_id)

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        """Action: Flip the switch to ON in the Vault."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.activate_pair(user_id, pair_id)

    # --- CORE REPOST LOGIC ---

    async def add_new_pair(self, user_id: int, source: str, destination: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.add_repost_pair(user_id, source, destination)
            user = await repo.get_user(user_id)

            session_str = user.session_string if user and user.session_string else None
            if not session_str:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                potential_file = os.path.join(base_dir, "data", "sessions", f"{user_id}.session")
                if os.path.exists(potential_file):
                    session_str = potential_file
            
            if not session_str:
                logger.warning(f"User {user_id} has no session. Eyes closed.")
                return 

        await self.telethon.start_listener(user_id, session_str, self._handle_new_message)

    async def _handle_new_message(self, message, user_id):
        if not (message.message or message.media):
            return

        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pairs = await repo.get_user_pairs(user_id)
            if not pairs: return
            
            try:
                chat = await message.get_chat() 
                chat_username = str(chat.username).lower() if chat and hasattr(chat, 'username') and chat.username else ""
            except Exception:
                chat_username = ""
            
            dest = None
            for p in pairs:
                # --- RULE 1: THE STATUS GUARD ---
                if not p.is_active:
                    continue

                source_identifier = str(p.source_id).lower().replace("@", "").strip()
                if (source_identifier == chat_username) or (source_identifier in str(message.chat_id)):
                    dest = p.destination_id
                    break
            
            if dest:
                try:
                    await self.telethon.send_message(user_id=user_id, destination=dest, message=message)
                except Exception as e:
                    logger.error(f"❌ Blink failed: {e}")

    async def recover_all_listeners(self):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            users_to_recover = await repo.get_all_active_users_with_pairs() 
            
            for user_id in users_to_recover:
                try:
                    user = await repo.get_user(user_id)
                    session_path = user.session_string or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sessions", f"{user_id}.session")

                    if os.path.exists(session_path):
                        await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                except Exception as e:
                    logger.error(f"❌ Recovery failed for {user_id}: {e}")

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        """Action: Flip the switch to ON and ensure the listener is alive."""
        # <THINK: Just changing the DB isn't enough if the listener is dormant.>
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            success = await repo.activate_pair(user_id, pair_id)
            
            if success:
                user = await repo.get_user(user_id)
                # Ensure we have the path to the soul (session file)
                session_path = user.session_string or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                    "data", "sessions", f"{user_id}.session"
                )

                if os.path.exists(session_path):
                    # Handshake: Tell Telethon to start/ensure listener is running
                    await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                
                return True
        return False