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
from telethon.errors import MessageIdInvalidError, rpcbaseerrors
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
MAX_ALBUM_WAIT = 30 # Senior Fix: 30s hard timeout for albums
MAX_ALBUM_ITEMS = 10 # Senior Fix: 10 items max per album


class RepostService:
    def __init__(self):
        self.telethon = TelethonProvider(
            config.API_ID,
            config.API_HASH
        )
        self.album_cache = {}
        self.schedule_queue = {}
        self.schedule_timers = {}
        self.backfill_tasks = {}
        self.media_cache = MediaCache()
        self.file_id_cache = {}
        self._dedup_seen = defaultdict(dict)
        self._bot = None
        # Rule 1: Tracking state to prevent duplicate listeners
        self._active_listeners = set()
        self.next_post_info = {}


    # Every conductor needs a baton. This connects our engine to the main bot interface
    # so we can send messages back to the users (like error alerts or status updates).
    def set_bot(self, bot):
        self._bot = bot

    # This is our 'Customer Service' department. If something goes wrong or we need 
    # to tell the user something, we use this to send them a direct message. 
    # We wrap it in a try-except block so that if the user has blocked the bot, 
    # the whole engine doesn't crash like a house of cards.
    async def _notify_user(self, user_id: int, text: str):
        """Rule 12: Handle notification errors explicitly."""
        if self._bot:
            try:
                await self._bot.send_message(user_id, text)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

    # Before we can do anything, we need to know if we have the 'keys' to the user's
    # Telegram account. We check for a session file on disk or a string in our database.
    # It's like checking if a driver has a valid license before letting them start the car.
    async def user_has_session(self, user_id: int) -> bool:
        # Senior Fix: Database is the single source of truth for paths
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            user = await repo.get_user(user_id)
            return bool(user and user.session_string)

    def _get_session_path(self, user_id: int, user=None) -> str | None:
        # Senior Fix: Rely on the database string which now stores the UUID path or string
        if user and user.session_string:
            return user.session_string
        return None

    # When a new user walks through the door, we need to add them to our ledger
    # so we can keep track of their pairs and settings later on.
    async def register_user(self, user_id: int, username: str):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            await repo.create_or_update_user(user_id, username)

    # This just pulls up the list of all 'Source -> Destination' connections
    # a specific user has created. It's like looking up a customer's order history.
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
                self._cancel_backfill_task(p.id)
                self.schedule_queue.pop(p.id, None)
                self._dedup_seen.pop(p.id, None)
            return await repo.delete_all_user_pairs(user_id)

    async def delete_single_pair(self, user_id: int, pair_id: int) -> bool:
        self._cancel_schedule_timer(pair_id)
        self._cancel_backfill_task(pair_id)
        self.schedule_queue.pop(pair_id, None)
        self._dedup_seen.pop(pair_id, None)
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            return await repo.delete_pair_by_id(user_id, pair_id)

    async def deactivate_pair(self, user_id: int, pair_id: int) -> bool:
        self._cancel_schedule_timer(pair_id)
        self._cancel_backfill_task(pair_id)
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

    # This is our 'Interpreter'. It takes a channel link or username and figures out
    # the actual numeric ID Telegram uses behind the scenes. If it's a private invite 
    # link, it'll even knock on the door (join) to get the ID.
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
            task = asyncio.create_task(
                self._backfill_from_message(
                    user_id, source, destination, start_from_msg_id, 
                    filter_type, replacement_link, schedule_interval, new_pair.id
                )
            )
            self.backfill_tasks[new_pair.id] = task
            
    async def get_effective_stats(self, user_id: int, pair_id: int):
        """The 'Brain' of the stats. One single place to calculate everything."""
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            pair = await repo.get_pair_by_id(pair_id)
            if not pair: return None
            
            # 1. Get the real-time total from TG (using the new GetHistoryRequest)
            total = await self.telethon.get_total_messages(user_id, pair.source_id)
            
            # 2. Update DB if we got a valid number
            if total >= 0:
                await repo.update_pair_total_posts(pair_id, total)
                pair.total_posts_source = total
            
            # 3. Handle anomalies (e.g. current > total)
            current = pair.start_from_msg_id or 1
            
            # Junior, if current > total, it means the channel has fewer posts 
            # than we think we've processed (maybe they deleted some). 
            # We cap remaining at 0.
            if total > 0 and current > total:
                remaining = 0 
            elif total > 0:
                remaining = max(0, total - current)
            else:
                remaining = 0
                
            time_left_min = remaining * (pair.schedule_interval or 0)
            
            return {
                "id": pair_id,
                "current": current,
                "total": total,
                "remaining": remaining,
                "time_left_min": time_left_min,
                "source": pair.source_id,
                "destination": pair.destination_id,
                "schedule": pair.schedule_interval,
                "is_active": pair.is_active,
                "next_post": self.next_post_info.get(pair_id)
            }

    async def sync_pair_stats(self, user_id: int, pair_id: int):
        """Wrapper for backward compatibility."""
        stats = await self.get_effective_stats(user_id, pair_id)
        return stats["total"] if stats else -1

    async def _backfill_from_message(self, user_id, source, destination, from_msg_id, filter_type, replacement_link, interval_minutes, pair_id):
        # Think of this like a bookmark in a long book. We're setting our initial position
        # just before the page we want to read, because our reader always skips the current 
        # page and goes to the next one. We use max(0, ...) to ensure we don't try to go
        # to a page number that doesn't exist (like page -1).
        current_id = max(0, from_msg_id - 1)
        
        # We'll give the system a few seconds to 'wake up' and settle before we start 
        # the marathon of fetching old messages.
        await asyncio.sleep(5) 
        
        while True:
            try:
                # First, we check if the channel has grown (new posts). 
                # It's like checking the total page count of a book that's still being written.
                total = await self.telethon.get_total_messages(user_id, source)
                if total >= 0:
                    async with async_session() as db_session:
                        repo = UserRepository(db_session)
                        await repo.update_pair_total_posts(pair_id, total)

                # If there's a 'live' message waiting (someone just posted), we let it 'cut the line'.
                # Backfilling history is a secondary priority compared to staying up-to-date with the present.
                if pair_id in self.schedule_queue and self.schedule_queue[pair_id]:
                    logger.info(f"Pair #{pair_id} has live messages queued. Pausing backfill for priority.")
                    await asyncio.sleep(60) 
                    continue

                # Before every fetch, we check if the 'boss' (the user) has turned off this pair
                # or if the pair has run into too many errors. No point running if the engine is off.
                async with async_session() as db_session:
                    repo = UserRepository(db_session)
                    pair = await repo.get_pair_by_id(pair_id)
                    if not pair or not pair.is_active or pair.status == "error":
                        logger.info(f"Backfill for Pair #{pair_id} stopped (not active/deleted).")
                        self.next_post_info.pop(pair_id, None)
                        break

                # Instead of asking for one message at a time (which is like walking to the store for a single egg),
                # we fetch a batch of 50. This is much kinder to the Telegram servers and faster for us.
                messages = await self.telethon.fetch_messages_from(user_id, source, current_id, limit=50)
                
                if not messages:
                    # If we've reached the very last page of the book, we wrap back to the beginning.
                    # It's a never-ending loop (recycling) to keep the channel active.
                    logger.info(f"Backfill for Pair #{pair_id} reached the end. Recycling to message #1.")
                    current_id = 0 # Next fetch will use offset_id=0, getting ID 1
                    async with async_session() as db_session:
                        repo = UserRepository(db_session)
                        await repo.update_pair_start_id(pair_id, 1)
                    continue


                # Now we process our bag of 50 messages one by one.
                for msg in messages:
                    if not msg:
                        continue # Sometimes Telegram has 'blank' spaces; we just skip them.

                    # --- THE SENIOR FIX: THE GUARDED GHOST CHECK ---
                    try:
                        fresh = await self.telethon.get_message(user_id, source, msg.id)
                        if not fresh:
                            logger.info(f"Ghost detected: Message {msg.id} was deleted. Skipping.")
                            current_id = msg.id
                            async with async_session() as db_session:
                                repo = UserRepository(db_session)
                                await repo.update_pair_start_id(pair_id, current_id + 1)
                            continue
                    except MessageIdInvalidError:
                        logger.info(f"Ghost detected (Invalid ID): Message {msg.id}. Skipping.")
                        current_id = msg.id
                        async with async_session() as db_session:
                            repo = UserRepository(db_session)
                            await repo.update_pair_start_id(pair_id, current_id + 1)
                        continue
                    except rpcbaseerrors.UnauthorizedError:
                        logger.critical(f"Session Revoked for User {user_id}! Stopping Pair #{pair_id}.")
                        await self.deactivate_pair(user_id, pair_id)
                        # Senior Fix: Kill the listener too! No zombie state allowed.
                        await self.telethon.stop_listener(user_id)
                        self._active_listeners.discard(user_id)
                    
                        await self._notify_user(user_id, "⚠️ Your Telegram session has been revoked. The bot has stopped all your active tasks.")
                        return # Exit the backfill loop entirely
                    except Exception as e:
                        logger.error(f"Unexpected error in Ghost Check for msg {msg.id}: {e}")
                        continue 
                    # ---------------------------------------------

                    # If the next message we found is way ahead of where we were (e.g., from ID 8 to ID 15),
                    # it means some messages were deleted. We note this 'jump' in the logs so we know why 
                    # there's a gap in the timeline.
                    if msg.id > current_id + 1:
                        logger.info(f"[Pair {pair_id}] Gap detected! Jumping from ID {current_id} to {msg.id}")

                    # If the user wants us to 'scrub' the text (remove links or swap @usernames), 
                    # we call our cleaning crew before sending it out.
                    if msg.message:
                        msg.message = MessageCleaner.clean(msg.message, mode=filter_type, replacement=replacement_link)

                    # We hand the message over to the delivery service.
                    result = await self._send_with_retry(user_id, destination, msg, pair_id=pair_id)
                
                    if result["ok"]:
                        # We've successfully processed this 'page'. We update our bookmark (current_id)
                        # and save it to the 'Vault' (database) so if the bot crashes, we know exactly 
                        # where to resume.
                        current_id = msg.id
                        async with async_session() as db_session:
                            repo = UserRepository(db_session)
                            # We save current_id + 1 because the next batch fetch should start AFTER this message.
                            await repo.update_pair_start_id(pair_id, current_id + 1)
                    
                        # We wait according to the user's schedule. This 'drip-feed' keeps the destination
                        # channel from looking like a bot is spamming a thousand posts in one second.
                        logger.info(f"Pair #{pair_id} posted msg {current_id}. Waiting {interval_minutes}m for next.")
                    
                        # Store info about the NEXT target
                        next_idx = messages.index(msg) + 1
                        preview = ""
                        if next_idx < len(messages):
                            next_msg = messages[next_idx]
                            if next_msg and next_msg.message:
                                preview = next_msg.message[:13] + "..." if len(next_msg.message) > 13 else next_msg.message
                        if not preview:
                            preview = "[Media/Unknown]"
                        
                        self.next_post_info[pair_id] = {
                            "time": time.time() + (interval_minutes * 60),
                            "preview": preview
                        }
                    
                        await asyncio.sleep(interval_minutes * 60)
                    else:
                        # If the delivery failed (e.g., we got kicked from the channel), we stop the operation
                        # for this pair to avoid making things worse.
                        logger.error(f"Backfill stopped on Pair #{pair_id} at msg {current_id} due to error.")
                        self.next_post_info.pop(pair_id, None)
                        return # Exit the function entirely
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in backfill loop for pair {pair_id}: {e}")
                await asyncio.sleep(60) # Wait before retrying to avoid spamming errors

        
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
        msg_list = message if isinstance(message, list) else [message]
        media_keys = {}
        for m in msg_list:
            key = self.media_cache.extract_media_key(getattr(m, 'media', None))
            if key:
                cached_id = self.media_cache.get_file_id(key)
                if cached_id:
                    m.cached_file_id = cached_id
                else:
                    media_keys[id(m)] = key

        for attempt in range(FLOOD_WAIT_MAX_RETRY + 1):
            result = await self.telethon.send_message(user_id, destination, message)

            if result["ok"]:
                if pair_id:
                    async with async_session() as db_session:
                        repo = UserRepository(db_session)
                        await repo.reset_error_count(pair_id)
                # Store new file ids
                sent_msg = result.get("message")
                if sent_msg:
                    sent_list = sent_msg if isinstance(sent_msg, list) else [sent_msg]
                    for idx, o_msg in enumerate(msg_list):
                        if id(o_msg) in media_keys and idx < len(sent_list):
                            sent_media = getattr(sent_list[idx], 'media', None)
                            if sent_media:
                                self.media_cache.store_file_id(media_keys[id(o_msg)], sent_media)
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
                self._cancel_backfill_task(pair_id)
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
        # Implementation of the "Waiter" timeout (Priority 3)
        start_time = time.time()
        while True:
            items = self.album_cache.get(gid, [])
            count = len(items)
            
            # Senior Rule: Cap at 10 items (Telegram limit)
            if count >= MAX_ALBUM_ITEMS:
                logger.info(f"Album {gid} reached max capacity ({MAX_ALBUM_ITEMS}). Processing now.")
                break
                
            await asyncio.sleep(1.0)
            
            # Rule: If count hasn't changed, or we've waited too long, break
            if count == len(self.album_cache.get(gid, [])):
                break
            
            if time.time() - start_time > MAX_ALBUM_WAIT:
                logger.warning(f"Album {gid} timed out after {MAX_ALBUM_WAIT}s. Processing partial album.")
                break
                
        messages = self.album_cache.pop(gid, [])
        if messages:
            # Sort messages by ID to ensure sequence (Telethon might receive out-of-order)
            messages.sort(key=lambda m: m.id)
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
                    # Smart Detection: Update total posts for this pair
                    total = await self.telethon.get_total_messages(user_id, p.source_id)
                    async with async_session() as db_session:
                        repo = UserRepository(db_session)
                        await repo.update_pair_total_posts(p.id, total)
                        
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
        
        # Set next post info if not exists
        if pair_id not in self.next_post_info:
            first_m = messages[0] if isinstance(messages, list) else messages
            preview = ""
            if getattr(first_m, "message", None):
                preview = first_m.message[:13] + "..." if len(first_m.message) > 13 else first_m.message
            if not preview:
                preview = "[Media/Unknown]"
            self.next_post_info[pair_id] = {
                "time": time.time() + (interval_minutes * 60),
                "preview": preview
            }
            
        if pair_id not in self.schedule_timers or self.schedule_timers[pair_id].done():
            self.schedule_timers[pair_id] = asyncio.create_task(self._flush_schedule(pair_id, interval_minutes))

    async def _flush_schedule(self, pair_id: int, interval_minutes: int):
        await asyncio.sleep(interval_minutes * 60)
        queued = self.schedule_queue.pop(pair_id, [])
        if not queued: return

        for item in queued:
            await self._send_with_retry(item["user_id"], item["destination"], item["messages"], pair_id=pair_id)
        
        self.schedule_timers.pop(pair_id, None)
        self.next_post_info.pop(pair_id, None)
        self.media_cache.clear_pair(pair_id)

    def _cancel_schedule_timer(self, pair_id: int):
        timer = self.schedule_timers.pop(pair_id, None)
        if timer and not timer.done(): timer.cancel()
        self.media_cache.clear_pair(pair_id)

    def _cancel_backfill_task(self, pair_id: int):
        task = self.backfill_tasks.pop(pair_id, None)
        if task and not task.done(): task.cancel()

    async def recover_all_listeners(self):
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            users_ids = await repo.get_all_active_users_with_pairs()
            for uid in users_ids:
                if uid not in self._active_listeners:
                    user = await repo.get_user(uid)
                    path = self._get_session_path(uid, user)
                    if path:
                        await self.telethon.start_listener(uid, path, self._handle_new_message)
                        self._active_listeners.add(uid)
                
                # Rule 11: Also recover backfill tasks for any scheduled pair
                pairs = await repo.get_user_pairs(uid)
                for p in pairs:
                    if not p.is_active or p.status == "error": continue
                    if p.start_from_msg_id and p.schedule_interval and p.schedule_interval > 0:
                        if p.id not in self.backfill_tasks or self.backfill_tasks[p.id].done():
                            logger.info(f"Recovering Backfill for Pair #{p.id} (msg {p.start_from_msg_id})")
                            task = asyncio.create_task(
                                self._backfill_from_message(
                                    uid, p.source_id, p.destination_id, p.start_from_msg_id,
                                    p.filter_type, p.replacement_link, p.schedule_interval, p.id
                                )
                            )
                            self.backfill_tasks[p.id] = task