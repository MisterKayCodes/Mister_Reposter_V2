"""
SERVICES: ENGINE LOOPS
Extracted background loops to meet file length requirements. (Rule 3)
"""
import asyncio
import logging
import time
from app.data.database import async_session
from app.data.repository import UserRepository
from telethon.errors import rpcbaseerrors
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def run_backfill(service, user_id, source, destination, from_msg_id, filter_type, replacement_link, interval_minutes, pair_id):
    """The main backfill loop extracted from RepostService."""
    current_id = max(0, from_msg_id - 1)
    await asyncio.sleep(5) 
    
    while True:
        try:
            total = await service.telethon.get_total_messages(user_id, source)
            if total < 0:
                logger.warning(f"Backfill Pair #{pair_id}: TG error. Sleeping 60s.")
                await asyncio.sleep(60)
                continue

            async with async_session() as db_session:
                repo = UserRepository(db_session)
                await repo.update_pair_total_posts(pair_id, total)
                pair = await repo.get_pair_by_id(pair_id)
                if not _is_pair_active(pair, pair_id):
                    service.next_post_info.pop(pair_id, None)
                    break

            await _check_3day_alert(service, user_id, pair, current_id, total, interval_minutes)

            # Rule 11: Persistent Timer - Respect the cooldown across restarts
            now = datetime.utcnow()
            if pair.next_allowed_post_at and pair.next_allowed_post_at > now:
                wait_seconds = (pair.next_allowed_post_at - now).total_seconds()
                logger.info(f"Pair #{pair_id}: Respecting persistent timer. Sleeping {int(wait_seconds)}s.")
                # Update UI info even while sleeping
                service.next_post_info[pair_id] = {
                    "time": time.time() + wait_seconds,
                    "preview": "Timer Sync..."
                }
                await asyncio.sleep(wait_seconds)

            messages = await service.telethon.fetch_messages_from(user_id, source, current_id, limit=50)
            if not messages:
                if await _handle_cycle_end(service, user_id, pair, pair_id):
                    current_id = 0
                    continue
                break

            batch_advanced = False
            for msg in messages:
                if not msg: continue
                ghost_status = await _check_ghost(service, user_id, source, msg, pair_id)
                if ghost_status == "ghost":
                    logger.info(f"Pair #{pair_id}: Skipping ghost msg #{msg.id}")
                    current_id = msg.id
                    batch_advanced = True
                    continue
                if ghost_status == "error":
                    break

                stop, current_id = await _process_single_backfill(service, user_id, destination, msg, pair_id, filter_type, replacement_link, interval_minutes, is_protected=getattr(pair, "is_protected", False))
                batch_advanced = True
                if stop: break

            if batch_advanced:
                async with async_session() as ds:
                    await UserRepository(ds).update_pair_start_id(pair_id, current_id + 1)
                
        except rpcbaseerrors.UnauthorizedError:
            await service._handle_fatal_error(user_id, pair_id, "Session revoked.")
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in backfill {pair_id}: {e}")
            await asyncio.sleep(60)

async def _process_single_backfill(service, user_id, destination, msg, pair_id, filter_type, replacement_link, interval_minutes, is_protected: bool = False):
    """Rule 8: Helper to flatten run_backfill."""
    from app.utils.protection import AntiBanGuard
    
    # 1. Throttle if needed to avoid bans
    await AntiBanGuard.throttle(pair_id, is_protected=is_protected)
    
    result = await _deliver_backfill(service, user_id, destination, msg, pair_id, filter_type, replacement_link, interval_minutes, is_protected=is_protected)
    if result["ok"]:
        async with async_session() as ds:
            await UserRepository(ds).update_pair_start_id(pair_id, msg.id + 1)
        await asyncio.sleep(interval_minutes * 60)
        return False, msg.id
    
    err = result.get("error", "unknown")
    detail = result.get("detail", "")
    full_err = f"{err} - {detail}" if detail else err

    if err in ["flood_wait", "timeout", "max_retries"]:
        logger.warning(f"Transient error {err} on Pair #{pair_id}. Sleeping 60s.")
        await asyncio.sleep(60)
        return True, msg.id # Stop the batch loop to retry later
    
    await service._handle_pair_error(user_id, pair_id, f"Backfill failed: {full_err}")
    return True, msg.id # Fatal error

def _is_pair_active(pair, pair_id):
    if not pair or not pair.is_active or pair.status == "error":
        return False
    return True

async def _check_3day_alert(service, user_id, pair, current_id, total, interval):
    remaining = total - current_id
    if remaining > 0 and interval > 0:
        if (remaining * interval) <= 4320 and not pair.alerted_3d:
            await service._notify_user(user_id, f"⚠️ <b>Low Inventory Alert</b>\nOne of your Pairs has < 3 days remaining.")
            async with async_session() as ds:
                await UserRepository(ds).update_alert_3d(pair.id, True)

