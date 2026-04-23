import os
import sqlite3
import asyncio
import time
from telethon import TelegramClient
from telethon.sessions import StringSession

def load_env():
    env = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env[k] = v
    return env

async def main():
    env = load_env()
    api_id = env.get('API_ID')
    api_hash = env.get('API_HASH')
    db_path = 'data/reposter.db'

    if not api_id or not api_hash:
        print("❌ Error: API_ID or API_HASH missing from .env")
        return

    if not os.path.exists(db_path):
        print(f"❌ Error: Database not found at {db_path}")
        return

    print("--- LIVE REPOSTER TEST ---")
    print("This script will send a test message to a SOURCE.")
    print("If your reposter engine is running in real-time, it should instantly appear in the DESTINATION.\n")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get active pairs to let user choose
    c.execute("SELECT id, user_id, source_id, destination_id FROM repost_pairs WHERE is_active = 1")
    pairs = c.fetchall()
    
    if not pairs:
        print("ℹ️ No active pairs found in database. Please ensure pairs exist to test.")
        return

    print("Active Pairs:")
    for idx, p in enumerate(pairs):
        print(f"  {idx + 1}. [Pair ID: {p[0]}] User {p[1]} | Source: {p[2]} -> Dest: {p[3]}")
    
    # Run interactive prompt directly (when run via CLI)
    choice = input("\nSelect a pair to test (1-" + str(len(pairs)) + ") or press Enter to cancel: ")
    if not choice.strip():
        print("Canceled.")
        return

    try:
        pair_idx = int(choice) - 1
        if pair_idx < 0 or pair_idx >= len(pairs):
            raise ValueError()
        selected_pair = pairs[pair_idx]
    except Exception:
        print("Invalid choice. Exiting.")
        return

    pair_id, uid, source, destination = selected_pair

    # Get session for this user
    c.execute("SELECT session_string FROM users WHERE id = ?", (uid,))
    session_row = c.fetchone()
    if not session_row or not session_row[0]:
        print(f"⚠️ No session found for User {uid}.")
        return

    session_str = session_row[0]
    conn.close()

    print(f"\n🚀 Connecting as User {uid}...")
    client = TelegramClient(StringSession(session_str), int(api_id), api_hash)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"❌ User {uid} session is unauthorized or revoked.")
            return

        print(f"✅ Connected successfully.")
        
        # Test finding source
        print(f"🔍 Resolving Source '{source}'...")
        try:
            s_ent = await client.get_entity(source)
        except Exception as e:
            print(f"❌ Failed to resolve source: {e}")
            print("To send a test message, the session must have write-access (e.g. admin in the source if it's a channel, or normal participant if it's a group).")
            return
            
        test_message = f"🚀 [LIVE TEST] Real-time engine test via Mister Reposter at {time.strftime('%H:%M:%S')}"
        print(f"📤 Sending test message to Source:\n   \"{test_message}\"")
        
        await client.send_message(s_ent, test_message)
        print("✅ Message sent to Source successfully!")
        print("\n👀 Check your Destination channel/chat now!")
        print("If the Mister Reposter engine is running in the background, it should automatically catch this new message and repost it instantly.")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
