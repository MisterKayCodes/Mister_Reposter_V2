"""
SERVICES: ENGINE UTILS
Helper functions for deduplication, album processing, and delivery retries.
"""
import hashlib
import time
import logging
import asyncio

logger = logging.getLogger(__name__)

class MessageClassification:
    SAFE = "safe"
    HEAVY = "heavy"
    PROTECTED = "protected"
    BROKEN = "broken"

class MessageClassifier:
    @staticmethod
    def classify(message) -> str:
        """Rule 11: Triage phase before any network or disk activity."""
        if not message: return MessageClassification.BROKEN
        
        # 1. Handle Albums (list of messages)
        msgs = message if isinstance(message, list) else [message]
        
        is_protected = False
        is_heavy = False
        is_broken = False
        
        for m in msgs:
            if not m:
                is_broken = True
                continue
            # Check for basic availability
            if not (getattr(m, 'message', None) or getattr(m, 'media', None)):
                is_broken = True
                continue
                
            # Check for protection (noforward)
            if getattr(m, 'noforward', False):
                is_protected = True
                
            # Check media properties
            media = getattr(m, 'media', None)
            if media:
                # Self-destructing media
                if hasattr(media, 'ttl_seconds') and media.ttl_seconds:
                    is_broken = True
                
                # Size check
                size = 0
                if hasattr(media, 'document') and media.document:
                    size = media.document.size
                
                if size > 50 * 1024 * 1024: # Increased to 50MB for 'Heavy'
                    is_heavy = True
        
        if is_broken: return MessageClassification.BROKEN
        if is_protected: return MessageClassification.PROTECTED
        if is_heavy: return MessageClassification.HEAVY
        return MessageClassification.SAFE


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

async def send_with_retry(service, user_id, destination, message, pair_id=None, is_protected=False, progress_callback=None):
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
        result = await service.telethon.send_message(user_id, destination, message, pair_id=pair_id, is_protected=is_protected, progress_callback=progress_callback)
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
                detail = str(result.get("detail", "")).lower()
                # Rule 11: Failed Media Lock - Detect 'landmine' messages
                if any(x in detail for x in ["media_invalid", "file_reference", "media_empty"]):
                    if not hasattr(service, 'failed_media_lock'): service.failed_media_lock = {}
                    if pair_id not in service.failed_media_lock: service.failed_media_lock[pair_id] = set()
                    
                    m_list = message if isinstance(message, list) else [message]
                    for m in m_list: service.failed_media_lock[pair_id].add(m.id)
                    
                    logger.critical(f"FML (Failed Media Lock): Pair #{pair_id} locked msg ids {[m.id for m in m_list]} due to: {detail}")
                    return {"ok": False, "error": "broken_media", "error_type": "fatal"}

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