async def _handle_cycle_end(service, user_id, pair, pair_id):
    if pair.loop_history:
        await service._notify_user(user_id, f"🎉 <b>Cycle Complete</b>\nOne of your Pairs has finished! Looping back to start...")
        async with async_session() as ds:
            repo = UserRepository(ds)
            await repo.update_pair_start_id(pair_id, 1)
            await repo.update_alert_3d(pair_id, False)
        await asyncio.sleep(15 * 60)
        return True
    
    # Rule 11: Resilient Watcher - Don't die, just watch.
    import random
    if not getattr(pair, "alerted_caught_up", False):
        await service._notify_user(user_id, f"✅ <b>Caught Up</b>\nPair #{pair_id} has reached the latest content. Switching to <b>Sentinel Mode</b>.")
        async with async_session() as ds:
            await UserRepository(ds).update_caught_up_alert(pair_id, True)

    # 5m + 1m random Jitter
    jitter = random.randint(1, 60)
    wait_time = (5 * 60) + jitter
    service.next_post_info[pair_id] = {
        "time": time.time() + wait_time,
        "preview": "🔍 Watching for new posts..."
    }
    await asyncio.sleep(wait_time)
    return True

async def _check_ghost(service, user_id, source, msg, pair_id):
    """Returns 'ok', 'ghost', or 'error'."""
    try:
        fresh = await service.telethon.get_message(user_id, source, msg.id)
        if not fresh:
            return "ghost"
        return "ok"
    except Exception as e:
        logger.warning(f"Ghost check failed for msg #{msg.id}: {e}")
        return "error"

async def _deliver_backfill(service, user_id, dest, msg, pair_id, f_type, repl, interval, is_protected: bool = False):
    from app.core.repost.logic import MessageCleaner
    if msg.message:
        msg.message = MessageCleaner.clean(msg.message, mode=f_type, replacement=repl)
        
    result = await service._send_with_retry(user_id, dest, msg, pair_id=pair_id, is_protected=is_protected)
    if result["ok"]:
        next_dt = datetime.utcnow() + timedelta(minutes=interval)
        async with async_session() as ds:
            await UserRepository(ds).update_next_post_time(pair_id, next_dt)
        
        service.next_post_info[pair_id] = {
            "time": time.time() + (interval * 60),
            "preview": (msg.message[:13] + "...") if msg.message else "[Media]"
        }
    else:
        # Prevent "0m" stuck state in UI
        service.next_post_info.pop(pair_id, None)
    return result

async def flush_schedule_loop(service, pair_id, interval_minutes):
    """Refactored schedule flusher with Stateless 'Fresh Fetch'."""
    # 1. Update UI Timer for the sleep duration
    service.next_post_info[pair_id] = {
        "time": time.time() + (interval_minutes * 60),
        "preview": "⏳ Pending in Queue..."
    }
    await asyncio.sleep(interval_minutes * 60)
    
    queued = service.schedule_queue.pop(pair_id, [])
    if not queued: return

    from app.data.database import async_session
    from app.data.repository import UserRepository
    from app.core.repost.logic import MessageCleaner
    
    async with async_session() as ds:
        repo = UserRepository(ds)
        pair = await repo.get_pair_by_id(pair_id)
        if not _is_pair_active(pair, pair_id): return
        is_protected = getattr(pair, "is_protected", False)
        f_type = pair.filter_type
        repl = pair.replacement_link

    for item in queued:
        # Rule: Fresh Fetch - Retrieve fresh attributes and file references 1s before sending
        logger.info(f"Fresh Fetch: Re-retrieving msg_ids {item['msg_ids']} for Pair #{pair_id}")
        fresh_msgs = await service.telethon.get_messages(item["user_id"], item["source_id"], item["msg_ids"])
        if not fresh_msgs: continue
        
        # Ensure it's a list for album consistency
        if not isinstance(fresh_msgs, list): fresh_msgs = [fresh_msgs]
        
        # Re-apply cleaning (in case original was changed or we want absolute freshness)
        for m in fresh_msgs:
            if m and m.message:
                m.message = MessageCleaner.clean(m.message, mode=f_type, replacement=repl)

        # Send
        result = await service._send_with_retry(item["user_id"], item["destination"], fresh_msgs, pair_id=pair_id, is_protected=is_protected)
        
        # Handover Protocol: Update pointer in DB to avoid Watchdog double-processing
        if result["ok"]:
            last_id = max([m.id for m in fresh_msgs if m])
            async with async_session() as ds:
                await UserRepository(ds).update_pair_start_id(pair_id, last_id + 1)
                await UserRepository(ds).update_caught_up_alert(pair_id, True) # Mark as caught up to prevent spam
    
    service.schedule_timers.pop(pair_id, None)
    service.next_post_info.pop(pair_id, None)
    service.media_cache.clear_pair(pair_id)
