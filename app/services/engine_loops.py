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

            messages = await service.telethon.fetch_messages_from(user_id, source, current_id, limit=50)
            if not messages:
                if await _handle_cycle_end(service, user_id, pair, pair_id):
                    current_id = 0
                    continue
                break

            for msg in messages:
                if not msg: continue
                # Ghost Check
                if not await _is_msg_valid(service, user_id, source, msg, pair_id):
                    current_id = msg.id
                    continue

                stop, current_id = await _process_single_backfill(service, user_id, destination, msg, pair_id, filter_type, replacement_link, interval_minutes)
                if stop: break
                
        except rpcbaseerrors.UnauthorizedError:
            await service._handle_fatal_error(user_id, pair_id, "Session revoked.")
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in backfill {pair_id}: {e}")
            await asyncio.sleep(60)

async def _process_single_backfill(service, user_id, destination, msg, pair_id, filter_type, replacement_link, interval_minutes):
    """Rule 8: Helper to flatten run_backfill."""
    result = await _deliver_backfill(service, user_id, destination, msg, pair_id, filter_type, replacement_link, interval_minutes)
    if result["ok"]:
        async with async_session() as ds:
            await UserRepository(ds).update_pair_start_id(pair_id, msg.id + 1)
        await asyncio.sleep(interval_minutes * 60)
        return False, msg.id
    
    err = result.get("error", "unknown")
    if err in ["flood_wait", "timeout", "max_retries"]:
        logger.warning(f"Transient error {err} on Pair #{pair_id}. Sleeping 60s.")
        await asyncio.sleep(60)
        return True, msg.id # Stop the batch loop to retry later
    
    await service._handle_fatal_error(user_id, pair_id, f"Backfill failed: {err}")
    return True, msg.id # Fatal error

def _is_pair_active(pair, pair_id):
    if not pair or not pair.is_active or pair.status == "error":
        return False
    return True

async def _check_3day_alert(service, user_id, pair, current_id, total, interval):
    remaining = total - current_id
    if remaining > 0 and interval > 0:
        if (remaining * interval) <= 4320 and not pair.alerted_3d:
            await service._notify_user(user_id, f"⚠️ <b>Low Inventory Alert</b>\nPair #{pair.id} has < 3 days remaining.")
            async with async_session() as ds:
                await UserRepository(ds).update_alert_3d(pair.id, True)

async def _handle_cycle_end(service, user_id, pair, pair_id):
    await service._notify_user(user_id, f"🎉 <b>Cycle Complete</b>\nPair #{pair_id} finished.")
    if pair.loop_history:
        async with async_session() as ds:
            repo = UserRepository(ds)
            await repo.update_pair_start_id(pair_id, 1)
            await repo.update_alert_3d(pair_id, False)
        await asyncio.sleep(15 * 60)
        return True
    await asyncio.sleep(60)
    return False

async def _is_msg_valid(service, user_id, source, msg, pair_id):
    try:
        fresh = await service.telethon.get_message(user_id, source, msg.id)
        if not fresh:
            async with async_session() as ds:
                await UserRepository(ds).update_pair_start_id(pair_id, msg.id + 1)
            return False
        return True
    except Exception:
        return False

async def _deliver_backfill(service, user_id, dest, msg, pair_id, f_type, repl, interval):
    from app.core.repost.logic import MessageCleaner
    if msg.message:
        msg.message = MessageCleaner.clean(msg.message, mode=f_type, replacement=repl)
        
    result = await service._send_with_retry(user_id, dest, msg, pair_id=pair_id)
    if result["ok"]:
        service.next_post_info[pair_id] = {
            "time": time.time() + (interval * 60),
            "preview": (msg.message[:13] + "...") if msg.message else "[Media]"
        }
    return result

async def flush_schedule_loop(service, pair_id, interval_minutes):
    """Refactored schedule flusher."""
    await asyncio.sleep(interval_minutes * 60)
    queued = service.schedule_queue.pop(pair_id, [])
    if not queued: return

    for item in queued:
        await service._send_with_retry(item["user_id"], item["destination"], item["messages"], pair_id=pair_id)
    
    service.schedule_timers.pop(pair_id, None)
    service.next_post_info.pop(pair_id, None)
    service.media_cache.clear_pair(pair_id)
