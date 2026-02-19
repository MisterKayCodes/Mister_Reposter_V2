"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
"""
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest

logger = logging.getLogger(__name__)

class TelethonProvider:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients = {}

    async def validate_session(self, session_data) -> bool:
        try:
            async with TelegramClient(session_data, self.api_id, self.api_hash) as client:
                return await asyncio.wait_for(client.is_user_authorized(), timeout=10)
        except Exception as e:
            logger.error(f"Telethon Validation Error: {e}")
            return False

    async def start_listener(self, user_id: int, session_data, callback):
        # Rule 1: Idempotency - Don't double-start
        if user_id in self.active_clients and self.active_clients[user_id].is_connected():
            logger.info(f"Eyes already open for User {user_id}")
            return

        try:
            client = TelegramClient(session_data, self.api_id, self.api_hash)
            
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
            err = str(e).lower()
            if "already" in err or "participant" in err:
                try:
                    result = await client(CheckChatInviteRequest(invite_hash))
                    chat = getattr(result, "chat", None)
                    if chat:
                        return {"id": chat.id, "title": getattr(chat, "title", "")}
                except: pass
                return {"id": None, "title": "already_joined"}
            return None

    async def resolve_entity(self, user_id: int, identifier: str) -> dict | None:
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected(): return None

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

    
    async def fetch_messages_from(self, user_id: int, source_id: str, from_msg_id: int, limit: int = 1):
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected(): return []

        try:
            target = int(source_id) if str(source_id).replace("-", "").isdigit() else source_id
            
            # Mister, we change 'min_id' to 'offset_id' and set 'reverse=True'
            # This forces Telethon to start at 19 and look FORWARD to 20, 21...
            # instead of starting at the newest and looking back.
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


    async def send_message(self, user_id: int, destination: str | int, message: any) -> dict:
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected():
            return {"ok": False, "error": "disconnected"}

        try:
            target = int(destination) if str(destination).replace("-", "").isdigit() else destination
            
            # Mister, if the engine sends a list of messages (an album), 
            # we use send_file with the list of media.
            if isinstance(message, list):
                sent = await client.send_file(target, [m.media for m in message if m.media], caption=message[0].message)
            else:
                sent = await client.send_message(target, message)
                
            return {"ok": True, "message": sent}
        except FloodWaitError as e:
            return {"ok": False, "error": "flood_wait", "wait_seconds": e.seconds}
        except Exception as e:
            logger.error(f"Telethon send error: {e}")
            return {"ok": False, "error": "exception", "detail": str(e)}

    
    
    async def stop_listener(self, user_id: int):
        client = self.active_clients.pop(user_id, None)
        if client:
            try:
                await client.disconnect()
                return True
            except: pass
        return False


