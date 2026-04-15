"""
BOT: KEYBOARDS
All inline keyboard builders live here.
The Mouth's button rack — separated for clean architecture.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder

MAX_PAIRS = 4

SCHEDULE_LABELS = {
    0: "Instant",
    5: "5 Minutes",
    15: "15 Minutes",
    30: "30 Minutes",
    60: "1 Hour",
    120: "2 Hours",
    240: "4 Hours",
    480: "8 Hours",
    720: "12 Hours",
    1440: "24 Hours",
}

FILTER_LABELS = {
    0: "Keep Original",
    1: "Remove Links",
    2: "Replace Links",
}


def main_menu_kb(has_session: bool = False, is_admin: bool = False):
    builder = InlineKeyboardBuilder()
    if not has_session:
        builder.button(text="☁️ Upload Session", callback_data="upload")
    builder.button(text="➕ Create Pair", callback_data="create")
    builder.button(text="👥 My Pairs", callback_data="pairs")
    builder.button(text="📊 Stats", callback_data="stats")
    if has_session:
        builder.button(text="🔑 Get Session", callback_data="get_session")
    if is_admin:
        builder.button(text="📜 Logs", callback_data="logs")
        builder.button(text="👤 Manage Users", callback_data="admin_users")
    builder.button(text="🗑️ Delete All", callback_data="delall")
    
    # Adjust layout based on role and session
    if not has_session and is_admin:
        builder.adjust(1, 2, 2, 1)
    elif not has_session:
        builder.adjust(1, 2, 1)
    elif is_admin:
        builder.adjust(2, 2, 2, 1)
    else:
        builder.adjust(2, 2, 1)
    return builder.as_markup()


def pairs_kb(pairs):
    builder = InlineKeyboardBuilder()
    for idx, p in enumerate(pairs, 1):
        if getattr(p, "status", "") == "error":
            label = "🔄 Clear"
        else:
            label = "Pause" if p.is_active else "Play"
        builder.button(text=f"{label} #{idx}", callback_data=f"tog_{p.id}")
        
        loop_label = "♻️ Loop: ON" if getattr(p, "loop_history", False) else "♻️ Loop: OFF"
        builder.button(text=loop_label, callback_data=f"loop_{p.id}")
        
        builder.button(text=f"Delete #{idx}", callback_data=f"del_{p.id}")
    if len(pairs) < MAX_PAIRS:
        builder.button(text="+ New Pair", callback_data="create")
    builder.button(text="Back", callback_data="main")
    builder.adjust(2)
    return builder.as_markup()


def back_kb(target="main"):
    builder = InlineKeyboardBuilder()
    builder.button(text="Back", callback_data=target)
    return builder.as_markup()


def cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Cancel", callback_data="main")
    return builder.as_markup()


def filter_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Remove All Links", callback_data="setfilt_1")
    builder.button(text="Replace with Mine", callback_data="setfilt_2")
    builder.button(text="Keep Original", callback_data="setfilt_0")
    builder.button(text="Cancel", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def schedule_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Instant (Real-time)", callback_data="setsched_0")
    builder.button(text="5 Minutes", callback_data="setsched_5")
    builder.button(text="15 Minutes", callback_data="setsched_15")
    builder.button(text="30 Minutes", callback_data="setsched_30")
    builder.button(text="1 Hour", callback_data="setsched_60")
    builder.button(text="2 Hours", callback_data="setsched_120")
    builder.button(text="4 Hours", callback_data="setsched_240")
    builder.button(text="8 Hours", callback_data="setsched_480")
    builder.button(text="12 Hours", callback_data="setsched_720")
    builder.button(text="24 Hours", callback_data="setsched_1440")
    builder.button(text="Cancel", callback_data="main")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def delete_confirm_kb(pair_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, Delete", callback_data=f"cdel_{pair_id}")
    builder.button(text="Cancel", callback_data="pairs")
    builder.adjust(2)
    return builder.as_markup()


def delete_all_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, Delete Everything", callback_data="delall_yes")
    builder.button(text="Cancel", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def session_required_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Upload Session", callback_data="upload")
    builder.button(text="Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def limit_reached_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="My Pairs", callback_data="pairs")
    builder.button(text="Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def empty_pairs_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Create Pair", callback_data="create")
    builder.button(text="Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def start_msg_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip", callback_data="skip_start_msg")
    builder.button(text="Cancel", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def confirm_pair_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Confirm", callback_data="confirm_pair")
    builder.button(text="Cancel", callback_data="main")
    builder.adjust(2)
    return builder.as_markup()


def logs_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Refresh", callback_data="logs")
    builder.button(text="Back", callback_data="main")
    builder.adjust(2)
    return builder.as_markup()


def stats_pairs_kb(pairs):
    builder = InlineKeyboardBuilder()
    for idx, p in enumerate(pairs, 1):
        builder.button(text=f"📊 Pair #{idx}", callback_data=f"statp_{p.id}")
    builder.button(text="🔙 Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def stats_detail_kb(pair_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh", callback_data=f"refr_{pair_id}")
    builder.button(text="🔙 Back to Stats", callback_data="stats")
    builder.adjust(1)
    return builder.as_markup()


# --- CLIENT-FACING KEYBOARDS (SIMPLE UI) ---

def client_main_menu_kb():
    """Simple menu for paying clients."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏸ Pause All", callback_data="c_pauseall")
    builder.button(text="📊 My Stats", callback_data="c_stats")
    builder.button(text="💬 Contact Support", callback_data="c_support")
    builder.adjust(1)
    return builder.as_markup()


def client_channels_kb(pairs):
    """Lists client channels with simple options."""
    builder = InlineKeyboardBuilder()
    for p in pairs:
        # Use destination_id since that's their channel
        name = p.destination_id
        if len(name) > 20: 
            name = name[:17] + "..."
        
        status_label = "⏸ Pause" if p.is_active else "▶️ Resume"
        builder.button(text=f"{status_label} {name}", callback_data=f"c_tog_{p.id}")
        builder.button(text=f"📊 Stats {name}", callback_data=f"c_statp_{p.id}")
        
    builder.button(text="🔙 Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


def client_stats_kb(pair_id: int):
    """Simple back button for stats."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh", callback_data=f"c_refr_{pair_id}")
    builder.button(text="🔙 Back", callback_data="c_stats")
    builder.adjust(1)
    return builder.as_markup()


def client_support_kb():
    """Link to admin for help."""
    builder = InlineKeyboardBuilder()
    # Replace with your actual username in production or make dynamic
    builder.button(text="💬 Message Owner", url="https://t.me/MisterKayCodes") 
    builder.button(text="🔙 Back", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()

def admin_users_kb(users):
    """List of all registered users."""
    builder = InlineKeyboardBuilder()
    for u in users:
        label = f"{u.id}"
        if u.username: label += f" (@{u.username})"
        builder.button(text=label, callback_data=f"uview_{u.id}")
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
    
    builder.button(text="📋 View Pairs", callback_data=f"upairs_{user_id}")
    builder.button(text="🔙 Back to Users", callback_data="admin_users")
    builder.adjust(1)
    return builder.as_markup()
