import asyncio
import logging
import os
import sys
import time
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure we can import from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///data/test_chaos.db"

import app.data.database
from app.data.database import init_db, async_session, engine
from app.data.repository import UserRepository
from app.services.repost_engine import RepostService
class MockUnauthorizedError(Exception): pass
# Senior Fix: Patch the newly refactored engine loops
from app.services import engine_loops
engine_loops.rpcbaseerrors.UnauthorizedError = MockUnauthorizedError

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ChaosSimulator")

class MockMessage:
    def __init__(self, msg_id, text, chat_id=-1001234567):
        self.id = msg_id
        self.message = text
        self.chat_id = chat_id
        self.media = None
        self.grouped_id = None

class MockChaosProvider:
    def __init__(self):
        self.fail_mode = None  # Choice: 'flood', 'ghost', 'fatal', 'timeout', None
        self.available_ids = list(range(1, 101))
        self.sent_count = 0
        self.last_sent_id = 0

    async def get_total_messages(self, user_id, source_id):
        return 100

    async def fetch_messages_from(self, user_id, source, offset_id, limit=50):
        # Always return next 50 from our list
        return [MockMessage(mid, f"Test Content {mid}") for mid in self.available_ids if mid > offset_id][:limit]

    async def get_message(self, user_id, source, msg_id):
        if self.fail_mode == 'ghost' and msg_id % 3 == 0:
            return None # Simulate deleted message
        return MockMessage(msg_id, f"Fresh Content {msg_id}")

    async def send_message(self, user_id, destination, message):
        self.sent_count += 1
        
        if self.fail_mode == 'flood':
            return {"ok": False, "error": "flood_wait", "wait_seconds": 1}
        
        if self.fail_mode == 'fatal':
            raise MockUnauthorizedError("Session Revoked (Chaos)")

        if self.fail_mode == 'timeout':
            return {"ok": False, "error": "timeout"}

        self.last_sent_id = message.id
        return {"ok": True, "message": message}

    async def start_listener(self, user_id, session_data, callback):
        pass

    async def stop_listener(self, user_id):
        pass

async def run_detailed_simulation():
    # 1. Prepare Database
    if os.path.exists("data/test_chaos.db"):
        os.remove("data/test_chaos.db")
    await init_db()
    
    user_id = 999
    source_id = "-100111"
    dest_id = "-100222"
    
    async with async_session() as session:
        repo = UserRepository(session)
        await repo.create_or_update_user(user_id, "ChaosTester")
        await repo.update_session_string(user_id, "mock_session_string")
        await repo.add_repost_pair(user_id, source_id, dest_id, schedule_interval=1, start_from_msg_id=1)
        # Get the pair ID
        pairs = await repo.get_user_pairs(user_id)
        pair_id = pairs[0].id

    # 2. Setup Service with Mock Provider
    service = RepostService()
    mock_provider = MockChaosProvider()
    service.telethon = mock_provider
    service._notify_user = AsyncMock() # Don't actually send telegram messages

    # 3. Define the Phased Chaos
    async def chaos_control():
        logger.info("PHASE 1: Smooth Sailing (1-10)")
        await asyncio.sleep(2) # Allow some posts
        
        logger.info("PHASE 2: Network Turbulence (Flood/Timeout) (11-20)")
        mock_provider.fail_mode = 'flood'
        await asyncio.sleep(1)
        mock_provider.fail_mode = 'timeout'
        await asyncio.sleep(2)
        
        logger.info("PHASE 3: Data Decay (Ghosts) (21-40)")
        mock_provider.fail_mode = 'ghost'
        await asyncio.sleep(5)
        
        logger.info("PHASE 4: Recovery (41-55)")
        mock_provider.fail_mode = None
        await asyncio.sleep(3)
        
        logger.info("PHASE 5: Fatal System Collapse (56+)")
        mock_provider.fail_mode = 'fatal'

    # 4. Time Dilation: Mock sleep to run much faster (1m -> 0.1s)
    real_sleep = asyncio.sleep
    async def dilated_sleep(seconds):
        # We process huge sleeps (schedule) instantly
        if seconds >= 5:
            await real_sleep(0.001)
        else:
            # We keep real-ish delays for short spans so phases can happen
            await real_sleep(min(seconds, 0.1))

    # 5. Start Simulation
    with patch("asyncio.sleep", side_effect=dilated_sleep):
        # Start backfill task
        backfill_task = asyncio.create_task(
            service._backfill_from_message(
                user_id, source_id, dest_id, 1, 1, None, 1, pair_id
            )
        )
        
        # Start chaos controller
        await chaos_control()
        
        # Give the backfill task a moment to process the Final Fatal Error
        await real_sleep(1.0)
        
        try:
            # We wait for the task to finish (it should finish on fatal error)
            await asyncio.wait_for(backfill_task, timeout=5)
        except asyncio.TimeoutError:
            logger.info("Simulation reached timeout (expected at Phased End)")
        except Exception as e:
            logger.info(f"Backfill Loop exited as expected: {type(e).__name__}")

    # 6. Final Audit
    logger.info("--- FINAL AUDIT ---")
    async with async_session() as session:
        repo = UserRepository(session)
        pair = await repo.get_pair_by_id(pair_id)
        logger.info(f"Final Pair Status: {pair.status}")
        logger.info(f"Final Message ID: {pair.start_from_msg_id}")
        logger.info(f"Error Count: {pair.error_count}")
        
        if pair.status == "paused" or pair.status == "error":
            logger.info("SUCCESS: Engine handled fatal error and paused correctly.")
        else:
            logger.error("FAILURE: Engine did not pause on fatal error.")

    # Cleanup
    await engine.dispose()

if __name__ == "__main__":
    try:
        asyncio.run(run_detailed_simulation())
    except KeyboardInterrupt:
        print("\nTest aborted by user.")
    except Exception as e:
        logger.error(f"Test Runner Crash: {e}")
        import traceback
        traceback.print_exc()
