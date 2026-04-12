"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
"""
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, FileReferenceExpiredError, MediaIdInvalidError
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest, GetHistoryRequest
from telethon.tl.functions.channels import JoinChannelRequest
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

    # Checking if our 'Passport' (the session) is still valid. 
    # We try to talk to Telegram and see if they recognize us. 
    # If they say 'Yes', we're good to go!
    async def validate_session(self, session_data) -> bool:
        session_obj = self._get_session(session_data)
        try:
            async with TelegramClient(session_obj, self.api_id, self.api_hash) as client:
                return await asyncio.wait_for(client.is_user_authorized(), timeout=30)
        except Exception as e:
            logger.error(f"Telethon Validation Error: {e}")
            return False

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
                        return
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

    async def resolve_entity(self, user_id: int, identifier: str) -> dict | None:
        if not await self._ensure_connected(user_id): return None
        client = self.active_clients.get(user_id)

        try:
            # Rule 6: Robust Entity Resolution
            target = identifier
            if str(identifier).replace("-", "").isdigit():
                target = int(identifier)
            
            entity = await client.get_entity(target)
            return {
                "id": entity.id,
                "title": getattr(entity, "title", getattr(entity, "username", "Unknown")),
            }
        except Exception as e:
            logger.error(f"Failed to resolve '{identifier}': {e}")
            return None

    
    # This is our 'Retrieval' service. We go into a channel and pull out 
    # specific messages starting from a certain point (the offset).
    # Since we use 'reverse=True', it's like reading a book from a specific page 
    # forward towards the end.
    async def fetch_messages_from(self, user_id: int, source_id: str, from_msg_id: int, limit: int = 1):
        if not await self._ensure_connected(user_id): return []
        client = self.active_clients.get(user_id)

        try:
            # Resolve target once to avoid Peer errors
            target = source_id
            if str(source_id).replace("-", "").isdigit():
                target = int(source_id)
            
            # Fetch the actual entity to 'warm up' the cache and avoid Peer errors
            target = await client.get_entity(target)
            
            messages = await client.get_messages(
                target, 
                offset_id=from_msg_id, 
                limit=limit, 
                reverse=True
            )
            return list(messages) if messages else []
        except Exception as e:
            logger.error(f"Fetch failed for {source_id}: {e}")
            return []

    # This is our 'Freshness Check'. We ask Telegram if a specific message 
    # still exists and hasn't been nuked by the original owner.
    async def get_message(self, user_id: int, source_id: str | int, msg_id: int):
        if not await self._ensure_connected(user_id): return None
        client = self.active_clients.get(user_id)
        try:
            target = int(source_id) if str(source_id).replace("-", "").isdigit() else source_id
            # We ask for a specific ID. If it's gone, Telegram returns None.
            return await client.get_messages(target, ids=msg_id)
        except Exception as e:
            logger.error(f"Refresh failed for {source_id} msg {msg_id}: {e}")
            return None

    async def get_total_messages(self, user_id: int, source_id: str) -> int:
        if not await self._ensure_connected(user_id): return -1
        client = self.active_clients.get(user_id)
        try:
            target = int(source_id) if str(source_id).replace("-", "").isdigit() else source_id
            
            # Senior Move: Use the low-level GetHistoryRequest for 100% accurate count
            # This bypasses any local caching issues in the client.
            result = await client(GetHistoryRequest(
                peer=target,
                offset_id=0,
                offset_date=None,
                add_offset=0,
                limit=0,
                max_id=0,
                min_id=0,
                hash=0
            ))
            return getattr(result, "count", 0)
        except Exception as e:
            logger.error(f"Failed to get message count for {source_id}: {e}")
            return -1


    # This is our 'Delivery' service. We take a message and hand it over 
    # to the destination channel. If it's a list (an album), we handle it 
    # as a single 'package' of media files.
    async def send_message(self, user_id: int, destination: str | int, message: any) -> dict:
        if not await self._ensure_connected(user_id):
            return {"ok": False, "error": "disconnected"}
        client = self.active_clients.get(user_id)

        try:
            target = destination
            if str(destination).replace("-", "").isdigit():
                target = int(destination)
            
            # Senior Fix: Use get_entity for robust peer resolution (avoids 'Invalid Peer' on fresh starts)
            target = await client.get_entity(target)
            
            if isinstance(message, list):
                sent = await self._send_album(client, target, message)
            else:
                sent = await self._send_single(client, target, message)
                
            return {"ok": True, "message": sent}
        except (FileReferenceExpiredError, MediaIdInvalidError) as e:
            logger.warning(f"File reference expired for User {user_id}. Attempting refresh and retry...")
            # Second Chance: Re-fetch and retry once
            refreshed_msg = await self._refresh_media_references(client, message)
            if refreshed_msg:
                try:
                    if isinstance(refreshed_msg, list):
                        sent = await self._send_album(client, target, refreshed_msg)
                    else:
                        sent = await self._send_single(client, target, refreshed_msg)
                    return {"ok": True, "message": sent}
                except Exception as e2:
                    logger.error(f"Retry after refresh failed: {e2}")
                    return {"ok": False, "error": "retry_failed", "detail": str(e2)}
            return {"ok": False, "error": "refresh_failed", "detail": str(e)}
        except FloodWaitError as e:
            return {"ok": False, "error": "flood_wait", "wait_seconds": e.seconds}
        except Exception as e:
            logger.error(f"Telethon send error: {e}")
            return {"ok": False, "error": "exception", "detail": str(e)}

    async def _refresh_media_references(self, client, message):
        """Rule 11: Self-healing mechanism to avoid stale file IDs."""
        try:
            if isinstance(message, list):
                # For albums, we assume all messages in the list are from the same chat
                chat = await client.get_entity(message[0].peer_id)
                msg_ids = [m.id for m in message]
                new_msgs = await client.get_messages(chat, ids=msg_ids)
                # Keep the order consistent
                id_map = {m.id: m for m in new_msgs if m}
                return [id_map.get(m.id) for m in message if id_map.get(m.id)]
            else:
                chat = await client.get_entity(message.peer_id)
                new_msg = await client.get_messages(chat, ids=message.id)
                return new_msg
        except Exception as e:
            logger.error(f"Failed to refresh media references: {e}")
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
        if file_id:
            return await client.send_file(target, file_id, caption=getattr(message, "message", ""))
        return await client.send_message(target, message)

    
    
    async def stop_listener(self, user_id: int):
        client = self.active_clients.pop(user_id, None)
        if client:
            try:
                await client.disconnect()
                return True
            except Exception as e:
                logger.debug(f"Stop listener error for {user_id}: {e}")
        return False


