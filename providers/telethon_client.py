"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
"""
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import RPCError

logger = logging.getLogger(__name__)

class TelethonProvider:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients = {} # Track active listeners to reuse connections

    async def validate_session(self, session_data: str) -> bool:
        """Isolated check for session validity."""
        try:
            session = StringSession(session_data) if len(session_data) > 50 else session_data
            async with TelegramClient(session, self.api_id, self.api_hash) as client:
                # Add 10s timeout to prevent hanging the whole bot
                return await asyncio.wait_for(client.is_user_authorized(), timeout=10)
        except Exception as e:
            logger.error(f"Telethon Validation Error: {e}")
            return False

    async def start_listener(self, user_id: int, session_data: str, source_id: str, callback):
        """Starts a background listener. Reuses client if already active."""
        if user_id in self.active_clients:
            logger.info(f"Listener already active for User {user_id}. Skipping start.")
            return

        session = StringSession(session_data) if len(session_data) > 50 else session_data
        client = TelegramClient(session, self.api_id, self.api_hash)
        
        await client.start()
        self.active_clients[user_id] = client 

        @client.on(events.NewMessage(chats=source_id))
        async def handler(event):
            # Pass the user_id back so the engine knows who sent it
            await callback(event.message, user_id)

        logger.info(f"Listener started for User {user_id} on {source_id}")
        asyncio.create_task(client.run_until_disconnected())

    async def send_message(self, user_id: int, session_data: str, destination: str, text: str):
        """
        Sends a message. 
        CRITICAL: Reuses existing client to avoid 'database is locked' errors.
        """
        client = self.active_clients.get(user_id)

        if client and client.is_connected():
            await client.send_message(destination, text)
            logger.info(f"Message sent via active client for User {user_id}")
        else:
            # Fallback for one-off sends if no listener is running
            session = StringSession(session_data) if len(session_data) > 50 else session_data
            async with TelegramClient(session, self.api_id, self.api_hash) as client:
                await client.send_message(destination, text)

    async def stop_listener(self, user_id: int):
        """Closes the connection and removes from memory."""
        client = self.active_clients.get(user_id)
        if client:
            await client.disconnect()
            del self.active_clients[user_id]
            return True
        return False
