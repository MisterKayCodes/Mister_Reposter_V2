import sys
import os
import asyncio
from unittest.mock import AsyncMock

# Handle Windows Console Emoji Printing Issue
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.repost_engine import RepostService

class DummyMessage:
    def __init__(self, chat_id, text, grouped_id=None, media=None):
        self.chat_id = chat_id
        self.message = text
        self.grouped_id = grouped_id
        self.media = media

class DummyPair:
    def __init__(self, pair_id, source, dest, filter_type=1, replacement=""):
        self.id = pair_id
        self.is_active = True
        self.status = "active"
        self.source_id = source
        self.destination_id = dest
        self.filter_type = filter_type
        self.replacement_link = replacement
        self.schedule_interval = 0

async def test_repost_logic():
    print("🧪 --- PROVING THE INSTANT REPOSTING BUG ---")

    engine = RepostService()
    engine._send_with_retry = AsyncMock()

    # ----------------------------------------------------
    # SCENARIO: User inputs a username into the bot when creating a pair.
    # The database stores it as a string: "@example_channel"
    db_source_id = "@example_channel" 
    # ----------------------------------------------------
    
    fake_pair = DummyPair(pair_id=99, source=db_source_id, dest="-1009876543", filter_type=1)

    print(f"\n[1] SETUP:")
    print(f"  Database Pair Source: '{fake_pair.source_id}'")

    # We replicate EXACTLY what _execute_repost does currently in production.
    async def exact_production_execute_repost(user_id, messages):
        cid = str(messages[0].chat_id)
        norm_cid = cid if cid.startswith("-100") else f"-100{cid}"
        
        src = str(fake_pair.source_id)
        norm_src = src if src.startswith("-100") else f"-100{src}"
        
        print(f"\n[3] ENGINE STRING MATCHING (Production Logic):")
        print(f"  Is '{norm_cid}' equal to '{norm_src}'?")
        
        if norm_cid == norm_src:
            print(f"  ✅ MATCH! Routing to Destination!")
            await engine._process_matched_pair(fake_pair, user_id, messages)
        else:
            print(f"  ❌ FAILURE! Strings do not match. Engine silently drops the message.")

    engine._execute_repost = exact_production_execute_repost

    # ----------------------------------------------------
    # SCENARIO: Telethon 'events.NewMessage()' triggers on a new post!
    # Telegram sends us the message with the RAW NUMERICAL ID.
    raw_telegram_chat_id = "-10012345678" 
    # ----------------------------------------------------

    dummy_msg = DummyMessage(chat_id=raw_telegram_chat_id, text="A new crypto signal!")

    print(f"\n[2] INCOMING TELEGRAM EVENT:")
    print(f"  A new message just arrived from Chat ID: {dummy_msg.chat_id} (Which is @example_channel)")

    # Execute the current bugged logic
    await engine._execute_repost(user_id=1, messages=[dummy_msg])

    print("\n---------------------------------------------------------")
    print("✨ HOW WE FIX IT (The Proposed Solution) ✨")

    async def fixed_execute_repost(user_id, messages):
        cid = str(messages[0].chat_id)
        norm_cid = cid if cid.startswith("-100") else f"-100{cid}"
        src = str(fake_pair.source_id)
        
        # NEW LOGIC: Dynamic Resolution
        if src.startswith("@") or src.startswith("http"):
            print(f"\n[4] FIXED LOGIC: Oh wait! '{src}' is a username/link!")
            print(f"    Checking Telethon API to get the numerical ID for '{src}'...")
            # We mock the Telethon resolution for the test
            src = raw_telegram_chat_id 
            print(f"    Telethon says '{fake_pair.source_id}' is actually ID {src}!")

        norm_src = src if src.startswith("-100") else f"-100{src}"
        
        print(f"    Is '{norm_cid}' equal to '{norm_src}'?")
        if norm_cid == norm_src:
            print(f"    ✅ MATCH! Routing to Destination!")
            await engine._process_matched_pair(fake_pair, user_id, messages)

    engine._execute_repost = fixed_execute_repost
    await engine._execute_repost(user_id=1, messages=[dummy_msg])


if __name__ == "__main__":
    asyncio.run(test_repost_logic())
