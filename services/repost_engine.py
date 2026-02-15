"""
SERVICES: REPOST ENGINE
The 'Nervous System' of the bot.
Bridges the Vault (Database), the Brain (MessageCleaner), and the Eyes (Telethon).
Includes The Scheduler, private channel orchestration, media caching,
health monitoring, FloodWait handling, and duplicate detection.
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

    def set_bot(self, bot):
        self._bot = bot

    async def _notify_user(self, user_id: int, text: str):
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
                user = await repo.get_user(user_id)
                session_path = self._get_session_path(user_id, user)
                if session_path:
                    await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                return True
        return False

    async def resolve_channel_for_pair(self, user_id: int, identifier: str, kind: str, invite_hash: str = None) -> str:
        if kind == "invite" and invite_hash:
            result = await self.telethon.join_channel(user_id, invite_hash)
            if result and result.get("id"):
                resolved_id = str(result["id"])
                if not resolved_id.startswith("-100"):
                    resolved_id = f"-100{resolved_id}"
                logger.info(f"Resolved invite to channel ID: {resolved_id}")
                return resolved_id
            logger.warning(f"Could not resolve invite hash, storing raw identifier")
            return identifier

        if kind in ("private_id", "numeric", "forwarded"):
            entity = await self.telethon.resolve_entity(user_id, identifier)
            if entity:
                return str(entity["id"])
            return identifier

        if kind == "username":
            entity = await self.telethon.resolve_entity(user_id, identifier)
            if entity:
                return str(entity["id"])
            return identifier

        return identifier

    async def add_new_pair(
        self, user_id: int, source: str, destination: str,
        filter_type: int = 1, replacement_link: str = None,
        schedule_interval: int = None, start_from_msg_id: int = None,
    ):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.add_repost_pair(
                user_id, source, destination, filter_type,
                replacement_link, schedule_interval, start_from_msg_id
            )
            user = await repo.get_user(user_id)

            session_path = self._get_session_path(user_id, user)
            if not session_path:
                logger.warning(f"User {user_id} has no session. Cannot start eyes.")
                return

        await self.telethon.start_listener(user_id, session_path, self._handle_new_message)

        if start_from_msg_id and schedule_interval and schedule_interval > 0:
            asyncio.create_task(
                self._backfill_from_message(user_id, source, destination, start_from_msg_id, filter_type, replacement_link)
            )

    async def _backfill_from_message(self, user_id, source, destination, from_msg_id, filter_type, replacement_link):
        await asyncio.sleep(2)
        messages = await self.telethon.fetch_messages_from(user_id, source, from_msg_id)
        if not messages:
            logger.info(f"No messages to backfill from msg #{from_msg_id}")
            return

        for msg in messages:
            if msg.message:
                msg.message = MessageCleaner.clean(msg.message, mode=filter_type, replacement=replacement_link)
            result = await self._send_with_retry(user_id, destination, msg)
            if not result["ok"]:
                logger.error(f"Backfill send failed: {result.get('detail')}")
            await asyncio.sleep(1)

        logger.info(f"Backfill complete: sent {len(messages)} messages from #{from_msg_id}")

    def _compute_dedup_key(self, message) -> str | None:
        parts = []
        msg_id = getattr(message, "id", None)
        chat_id = getattr(message, "chat_id", None)
        if msg_id and chat_id:
            parts.append(f"{chat_id}:{msg_id}")

        if hasattr(message, "media") and message.media:
            media_str = str(type(message.media).__name__)
            if hasattr(message.media, "photo") and message.media.photo:
                media_str += f":{message.media.photo.id}"
            elif hasattr(message.media, "document") and message.media.document:
                media_str += f":{message.media.document.id}"
            parts.append(media_str)

        if not parts:
            text = getattr(message, "message", "") or ""
            if text:
                parts.append(hashlib.md5(text.encode()).hexdigest()[:12])

        return "|".join(parts) if parts else None

    def _is_duplicate(self, pair_id: int, message) -> bool:
        key = self._compute_dedup_key(message)
        if not key:
            return False

        seen = self._dedup_seen[pair_id]
        if key in seen:
            logger.debug(f"Duplicate detected for Pair #{pair_id}: {key}")
            return True

        seen[key] = time.time()

        if len(seen) > DEDUP_CACHE_SIZE:
            oldest_keys = sorted(seen, key=seen.get)[:DEDUP_CACHE_SIZE // 4]
            for k in oldest_keys:
                del seen[k]

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
                wait_seconds = result.get("wait_seconds", 30)
                if wait_seconds > 300:
                    await self._notify_user(
                        user_id,
                        f"Pair #{pair_id or '?'}: Telegram rate limit ({wait_seconds}s). "
                        f"Too long to wait, message skipped."
                    )
                    return result

                await self._notify_user(
                    user_id,
                    f"Pair #{pair_id or '?'}: Telegram is rate limiting. "
                    f"Retrying in {wait_seconds}s... (attempt {attempt + 1}/{FLOOD_WAIT_MAX_RETRY})"
                )
                logger.info(f"FloodWait retry: sleeping {wait_seconds}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_seconds)
                continue

            return result

        return {"ok": False, "error": "max_retries", "detail": "Exceeded FloodWait retry limit"}

    async def _record_pair_error(self, pair_id: int, user_id: int, error_detail: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            new_count = await repo.increment_error_count(pair_id)

            if new_count >= MAX_ERRORS_BEFORE_DISABLE:
                await repo.deactivate_pair_as_error(pair_id)
                self._cancel_schedule_timer(pair_id)
                self.schedule_queue.pop(pair_id, None)
                await self._notify_user(
                    user_id,
                    f"Pair #{pair_id} auto-disabled after {new_count} consecutive errors.\n"
                    f"Last error: {error_detail}\n\n"
                    f"Re-activate it from My Pairs when the issue is resolved."
                )
                logger.warning(f"Pair #{pair_id} auto-disabled: {new_count} errors")
            elif new_count >= 3:
                await self._notify_user(
                    user_id,
                    f"Pair #{pair_id}: {new_count} consecutive errors.\n"
                    f"Last: {error_detail}\n"
                    f"Will auto-disable at {MAX_ERRORS_BEFORE_DISABLE} errors."
                )

    async def _handle_new_message(self, message, user_id):
        if not (message.message or message.media):
            return

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
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pairs = await repo.get_user_pairs(user_id)
            if not pairs:
                return

            main_msg = messages[0]
            try:
                chat = await main_msg.get_chat()
                chat_username = str(chat.username).lower() if chat and hasattr(chat, 'username') and chat.username else ""
                chat_id = str(main_msg.chat_id) if main_msg.chat_id else ""
            except Exception:
                chat_username = ""
                chat_id = str(main_msg.chat_id) if hasattr(main_msg, 'chat_id') and main_msg.chat_id else ""

            for p in pairs:
                if not p.is_active or p.status == "error":
                    continue

                source_identifier = str(p.source_id).lower().replace("@", "").strip()

                matched = (
                    (source_identifier == chat_username) or
                    (source_identifier in chat_id) or
                    (chat_id and source_identifier.replace("-100", "") == chat_id.replace("-100", ""))
                )

                if matched:
                    if self._is_duplicate(p.id, main_msg):
                        logger.info(f"Skipped duplicate for Pair #{p.id}")
                        continue

                    for msg in messages:
                        if msg.message:
                            msg.message = MessageCleaner.clean(
                                msg.message,
                                mode=p.filter_type,
                                replacement=p.replacement_link
                            )

                    if p.schedule_interval and p.schedule_interval > 0:
                        cached_bundle = self.media_cache.cache_bundle(p.id, messages)
                        self._enqueue_scheduled(p.id, user_id, p.destination_id, cached_bundle, p.schedule_interval)
                        logger.info(f"Queued message for Pair #{p.id} (next flush in {p.schedule_interval}m)")
                    else:
                        result = await self._send_with_retry(user_id, p.destination_id, messages, pair_id=p.id)
                        if not result["ok"]:
                            await self._record_pair_error(p.id, user_id, result.get("detail", "Unknown error"))

                    break

    def _enqueue_scheduled(self, pair_id: int, user_id: int, destination: str, messages, interval_minutes: int):
        if pair_id not in self.schedule_queue:
            self.schedule_queue[pair_id] = []

        self.schedule_queue[pair_id].append({
            "user_id": user_id,
            "destination": destination,
            "messages": messages,
            "queued_at": time.time()
        })

        if pair_id not in self.schedule_timers or self.schedule_timers[pair_id].done():
            self.schedule_timers[pair_id] = asyncio.create_task(
                self._flush_schedule(pair_id, interval_minutes)
            )

    async def _flush_schedule(self, pair_id: int, interval_minutes: int):
        await asyncio.sleep(interval_minutes * 60)

        queued_items = self.schedule_queue.pop(pair_id, [])
        if not queued_items:
            return

        from sqlalchemy import select as sa_select
        from data.models import RepostPair
        async with async_session() as db_session:
            result = await db_session.execute(
                sa_select(RepostPair).where(RepostPair.id == pair_id, RepostPair.is_active == True)
            )
            pair = result.scalar_one_or_none()
            if not pair:
                logger.info(f"Scheduled flush aborted for Pair #{pair_id}: pair inactive or deleted.")
                return

        for item in queued_items:
            result = await self._send_with_retry(
                item["user_id"], item["destination"], item["messages"], pair_id=pair_id
            )
            if not result["ok"]:
                await self._record_pair_error(pair_id, item["user_id"], result.get("detail", "Flush failed"))
                logger.error(f"Scheduled flush failed for Pair #{pair_id}: {result.get('detail')}")

        self.schedule_timers.pop(pair_id, None)
        self.media_cache.clear_pair(pair_id)

    def _cancel_schedule_timer(self, pair_id: int):
        timer = self.schedule_timers.pop(pair_id, None)
        if timer and not timer.done():
            timer.cancel()
        self.media_cache.clear_pair(pair_id)

    def cache_file_id(self, original_id: str, file_id: str):
        self.file_id_cache[original_id] = {
            "file_id": file_id,
            "cached_at": time.time()
        }

    def get_cached_file_id(self, original_id: str) -> str | None:
        entry = self.file_id_cache.get(original_id)
        if not entry:
            return None
        if time.time() - entry["cached_at"] > 86400:
            del self.file_id_cache[original_id]
            return None
        return entry["file_id"]

    async def recover_all_listeners(self):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            users_to_recover = await repo.get_all_active_users_with_pairs()

            for user_id in users_to_recover:
                try:
                    user = await repo.get_user(user_id)
                    session_path = self._get_session_path(user_id, user)
                    if session_path:
                        await self.telethon.start_listener(user_id, session_path, self._handle_new_message)
                except Exception as e:
                    logger.error(f"Recovery failed for {user_id}: {e}")
