"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
Pure communication, no logic allowed.
"""
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

class TelethonProvider:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients = {}

    async def validate_session(self, session_data) -> bool:
        """Isolated check for session validity."""
        try:
            async with TelegramClient(session_data, self.api_id, self.api_hash) as client:
                return await asyncio.wait_for(client.is_user_authorized(), timeout=10)
        except Exception as e:
            logger.error(f"Telethon Validation Error: {e}")
            return False

    async def start_listener(self, user_id: int, session_data, callback):
        """Starts a global listener for the user. Matches are handled in the Service."""
        if user_id in self.active_clients:
            return

        client = TelegramClient(session_data, self.api_id, self.api_hash)
        await client.start()
        self.active_clients[user_id] = client 

        @client.on(events.NewMessage()) # Listen to ALL incoming messages
        async def handler(event):
            # The Service will decide if this message matches any of the user's pairs
            await callback(event.message, user_id)

        asyncio.create_task(client.run_until_disconnected())


    async def send_message(self, user_id: int, destination: str, message):
        """The Eyes: Action (The Blink). Now accepts raw message objects."""
        client = self.active_clients.get(user_id)

        # Rule 7: Resilience - check if client is alive
        if not client or not client.is_connected():
            logger.warning(f"No active client for {user_id}. The Eyes are closed!")
            return

        try:
            # <REACTION: Sending the message object directly preserves everything—text, photo, video.>
            await client.send_message(destination, message)
            logger.info(f"✅ Successful blink to {destination}")
        except Exception as e:
            logger.error(f"❌ Blink failed: {e}")


    async def stop_listener(self, user_id: int):
        client = self.active_clients.get(user_id)
        if client:
            await client.disconnect()
            del self.active_clients[user_id]
            return True
        return False