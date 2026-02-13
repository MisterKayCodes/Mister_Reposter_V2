"""
SERVICES: REPOST ENGINE
The 'Nervous System'. (Anatomy: Nervous System)
Bridges the Brain (Core) and the Eyes (Telethon).
"""
import logging
import os
import asyncio
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
        # The Waiting Room for albums
        self.album_cache = {}

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

    # --- TOGGLE LOGIC ---

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.deactivate_pair(user_id, pair_id)

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        """Action: Flip the switch to ON and ensure the listener is alive."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            success = await repo.activate_pair(user_id, pair_id)
            
            if success:
                user = await repo.get_user(user_id)
                session_path = user.session_string or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                    "data", "sessions", f"{user_id}.session"
                )
                if os.path.exists(session_path):
                    await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                return True
        return False

    # --- CORE REPOST LOGIC ---

    async def add_new_pair(self, user_id: int, source: str, destination: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.add_repost_pair(user_id, source, destination)
            user = await repo.get_user(user_id)

            session_str = user.session_string or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "data", "sessions", f"{user_id}.session"
            )
            
            if not os.path.exists(session_str) and not user.session_string:
                logger.warning(f"User {user_id} has no session. Eyes closed.")
                return 

        await self.telethon.start_listener(user_id, session_str, self._handle_new_message)

    async def _handle_new_message(self, message, user_id):
        """Reflex Arc: Handles incoming signals, including albums."""
        if not (message.message or message.media):
            return

        # --- ALBUM BUFFER LOGIC ---
        if message.grouped_id:
            gid = message.grouped_id
            if gid not in self.album_cache:
                self.album_cache[gid] = []
                # Start the timer to process the group
                asyncio.create_task(self._process_album_after_delay(gid, user_id))
            
            self.album_cache[gid].append(message)
            return

        # Standard single message flow
        await self._execute_repost(user_id, [message])

    async def _process_album_after_delay(self, gid, user_id):
        """Wait for all parts of the album to arrive before blinking."""
        await asyncio.sleep(1.0) # Buffer window
        messages = self.album_cache.pop(gid, [])
        if messages:
            await self._execute_repost(user_id, messages)

    async def _execute_repost(self, user_id, messages):
        """Final execution of the blink for one or more messages."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pairs = await repo.get_user_pairs(user_id)
            if not pairs:
                return

            main_msg = messages[0]
            try:
                chat = await main_msg.get_chat() 
                chat_username = str(chat.username).lower() if chat and hasattr(chat, 'username') and chat.username else ""
            except Exception:
                chat_username = ""

            for p in pairs:
                if not p.is_active:
                    continue

                source_identifier = str(p.source_id).lower().replace("@", "").strip()
                if (source_identifier == chat_username) or (source_identifier in str(main_msg.chat_id)):
                    try:
                        await self.telethon.send_message(
                            user_id=user_id, 
                            destination=p.destination_id, 
                            message=messages
                        )
                        break
                    except Exception as e:
                        logger.error(f"❌ Blink failed: {e}")

    async def recover_all_listeners(self):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            users_to_recover = await repo.get_all_active_users_with_pairs() 
            
            for user_id in users_to_recover:
                try:
                    user = await repo.get_user(user_id)
                    session_path = user.session_string or os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                        "data", "sessions", f"{user_id}.session"
                    )

                    if os.path.exists(session_path):
                        await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                except Exception as e:
                    logger.error(f"❌ Recovery failed for {user_id}: {e}")