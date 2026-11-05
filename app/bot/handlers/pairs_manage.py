"""
BOT: PAIR MANAGEMENT HANDLERS
Split from pairs.py to comply with line limits.
Handles toggling, looping, and deleting pairs.
"""
import logging
from aiogram import Router, F, types

from app.bot.keyboards import delete_confirm_kb, preset_selection_kb
from app.bot.handlers.utils import (
    render_pairs_view, render_pair_detail_view, repost_service, safe_callback_answer
)
from app.data.database import async_session
from app.data.repository import UserRepository

PRESET_CONFIGS = {
    "aggressive": {"interval": 120, "stars_short": 10, "stars_long": 35, "cadence": 5},
    "monetization": {"interval": 240, "stars_short": 15, "stars_long": 50, "cadence": 4},
    "vip_drip": {"interval": 360, "stars_short": 25, "stars_long": 75, "cadence": 2},
    "custom": {"interval": None, "stars_short": 0, "stars_long": 0, "cadence": 4},
}

logger = logging.getLogger(__name__)
router = Router()

# --- VIEW PAIR DETAIL HANDLERS ---

@router.callback_query(F.data.startswith("pview_"))
async def cb_view_pair_detail(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    pair_id = int(callback.data.split("_")[1])
    await render_pair_detail_view(callback.message, callback.from_user.id, pair_id)


@router.callback_query(F.data.startswith("upview_"))
async def cb_remote_view_pair_detail(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    await safe_callback_answer(callback)
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    await render_pair_detail_view(callback.message, user_id, pair_id, is_remote=True)


# --- STRATEGY PRESET HANDLERS ---

@router.callback_query(F.data.startswith("preset_"))
async def cb_open_preset_menu(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    pairs = await repost_service.get_user_pairs(user_id)
    target = next((p for p in pairs if p.id == pair_id), None)
    if not target:
        return await safe_callback_answer(callback, "❌ Pair not found.", show_alert=True)

    curr_preset = getattr(target, "active_preset", "custom") or "custom"
    src = target.source_display or target.source_id
    dest = target.destination_display or target.destination_id

    text = (
        "⚡ <b>SELECT STRATEGY PRESET</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Pair: <code>{src}</code> ➜ <code>{dest}</code>\n"
        f"Current: <b>{curr_preset.upper()}</b>\n\n"
        "Select an automated schedule &amp; monetization formula:\n\n"
        "🚀 <b>Aggressive Growth</b>\n"
        "• 2h interval • 10 / 35 ⭐ • 1 in 5 monetized\n"
        "• <i>Best for viral public channels rapid scaling</i>\n\n"
        "💰 <b>Monetization Beast</b> (Recommended)\n"
        "• 4h interval • 15 / 50 ⭐ • 1 in 4 monetized\n"
        "• <i>Balanced cashflow &amp; retention sweet-spot</i>\n\n"
        "👑 <b>Exclusive VIP Drip</b>\n"
        "• 6h interval • 25 / 75 ⭐ • 1 in 2 monetized\n"
        "• <i>Premium content high-ticket paywall cadence</i>\n\n"
        "⚪ <b>Custom / OFF</b>\n"
        "• Manual delay &amp; custom rules (Stars off)"
    )

    await callback.message.edit_text(
        text,
        reply_markup=preset_selection_kb(pair_id, curr_preset),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("upreset_"))
async def cb_remote_open_preset_menu(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    await safe_callback_answer(callback)
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])

    pairs = await repost_service.get_user_pairs(user_id)
    target = next((p for p in pairs if p.id == pair_id), None)
    if not target:
        return await safe_callback_answer(callback, "❌ Pair not found.", show_alert=True)

    curr_preset = getattr(target, "active_preset", "custom") or "custom"
    src = target.source_display or target.source_id
    dest = target.destination_display or target.destination_id

    text = (
        f"⚡ <b>[REMOTE] SELECT STRATEGY PRESET (User {user_id})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Pair: <code>{src}</code> ➜ <code>{dest}</code>\n"
        f"Current: <b>{curr_preset.upper()}</b>\n\n"
        "Select an automated schedule &amp; monetization formula:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=preset_selection_kb(pair_id, curr_preset, target_id=user_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("setpreset_"))
async def cb_apply_preset(callback: types.CallbackQuery):
    await safe_callback_answer(callback, "⚡ Applying preset...")
    parts = callback.data.split("_")
    pair_id = int(parts[1])
    preset_key = parts[2]
    user_id = callback.from_user.id

    cfg = PRESET_CONFIGS.get(preset_key, PRESET_CONFIGS["custom"])
    async with async_session() as ds:
        repo = UserRepository(ds)
        await repo.update_pair_preset(
            pair_id=pair_id,
            preset_key=preset_key,
            interval=cfg["interval"],
            stars_short=cfg["stars_short"],
            stars_long=cfg["stars_long"],
            cadence=cfg["cadence"],
        )

    await safe_callback_answer(callback, f"✅ Preset '{preset_key}' applied!")
    await render_pair_detail_view(callback.message, user_id, pair_id)


@router.callback_query(F.data.startswith("usetpreset_"))
async def cb_remote_apply_preset(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    await safe_callback_answer(callback, "⚡ Applying preset...")
    parts = callback.data.split("_")
    user_id, pair_id, preset_key = int(parts[1]), int(parts[2]), parts[3]

    cfg = PRESET_CONFIGS.get(preset_key, PRESET_CONFIGS["custom"])
    async with async_session() as ds:
        repo = UserRepository(ds)
        await repo.update_pair_preset(
            pair_id=pair_id,
            preset_key=preset_key,
            interval=cfg["interval"],
            stars_short=cfg["stars_short"],
            stars_long=cfg["stars_long"],
            cadence=cfg["cadence"],
        )

    await safe_callback_answer(callback, f"✅ Preset '{preset_key}' applied!")
    await render_pair_detail_view(callback.message, user_id, pair_id, is_remote=True)


# --- TOGGLE & LIST HANDLERS ---

@router.callback_query(F.data.startswith("tog_"))
async def cb_toggle_pair(callback: types.CallbackQuery):
    await safe_callback_answer(callback, "🔄 Processing...") 
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    try:
        pairs = await repost_service.get_user_pairs(user_id)
        target = next((p for p in pairs if p.id == pair_id), None)

        if not target:
            return await safe_callback_answer(callback, "❌ Pair not found.", show_alert=True)

        if target.is_active:
            await repost_service.deactivate_pair(user_id, pair_id)
        else:
            await repost_service.activate_pair(user_id, pair_id)
        
        await render_pair_detail_view(callback.message, user_id, pair_id)
    except Exception as e:
        logger.error(f"Toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Connection lag.", show_alert=True)


@router.callback_query(F.data.startswith("loop_"))
async def cb_toggle_loop(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    try:
        new_state = await repost_service.toggle_pair_recycling(user_id, pair_id)
        status = "ENABLED" if new_state else "DISABLED"
        await safe_callback_answer(callback, f"♻️ Smart Loop: {status}")
        await render_pair_detail_view(callback.message, user_id, pair_id)
    except Exception as e:
        logger.error(f"Loop toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Error updating setting.", show_alert=True)


@router.callback_query(F.data.startswith("prot_"))
async def cb_toggle_protection(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    try:
        new_state = await repost_service.toggle_pair_protection(user_id, pair_id)
        status = "ENABLED" if new_state else "DISABLED"
        await safe_callback_answer(callback, f"🔒 Protected Mode: {status}")
        await render_pair_detail_view(callback.message, user_id, pair_id)
    except Exception as e:
        logger.error(f"Protection toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Error updating setting.", show_alert=True)


@router.callback_query(F.data.startswith("force_"))
async def cb_force_repost(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    await safe_callback_answer(callback, "🚀 Triggering one post...")
    
    success = await repost_service.force_repost_once(user_id, pair_id)
    if success:
        await callback.answer("✅ Success! Check your channel.", show_alert=True)
    else:
        await callback.answer("❌ Failed. Ensure pair is set up and pointer is valid.", show_alert=True)
    await render_pair_detail_view(callback.message, user_id, pair_id)


# --- DELETE LOGIC ---

@router.callback_query(F.data.startswith("del_"))
async def cb_ask_delete(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    pair_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        f"<b>⚠️ Delete this Pair?</b>\n\nThis cannot be undone.",
        reply_markup=delete_confirm_kb(pair_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cdel_"))
async def cb_execute_delete(callback: types.CallbackQuery):
    await safe_callback_answer(callback, "🧨 Deleting...")
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    try:
        if await repost_service.delete_single_pair(user_id, pair_id):
            await render_pairs_view(callback.message, user_id)
        else:
            await safe_callback_answer(callback, "❌ Not found.", show_alert=True)
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        await safe_callback_answer(callback, "⚠️ Error.", show_alert=True)


# --- REMOTE ADMIN HANDLERS ---

@router.callback_query(F.data.startswith("utog_"))
async def cb_remote_toggle(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    
    pairs = await repost_service.get_user_pairs(user_id)
    target = next((p for p in pairs if p.id == pair_id), None)
    if target:
        if target.is_active: await repost_service.deactivate_pair(user_id, pair_id)
        else: await repost_service.activate_pair(user_id, pair_id)
        await render_pair_detail_view(callback.message, user_id, pair_id, is_remote=True)
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("uloo_"))
async def cb_remote_loop(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    await repost_service.toggle_pair_recycling(user_id, pair_id)
    await render_pair_detail_view(callback.message, user_id, pair_id, is_remote=True)
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("uprot_"))
async def cb_remote_prot(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    await repost_service.toggle_pair_protection(user_id, pair_id)
    await render_pair_detail_view(callback.message, user_id, pair_id, is_remote=True)
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("uforce_"))
async def cb_remote_force(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    await safe_callback_answer(callback, "🚀 Triggering remote post...")
    await repost_service.force_repost_once(user_id, pair_id)
    await render_pair_detail_view(callback.message, user_id, pair_id, is_remote=True)

@router.callback_query(F.data.startswith("udel_"))
async def cb_remote_ask_delete(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    await callback.message.edit_text(
        f"<b>⚠️ Remote Delete: Pair #{pair_id} (User {user_id})?</b>\n\nThis cannot be undone.",
        reply_markup=delete_confirm_kb(pair_id, target_id=user_id),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("ucdel_"))
async def cb_remote_execute_delete(callback: types.CallbackQuery):
    if not await repost_service.is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    await repost_service.delete_single_pair(user_id, pair_id)
    await render_pairs_view(callback.message, user_id, is_remote=True)
    await safe_callback_answer(callback, "🧨 Deleted remotely.")
