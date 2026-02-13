"""
SERVICES: REPOST ENGINE
The 'Nervous System' of the bot.
Bridges the Vault (Database), the Brain (MessageCleaner), and the Eyes (Telethon).
"""
import logging
import os
import asyncio
from providers.telethon_client import TelethonProvider
from data.database import async_session
from data.repository import UserRepository
from core.repost.logic import MessageCleaner
from config import config

logger = logging.getLogger(__name__)

class RepostService:
    def __init__(self):
        self.telethon = TelethonProvider(
            config.API_ID, 
            config.API_HASH
        )
        # The Waiting Room for incoming media groups (albums)
        self.album_cache = {}

    # --- VAULT OPERATIONS ---

    async def register_user(self, user_id: int, username: str):
        """Creates or updates user records in the database."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.create_or_update_user(user_id, username)

    async def get_user_pairs(self, user_id: int):
        """Retrieves all repost rules for a specific user."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.get_user_pairs(user_id)

    async def delete_all_user_pairs(self, user_id: int):
        """Wipes the user's ledger clean."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.delete_all_user_pairs(user_id)

    async def delete_single_pair(self, user_id: int, pair_id: int) -> bool:
        """Removes a single specific repost rule."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.delete_pair_by_id(user_id, pair_id)

    # --- TOGGLE LOGIC ---

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        """Pauses a reposting rule."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.deactivate_pair(user_id, pair_id)

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        """Resumes a reposting rule and ensures the listener is running."""
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

    # --- CORE REPOST & FILTER LOGIC ---

    async def add_new_pair(self, user_id: int, source: str, destination: str, filter_type: int = 1, replacement_link: str = None):
        """Creates a new pair and records the specific filtering choice."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            # Important: We now pass filter_type and replacement_link to the Librarian
            await repo.add_repost_pair(user_id, source, destination, filter_type, replacement_link)
            user = await repo.get_user(user_id)

            session_str = user.session_string or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "data", "sessions", f"{user_id}.session"
            )
            
            if not os.path.exists(session_str) and not user.session_string:
                logger.warning(f"User {user_id} has no session. Cannot start eyes.")
                return 

        await self.telethon.start_listener(user_id, session_str, self._handle_new_message)

    async def _handle_new_message(self, message, user_id):
        """The main reflex arc for incoming messages."""
        if not (message.message or message.media):
            return

        # Handle albums (media groups) using the 1-second buffer
        if message.grouped_id:
            gid = message.grouped_id
            if gid not in self.album_cache:
                self.album_cache[gid] = []
                asyncio.create_task(self._process_album_after_delay(gid, user_id))
            
            self.album_cache[gid].append(message)
            return

        # Handle standard single messages
        await self._execute_repost(user_id, [message])

    async def _process_album_after_delay(self, gid, user_id):
        """Wait for the full album 'tray' to be filled before processing."""
        await asyncio.sleep(1.0)
        messages = self.album_cache.pop(gid, [])
        if messages:
            await self._execute_repost(user_id, messages)

    async def _execute_repost(self, user_id, messages):
        """Cleans the text based on user settings and blinks it to the destination."""
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
                
                # Identify if the incoming message matches the source in the vault
                if (source_identifier == chat_username) or (source_identifier in str(main_msg.chat_id)):
                    
                    # Apply the chosen filter to every message in the bundle
                    for msg in messages:
                        if msg.message:
                            msg.message = MessageCleaner.clean(
                                msg.message, 
                                mode=p.filter_type, 
                                replacement=p.replacement_link
                            )
                    
                    try:
                        await self.telethon.send_message(
                            user_id=user_id, 
                            destination=p.destination_id, 
                            message=messages
                        )
                        break # Only repost to the first matching pair to avoid loops
                    except Exception as e:
                        logger.error(f"❌ Repost failed: {e}")

    async def recover_all_listeners(self):
        """Wakes up the listeners for all active users on bot reboot."""
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