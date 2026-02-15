"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
Pure communication, no logic allowed.
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
        if user_id in self.active_clients:
            client = self.active_clients[user_id]
            try:
                if client.is_connected():
                    return
                else:
                    logger.info(f"Re-opening closed eyes for User {user_id}")
                    await self.stop_listener(user_id)
            except Exception:
                del self.active_clients[user_id]

        try:
            client = TelegramClient(session_data, self.api_id, self.api_hash)
            await client.start()
            self.active_clients[user_id] = client

            @client.on(events.NewMessage())
            async def handler(event):
                await callback(event.message, user_id)

            asyncio.create_task(client.run_until_disconnected())
            logger.info(f"Eyes wide open for User {user_id}")

        except Exception as e:
            logger.error(f"Failed to open Eyes for User {user_id}: {e}")
            if user_id in self.active_clients:
                del self.active_clients[user_id]

    async def send_message(self, user_id: int, destination: str, message) -> dict:
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected():
            return {"ok": False, "error": "no_client", "detail": "No active client"}

        try:
            if destination.replace('-', '').isdigit():
                target = int(destination)
            else:
                target = destination

            if isinstance(message, list):
                files = [m.media for m in message if m.media]
                text = next((m.text for m in message if m.text), "")

                if files:
                    result = await client.send_file(target, files, caption=text)
                else:
                    result = await client.send_message(target, message=text)
            else:
                result = await client.send_message(target, message)

            logger.info(f"Successful blink to {destination}")
            sent_id = None
            if hasattr(result, "id"):
                sent_id = result.id
            elif isinstance(result, list) and result:
                sent_id = result[0].id if hasattr(result[0], "id") else None
            return {"ok": True, "sent_id": sent_id}
        except FloodWaitError as e:
            wait_seconds = e.seconds
            logger.warning(f"FloodWait: must wait {wait_seconds}s before sending to {destination}")
            return {"ok": False, "error": "flood_wait", "wait_seconds": wait_seconds, "detail": f"Rate limited for {wait_seconds}s"}
        except Exception as e:
            logger.error(f"Blink failed: {e}")
            return {"ok": False, "error": "send_error", "detail": str(e)}

    async def join_channel(self, user_id: int, invite_hash: str) -> dict | None:
        """Joins a private channel via invite hash. Returns the chat entity or None."""
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected():
            logger.warning(f"Cannot join channel: no active client for {user_id}")
            return None

        try:
            result = await client(ImportChatInviteRequest(invite_hash))
            chat = result.chats[0] if result.chats else None
            if chat:
                logger.info(f"Joined private channel via invite for User {user_id}: {chat.id}")
                return {"id": chat.id, "title": getattr(chat, "title", "")}
            return None
        except Exception as e:
            error_msg = str(e)
            if "already" in error_msg.lower() or "USER_ALREADY_PARTICIPANT" in error_msg:
                try:
                    result = await client(CheckChatInviteRequest(invite_hash))
                    chat = getattr(result, "chat", None)
                    if chat:
                        return {"id": chat.id, "title": getattr(chat, "title", "")}
                except Exception:
                    pass
                logger.info(f"User {user_id} already in channel from invite")
                return {"id": None, "title": "already_joined"}
            logger.error(f"Failed to join channel for User {user_id}: {e}")
            return None

    async def resolve_entity(self, user_id: int, identifier: str) -> dict | None:
        """Resolves a username or numeric ID to a Telegram entity."""
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected():
            return None

        try:
            if identifier.replace("-", "").isdigit():
                entity = await client.get_entity(int(identifier))
            else:
                entity = await client.get_entity(identifier)
            return {
                "id": entity.id,
                "title": getattr(entity, "title", getattr(entity, "username", "")),
            }
        except Exception as e:
            logger.error(f"Failed to resolve entity '{identifier}': {e}")
            return None

    async def fetch_messages_from(self, user_id: int, source_id: str, from_msg_id: int, limit: int = 100):
        """Fetches messages from a channel starting from a specific message ID."""
        client = self.active_clients.get(user_id)
        if not client or not client.is_connected():
            return []

        try:
            if source_id.replace("-", "").isdigit():
                entity = int(source_id)
            else:
                entity = source_id

            messages = await client.get_messages(
                entity, min_id=from_msg_id - 1, limit=limit
            )
            return list(reversed(messages)) if messages else []
        except Exception as e:
            logger.error(f"Failed to fetch messages from {source_id}: {e}")
            return []

    async def stop_listener(self, user_id: int):
        client = self.active_clients.get(user_id)
        if client:
            try:
                logger.info(f"Closing Eyes for User {user_id}...")
                await client.disconnect()
                await asyncio.sleep(0.2)
                if user_id in self.active_clients:
                    del self.active_clients[user_id]
                return True
            except Exception as e:
                logger.error(f"Error while closing eyes for {user_id}: {e}")
        return False
