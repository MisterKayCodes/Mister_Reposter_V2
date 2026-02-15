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
        builder.button(text="Upload Session", callback_data="upload")
    builder.button(text="Create Pair", callback_data="create")
    builder.button(text="My Pairs", callback_data="pairs")
    if is_admin:
        builder.button(text="Logs", callback_data="logs")
    builder.button(text="Delete All", callback_data="delall")
    if not has_session and is_admin:
        builder.adjust(1, 2, 2, 1)
    elif not has_session:
        builder.adjust(1, 2, 1)
    elif is_admin:
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(2, 1)
    return builder.as_markup()


def pairs_kb(pairs):
    builder = InlineKeyboardBuilder()
    for p in pairs:
        label = "Pause" if p.is_active else "Play"
        builder.button(text=f"{label} #{p.id}", callback_data=f"tog_{p.id}")
        builder.button(text=f"Delete #{p.id}", callback_data=f"del_{p.id}")
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
