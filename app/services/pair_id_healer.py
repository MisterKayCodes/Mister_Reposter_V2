"""
SERVICES: PAIR ID HEALER
Startup task that scans existing database pairs and auto-heals non-numeric
channel usernames into permanent, bulletproof numeric Telegram IDs (-100...).
"""
import logging
from app.data.database import async_session
from app.data.repository import UserRepository

logger = logging.getLogger(__name__)

async def heal_all_pair_ids(repost_service):
    """Scans all existing pairs and resolves non-numeric IDs upfront."""
    logger.info("🩺 [Healer] Starting background channel ID auto-healing check...")
    healed_count = 0
    failed_count = 0
    
    try:
        async with async_session() as ds:
            repo = UserRepository(ds)
            users = await repo.get_all_users()
            
            for u in users:
                pairs = await repo.get_user_pairs(u.id)
                for p in pairs:
                    needs_update = False
                    new_src_id = p.source_id
                    new_dest_id = p.destination_id
                    
                    # 1. Check Source ID
                    clean_src = str(p.source_id).replace("-100", "").replace("-", "")
                    if not clean_src.isdigit():
                        logger.info(f"🩺 [Healer] Resolving non-numeric source for Pair #{p.id}: '{p.source_id}'...")
                        resolved = await repost_service.resolve_channel_id(u.id, p.source_id)
                        if resolved:
                            new_src_id = resolved
                            needs_update = True
                            logger.info(f"✨ [Healer] Healed Pair #{p.id} source '{p.source_id}' -> '{resolved}'")
                        else:
                            failed_count += 1
                            logger.warning(f"⚠️ [Healer] Could not resolve source '{p.source_id}' for Pair #{p.id}. Leaving as-is.")
                    
                    # 2. Check Destination ID
                    clean_dest = str(p.destination_id).replace("-100", "").replace("-", "")
                    if not clean_dest.isdigit() and not ("+" in str(p.destination_id) or "joinchat" in str(p.destination_id)):
                        logger.info(f"🩺 [Healer] Resolving non-numeric destination for Pair #{p.id}: '{p.destination_id}'...")
                        resolved = await repost_service.resolve_channel_id(u.id, p.destination_id)
                        if resolved:
                            new_dest_id = resolved
                            needs_update = True
                            logger.info(f"✨ [Healer] Healed Pair #{p.id} destination '{p.destination_id}' -> '{resolved}'")
                        else:
                            failed_count += 1
                            logger.warning(f"⚠️ [Healer] Could not resolve destination '{p.destination_id}' for Pair #{p.id}. Leaving as-is.")
                    
                    # Apply updates if any resolved
                    if needs_update:
                        p.source_id = str(new_src_id)
                        p.destination_id = str(new_dest_id)
                        healed_count += 1

            if healed_count > 0:
                await ds.commit()
                logger.info(f"🎉 [Healer] Successfully healed {healed_count} pair ID(s) in database!")
            else:
                logger.info("🩺 [Healer] All pair IDs are already numeric or up to date.")
                
    except Exception as e:
        logger.error(f"❌ [Healer] Unexpected error during ID auto-healing: {e}")
