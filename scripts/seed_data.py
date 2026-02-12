"""
SCRIPTS: SEED DATA
The 'Medical Injection'.
Used to jumpstart the Vault with initial pairs. (Rule 1)
"""
import asyncio
import sys
import os

# Add the project root to the path so it can find 'data' and 'config'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import async_session, init_db
from data.repository import UserRepository

async def seed():
    print("🌱 Injecting initial pairs into the Vault...")
    
    # Ensure the Vault exists (Rule 1)
    await init_db()
    
    async with async_session() as session:
        repo = UserRepository(session)
        
        # --- CONFIGURATION ---
        # Replace this with your actual Telegram User ID
        MY_USER_ID = 12345678 
        
        # Replace these with your actual channel IDs or Usernames
        pairs_to_add = [
            ("@source_chan_1", "@dest_chan_1"),
            ("@source_chan_2", "@dest_chan_2"),
            ("@source_chan_3", "@dest_chan_3"),
            ("@source_chan_4", "@dest_chan_4"),
        ]
        # ---------------------

        # 1. Create the user in the database
        await repo.create_or_update_user(MY_USER_ID, "Admin")
        
        # 2. Add the 4 pairs
        for src, dst in pairs_to_add:
            await repo.add_repost_pair(MY_USER_ID, src, dst)
            print(f"✅ Linked: {src} -> {dst}")

if __name__ == "__main__":
    asyncio.run(seed())