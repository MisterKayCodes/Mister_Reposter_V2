"""
SERVICES: REPOST ENGINE
The 'Nervous System'. (Anatomy: Nervous System)
Bridges the Brain (Core) and the Eyes (Telethon).
Fighting path ghosts while Gabzy plays in the background.
"""
import logging
import os
from providers.telethon_client import TelethonProvider
from core.repost.logic import clean_message_text
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

    async def get_user(self, user_id: int):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.get_user(user_id)

    async def get_user_pairs(self, user_id: int):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.get_user_pairs(user_id)

    async def delete_all_user_pairs(self, user_id: int):
        """Action: Burn all pairs for a user. (Oga's Clutter Fix)"""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            count = await repo.delete_all_user_pairs(user_id)
            return count

    # --- CORE REPOST LOGIC ---

    async def add_new_pair(self, user_id: int, source: str, destination: str):
        """Link a new pair and ensure the listener is active."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.add_repost_pair(user_id, source, destination)
            user = await repo.get_user(user_id)

            # --- THE ABSOLUTE PATH FIX ---
            session_str = user.session_string if user and user.session_string else None
            
            if not session_str:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                potential_file = os.path.join(base_dir, "data", "sessions", f"{user_id}.session")
                if os.path.exists(potential_file):
                    session_str = potential_file
            
            if not session_str:
                logger.warning(f"User {user_id} has no Session file or string. Eyes remaining closed.")
                return 

        # <REACTION: Handshake fix. We only send user_id, path, and callback now.>
        await self.telethon.start_listener(
            user_id, 
            session_str,
            self._handle_new_message
        )

    async def _handle_new_message(self, message, user_id):
        """Reflex Arc: Triggered when the Eyes see a photon."""
        # 1. Sensory Check: Using Telethon vocabulary (.message instead of .text/.caption)
        if not (message.message or message.media):
            return

        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pairs = await repo.get_user_pairs(user_id)
            
            if not pairs: 
                return
            
            # --- THE MATCHING FIX ---
            dest = None
            try:
                chat = await message.get_chat() 
            except Exception:
                chat = None
            
            for p in pairs:
                # Normalize identifiers for a fair fight
                source_identifier = str(p.source_id).lower().replace("@", "").strip()
                chat_username = str(chat.username).lower() if chat and hasattr(chat, 'username') and chat.username else ""
                
                # Check match against Username OR raw ID (handling prefixes)
                if (source_identifier == chat_username) or (source_identifier in str(message.chat_id)):
                    dest = p.destination_id
                    break
            
            if not dest:
                return

            # --- THE FINAL BLINK ---
            logger.info(f"🚀 Reposting message from {message.chat_id} to {dest} for User {user_id}")
            
            try:
                await self.telethon.send_message(
                    user_id=user_id,
                    destination=dest,
                    message=message
                )
            except Exception as e:
                logger.error(f"❌ Failed to blink message: {e}")

    async def recover_all_listeners(self):
        """Resurrection: Wakes up all Eyes after the organism reboots."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            # Fetch users who have active pairs to avoid duplicate listeners
            users_to_recover = await repo.get_all_active_users_with_pairs() 
            
            for user_id in users_to_recover:
                try:
                    user = await repo.get_user(user_id)
                    session_path = user.session_string if user and user.session_string else None
                    
                    if not session_path:
                        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        session_path = os.path.join(base_dir, "data", "sessions", f"{user_id}.session")

                    if not session_path or not os.path.exists(session_path):
                        logger.warning(f"⚠️ Skipping recovery for User {user_id}: Session missing.")
                        continue

                    logger.info(f"Recovering global listener for User {user_id}")
                    await self.telethon.start_listener(
                        user_id, 
                        session_path, 
                        self._handle_new_message
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to recover User {user_id}: {e}")
                    continue

    async def stop_repost_pair(self, user_id: int, pair_id: int):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.deactivate_pair(pair_id)
        # Note: We keep the listener alive if they have other active pairs
        return await self.telethon.stop_listener(user_id)