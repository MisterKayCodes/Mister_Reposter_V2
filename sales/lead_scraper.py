import asyncio
import os
import sys
import csv
from datetime import datetime, timezone

# Adding parent directory to path so we can import app config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from app.core.config import config

# We use the existing session from Mister Reposter to avoid logging in again
SESSION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "app", "data", "sessions", "8526011565"
)
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "high_quality_leads.csv")

def evaluate_lead(sub_count, avg_views, messages_per_day):
    """
    Applies the "Smartness Scale" to determine lead value.
    """
    if sub_count < 100:
        return "REJECT", "Too small to monetize"
        
    engagement_rate = (avg_views / sub_count) * 100
    
    if engagement_rate < 3.0:
        return "REJECT", f"Fake/Bot Farm (Eng: {engagement_rate:.1f}%)"
    
    if messages_per_day > 25:
        return "REJECT", f"Already Automated ({messages_per_day:.1f} msgs/day)"
        
    if engagement_rate > 30.0:
        return "GOLD", "Hyper-engaged manual poster"
        
    return "SILVER", "Good engagement, worth a pitch"

async def hunter_module(client, keyword: str, limit: int = 15):
    """
    Phase 3: The Hunter
    Searches Telegram's global database for public channels matching a keyword.
    """
    print(f"\n[HUNTER] Searching Telegram for keyword: '{keyword}'...")
    try:
        result = await client(SearchRequest(
            q=keyword,
            limit=limit
        ))
        
        found_links = []
        for chat in result.chats:
            # We only want broadcast channels that are public (have a username)
            if getattr(chat, 'broadcast', False) and getattr(chat, 'username', None):
                link = f"https://t.me/{chat.username}"
                if link not in found_links:
                    found_links.append(link)
                
        print(f"[HUNTER] Found {len(found_links)} public channels for '{keyword}'.")
        return found_links
        
    except Exception as e:
        print(f"[-] Hunter search failed: {e}")
        return []

async def evaluate_channels(client, target_channels):
    """
    Phase 2: Evaluates a list of channels against the Smartness Scale.
    """
    if not target_channels:
        return

    print(f"\n[*] Commencing Smartness Evaluation on {len(target_channels)} channels...")
    file_exists = os.path.isfile(OUTPUT_CSV)
    
    with open(OUTPUT_CSV, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Channel Name", "Link", "Subscribers", "Avg Views", "Eng Rate (%)", "Msgs/Day", "Admin Username", "Score", "Reason"])
            
        for channel_link in target_channels:
            print(f"\n[*] Analyzing: {channel_link}")
            try:
                entity = await client.get_entity(channel_link)
                full_ch = await client(GetFullChannelRequest(channel=entity))
                
                title = entity.title
                sub_count = full_ch.full_chat.participants_count
                
                messages = await client.get_messages(entity, limit=20)
                valid_messages = [m for m in messages if m.views is not None]
                
                if len(valid_messages) < 2:
                    print(f"[-] Not enough broadcast data to score.")
                    continue
                    
                total_views = sum(m.views for m in valid_messages)
                avg_views = total_views / len(valid_messages)
                
                oldest_msg = valid_messages[-1].date
                newest_msg = valid_messages[0].date
                time_diff_days = (newest_msg - oldest_msg).total_seconds() / 86400.0
                
                msgs_per_day = len(valid_messages) / time_diff_days if time_diff_days > 0.01 else 100
                
                score, reason = evaluate_lead(sub_count, avg_views, msgs_per_day)
                eng_rate = (avg_views / sub_count) * 100
                
                admin_user = "Unknown"
                about = full_ch.full_chat.about or ""
                if "@" in about:
                    for w in about.split():
                        if w.startswith("@"):
                            admin_user = w
                            break
                
                writer.writerow([title, channel_link, sub_count, int(avg_views), f"{eng_rate:.1f}%", f"{msgs_per_day:.1f}", admin_user, score, reason])
                
                print(f"  -> Subs: {sub_count:,} | Avg Views: {int(avg_views):,}")
                print(f"  -> Scoring: {score} ({reason})")
                if admin_user != "Unknown":
                    print(f"  -> Extracted Admin: {admin_user}")
                
                # Human delay to avoid API bans
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"[-] Error parsing {channel_link}: {e}")

async def run_scraper(keywords):
    """Main execution block."""
    client = TelegramClient(SESSION_PATH, config.API_ID, config.API_HASH)
    
    await client.connect()
    if not await client.is_user_authorized():
        print("[-] Session is not authorized.")
        await client.disconnect()
        return

    try:
        all_found_links = set()
        
        # Phase 3: The Hunt
        for kw in keywords:
            links = await hunter_module(client, kw, limit=10)
            all_found_links.update(links)
            await asyncio.sleep(3) # Prevent flood waits on searches
            
        # Phase 2: The Evaluation
        await evaluate_channels(client, list(all_found_links))

    finally:
        await client.disconnect()
        print(f"\n[*] Script Finished. Data exported to {OUTPUT_CSV}")

if __name__ == "__main__":
    # Keywords you think your ideal clients are using in their channel names
    search_keywords = [
        "crypto signals", 
        "premium models",
        "forex trading",
        "hot leaks",
        "nude leaks",
        "onlyfans leaks",
        "onlyfans free",
        "onlyfans premium",
        "onlyfans free trial",
        "onlyfans free trial",
        "hookup",
        "escorts",
        "sophie rain", 
        "pussy",
        "milf",
        "anal",
        "lesbian",
        "teen",
        "chinese",
        

    ]
    asyncio.run(run_scraper(search_keywords))
