"""
SERVICES: AUTONOMIC IMMUNE SYSTEM
The 'Guardian Heartbeat' that detects stalls and performs surgical self-healing.
"""
import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from app.data.database import async_session
from app.data.repository import UserRepository

logger = logging.getLogger(__name__)

class HeartbeatMonitor:
    def __init__(self, service):
        self.service = service
        self.is_running = False
        self._task = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Autonomic Heartbeat initialized.")

    async def _heartbeat_loop(self):
        # Initial wait to let the bot stabilize
        await asyncio.sleep(60)
        
        while self.is_running:
            try:
                await self.scan_and_heal()
            except Exception as e:
                logger.error(f"Heartbeat Scan Error: {e}")
            
            # Scan every 15 minutes
            await asyncio.sleep(15 * 60)

    async def scan_and_heal(self):
        logger.info("Guardian Pulse: Scanning for stalled loops...")
        async with async_session() as ds:
            repo = UserRepository(ds)
            pairs = await repo.get_all_active_pairs()
            
            for p in pairs:
                if p.status == "paused" or p.status == "error": continue
                if not p.schedule_interval or p.schedule_interval <= 0: continue
                
                # Rule: Heartbeat Drift Calculation
                # Interval + max(15 min, 0.25 * Interval)
                buffer_mins = max(15, int(0.25 * p.schedule_interval))
                threshold_mins = p.schedule_interval + buffer_mins
                
                last_ref = p.last_reposted_at or p.created_at # Fallback to creation if first post
                drift = (datetime.utcnow() - last_ref).total_seconds() / 60
                
                if drift > threshold_mins:
                    # HEAL CANDIDATE DETECTED
                    await self._surgical_heal(p, int(drift))
                    # Staggered healing to avoid API burst
                    await asyncio.sleep(random.randint(5, 12))

    async def _surgical_heal(self, pair, drift_mins):
        pid = pair.id
        uid = pair.user_id
        
        # Rule: Safety Latch (Limit 3 consecutive heals)
        if (pair.consecutive_heals or 0) >= 3:
            logger.critical(f"Pair #{pid} hit safety latch (3 failed heals). Moving to Fatal Error.")
            async with async_session() as ds:
                await UserRepository(ds).deactivate_pair_as_error(pid)
            await self.service._notify_user(uid, f"🚫 <b>Immune System Warning</b>\nPair #{pid} is persistently stalling. It has been moved to <b>Error Status</b> for manual inspection.")
            return

        logger.warning(f"Immune System: Stall detected on Pair #{pid} (Drift: {drift_mins}m). Initializing healing...")
        
        try:
            # Phase 1: Verify Authorization & Reconnect
            from telethon.sessions import StringSession
            async with async_session() as ds:
                user = await UserRepository(ds).get_user(uid)
                if not user or not user.session_string: return
                
            # Rule: Session Verification before Jumpstart
            client = self.service.telethon.active_clients.get(uid)
            if not client or not client.is_connected():
                logger.info(f"Phase 1: Session for User {uid} disconnected. Resolving...")
                await self.service.telethon.start_listener(uid, user.session_string, self.service._handle_new_message)
            else:
                is_auth = await client.is_user_authorized()
                if not is_auth:
                    logger.critical(f"Phase 1: User {uid} session authorized=False.")
                    return

            # Phase 2: Jumpstart via Force Repost
            logger.info(f"Phase 2: Jumpstarting Pair #{pid}...")
            # We use force_repost_once to bridge the gap and trigger a new loop
            success = await self.service.force_repost_once(uid, pid)
            
            if success:
                logger.info(f"Phase 3: Pair #{pid} Jumpstarted successfully.")
                async with async_session() as ds:
                    await UserRepository(ds).increment_consecutive_heals(pid)
                
                await self.service._notify_user(uid, f"🛡 <b>Heartbeat Restored</b>\nYour Pair #{pid} experienced a silent stall. The Immune System has automatically performed a surgical jumpstart.")
            else:
                logger.error(f"Phase 3: Jumpstart failed for Pair #{pid}.")
        
        except Exception as e:
            logger.error(f"Surgical Healing Exception for Pair #{pid}: {e}")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
