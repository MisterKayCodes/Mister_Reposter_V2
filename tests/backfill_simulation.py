"""
TESTS: BACKFILL SIMULATION
A playground to verify our 'Gap Jumping' logic without needing a million Telegram accounts.
"""
import asyncio
import logging

# Set up our logging so we can see the 'Jump detected' messages clearly.
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mock message class to represent what we get from Telegram.
# Imagine this is a single page in our book.
class MockMessage:
    def __init__(self, msg_id, text):
        self.id = msg_id
        self.message = text

# Mock Telethon provider. 
# Think of this like a 'Fake Library' that only has certain pages available.
class MockTelethon:
    def __init__(self, available_ids):
        # We store the IDs that haven't been 'deleted'.
        self.available_ids = sorted(available_ids)

    async def fetch_messages_from(self, user_id, source, offset_id, limit=50):
        # In the real world, Telethon's offset_id with reverse=True gets messages GREATER than offset_id.
        # This simulates that behavior.
        results = [MockMessage(mid, f"Message content for {mid}") for mid in self.available_ids if mid > offset_id]
        return results[:limit]

# The 'Brain' of our test.
# This mimics the _backfill_from_message loop in repost_engine.py.
async def simulate_backfill(start_from_id, available_ids):
    telethon = MockTelethon(available_ids)
    
    # max(0, start-1) is our 'bookmark' placement.
    current_id = max(0, start_from_id - 1)
    
    logger.info(f"--- Starting Simulation from ID {start_from_id} ---")
    logger.info(f"Available IDs in 'Channel': {available_ids}")
    
    while True:
        # We grab a batch of messages.
        messages = await telethon.fetch_messages_from(1, "source", current_id, limit=5)
        
        if not messages:
            logger.info("Simulation complete: No more messages.")
            break
        
        for msg in messages:
            # Check for the jump! This is the core logic we're testing.
            if msg.id > current_id + 1:
                logger.info(f"Gap detected! Jumping from ID {current_id} to {msg.id}")
            
            logger.info(f"Successfully 'posted' message {msg.id}")
            
            # Move the bookmark forward.
            current_id = msg.id
            
            # Tiny sleep to mimic the real schedule (but faster for testing).
            await asyncio.sleep(0.1)

# Run the simulation.
if __name__ == "__main__":
    # SCENARIO: Gaps at 2 and 4.
    # We have 1, then a gap, then 3, then a gap, then 5.
    available_pages = [1, 3, 5, 6, 7]
    
    asyncio.run(simulate_backfill(start_from_id=1, available_ids=available_pages))

    # SCENARIO: Massive gap.
    # We start at 1, but the next available is 100.
    print("\n--- Testing Massive Gap ---")
    available_pages_2 = [1, 100, 101]
    asyncio.run(simulate_backfill(start_from_id=1, available_ids=available_pages_2))
