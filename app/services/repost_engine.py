"""
SERVICES: REPOST ENGINE
The 'Nervous System' of the bot. Bridges Database, Logic, and Telethon.
"""
import logging
import asyncio
from app.services.engine_loops import run_backfill, flush_schedule_loop
from app.services.stats_service import get_pair_stats
from app.services.engine_utils import compute_dedup_key, send_with_retry, process_album_waiter
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
                if user_id not in self._active_listeners and user.session_string:
                    await self.telethon.start_listener(user_id, user.session_string, self._handle_new_message)
                    self._active_listeners.add(user_id)
                return True
        return False

    async def add_new_pair(self, user_id, source, destination, **kwargs):
        async with async_session() as ds:
            repo = UserRepository(ds)
            
            # Pass display names if present
            s_disp = kwargs.get('source_display')
            d_disp = kwargs.get('destination_display')
            
            new_p = await repo.add_repost_pair(user_id, source, destination, source_display=s_disp, destination_display=d_disp, **kwargs)
            user = await repo.get_user(user_id)
            if user_id not in self._active_listeners and user.session_string:
                await self.telethon.start_listener(user_id, user.session_string, self._handle_new_message)
                self._active_listeners.add(user_id)
        
        if kwargs.get('start_from_msg_id') and kwargs.get('schedule_interval', 0) > 0:
            task = asyncio.create_task(run_backfill(self, user_id, source, destination, kwargs['start_from_msg_id'], kwargs.get('filter_type', 1), kwargs.get('replacement_link'), kwargs['schedule_interval'], new_p.id))
            self.backfill_tasks[new_p.id] = task

    async def get_effective_stats(self, uid, pid): return await get_pair_stats(self, uid, pid)
    async def sync_pair_stats(self, uid, pid): return await self.get_effective_stats(uid, pid)
    async def _backfill_from_message(self, *args, **kwargs): return await run_backfill(self, *args, **kwargs)
    async def _flush_schedule(self, *args, **kwargs): return await flush_schedule_loop(self, *args, **kwargs)

    async def _send_with_retry(self, *args, **kwargs): return await send_with_retry(self, *args, **kwargs)

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
        cid = str(messages[0].chat_id)
        norm_cid = cid if cid.startswith("-100") else f"-100{cid}"
        async with async_session() as ds:
            pairs = await UserRepository(ds).get_user_pairs(user_id)
            for p in pairs:
                if not p.is_active or p.status == "error": continue
                
                src = str(p.source_id)
                
                # Rule 11: Dynamic Username Resolution for instant triggers
                # If it's not a pure number (with optional '-'), it must be a username/link
                if not src.replace("-", "").isdigit():
                    res = await self.telethon.resolve_entity(user_id, src)
                    if res and res.get("id"):
                        resolved_id = str(res["id"])
                        # Some resolved IDs might already include -100 depending on Telethon version
                        src = resolved_id if resolved_id.startswith("-100") else f"-100{resolved_id}"
                
                if norm_cid == (src if src.startswith("-100") else f"-100{src}"):
                    await self._process_matched_pair(p, user_id, messages)
                    break

    async def _process_matched_pair(self, p, user_id, messages):
        key = compute_dedup_key(messages[0])
        if key and key in self._dedup_seen.get(p.id, {}): return
        if key: 
            if p.id not in self._dedup_seen: self._dedup_seen[p.id] = {}
            self._dedup_seen[p.id][key] = 1

        from app.core.repost.logic import MessageCleaner
        for msg in messages:
            if msg.message: msg.message = MessageCleaner.clean(msg.message, mode=p.filter_type, replacement=p.replacement_link)

        if p.schedule_interval and p.schedule_interval > 0:
            bundle = self.media_cache.cache_bundle(p.id, messages)
            self._enqueue_scheduled(p.id, user_id, p.destination_id, bundle, p.schedule_interval)
        else: await self._send_with_retry(user_id, p.destination_id, messages, pair_id=p.id, is_protected=p.is_protected)

    def _enqueue_scheduled(self, pid, uid, dest, msgs, interval):
        if pid not in self.schedule_queue: self.schedule_queue[pid] = []
        self.schedule_queue[pid].append({"user_id": uid, "destination": dest, "messages": msgs})
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
                    await self.telethon.start_listener(uid, user.session_string, self._handle_new_message)
                    self._active_listeners.add(uid)
                pairs = await repo.get_user_pairs(uid)
                for p in pairs:
                    if p.is_active and p.status != "error" and p.start_from_msg_id and p.schedule_interval:
                        if p.id not in self.backfill_tasks or self.backfill_tasks[p.id].done():
                            self.backfill_tasks[p.id] = asyncio.create_task(run_backfill(self, uid, p.source_id, p.destination_id, p.start_from_msg_id, p.filter_type, p.replacement_link, p.schedule_interval, p.id))

    async def toggle_pair_recycling(self, uid, pid):
        async with async_session() as ds: return await UserRepository(ds).toggle_pair_loop(uid, pid)

    async def toggle_pair_protection(self, uid, pid):
        async with async_session() as ds: return await UserRepository(ds).toggle_pair_protection(uid, pid)

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
