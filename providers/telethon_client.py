"""
PROVIDERS: TELETHON CLIENT
The 'Eyes' of the organism. (Rule 11)
Handles raw communication with Telegram Servers.
Pure communication, no logic allowed.
"""
import logging
import asyncio
from telethon import TelegramClient, events

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
        """Starts a global listener for the user. (Rule: Self-Healing)"""
        
        # 1. Check for stale connections
        if user_id in self.active_clients:
            client = self.active_clients[user_id]
            try:
                if client.is_connected():
                    return
                else:
                    logger.info(f"🔄 Re-opening closed eyes for User {user_id}")
                    await self.stop_listener(user_id) # Clean up properly first
            except Exception:
                del self.active_clients[user_id]

        try:
            # Note: Using the session path/string directly
            client = TelegramClient(session_data, self.api_id, self.api_hash)
            
            # 2. Connection with retry logic to fight the "Database Locked" ghost
            await client.start()
            self.active_clients[user_id] = client 

            @client.on(events.NewMessage())
            async def handler(event):
                # Reflex Arc: Send signal back to the Nervous System
                await callback(event.message, user_id)

            # Rule 7: Run in background. 
            # We store the task to manage it if needed.
            asyncio.create_task(client.run_until_disconnected())
            logger.info(f"👁️ Eyes wide open for User {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to open Eyes for User {user_id}: {e}")
            if user_id in self.active_clients:
                del self.active_clients[user_id]

    async def send_message(self, user_id: int, destination: str, message):
        """The Eyes: Action (The Blink). Now accepts raw message objects."""
        client = self.active_clients.get(user_id)

        if not client or not client.is_connected():
            logger.warning(f"No active client for {user_id}. The Eyes are closed!")
            return

        try:
            await client.send_message(destination, message)
            logger.info(f"✅ Successful blink to {destination}")
        except Exception as e:
            logger.error(f"❌ Blink failed: {e}")

    async def stop_listener(self, user_id: int):
        """The 'Graceful Sleep'. Prevents Task Destroyed errors."""
        client = self.active_clients.get(user_id)
        if client:
            try:
                # <REACTION: We must disconnect properly to release the .session file lock.>
                logger.info(f"🛑 Closing Eyes for User {user_id}...")
                await client.disconnect()
                
                # Give the event loop a heartbeat to finish background tasks
                await asyncio.sleep(0.2)
                
                if user_id in self.active_clients:
                    del self.active_clients[user_id]
                return True
            except Exception as e:
                logger.error(f"Error while closing eyes for {user_id}: {e}")
        return False