"""
scripts/migrate_sorter.py — One-Time Media Classification & Channel Sorter
===========================================================================
Scans a source Telegram channel (e.g., 'Wet3 private server') and sorts
videos into dedicated VIP and VVIP channels based on duration:
  - 120s <= duration < 360s (2m to 6m) -> VIP Channel (The Velvet Vault)
  - duration >= 360s (6m+)              -> VVIP Channel (Obsidian Black)
  - duration < 120s (< 2m)              -> Skipped (remain free teasers for frontend)

Features:
  - Real-time terminal progress display.
  - Periodic Telegram status updates & completion notification sent to the owner.
  - Safe randomized sleep jitter (3.5s - 7.0s) to guarantee zero account ban risk.
  - Checkpoint file (.json) to resume cleanly after network drop or FloodWait.
"""

import os
import sys
import json
import time
import random
import asyncio
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo
from telethon.errors import FloodWaitError

from app.core.config import config
from app.data.database import async_session
from app.data.models import User
from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MigrateSorter")


async def get_worker_session(worker_id: int | None = None, niche: str = "nsfw") -> str:
    """Fetch active session string directly from database."""
    async with async_session() as ds:
        if worker_id:
            stmt = select(User).where(User.id == worker_id, User.has_active_session == True)
        else:
            stmt = select(User).where(User.worker_niche == niche, User.has_active_session == True)
        result = await ds.execute(stmt)
        user = result.scalars().first()
        if not user or not user.session_string:
            raise RuntimeError(f"No active worker session found for id={worker_id} / niche={niche}")
        return user.session_string


async def send_tg_notification(client, owner_id: int | str, text: str):
    """Gracefully send status alert directly to the owner on Telegram."""
    if not owner_id:
        return
    try:
        await client.send_message(int(owner_id), text)
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification to {owner_id}: {e}")


def load_checkpoint(cp_file: Path) -> dict:
    if cp_file.exists():
        try:
            with open(cp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_scanned_id": 0, "vip_count": 0, "vvip_count": 0, "skipped_count": 0}


def save_checkpoint(cp_file: Path, data: dict):
    try:
        with open(cp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save checkpoint: {e}")


async def run_migration(args):
    session_str = await get_worker_session(args.worker_id, args.niche)
    client = TelegramClient(StringSession(session_str), config.API_ID, config.API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("Worker session is not authorized.")
        return

    source = int(args.source) if args.source.replace("-", "").isdigit() else args.source
    vip_dest = int(args.vip) if args.vip.replace("-", "").isdigit() else args.vip
    vvip_dest = int(args.vvip) if args.vvip.replace("-", "").isdigit() else args.vvip
    owner_id = args.owner_id or config.OWNER_ID

    source_entity = await client.get_input_entity(source)
    vip_entity = await client.get_input_entity(vip_dest)
    vvip_entity = await client.get_input_entity(vvip_dest)

    cp_file = Path("data") / f"checkpoint_migration_{abs(hash(str(source)))}.json"
    cp_file.parent.mkdir(exist_ok=True)
    state = load_checkpoint(cp_file)

    logger.info("=" * 60)
    logger.info("🚀 MIGRATION SORTER INITIALIZED")
    logger.info(f"Source: {source} | VIP: {vip_dest} | VVIP: {vvip_dest}")
    logger.info(f"Resuming from Message ID: {state['last_scanned_id']}")
    logger.info("=" * 60)

    # Initial start notification to owner
    await send_tg_notification(
        client, owner_id,
        f"🚀 <b>Migration Started</b>\n"
        f"Sorting videos from <code>{source}</code> into VIP & VVIP.\n"
        f"You will receive updates and a completion alert here."
    )

    last_notify_time = time.time()
    total_scanned = 0

    try:
        # Scan from oldest to newest or stream messages
        async for msg in client.iter_messages(source_entity, reverse=True, min_id=state["last_scanned_id"]):
            total_scanned += 1
            state["last_scanned_id"] = msg.id

            if not msg or not msg.media:
                state["skipped_count"] += 1
                continue

            # Duration extraction
            video_duration = None
            doc = getattr(msg.media, "document", None)
            if doc:
                for a in getattr(doc, "attributes", []):
                    if isinstance(a, DocumentAttributeVideo):
                        video_duration = a.duration
                        break

            if video_duration is None or video_duration < 120:
                # Under 2 mins: stays on frontend as free teaser
                state["skipped_count"] += 1
                continue

            target_entity = None
            target_label = ""

            if 120 <= video_duration < 360:
                target_entity = vip_entity
                target_label = "VIP (Velvet Vault)"
            elif video_duration >= 360:
                target_entity = vvip_entity
                target_label = "VVIP (Obsidian Black)"

            if target_entity:
                while True:
                    try:
                        await client.forward_messages(target_entity, msg, drop_author=True)
                        if target_label.startswith("VIP"):
                            state["vip_count"] += 1
                        else:
                            state["vvip_count"] += 1

                        logger.info(f"✅ Msg #{msg.id} ({video_duration:.1f}s) ➔ {target_label} | Total: VIP={state['vip_count']}, VVIP={state['vvip_count']}")
                        save_checkpoint(cp_file, state)

                        # Enforce anti-flood jitter
                        jitter = random.uniform(3.5, 7.0)
                        await asyncio.sleep(jitter)
                        break

                    except FloodWaitError as fe:
                        wait_s = fe.seconds + 5
                        logger.warning(f"⏳ FloodWait encountered: sleeping {wait_s}s...")
                        await asyncio.sleep(wait_s)
                    except Exception as e:
                        logger.error(f"❌ Error forwarding Msg #{msg.id}: {e}")
                        break

            # Periodic Telegram update every 15 minutes
            if time.time() - last_notify_time > 900:
                last_notify_time = time.time()
                await send_tg_notification(
                    client, owner_id,
                    f"📊 <b>Migration Progress</b>\n"
                    f"• Scanned: {total_scanned}\n"
                    f"• VIP (2–6m): {state['vip_count']}\n"
                    f"• VVIP (6m+): {state['vvip_count']}\n"
                    f"• Teasers (<2m): {state['skipped_count']}"
                )

    finally:
        save_checkpoint(cp_file, state)
        summary = (
            f"🎉 <b>Migration Completed!</b>\n\n"
            f"All inventory from <code>{source}</code> has been processed:\n"
            f"• 📁 <b>VIP Channel:</b> {state['vip_count']} videos\n"
            f"• 👑 <b>VVIP Channel:</b> {state['vvip_count']} videos\n"
            f"• ⏩ <b>Teasers (<2m):</b> {state['skipped_count']} clips\n\n"
            f"Your VIP & VVIP channels are ready for monetization!"
        )
        logger.info(summary.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
        await send_tg_notification(client, owner_id, summary)
        await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sort channel videos into VIP and VVIP channels by duration")
    parser.add_argument("--source", required=True, help="Source Channel ID / Username")
    parser.add_argument("--vip", required=True, help="VIP Channel ID for 2-6m videos")
    parser.add_argument("--vvip", required=True, help="VVIP Channel ID for 6m+ videos")
    parser.add_argument("--worker-id", type=int, default=None, help="Specific worker Telegram ID")
    parser.add_argument("--niche", default="nsfw", help="Worker niche (default: nsfw)")
    parser.add_argument("--owner-id", default=None, help="Telegram ID to receive progress alerts")
    args = parser.parse_args()

    asyncio.run(run_migration(args))
