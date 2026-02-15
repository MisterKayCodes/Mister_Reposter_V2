"""
SERVICES: REPOST ENGINE
The 'Nervous System' of the bot.
Bridges the Vault (Database), the Brain (MessageCleaner), and the Eyes (Telethon).
"""
import logging
import os
import asyncio
import time
import hashlib
from collections import defaultdict
from providers.telethon_client import TelethonProvider
from data.database import async_session
from data.repository import UserRepository
from core.repost.logic import MessageCleaner
from services.media_cache import MediaCache
from config import config

logger = logging.getLogger(__name__)

MAX_ERRORS_BEFORE_DISABLE = 5
FLOOD_WAIT_MAX_RETRY = 3
DEDUP_CACHE_SIZE = 500


class RepostService:
    def __init__(self):
        self.telethon = TelethonProvider(
            config.API_ID,
            config.API_HASH
        )
        self.album_cache = {}
        self.schedule_queue = {}
        self.schedule_timers = {}
        self.media_cache = MediaCache()
        self.file_id_cache = {}
        self._dedup_seen = defaultdict(dict)
        self._bot = None
        # Rule 1: Tracking state to prevent duplicate listeners
        self._active_listeners = set()

    def set_bot(self, bot):
        self._bot = bot

    async def _notify_user(self, user_id: int, text: str):
        """Rule 12: Handle notification errors explicitly."""
        if self._bot:
            try:
                await self._bot.send_message(user_id, text)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

    async def user_has_session(self, user_id: int) -> bool:
        session_file = os.path.join("data", "sessions", f"{user_id}.session")
        if os.path.exists(session_file):
            return True
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            user = await repo.get_user(user_id)
            return bool(user and user.session_string)

    def _get_session_path(self, user_id: int, user=None) -> str | None:
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "sessions", f"{user_id}.session"
        )
        if os.path.exists(file_path):
            return file_path
        if user and user.session_string:
            return user.session_string
        return None

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
            pairs = await repo.get_user_pairs(user_id)
            for p in pairs:
                self._cancel_schedule_timer(p.id)
                self.schedule_queue.pop(p.id, None)
                self._dedup_seen.pop(p.id, None)
            return await repo.delete_all_user_pairs(user_id)

    async def delete_single_pair(self, user_id: int, pair_id: int) -> bool:
        self._cancel_schedule_timer(pair_id)
        self.schedule_queue.pop(pair_id, None)
        self._dedup_seen.pop(pair_id, None)
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.delete_pair_by_id(user_id, pair_id)

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        self._cancel_schedule_timer(pair_id)
        self.schedule_queue.pop(pair_id, None)
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.deactivate_pair(user_id, pair_id)

    async def activate_pair(self, user_id: int, pair_id: int) -> bool:
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            success = await repo.activate_pair(user_id, pair_id)
            if success:
                if user_id not in self._active_listeners:
                    user = await repo.get_user(user_id)
                    session_path = self._get_session_path(user_id, user)
                    if session_path:
                        await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                        self._active_listeners.add(user_id)
                return True
        return False

    async def resolve_channel_for_pair(self, user_id: int, identifier: str, kind: str, invite_hash: str = None) -> str:
        """Joins private channels and returns a normalized ID."""
        if kind == "invite" and invite_hash:
            result = await self.telethon.join_channel(user_id, invite_hash)
            if result and result.get("id"):
                resolved_id = str(result["id"])
                if not resolved_id.startswith("-100"):
                    resolved_id = f"-100{resolved_id}"
                return resolved_id
            return identifier

        # Rule 6: No guessing. Resolve known entities.
        if kind in ("private_id", "numeric", "forwarded", "username"):
            entity = await self.telethon.resolve_entity(user_id, identifier)
            if entity:
                return str(entity["id"])
        
        return identifier

    async def add_new_pair(
        self, user_id: int, source: str, destination: str,
        filter_type: int = 1, replacement_link: str = None,
        schedule_interval: int = None, start_from_msg_id: int = None,
    ):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            # Rule 11: Capture the new pair object to get its ID
            new_pair = await repo.add_repost_pair(
                user_id, source, destination, filter_type,
                replacement_link, schedule_interval, start_from_msg_id
            )
            
            user = await repo.get_user(user_id)
            session_path = self._get_session_path(user_id, user)
            
            if not session_path:
                logger.warning(f"User {user_id} has no session.")
                return

        # Start listening if not already doing so
        if user_id not in self._active_listeners:
            await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
            self._active_listeners.add(user_id)

        # Rule 7: Pass all required arguments to the backfill task
        if start_from_msg_id and schedule_interval and schedule_interval > 0:
            asyncio.create_task(
                self._backfill_from_message(
                    user_id, source, destination, start_from_msg_id, 
                    filter_type, replacement_link, schedule_interval, new_pair.id
                )
            )
            

    async def _backfill_from_message(self, user_id, source, destination, from_msg_id, filter_type, replacement_link, interval_minutes, pair_id):
        """Rule 11: Optimized for scheduled progression (msg 19 -> 20 -> 21)."""
        await asyncio.sleep(5) # Brief pause to let system stabilize
        
        current_id = from_msg_id
        
        while True:
            # Rule 6: Fetch only ONE message to ensure we don't skip logic
            messages = await self.telethon.fetch_messages_from(user_id, source, current_id, limit=1)
            
            if not messages:
                logger.info(f"Backfill for Pair #{pair_id} reached the 'present'. Switching to live listening.")
                break

            msg = messages[0]
            if msg.message:
                msg.message = MessageCleaner.clean(msg.message, mode=filter_type, replacement=replacement_link)

            # Send the message
            result = await self._send_with_retry(user_id, destination, msg, pair_id=pair_id)
            
            if result["ok"]:
                # --- THE CRITICAL UPDATE ---
                # Move the pointer forward in the Vault
                current_id += 1 
                async with async_session() as db_session:
                    repo = UserRepository(db_session)
                    await repo.update_pair_start_id(pair_id, current_id)
                
                # Rule 4.2: Respect the user's 5-minute schedule
                logger.info(f"Pair #{pair_id} posted msg {current_id-1}. Waiting {interval_minutes}m for next.")
                await asyncio.sleep(interval_minutes * 60)
            else:
                # If we hit a flood wait or error, stop the loop to prevent bot-wide lockout
                logger.error(f"Backfill stopped on Pair #{pair_id} at msg {current_id} due to error.")
                break

        
    def _compute_dedup_key(self, message) -> str | None:
        parts = []
        msg_id = getattr(message, "id", None)
        chat_id = getattr(message, "chat_id", None)
        if msg_id and chat_id:
            parts.append(f"{chat_id}:{msg_id}")

        if hasattr(message, "media") and message.media:
            media_type = type(message.media).__name__
            if hasattr(message.media, "photo") and message.media.photo:
                parts.append(f"{media_type}:{message.media.photo.id}")
            elif hasattr(message.media, "document") and message.media.document:
                parts.append(f"{media_type}:{message.media.document.id}")

        if not parts and getattr(message, "message", ""):
            parts.append(hashlib.md5(message.message.encode()).hexdigest()[:12])

        return "|".join(parts) if parts else None

    def _is_duplicate(self, pair_id: int, message) -> bool:
        key = self._compute_dedup_key(message)
        if not key: return False

        seen = self._dedup_seen[pair_id]
        if key in seen: return True

        seen[key] = time.time()
        # Rule 14: Cache cleanup
        if len(seen) > DEDUP_CACHE_SIZE:
            oldest = sorted(seen, key=seen.get)[:100]
            for k in oldest: del seen[k]
        return False

    async def _send_with_retry(self, user_id: int, destination: str, message, pair_id: int = None) -> dict:
        for attempt in range(FLOOD_WAIT_MAX_RETRY + 1):
            result = await self.telethon.send_message(user_id, destination, message)

            if result["ok"]:
                if pair_id:
                    async with async_session() as db_session:
                        repo = UserRepository(db_session)
                        await repo.reset_error_count(pair_id)
                return result

            if result.get("error") == "flood_wait":
                wait = result.get("wait_seconds", 30)
                if wait > 300: return result
                
                await self._notify_user(user_id, f"Rate limited. Retrying in {wait}s...")
                await asyncio.sleep(wait)
                continue

            return result
        return {"ok": False, "error": "max_retries"}

    async def _record_pair_error(self, pair_id: int, user_id: int, error_detail: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            new_count = await repo.increment_error_count(pair_id)
            if new_count >= MAX_ERRORS_BEFORE_DISABLE:
                await repo.deactivate_pair_as_error(pair_id)
                self._cancel_schedule_timer(pair_id)
                await self._notify_user(user_id, f"Pair #{pair_id} disabled after {new_count} errors.")

    async def _handle_new_message(self, message, user_id):
        if not (message.message or message.media): return

        if message.grouped_id:
            gid = message.grouped_id
            if gid not in self.album_cache:
                self.album_cache[gid] = []
                asyncio.create_task(self._process_album_after_delay(gid, user_id))
            self.album_cache[gid].append(message)
            return

        await self._execute_repost(user_id, [message])

    async def _process_album_after_delay(self, gid, user_id):
        await asyncio.sleep(1.0)
        messages = self.album_cache.pop(gid, [])
        if messages:
            await self._execute_repost(user_id, messages)

    async def _execute_repost(self, user_id, messages):
        # Optimization: Normalize incoming chat ID once
        raw_cid = str(messages[0].chat_id)
        norm_cid = raw_cid if raw_cid.startswith("-100") else f"-100{raw_cid}"

        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pairs = await repo.get_user_pairs(user_id)
            if not pairs: return

            for p in pairs:
                if not p.is_active or p.status == "error": continue

                # Normalize source ID for matching
                src = str(p.source_id)
                norm_src = src if src.startswith("-100") else f"-100{src}"

                if norm_cid == norm_src:
                    await self._process_matched_pair(p, user_id, messages)
                    break

    async def _process_matched_pair(self, p, user_id, messages):
        if self._is_duplicate(p.id, messages[0]): return

        for msg in messages:
            if msg.message:
                msg.message = MessageCleaner.clean(msg.message, mode=p.filter_type, replacement=p.replacement_link)

        if p.schedule_interval and p.schedule_interval > 0:
            bundle = self.media_cache.cache_bundle(p.id, messages)
            self._enqueue_scheduled(p.id, user_id, p.destination_id, bundle, p.schedule_interval)
        else:
            result = await self._send_with_retry(user_id, p.destination_id, messages, pair_id=p.id)
            if not result["ok"]:
                await self._record_pair_error(p.id, user_id, result.get("error", "Unknown"))

    def _enqueue_scheduled(self, pair_id: int, user_id: int, destination: str, messages, interval_minutes: int):
        if pair_id not in self.schedule_queue:
            self.schedule_queue[pair_id] = []
        self.schedule_queue[pair_id].append({
            "user_id": user_id, "destination": destination, "messages": messages
        })
        if pair_id not in self.schedule_timers or self.schedule_timers[pair_id].done():
            self.schedule_timers[pair_id] = asyncio.create_task(self._flush_schedule(pair_id, interval_minutes))

    async def _flush_schedule(self, pair_id: int, interval_minutes: int):
        await asyncio.sleep(interval_minutes * 60)
        queued = self.schedule_queue.pop(pair_id, [])
        if not queued: return

        for item in queued:
            await self._send_with_retry(item["user_id"], item["destination"], item["messages"], pair_id=pair_id)
        
        self.schedule_timers.pop(pair_id, None)
        self.media_cache.clear_pair(pair_id)

    def _cancel_schedule_timer(self, pair_id: int):
        timer = self.schedule_timers.pop(pair_id, None)
        if timer and not timer.done(): timer.cancel()
        self.media_cache.clear_pair(pair_id)

    async def recover_all_listeners(self):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            users = await repo.get_all_active_users_with_pairs()
            for uid in users:
                if uid not in self._active_listeners:
                    user = await repo.get_user(uid)
                    path = self._get_session_path(uid, user)
                    if path:
                        await self.telethon.start_listener(uid, path, self._handle_new_message)
                        self._active_listeners.add(uid)