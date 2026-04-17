"""
SERVICES: ENGINE UTILS
Helper functions for deduplication, album processing, and delivery retries.
"""
import hashlib
import time
import logging
import asyncio

logger = logging.getLogger(__name__)

def compute_dedup_key(message) -> str | None:
    parts = []
    msg_id = getattr(message, "id", None)
    chat_id = getattr(message, "chat_id", None)
    if msg_id and chat_id: parts.append(f"{chat_id}:{msg_id}")

    media = getattr(message, "media", None)
    if media:
        m_type = type(media).__name__
        if hasattr(media, "photo") and media.photo:
            parts.append(f"{m_type}:{media.photo.id}")
        elif hasattr(media, "document") and media.document:
            parts.append(f"{m_type}:{media.document.id}")

    if not parts and getattr(message, "message", ""):
        parts.append(hashlib.md5(message.message.encode()).hexdigest()[:12])
    return "|".join(parts) if parts else None

async def send_with_retry(service, user_id, destination, message, pair_id=None, is_protected=False):
    from app.data.database import async_session
    from app.data.repository import UserRepository
    
    # Media caching logic simplified
    msg_list = message if isinstance(message, list) else [message]
    for m in msg_list:
        key = service.media_cache.extract_media_key(getattr(m, 'media', None))
        if key:
            cached_id = service.media_cache.get_file_id(key)
            if cached_id: m.cached_file_id = cached_id

    for attempt in range(4): # FLOOD_WAIT_MAX_RETRY + 1
        result = await service.telethon.send_message(user_id, destination, message, is_protected=is_protected)
        if result["ok"]:
            if pair_id:
                async with async_session() as ds:
                    await UserRepository(ds).reset_error_count(pair_id)
            return result
        
        if result.get("error_type") == "transient":
            wait = result.get("wait_seconds", 30)
            if wait > 300: return result
            await service._notify_user(user_id, f"Rate limited. Retrying in {wait}s...")
            await asyncio.sleep(wait)
            continue
            
        if result.get("error_type") == "fatal":
            if pair_id:
                asyncio.create_task(service._handle_pair_error(user_id, pair_id, result.get("detail", "Unknown fatal error")))
            return result
            
        return result
    return {"ok": False, "error": "max_retries", "error_type": "transient"}

async def process_album_waiter(service, gid, user_id):
    start_time = time.time()
    while True:
        items = service.album_cache.get(gid, [])
        if len(items) >= 10: break # MAX_ALBUM_ITEMS
        await asyncio.sleep(1.0)
        if len(items) == len(service.album_cache.get(gid, [])): break
        if time.time() - start_time > 30: break # MAX_ALBUM_WAIT
        
    messages = service.album_cache.pop(gid, [])
    if messages:
        messages.sort(key=lambda m: m.id)
        await service._execute_repost(user_id, messages)
