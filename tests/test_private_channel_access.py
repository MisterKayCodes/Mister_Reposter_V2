import asyncio
import logging
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure we can import from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///data/test_private.db"

import data.database
from data.database import init_db, async_session, engine
from data.repository import UserRepository
from services.repost_engine import RepostService

# Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("PrivateTester")

class MockMessage:
    def __init__(self, msg_id, text, chat_id):
        self.id = msg_id
        self.message = text
        self.chat_id = chat_id # e.g. 1567469683
        self.media = None
        self.grouped_id = None

class MockPrivateProvider:
    async def join_channel(self, user_id, invite_hash):
        # Simulator for a private join
        return {"id": 1567469683, "title": "Private Channel 1"}

    async def resolve_entity(self, user_id, identifier):
        return {"id": 1567469683, "title": "Private Channel 1"}

    async def get_total_messages(self, user_id, source_id):
        return 10

    async def start_listener(self, user_id, session_data, callback): pass
    async def stop_listener(self, user_id): pass
    
    async def send_message(self, user_id, destination, message):
        logger.info(f"MOCK SEND to {destination}: Message {message.id}")
        return {"ok": True, "message": message}

async def run_private_test():
    if os.path.exists("data/test_private.db"):
        os.remove("data/test_private.db")
    await init_db()

    user_id = 555
    service = RepostService()
    provider = MockPrivateProvider()
    service.telethon = provider
    service._notify_user = AsyncMock()

    # 1. Simulate adding a pair via invite link
    invite_link = "https://t.me/+AbCdEfGhIjKlMn"
    invite_hash = "AbCdEfGhIjKlMn"
    
    logger.info(f"--- Step 1: Resolving invite link {invite_link} ---")
    resolved_id = await service.resolve_channel_for_pair(user_id, invite_link, "invite", invite_hash)
    logger.info(f"Resolved ID: {resolved_id}")
    
    async with async_session() as session:
        repo = UserRepository(session)
        await repo.create_or_update_user(user_id, "PrivateTester")
        await repo.update_session_string(user_id, "mock_session")
        await repo.add_repost_pair(user_id, resolved_id, "-100OUT", schedule_interval=0) # Real-time mode

    # 2. Simulate an incoming message from the listener
    logger.info("--- Step 2: Simulating real-time incoming message ---")
    incoming_msg = MockMessage(msg_id=100, text="Hello Private", chat_id=1567469683)
    
    # We call the listener handler directly
    await service._handle_new_message(incoming_msg, user_id)
    
    # Give it a moment to process
    await asyncio.sleep(0.5)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_private_test())
