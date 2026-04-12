import asyncio
import logging
from app.data.database import async_session
from sqlalchemy import text
from telethon import TelegramClient
from telethon.sessions import StringSession
from app.core.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_peers():
    async with async_session() as ds:
        # Fetch active pairs
        result = await ds.execute(text("SELECT id, user_id, source_id, destination_id FROM repost_pairs WHERE is_active = 1"))
        pairs = result.fetchall()
        
        if not pairs:
            print("No active pairs found in DB.")
            return

        for p in pairs:
            pid, uid, src, dest = p
            print(f"--- Pair #{pid} (User {uid}) ---")
            print(f"Source: {src}")
            print(f"Destination: {dest}")
            
            # Get session for this user
            user_res = await ds.execute(text(f"SELECT session_string FROM users WHERE id = {uid}"))
            session_str = user_res.scalar()
            
            if not session_str:
                print(f"No session for user {uid}")
                continue
                
            try:
                client = TelegramClient(StringSession(session_str), config.API_ID, config.API_HASH)
                await client.connect()
                if not await client.is_user_authorized():
                    print("Unauthorized")
                    await client.disconnect()
                    continue
                
                print("Testing Source Resolution:")
                try:
                    s_ent = await client.get_entity(src)
                    print(f"  OK: {type(s_ent).__name__} (ID: {s_ent.id})")
                except Exception as e:
                    print(f"  FAIL: {e}")
                    
                print("Testing Destination Resolution:")
                try:
                    d_ent = await client.get_entity(dest)
                    print(f"  OK: {type(d_ent).__name__} (ID: {d_ent.id})")
                    print("Testing Media Capability (Checking if it's a Channel/Chat):")
                    if hasattr(d_ent, 'broadcast'):
                        print(f"  Type: Broadcast Channel({'Yes' if d_ent.broadcast else 'No'})")
                    if hasattr(d_ent, 'megagroup'):
                        print(f"  Type: Megagroup({'Yes' if d_ent.megagroup else 'No'})")
                        
                except Exception as e:
                    print(f"  FAIL: {e}")
                
                await client.disconnect()
            except Exception as e:
                print(f"Client error: {e}")

if __name__ == "__main__":
    asyncio.run(test_peers())
