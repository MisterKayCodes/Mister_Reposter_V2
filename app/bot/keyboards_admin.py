"""
BOT: ADMIN KEYBOARDS
Functions specifically for management and system configuration.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder

def bot_settings_kb():
    """Menu to manage system variables."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Import Session", callback_data="upload")
    builder.button(text="💬 Edit Support Username", callback_data="edit_owner_user")
    builder.button(text="🔙 Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()

def admin_users_kb(users):
    """List of all registered users."""
    builder = InlineKeyboardBuilder()
    for u in users:
        prefix = "" if u.has_active_session else "⚠️ "
        label = f"{prefix}{u.id}"
        if u.username: label += f" (@{u.username})"
        builder.button(text=label, callback_data=f"uview_{u.id}")
    builder.button(text="🧹 Purge Invalid", callback_data="upurge_bad")
    builder.button(text="🔙 Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()

def user_detail_kb(user_id: int, target_is_admin: bool, target_is_premium: bool):
    """Detailed management for a specific user."""
    builder = InlineKeyboardBuilder()
    
    admin_label = "❌ Revoke Admin" if target_is_admin else "👑 Promote to Admin"
    builder.button(text=admin_label, callback_data=f"uprom_{user_id}")
    
    prem_label = "💎 Extend Premium" if target_is_premium else "💎 Grant Premium (1mo)"
    builder.button(text=prem_label, callback_data=f"uprem_{user_id}")
    
    builder.button(text="🔄 Reconnect Session", callback_data=f"ureconn_{user_id}")
    builder.button(text="🗑️ Delete User", callback_data=f"uacc_confirm_{user_id}")
    builder.button(text="➕ Create Pair", callback_data=f"uaddpair_{user_id}")
    builder.button(text="📋 View Pairs", callback_data=f"upairs_{user_id}")
    builder.button(text="📊 View Stats", callback_data=f"ustat_{user_id}")
    builder.button(text="🔙 Back to Users", callback_data="admin_users")
    builder.adjust(2, 2, 1, 1, 1, 1)
    return builder.as_markup()

def admin_stats_pairs_kb(user_id: int, pairs):
    """Admin view of user's stats list."""
    builder = InlineKeyboardBuilder()
    for idx, p in enumerate(pairs, 1):
        builder.button(text=f"📊 Pair #{idx}", callback_data=f"ustp_{user_id}_{p.id}")
    builder.button(text="🔙 Back to User", callback_data=f"uview_{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def admin_stats_detail_kb(user_id: int, pair_id: int):
    """Admin view of specific pair stats."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh", callback_data=f"uref_{user_id}_{pair_id}")
    builder.button(text="🔙 Back to List", callback_data=f"ustat_{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def delete_user_confirm_kb(user_id: int):
    """Safety check for user deletion."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🧨 Yes, DELETE USER", callback_data=f"uacc_del_{user_id}")
    builder.button(text="🔙 Cancel", callback_data=f"uview_{user_id}")
    builder.adjust(1)
    return builder.as_markup()
