"""
SERVICES: STATS SERVICE
Logic for calculating reposting progress and time estimates. (Rule 3)
"""
import time
import logging
from app.data.database import async_session
from app.data.repository import UserRepository

logger = logging.getLogger(__name__)

async def get_pair_stats(service, user_id: int, pair_id: int):
    """Calculates real-time stats by bridging DB and Telethon."""
    async with async_session() as ds:
        repo = UserRepository(ds)
        pair = await repo.get_pair_by_id(pair_id)
        if not pair: return None
        
        total = await service.telethon.get_total_messages(user_id, pair.source_id)
        if total >= 0:
            await repo.update_pair_total_posts(pair_id, total)
            pair.total_posts_source = total
        
        current = pair.start_from_msg_id or 1
        remaining = max(0, total - current) if total > 0 else 0
        time_left_min = remaining * (pair.schedule_interval or 0)
        
        # Rule 11: Lazy Healing for display names
        src_disp = pair.source_display or pair.source_id
        dest_disp = pair.destination_display or pair.destination_id
        
        if not pair.source_display or not pair.destination_display:
            try:
                # Try to resolve names if they are numeric IDs
                if not pair.source_display:
                    res = await service.telethon.resolve_entity(user_id, pair.source_id)
                    if res: 
                        pair.source_display = res.get("title") or res.get("id")
                        src_disp = pair.source_display
                if not pair.destination_display:
                    res = await service.telethon.resolve_entity(user_id, pair.destination_id)
                    if res: 
                        pair.destination_display = res.get("title") or res.get("id")
                        dest_disp = pair.destination_display
                await ds.commit()
            except Exception: pass

        return {
            "id": pair_id, "current": current, "total": total,
            "remaining": remaining, "time_left_min": time_left_min,
            "source": src_disp, "destination": dest_disp,
            "schedule": pair.schedule_interval, "is_active": pair.is_active,
            "next_post": service.next_post_info.get(pair_id),
            "loop_history": pair.loop_history,
            "last_error": service.last_errors.get(pair_id) if pair.status == "error" else None
        }
