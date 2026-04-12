import os
import sqlite3
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import PeerIdInvalidError

def load_env():
    env = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env[k] = v
    return env

async def test_pair_resolution(client, pair_id, source, destination):
    print(f"\n🔍 Testing Pair #{pair_id}")
    print(f"  Source Input: {source}")
    print(f"  Destination Input: {destination}")
    
    # 1. Test Source
    try:
        print(f"  Resolving Source...")
        s_ent = await client.get_entity(source)
        print(f"    ✅ Source OK: {type(s_ent).__name__} (ID: {s_ent.id})")
    except Exception as e:
        print(f"    ❌ Source FAIL: {e}")

    # 2. Test Destination
    try:
        print(f"  Resolving Destination...")
        d_ent = await client.get_entity(destination)
        print(f"    ✅ Destination OK: {type(d_ent).__name__} (ID: {d_ent.id})")
        
        # 3. Test "Input" Peer (what SendMediaRequest actually uses)
        try:
            print(f"  Checking InputPeer capability...")
            input_peer = await client.get_input_entity(d_ent)
            print(f"    ✅ InputPeer OK: {type(input_peer).__name__}")
        except Exception as e:
            print(f"    ❌ InputPeer FAIL: {e}")
            
    except PeerIdInvalidError:
        print(f"    ❌ Destination FAIL: Invalid Peer. This usually means the account hasn't 'seen' this entity yet.")
    except Exception as e:
        print(f"    ❌ Destination FAIL: {e}")

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

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get active pairs
    c.execute("SELECT id, user_id, source_id, destination_id FROM repost_pairs WHERE is_active = 1")
    pairs = c.fetchall()
    
    if not pairs:
        print("ℹ️ No active pairs found in database.")
        return

    print(f"🚀 Found {len(pairs)} active pairs. Starting diagnostic...\n")

    # Group by user to reuse clients
    users = {}
    for p in pairs:
        uid = p[1]
        if uid not in users:
            users[uid] = []
        users[uid].append(p)

    for uid, u_pairs in users.items():
        c.execute("SELECT session_string FROM users WHERE id = ?", (uid,))
        session_row = c.fetchone()
        if not session_row or not session_row[0]:
            print(f"⚠️ No session found for User {uid}. Skipping.")
            continue
        
        session_str = session_row[0]
        print(f"--- Testing for User {uid} ---")
        
        client = TelegramClient(StringSession(session_str), int(api_id), api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                print(f"  ❌ User {uid} balance is unauthorized.")
                await client.disconnect()
                continue
                
            for p in u_pairs:
                await test_pair_resolution(client, p[0], p[2], p[3])
                
            await client.disconnect()
        except Exception as e:
            print(f"  ❌ Client error for User {uid}: {e}")

    conn.close()
    print("\n✅ Diagnostic complete.")

if __name__ == "__main__":
    asyncio.run(main())
