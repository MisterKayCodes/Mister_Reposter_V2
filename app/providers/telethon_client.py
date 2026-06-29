"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
"""
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, FileReferenceExpiredError, MediaInvalidError, PeerIdInvalidError, rpcbaseerrors
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest, GetHistoryRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

class TelethonProvider:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients = {}

    async def _ensure_connected(self, user_id: int) -> bool:
        """The Safe-Start Reconnection Logic."""
        client = self.active_clients.get(user_id)
        if not client: return False
        
        if not client.is_connected():
            logger.warning(f"Connection lost for User {user_id}. Reconnecting...")
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    logger.critical(f"Session revoked for User {user_id}!")
                    return False
            except Exception as e:
                logger.error(f"Failed to reconnect User {user_id}: {e}")
                return False
        return True

    def _get_session(self, session_data):
        if isinstance(session_data, str) and not session_data.endswith('.session'):
            return StringSession(session_data)
        return session_data

    async def validate_session(self, session_data) -> tuple[bool, int | None, str | None]:
        """Validates session and returns (is_valid, user_id, username)."""
        session_obj = self._get_session(session_data)
        try:
            async with TelegramClient(session_obj, self.api_id, self.api_hash) as client:
                is_auth = await asyncio.wait_for(client.is_user_authorized(), timeout=30)
                if not is_auth:
                    return False, None, None
                
                me = await client.get_me()
                return True, me.id, me.username
        except Exception as e:
            logger.error(f"Telethon Validation Error: {e}")
            return False, None, None

    async def start_listener(self, user_id: int, session_data, callback):
        # Rule 1: Idempotency - Don't double-start
        if user_id in self.active_clients and self.active_clients[user_id].is_connected():
            logger.info(f"Eyes already open for User {user_id}")
            return

        try:
            session_obj = self._get_session(session_data)
            client = TelegramClient(session_obj, self.api_id, self.api_hash)
            
            for attempt in range(2):
                try:
                    await client.connect()
                    if not await client.is_user_authorized():
                        logger.warning(f"User {user_id} unauthorized.")
                        await client.disconnect()
                        raise PermissionError(f"Session for User {user_id} is unauthorized.")
                    break
                except (OSError, asyncio.TimeoutError) as e:
                    if attempt == 1: raise e
                    await asyncio.sleep(2)

            self.active_clients[user_id] = client

            @client.on(events.NewMessage())
            async def handler(event):
                if event and event.message:
                    # Rule 3: Single Responsibility - Just pass the signal back
                    await callback(event.message, user_id)

            asyncio.create_task(
                client.run_until_disconnected(), 
                name=f"eyes_{user_id}"
            )
            logger.info(f"Eyes wide open for User {user_id}")

        except Exception as e:
            logger.error(f"Failed to open Eyes for User {user_id}: {e}")
            self.active_clients.pop(user_id, None)
            raise  # Re-raise so callers (autonomic) can detect fatal errors

    async def join_channel(self, user_id: int, invite_hash: str) -> dict | None:
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected(): return None

        try:
            result = await client(ImportChatInviteRequest(invite_hash))
            chat = result.chats[0] if result.chats else None
            if chat:
                return {"id": chat.id, "title": getattr(chat, "title", "")}
            return None
        except Exception as e:
            return await self._handle_join_error(client, invite_hash, e)

    async def _handle_join_error(self, client, invite_hash, e):
        """Rule 8: Move complex error handling to a helper."""
        err = str(e).lower()
        if "already" not in err and "participant" not in err:
            logger.error(f"Join failed for {invite_hash}: {e}")
            return None
            
        try:
            result = await client(CheckChatInviteRequest(invite_hash))
            chat = getattr(result, "chat", None)
            if chat:
                return {"id": chat.id, "title": getattr(chat, "title", "")}
        except Exception as e2:
            logger.warning(f"Fallback check failed for {invite_hash}: {e2}")
        return {"id": None, "title": "already_joined"}

    async def _get_entity_safe(self, client, identifier):
        """Rule 6: Robust Entity Resolution with Cache Warm-up for StringSessions"""
        try:
            return await client.get_entity(identifier)
        except ValueError as e:
            if "Could not find the input entity" in str(e) or "Cannot find any entity" in str(e):
                logger.warning(f"Entity {identifier} not in cache. Warming up dialogs...")
                try:
                    await client.get_dialogs(limit=200) # Fetch recent dialogs to build memory cache
                    return await client.get_entity(identifier)
                except Exception as e2:
                    raise Exception(f"Failed to find entity {identifier} even after cache warm-up.")
            raise e

    async def resolve_entity(self, user_id: int, identifier: str) -> dict | None:
        if not await self._ensure_connected(user_id): return None
        client = self.active_clients.get(user_id)

        try:
            # Rule 6: Robust Entity Resolution
            target = identifier
            if str(identifier).replace("-", "").isdigit():
                target = int(identifier)
            
            entity = await self._get_entity_safe(client, target)
            return {
                "id": entity.id,
                "title": getattr(entity, "title", getattr(entity, "username", "Unknown")),
            }
        except Exception as e:
            logger.error(f"Failed to resolve '{identifier}': {e}")
            return None

    async def fetch_messages_from(self, user_id: int, source_id: str, from_msg_id: int, limit: int = 1):
        if not await self._ensure_connected(user_id): return []
        client = self.active_clients.get(user_id)

        try:
            target = source_id
            if str(source_id).replace("-", "").isdigit():
                target = int(source_id)
            target = await self._get_entity_safe(client, target)
            messages = await client.get_messages(target, offset_id=from_msg_id, limit=limit, reverse=True)
            return list(messages) if messages else []
        except Exception as e:
            logger.error(f"Fetch failed for {source_id}: {e}")
            return []

    async def get_message(self, user_id: int, source_id: str | int, msg_id: int):
        if not await self._ensure_connected(user_id): return None
        client = self.active_clients.get(user_id)
        try:
            target = int(source_id) if str(source_id).replace("-", "").isdigit() else source_id
            try: target = await self._get_entity_safe(client, target)
            except Exception: pass
            return await client.get_messages(target, ids=msg_id)
        except Exception as e:
            logger.error(f"Refresh failed for {source_id} msg {msg_id}: {e}")
            return None

    async def get_total_messages(self, user_id: int, source_id: str) -> int:
        if not await self._ensure_connected(user_id): return -1
        client = self.active_clients.get(user_id)
        try:
            target = int(source_id) if str(source_id).replace("-", "").isdigit() else source_id
            try: target = await self._get_entity_safe(client, target)
            except Exception: pass
            result = await client(GetHistoryRequest(peer=target, offset_id=0, offset_date=None, add_offset=0, limit=0, max_id=0, min_id=0, hash=0))
            return getattr(result, "count", 0)
        except Exception as e:
            logger.error(f"Failed to get message count for {source_id}: {e}")
            return -1

    async def send_message(self, user_id: int, destination: str | int, message: any, pair_id: int = None, is_protected: bool = False, progress_callback=None) -> dict:
        if not await self._ensure_connected(user_id): return {"ok": False, "error": "disconnected"}
        client = self.active_clients.get(user_id)
        
        # DEBUG: Verify flag flow
        logger.info(f"[DEBUG] Telethon send_message called for Pair #{pair_id}. Protected Mode: {is_protected}")
        
        try:
            target = destination
            if str(destination).replace("-", "").isdigit(): target = int(destination)
            try: target = await client.get_input_entity(target)
            except Exception: target = await self._get_entity_safe(client, target)

            if is_protected:
                return await self._download_and_upload(client, target, message, progress_callback=progress_callback)

            if isinstance(message, list): sent = await self._send_album(client, target, message)
            else: sent = await self._send_single(client, target, message)
            return {"ok": True, "message": sent}
        except (FileReferenceExpiredError, MediaInvalidError, PeerIdInvalidError) as e:
            refreshed_msg = await self._refresh_media_references(client, message)
            if refreshed_msg:
                try:
                    if isinstance(refreshed_msg, list): sent = await self._send_album(client, target, refreshed_msg)
                    else: sent = await self._send_single(client, target, refreshed_msg)
                    return {"ok": True, "message": sent}
                except Exception as e2:
                    return {"ok": False, "error": "retry_failed", "error_type": "fatal" if isinstance(e2, (PeerIdInvalidError, rpcbaseerrors.ForbiddenError)) else "retryable", "detail": str(e2)}
            return {"ok": False, "error": "refresh_failed", "error_type": "fatal", "detail": str(e)}
        except Exception as e:
            is_fatal = isinstance(e, (rpcbaseerrors.UnauthorizedError, rpcbaseerrors.ForbiddenError))
            return {"ok": False, "error": "exception", "error_type": "fatal" if is_fatal else "retryable", "detail": str(e)}

    async def _download_and_upload(self, client, target, message, progress_callback=None):
        """Bypasses content protection by physically downloading then uploading (preserving metadata)."""
        import os
        from app.utils.protection import AntiBanGuard
        
        # Rule 6: Safety First - Create temp dirs
        temp_dir = "scratch/temp_media"
        thumb_dir = "scratch/temp_thumbs"
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)
        
        try:
            # We only handle single messages for protected mode for now (albums are rare in protected)
            if isinstance(message, list): message = message[0]
            
            if not getattr(message, "media", None):
                # If no media, just send as text
                sent = await client.send_message(target, message.message)
                return {"ok": True, "message": sent}

            # 1. Extract Metadata (Attributes)
            attrs = []
            supports_streaming = False
            if hasattr(message.media, 'document') and message.media.document:
                for attr in message.media.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        # Preserve dimensions and duration
                        attrs.append(DocumentAttributeVideo(
                            duration=attr.duration,
                            w=attr.w,
                            h=attr.h,
                            supports_streaming=True
                        ))
                        supports_streaming = True
                    elif isinstance(attr, DocumentAttributeFilename):
                        # Rule: Preserve original filename as requested by USER
                        attrs.append(DocumentAttributeFilename(file_name=attr.file_name))

            # 2. Download Media and Thumbnail
            logger.info(f"Protected Transfer: Downloading media from {message.id}...")
            path = await client.download_media(message, file=temp_dir)
            
            thumb_path = None
            if hasattr(message, 'thumb') or (hasattr(message.media, 'document') and message.media.document.thumbs):
                logger.debug(f"Protected Transfer: Downloading thumbnail for msg {message.id}...")
                thumb_path = await client.download_media(message, thumb=-1, file=thumb_dir)

            if not path or not os.path.exists(path):
                return {"ok": False, "error": "download_failed"}

            # 3. Add Jitter to look human
            if progress_callback: await progress_callback("📥 Download Complete. Preparing surgical transfer...")
            await AntiBanGuard.human_jitter(base_seconds=5)
            
            # 4. Upload to destination with preserved metadata
            if progress_callback: await progress_callback("📤 Surgical Transfer: Uploading to destination...")
            logger.info(f"Protected Transfer: Uploading {os.path.basename(path)} to destination...")
            sent = await client.send_file(
                target, 
                path, 
                caption=message.message,
                thumb=thumb_path,
                attributes=attrs,
                supports_streaming=supports_streaming
            )

            # 5. Clean up immediately to save VPS space
            if os.path.exists(path): os.remove(path)
            if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
            
            logger.info(f"Protected Transfer: SUCCESS. File {os.path.basename(path)} posted to destination.")
            if progress_callback: await progress_callback("✅ Transfer Successful. Media posted.")
            return {"ok": True, "message": sent}

        except Exception as e:
            logger.error(f"Protected Transfer Exception: {e}")
            return {"ok": False, "error": str(e)}

    async def _refresh_media_references(self, client, message):
        """Rule 11: The Surgical Healing Protocol - gets fresh references from source."""
        try:
            # 1. Determine the source peer reliably
            sample = message[0] if isinstance(message, list) else message
            peer = sample.peer_id
            
            # 2. Safety Check: If we don't have a peer, we can't refresh
            if not peer: return None
            
            # 3. Fresh Fetch: Use get_entity_safe to ensure we can reach the source
            try:
                chat = await self._get_entity_safe(client, peer)
            except Exception as e:
                logger.warning(f"Surgical Healing: Could not resolve peer {peer} for refresh: {e}")
                return None
                
            # 4. Pull fresh copies of the messages (and their file references)
            if isinstance(message, list):
                msg_ids = [m.id for m in message]
                new_msgs = await client.get_messages(chat, ids=msg_ids)
                # Map them back to the original list order
                id_map = {m.id: m for m in new_msgs if m}
                return [id_map.get(m.id) for m in message if id_map.get(m.id)]
            else:
                return await client.get_messages(chat, ids=message.id)
        except Exception as e:
            logger.error(f"Surgical Healing Failure: {e}")
            return None

    async def _send_album(self, client, target, messages):
        media_list = []
        for m in messages:
            file_id = getattr(m, "cached_file_id", None) or getattr(m, "media", None)
            if file_id: media_list.append(file_id)
        if not media_list: raise Exception("empty_album")
        return await client.send_file(target, media_list, caption=getattr(messages[0], "message", ""))

    async def _send_single(self, client, target, message):
        file_id = getattr(message, "cached_file_id", None)
        # Rule: Never 'Forward' if we want to change the caption.
        # We pass the media and the (possibly cleaned) message text separately.
        return await client.send_message(target, message.message, file=file_id or message.media)

    async def stop_listener(self, user_id: int):
        client = self.active_clients.pop(user_id, None)
        if client:
            try: await client.disconnect(); return True
            except Exception: pass
        return False
