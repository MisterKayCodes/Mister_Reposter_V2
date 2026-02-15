"""
BOT: PAIR HANDLERS
Create pair flow (5-step FSM), toggle, delete.
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from bot.states import CreatePair
from bot.keyboards import (
    MAX_PAIRS, SCHEDULE_LABELS, FILTER_LABELS,
    cancel_kb, filter_kb, schedule_kb,
    delete_confirm_kb, session_required_kb,
    limit_reached_kb, main_menu_kb, start_msg_kb,
    confirm_pair_kb,
)
from bot.handlers.utils import render_pairs_view, repost_service
from core.repost.resolver import resolve_channel_input
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()

# --- UTILS (Rule 8: Boring code is good code) ---

async def safe_callback_answer(callback: types.CallbackQuery, text: str = None, show_alert: bool = False):
    """Rule 12: Handle errors explicitly. Prevents 'Query is too old' crashes."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest:
        pass

async def handle_channel_input(message: types.Message, state: FSMContext, step_name: str):
    """Rule 5 & 16: Reduced repetition for source/destination logic."""
    if message.text and message.text.startswith("/"):
        return await message.answer("Please provide a channel, not a command.")

    # Rule 11: Business logic (resolving) is separate from the handler
    resolved = resolve_channel_input(
        message.text if not message.forward_from_chat else None, 
        forwarded_chat=message.forward_from_chat
    )

    if not resolved["identifier"]:
        return await message.answer(
            "Could not parse that input.\n"
            "Try a link, @username, or forward a message from the channel."
        )

    await state.update_data({
        f"{step_name}_id": resolved["identifier"],
        f"{step_name}_kind": resolved["kind"],
        f"{step_name}_invite_hash": resolved.get("invite_hash"),
    })
    return resolved

# --- HANDLERS ---

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
        
        await render_pairs_view(callback.message, user_id)
    except Exception as e:
        logger.error(f"Toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Connection lag.", show_alert=True)

@router.callback_query(F.data == "create")
async def cb_create_pair(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback, "🔨 Starting setup...")
    user_id = callback.from_user.id

    if not await repost_service.user_has_session(user_id):
        return await callback.message.edit_text("Session Required", reply_markup=session_required_kb())

    pairs = await repost_service.get_user_pairs(user_id)
    if len(pairs) >= MAX_PAIRS:
        return await callback.message.edit_text(f"Limit Reached ({MAX_PAIRS})", reply_markup=limit_reached_kb())

    await state.set_state(CreatePair.waiting_for_source)
    await callback.message.edit_text("Create Pair (1/5)\n\nSend the source channel.", reply_markup=cancel_kb())

@router.message(CreatePair.waiting_for_source)
async def process_source(message: types.Message, state: FSMContext):
    resolved = await handle_channel_input(message, state, "source")
    if not resolved: return

    display = resolved["identifier"] if resolved["kind"] != "invite" else f"Private ({resolved['invite_hash'][:8]}...)"
    await message.answer(f"Source: {display}\n\nCreate Pair (2/5)\n\nSend the destination channel.", reply_markup=cancel_kb())
    await state.set_state(CreatePair.waiting_for_destination)

@router.message(CreatePair.waiting_for_destination)
async def process_destination(message: types.Message, state: FSMContext):
    resolved = await handle_channel_input(message, state, "destination")
    if not resolved: return

    await message.answer("Create Pair (3/5)\n\nChoose a filter:", reply_markup=filter_kb())
    await state.set_state(CreatePair.waiting_for_filter)

@router.callback_query(F.data.startswith("setfilt_"))
async def process_filter_choice(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    filter_mode = int(callback.data.split("_")[1])
    await state.update_data(filter_type=filter_mode)

    if filter_mode == 2:
        await callback.message.edit_text("Create Pair (4/5)\n\nSend replacement text:", reply_markup=cancel_kb())
        await state.set_state(CreatePair.waiting_for_replacement)
    else:
        await callback.message.edit_text("Create Pair (5/5)\n\nChoose schedule:", reply_markup=schedule_kb())
        await state.set_state(CreatePair.waiting_for_schedule)

@router.callback_query(F.data == "confirm_pair")
async def cb_confirm_pair(callback: types.CallbackQuery, state: FSMContext):
    # Rule 7: Design for recovery. Answer first, then do the heavy DB work.
    await safe_callback_answer(callback, "⚙️ Finalizing pair...")
    
    data = await state.get_data()
    if not data:
        return await callback.message.answer("❌ Session expired. Try again.", reply_markup=main_menu_kb(True))

    user_id = callback.from_user.id
    try:
        # Rule 11: Integration call
        await repost_service.add_new_pair(
            user_id=user_id,
            source=data.get("resolved_source", data["source_id"]),
            destination=data.get("resolved_dest", data["destination_id"]),
            filter_type=data.get("filter_type", 1),
            replacement_link=data.get("replacement_link"),
            schedule_interval=data.get("schedule_interval") or None,
            start_from_msg_id=data.get("start_from_msg_id"),
        )

        await callback.message.edit_text("<b>✅ Pair Created!</b>\n\nReturning to menu...", 
                                      reply_markup=main_menu_kb(True, user_id in ADMIN_IDS), 
                                      parse_mode="HTML")
        await state.clear() # Rule 1: Clear state only on success

    except Exception as e:
        logger.error(f"Rule 12: Fail for {user_id}: {e}")
        await callback.message.answer("⚠️ Database busy. Please tap **Confirm** again.", reply_markup=confirm_pair_kb())