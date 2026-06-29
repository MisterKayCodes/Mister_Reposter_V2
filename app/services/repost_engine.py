"""
SERVICES: REPOST ENGINE
The 'Nervous System' of the bot. Bridges Database, Logic, and Telethon.
"""
from datetime import datetime
import logging
import asyncio
from app.services.engine_loops import run_backfill, flush_schedule_loop
from app.services.stats_service import get_pair_stats
from app.services.engine_utils import (
    compute_dedup_key, send_with_retry, process_album_waiter,
    MessageClassifier, MessageClassification
)
from app.services.autonomic import HeartbeatMonitor
from app.services.media_cache import MediaCache
from app.providers.telethon_client import TelethonProvider
from app.data.database import async_session
from app.data.repository import UserRepository
from app.core.config import config

logger = logging.getLogger(__name__)

class RepostService:
    def __init__(self):
        self.telethon = TelethonProvider(config.API_ID, config.API_HASH)
        self.album_cache, self.schedule_queue = {}, {}
        self.schedule_timers, self.backfill_tasks = {}, {}
        self.media_cache = MediaCache()
        self._active_listeners = set()
        self.next_post_info, self.last_errors = {}, {}
        self._dedup_seen = {}
        self.failed_media_lock = {} # Rule 11: Failed Media Lock (Pair ID -> Set of Msg IDs)
        self._resolved_cache = {}
        self.heartbeat = HeartbeatMonitor(self)

    def set_bot(self, bot): self._bot = bot

    async def _notify_user(self, user_id, text):
        if self._bot:
            try:
                await self._bot.send_message(user_id, text, parse_mode="HTML")
            except Exception as e:
                err_msg = str(e).lower()
                logger.error(f"Notify failed {user_id}: {e}")
                if "deactivated" in err_msg or "blocked" in err_msg:
                    # Rule 11: Real-time Dead Account Cleanup
                    logger.critical(f"User {user_id} account is dead or bot was blocked. Stopping all loops for this user.")
                    asyncio.create_task(self._handle_fatal_error(user_id, 0, "Account Deactivated/Blocked"))

    async def _handle_fatal_error(self, user_id, pair_id, reason):
        await self.deactivate_pair(user_id, pair_id)
        await self.telethon.stop_listener(user_id)
        self._active_listeners.discard(user_id)
        await self._notify_user(user_id, f"⚠️ {reason} Bot stopped.")

    async def _handle_pair_error(self, user_id, pair_id, reason):
        """Rule 11: Granular deactivation for bad data (nuked channels)."""
        async with async_session() as ds:
            await UserRepository(ds).deactivate_pair_as_error(pair_id)
        self._cancel_schedule_timer(pair_id)
        self._cancel_backfill_task(pair_id)
        logger.error(f"Pair #{pair_id} deactivated due to fatal error: {reason}")
        await self._notify_user(user_id, f"🚫 <b>A Pair was Deactivated</b>\nFatal error: {reason}\n\nPlease check if the destination channel still exists.")

    async def register_user(self, user_id, username):
        async with async_session() as ds:
            return await UserRepository(ds).create_or_update_user(user_id, username)

    async def is_admin(self, user_id: int) -> bool:
        async with async_session() as ds:
            user = await UserRepository(ds).get_user(user_id)
            return user.is_admin if user else False

    async def is_premium(self, user_id: int) -> bool:
        async with async_session() as ds:
            user = await UserRepository(ds).get_user(user_id)
            if not user: return False
            if not user.is_premium: return False
            if user.premium_until and user.premium_until < datetime.utcnow():
                # Self-healing: revoke expired premium
                await UserRepository(ds).grant_premium(user_id, months=0) 
                # ^ Need a separate 'revoke' method or just handle it here
                return False
            return True

    async def user_has_session(self, user_id):
        async with async_session() as ds:
            user = await UserRepository(ds).get_user(user_id)
            return bool(user and user.session_string)

    async def get_user_pairs(self, user_id):
        async with async_session() as ds:
            return await UserRepository(ds).get_user_pairs(user_id)

    async def delete_all_pairs(self, user_id):
        async with async_session() as ds:
            repo = UserRepository(ds)
            pairs = await repo.get_user_pairs(user_id)
            for p in pairs:
                self._cancel_schedule_timer(p.id)
                self._cancel_backfill_task(p.id)
            return await repo.delete_all_pairs(user_id)

    async def delete_single_pair(self, user_id, pair_id):
        self._cancel_schedule_timer(pair_id)
        self._cancel_backfill_task(pair_id)
        async with async_session() as ds:
            return await UserRepository(ds).delete_pair_by_id(user_id, pair_id)

    async def delete_user(self, user_id: int) -> bool:
        """Rule 11: Nuclear option for account cleanup."""
        pairs = await self.get_user_pairs(user_id)
        for p in pairs:
            self._cancel_schedule_timer(p.id)
            self._cancel_backfill_task(p.id)
        
        await self.telethon.stop_listener(user_id)
        self._active_listeners.discard(user_id)
        
        async with async_session() as ds:
            return await UserRepository(ds).delete_user(user_id)

    async def deactivate_all_pairs(self, user_id):
        async with async_session() as ds:
            repo = UserRepository(ds)
            pairs = await repo.get_user_pairs(user_id)
            for p in pairs:
                self._cancel_schedule_timer(p.id)
                self._cancel_backfill_task(p.id)
                await repo.deactivate_pair(user_id, p.id)
            return True

    async def deactivate_pair(self, user_id, pair_id):
        self._cancel_schedule_timer(pair_id)
        self._cancel_backfill_task(pair_id)
        async with async_session() as ds:
            return await UserRepository(ds).deactivate_pair(user_id, pair_id)

    async def activate_pair(self, user_id, pair_id):
        async with async_session() as ds:
            repo = UserRepository(ds)
            if await repo.activate_pair(user_id, pair_id):
                user = await repo.get_user(user_id)
                if user_id not in self._active_listeners:
                    try:
                        await self.telethon.start_listener(user_id, user.session_string, self._handle_new_message)
                        self._active_listeners.add(user_id)
                    except Exception as e:
                        logger.error(f"Failed to start listener for {user_id}: {e}")
                return True
        return False

    async def add_new_pair(self, user_id, source, destination, **kwargs):
        async with async_session() as ds:
            repo = UserRepository(ds)
            new_p = await repo.add_repost_pair(user_id, source, destination, **kwargs)
            user = await repo.get_user(user_id)
            if user_id not in self._active_listeners:
                try:
                    await self.telethon.start_listener(user_id, user.session_string, self._handle_new_message)
                    self._active_listeners.add(user_id)
                except Exception as e:
                    logger.error(f"Failed to start listener for {user_id}: {e}")
        
        if kwargs.get('start_from_msg_id') and kwargs.get('schedule_interval', 0) > 0:
            task = asyncio.create_task(run_backfill(self, user_id, source, destination, kwargs['start_from_msg_id'], kwargs.get('filter_type', 1), kwargs.get('replacement_link'), kwargs['schedule_interval'], new_p.id))
            self.backfill_tasks[new_p.id] = task

    async def get_effective_stats(self, uid, pid): return await get_pair_stats(self, uid, pid)
    async def sync_pair_stats(self, uid, pid): return await self.get_effective_stats(uid, pid)
    async def _backfill_from_message(self, *args, **kwargs): return await run_backfill(self, *args, **kwargs)
    async def _flush_schedule(self, *args, **kwargs): return await flush_schedule_loop(self, *args, **kwargs)

    async def _send_with_retry(self, *args, **kwargs): return await send_with_retry(self, *args, **kwargs)

    def _get_progress_notifier(self, user_id):
        """Creates a closure that manages a single status message in Telegram."""
        status_msg = [None] # Use list to allow closure modification
        async def notifier(text):
            if not self._bot: return
            try:
                if status_msg[0] is None:
                    msg = await self._bot.send_message(user_id, f"🔄 {text}")
                    status_msg[0] = msg.message_id
                else:
                    await self._bot.edit_message_text(f"🔄 {text}", user_id, status_msg[0])
            except Exception as e:
                logger.error(f"Notifier failed: {e}")
        return notifier

    async def _handle_new_message(self, message, user_id):
        if not (message.message or message.media): return
        if message.grouped_id:
            gid = message.grouped_id
            if gid not in self.album_cache:
                self.album_cache[gid] = []
                asyncio.create_task(process_album_waiter(self, gid, user_id))
            self.album_cache[gid].append(message)
        else: await self._execute_repost(user_id, [message])

    async def _execute_repost(self, user_id, messages):
        # 1. Standardize Incoming ID
        raw_cid = messages[0].chat_id
        # Telegram IDs are integers. We'll use the absolute value of the short ID for matching.
        norm_cid = abs(raw_cid)
        if str(raw_cid).startswith("-100"):
             norm_cid = int(str(raw_cid).replace("-100", ""))
        
        incoming_username = getattr(messages[0].chat, 'username', '')
        logger.info(f"👂 [Instant] Triage: Heard msg from {raw_cid} (Normalized: {norm_cid}, Username: @{incoming_username})")
        
        async with async_session() as ds:
            pairs = await UserRepository(ds).get_user_pairs(user_id)
            for p in pairs:
                if not p.is_active or p.status == "error": continue
                
                # 2. Standardize Database Source ID
                db_src_id = None
                is_username_match = False
                try:
                    src_str = str(p.source_id).replace("-100", "").replace("-", "")
                    if not src_str.isdigit():
                        # Check resolution cache first
                        if p.source_id not in self._resolved_cache:
                            logger.info(f"🔄 [Instant] Warming up cache for string source: {p.source_id}")
                            try:
                                src_val = str(p.source_id)
                                # Private invite links (t.me/+hash) can't be resolved directly
                                # Use join_channel which handles the CheckChatInviteRequest fallback
                                if "+" in src_val or "joinchat" in src_val:
                                    import re as _re
                                    hash_match = _re.search(r'[+/]([A-Za-z0-9_-]+)$', src_val)
                                    if hash_match:
                                        invite_hash = hash_match.group(1)
                                        result = await self.telethon.join_channel(user_id, invite_hash)
                                        if result and result.get("id"):
                                            self._resolved_cache[p.source_id] = abs(int(str(result["id"]).replace("-100", "")))
                                            logger.info(f"✅ [Instant] Invite resolved {p.source_id} -> {self._resolved_cache[p.source_id]}")
                                        else:
                                            self._resolved_cache[p.source_id] = -1
                                    else:
                                        self._resolved_cache[p.source_id] = -1
                                else:
                                    entity_info = await self.telethon.resolve_entity(user_id, src_val)
                                    if entity_info and entity_info.get("id"):
                                        self._resolved_cache[p.source_id] = abs(int(str(entity_info["id"]).replace("-100", "")))
                                        logger.info(f"✅ [Instant] Cached {p.source_id} -> {self._resolved_cache[p.source_id]}")
                                    else:
                                        self._resolved_cache[p.source_id] = -1
                                        logger.warning(f"⚠️ [Instant] Could not resolve {p.source_id}")
                            except Exception as e:
                                self._resolved_cache[p.source_id] = -1
                                logger.error(f"❌ [Instant] Cache warmup failed for {p.source_id}: {e}")

                        resolved_db_id = self._resolved_cache.get(p.source_id)
                        if resolved_db_id and resolved_db_id != -1 and resolved_db_id == norm_cid:
                            logger.info(f"🚀 [Instant] Cached Resolve Match Found! Routing to Destination! Pair #{p.id}")
                            await self._process_matched_pair(p, user_id, messages)
                            continue

                        # Fallback to string username match
                        db_username = str(p.source_id).lower().strip("@").split("/")[-1]
                        msg_username = str(incoming_username).lower()
                        logger.info(f"🔍 [Instant] Checking Username match for Pair #{p.id}: DB='{db_username}' vs Incoming='{msg_username}'")
                        if db_username == msg_username and db_username != "":
                            is_username_match = True
                            logger.info(f"✅ [Instant] Username Match True!")
                        else:
                            continue
                    else:
                        db_src_id = abs(int(src_str))
                        logger.info(f"🔍 [Instant] Checking Numeric ID match for Pair #{p.id}: DB={db_src_id} vs Incoming={norm_cid}")
                except Exception as e:
                    logger.error(f"❌ [Instant] Error parsing source ID for Pair #{p.id}: {e}")
                    continue

                # 3. The "Perfect Match"
                if is_username_match or (db_src_id is not None and norm_cid == db_src_id) or str(p.source_id) == str(raw_cid):
                    logger.info(f"🚀 [Instant] Perfect Match Found! Routing to Destination! Pair #{p.id} (Source: {p.source_id})")
                    await self._process_matched_pair(p, user_id, messages)
                    # Note: We DON'T break here, in case one source feeds multiple destinations

    async def _process_matched_pair(self, p, user_id, messages):
        # 1. Triage Phase (Pre-check)
        locked_ids = self.failed_media_lock.get(p.id, set())
        if any(m.id in locked_ids for m in messages):
            logger.warning(f"FML Skip: Pair #{p.id} msg {[m.id for m in messages]} is LOCKED.")
            return

        classification = MessageClassifier.classify(messages)
        if classification == MessageClassification.BROKEN:
            logger.error(f"Classification: BROKEN. Locking msg {[m.id for m in messages]} for Pair #{p.id}")
            if p.id not in self.failed_media_lock: self.failed_media_lock[p.id] = set()
            for m in messages: self.failed_media_lock[p.id].add(m.id)
            return
            
        is_protected = p.is_protected
        if classification == MessageClassification.PROTECTED:
            logger.info(f"Classification: PROTECTED. Auto-enabling bypass for Pair #{p.id}")
            is_protected = True

        if classification == MessageClassification.HEAVY:
            logger.info(f"Classification: HEAVY. Resource intensive post detected for Pair #{p.id}")

        key = compute_dedup_key(messages[0])
        if key and key in self._dedup_seen.get(p.id, {}): return
        if key: 
            if p.id not in self._dedup_seen: self._dedup_seen[p.id] = {}
            self._dedup_seen[p.id][key] = 1

        from app.core.repost.logic import MessageCleaner
        for msg in messages:
            # We always clean, because Mode 3 needs to ADD text even if it's missing
            msg.message = MessageCleaner.clean(msg.message or "", mode=p.filter_type, replacement=p.replacement_link)

        if p.schedule_interval and p.schedule_interval > 0:
            msg_ids = [m.id for m in messages]
            self._enqueue_scheduled(p.id, user_id, p.source_id, p.destination_id, msg_ids, p.schedule_interval)
            
            # UI: Show the timer immediately
            self.next_post_info[p.id] = {
                "time": time.time() + (p.schedule_interval * 60),
                "preview": "Queueing Live Post..."
            }
        notifier = self._get_progress_notifier(user_id) if is_protected else None
        if notifier: await notifier("Detecting protected content. Starting surgical bypass...")
        
        await self._send_with_retry(user_id, p.destination_id, messages, pair_id=p.id, is_protected=is_protected, progress_callback=notifier)

    def _enqueue_scheduled(self, pid, uid, source, dest, msg_ids, interval):
        if pid not in self.schedule_queue: self.schedule_queue[pid] = []
        self.schedule_queue[pid].append({
            "user_id": uid, 
            "source_id": source,
            "destination": dest, 
            "msg_ids": msg_ids
        })
        if pid not in self.schedule_timers or self.schedule_timers[pid].done():
            self.schedule_timers[pid] = asyncio.create_task(flush_schedule_loop(self, pid, interval))

    def _cancel_schedule_timer(self, pid):
        t = self.schedule_timers.pop(pid, None)
        if t and not t.done(): t.cancel()
        self.media_cache.clear_pair(pid)

    def _cancel_backfill_task(self, pid):
        t = self.backfill_tasks.pop(pid, None)
        if t and not t.done(): t.cancel()

    async def recover_all_listeners(self):
        async with async_session() as ds:
            repo = UserRepository(ds)
            uids = await repo.get_all_active_users_with_pairs()
            for uid in uids:
                user = await repo.get_user(uid)
                if uid not in self._active_listeners and user.session_string:
                    try:
                        await self.telethon.start_listener(uid, user.session_string, self._handle_new_message)
                        self._active_listeners.add(uid)
                    except Exception as e:
                        logger.error(f"Startup: Failed to start listener for {uid}: {e}")
                pairs = await repo.get_user_pairs(uid)
                for p in pairs:
                    if p.is_active and p.status != "error" and p.start_from_msg_id and p.schedule_interval:
                        if p.id not in self.backfill_tasks or self.backfill_tasks[p.id].done():
                            self.backfill_tasks[p.id] = asyncio.create_task(run_backfill(self, uid, p.source_id, p.destination_id, p.start_from_msg_id, p.filter_type, p.replacement_link, p.schedule_interval, p.id))

    async def toggle_pair_recycling(self, uid, pid):
        async with async_session() as ds: return await UserRepository(ds).toggle_pair_loop(uid, pid)

    async def toggle_pair_protection(self, uid, pid):
        async with async_session() as ds: return await UserRepository(ds).toggle_pair_protection(uid, pid)

    async def force_repost_once(self, user_id: int, pair_id: int) -> bool:
        """Rule 11: Manually triggers the next post in the backfill sequence."""
        from app.services.engine_loops import _deliver_backfill
        async with async_session() as ds:
            repo = UserRepository(ds)
            pair = await repo.get_pair_by_id(pair_id)
            if not pair or pair.user_id != user_id or not pair.start_from_msg_id:
                return False
            
            # Fetch the specific message
            msg = await self.telethon.get_message(user_id, pair.source_id, pair.start_from_msg_id)
            if not msg:
                return False
                
            # Deliver
            result = await _deliver_backfill(
                self, user_id, pair.destination_id, msg, pair_id, 
                pair.filter_type, pair.replacement_link, pair.schedule_interval or 0,
                is_protected=pair.is_protected
            )
            
            if result["ok"]:
                # Advance pointer
                await repo.update_pair_start_id(pair_id, msg.id + 1)
                return True
            return False

    async def update_pair(self, user_id: int, pair_id: int, interval: int = None, filter_type: int = None, replacement: str = None) -> bool:
        """Live-edit a pair's settings without recreating it."""
        async with async_session() as ds:
            repo = UserRepository(ds)
            pair = await repo.get_pair_by_id(pair_id)
            if not pair or pair.user_id != user_id:
                return False
            if interval is not None:
                pair.schedule_interval = interval
            if filter_type is not None:
                pair.filter_type = filter_type
            if replacement is not None:
                pair.replacement_link = replacement
            await ds.commit()
            return True

    async def get_all_pairs(self) -> list:
        """Admin: returns all pairs from all users for the control panel."""
        async with async_session() as ds:
            return await UserRepository(ds).get_all_pairs()

    async def get_system_setting(self, key: str, default: str = None) -> str:
        async with async_session() as ds:
            return await UserRepository(ds).get_setting(key, default)

    async def set_system_setting(self, key: str, value: str):
        async with async_session() as ds:
            return await UserRepository(ds).set_setting(key, value)
