import asyncio
import json
import os

# File to store verified users
VERIFIED_FILE = "data/verified_alerts.json"

def load_verified_users():
    """Load list of verified user IDs"""
    try:
        with open(VERIFIED_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

async def inventory_monitor_loop(bot):
    """Run every hour, check inventory, send alerts to verified users"""
    while True:
        await asyncio.sleep(3600)  # Wait 1 hour
        
        try:
            from app.services.singleton import repost_service
            
            # Get all pairs
            pairs = await repost_service.get_all_pairs()
            
            # Get verified users
            verified_users = load_verified_users()
            
            if not verified_users:
                continue
            
            # Check each pair
            alerts_by_user = {}
            
            for pair in pairs:
                total = pair.total_posts_source or 0
                current = pair.start_from_msg_id or 1
                
                if total <= 0:
                    continue
                
                remaining = total - current
                if remaining <= 0:
                    continue
                
                interval_min = pair.schedule_interval or 60
                days_left = (remaining * interval_min) / (24 * 60)
                
                alert_text = None
                if days_left <= 1:
                    alert_text = f"🔴 **CRITICAL** Pair #{pair.id}\nSource: {pair.source_id}\nProgress: {current}/{total} ({int(current/total*100)}%)\n⚠️ ONLY 1 DAY LEFT!\n\n"
                elif days_left <= 3:
                    alert_text = f"🟡 **WARNING** Pair #{pair.id}\nSource: {pair.source_id}\nProgress: {current}/{total} ({int(current/total*100)}%)\n📅 {int(days_left)} days left\n\n"
                elif days_left <= 7:
                    alert_text = f"🟢 **INFO** Pair #{pair.id}\nSource: {pair.source_id}\nProgress: {current}/{total} ({int(current/total*100)}%)\n📅 {int(days_left)} days left\n\n"
                
                if alert_text:
                    for user_id in verified_users:
                        if user_id not in alerts_by_user:
                            alerts_by_user[user_id] = []
                        alerts_by_user[user_id].append(alert_text)
            
            # Send alerts
            for user_id, alerts in alerts_by_user.items():
                if alerts:
                    message = "📊 **INVENTORY REPORT**\n\n" + "\n".join(alerts)
                    try:
                        await bot.send_message(user_id, message)
                    except Exception as e:
                        print(f"Failed to send to {user_id}: {e}")
                        
        except Exception as e:
            print(f"Inventory monitor error: {e}")