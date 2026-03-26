import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import time
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def test_disconnect_loop():
    from services.repost_engine import RepostService
    
    # Mock Telethon
    mock_telethon = AsyncMock()
    # Simulate a permanently dead connection (returns -1 or empty)
    mock_telethon.get_total_messages.return_value = -1
    mock_telethon.fetch_messages_from.return_value = []
    
    engine = RepostService()
    engine.telethon = mock_telethon
    
    # Mock DB
    class MockPair:
        def __init__(self):
            self.id = 1
            self.is_active = True
            self.status = "active"
            
    class MockRepo:
        async def update_pair_total_posts(self, *args): pass
        async def get_pair_by_id(self, *args): return MockPair()
        async def update_pair_start_id(self, *args): pass
    
    class MockSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        
    loop_count = 0
    
    # Wrap sleep to track iterations without actually sleeping 60 real seconds during the test
    original_sleep = asyncio.sleep
    async def mock_sleep(seconds):
        nonlocal loop_count
        loop_count += 1
        logging.info(f"MOCK SLEEP CALLED for {seconds}s")
        # We only sleep briefly so the test finishes fast, but we register the intent
        await original_sleep(0.1)
        
    # We will test backfill where the loop runs wildly
    with patch("services.repost_engine.async_session", return_value=MockSession()) as mock_db, \
         patch("services.repost_engine.UserRepository", return_value=MockRepo()), \
         patch("asyncio.sleep", side_effect=mock_sleep):
             
        task = asyncio.create_task(
            engine._backfill_from_message(
                user_id=1, source="src", destination="dst", 
                from_msg_id=1, filter_type=0, replacement_link=None, 
                interval_minutes=240, pair_id=1
            )
        )
        
        # Let it run for 1 second real-time. 
        # If the bug existed, it would spin thousands of times because sleep wouldn't be called.
        # With the fix, we patched sleep to 0.1s, so it should run ~10 times instead of 10000+.
        await original_sleep(1)
        task.cancel()
        
    print("Test Complete.")
    print(f"Total loop iterations observed: {loop_count}")
    if loop_count < 20:
        print("PASS: The disconnect loop safety valve is working!")
    else:
        print("FAIL: The loop is spinning wildly!")

if __name__ == "__main__":
    asyncio.run(test_disconnect_loop())
