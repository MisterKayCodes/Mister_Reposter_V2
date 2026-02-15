"""
BOT: PAIR HANDLERS
Complete flow for creating, toggling, and deleting repost pairs.
Matches states.py and keyboards.py word-to-word.
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

# --- UTILS ---

async def safe_callback_answer(callback: types.CallbackQuery, text: str = None, show_alert: bool = False):
    """Rule 12: Prevents 'Query is too old' crashes."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest:
        pass

async def handle_channel_input(message: types.Message, state: FSMContext, step_name: str):
    """Rule 5 & 16: Standardized resolution logic."""
    if message.text and message.text.startswith("/"):
        return await message.answer("Please provide a channel, not a command.")

    resolved = resolve_channel_input(
        message.text if not message.forward_from_chat else None, 
        forwarded_chat=message.forward_from_chat
    )

    if not resolved["identifier"]:
        await message.answer(
            "Could not parse that input.\n"
            "Try a link, @username, or forward a message from the channel."
        )
        return None

    await state.update_data({
        f"{step_name}_id": resolved["identifier"],
        f"{step_name}_kind": resolved["kind"],
        f"{step_name}_invite_hash": resolved.get("invite_hash"),
    })
    return resolved

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
        
        await render_pairs_view(callback.message, user_id)
    except Exception as e:
        logger.error(f"Toggle failed: {e}")
        await safe_callback_answer(callback, "⚠️ Connection lag.", show_alert=True)

# --- CREATE FLOW (FSM) ---

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
    await callback.message.edit_text("Create Pair (1/5)\n\nSend the source channel (Link, @Username, or Forward a message).", reply_markup=cancel_kb())

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

    await message.answer("Create Pair (3/5)\n\nChoose a filter mode:", reply_markup=filter_kb())
    await state.set_state(CreatePair.waiting_for_filter)

@router.callback_query(F.data.startswith("setfilt_"), CreatePair.waiting_for_filter)
async def process_filter_choice(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    filter_mode = int(callback.data.split("_")[1])
    await state.update_data(filter_type=filter_mode)

    if filter_mode == 2:
        await callback.message.edit_text("Create Pair (4/5)\n\nSend the replacement link/text:", reply_markup=cancel_kb())
        await state.set_state(CreatePair.waiting_for_replacement)
    else:
        await callback.message.edit_text("Create Pair (5/5)\n\nChoose schedule:", reply_markup=schedule_kb())
        await state.set_state(CreatePair.waiting_for_schedule)

@router.message(CreatePair.waiting_for_replacement)
async def process_replacement(message: types.Message, state: FSMContext):
    if not message.text or message.text.startswith("/"):
        return await message.answer("Please send valid replacement text.")
    
    await state.update_data(replacement_link=message.text.strip())
    await message.answer("Create Pair (5/5)\n\nChoose schedule:", reply_markup=schedule_kb())
    await state.set_state(CreatePair.waiting_for_schedule)

@router.callback_query(F.data.startswith("setsched_"), CreatePair.waiting_for_schedule)
async def process_schedule_choice(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    interval = int(callback.data.split("_")[1])
    await state.update_data(schedule_interval=interval)

    await callback.message.edit_text(
        "<b>Almost Done!</b>\n\nSend a message ID to start backfilling from, or skip to start from now.",
        reply_markup=start_msg_kb(),
        parse_mode="HTML"
    )
    await state.set_state(CreatePair.waiting_for_start_message)

@router.message(CreatePair.waiting_for_start_message)
async def process_start_message(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Please send a numeric ID or press Skip.")
    
    await state.update_data(start_from_msg_id=int(message.text))
    await _show_preview(message, state)

@router.callback_query(F.data == "skip_start_msg", CreatePair.waiting_for_start_message)
async def cb_skip_start_msg(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    await state.update_data(start_from_msg_id=None)
    await _show_preview(callback.message, state)

async def _show_preview(target: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        return await target.answer("❌ Session expired. Try again.", reply_markup=main_menu_kb())

    source = data['source_id']
    dest = data['destination_id']
    filt = FILTER_LABELS.get(data['filter_type'], "Unknown")
    sched = SCHEDULE_LABELS.get(data['schedule_interval'], "Instant")
    backfill = f"Message #{data['start_from_msg_id']}" if data.get('start_from_msg_id') else "Next new message"

    summary = (
        "<b>🔍 Review Your Pair</b>\n\n"
        f"<b>Source:</b> <code>{source}</code>\n"
        f"<b>Destination:</b> <code>{dest}</code>\n"
        f"<b>Filter:</b> {filt}\n"
        f"<b>Schedule:</b> {sched}\n"
        f"<b>Start From:</b> {backfill}\n\n"
        "Does this look correct?"
    )

    if isinstance(target, types.Message):
        await target.answer(summary, reply_markup=confirm_pair_kb(), parse_mode="HTML")
    else:
        await target.edit_text(summary, reply_markup=confirm_pair_kb(), parse_mode="HTML")
    
    await state.set_state(CreatePair.waiting_for_confirmation)

@router.callback_query(F.data == "confirm_pair", CreatePair.waiting_for_confirmation)
async def cb_confirm_pair(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback, "⚙️ Finalizing...")
    data = await state.get_data()
    if not data: return

    user_id = callback.from_user.id
    try:
        await repost_service.add_new_pair(
            user_id=user_id,
            source=data["source_id"],
            destination=data["destination_id"],
            filter_type=data["filter_type"],
            replacement_link=data.get("replacement_link"),
            schedule_interval=data["schedule_interval"] or None,
            start_from_msg_id=data.get("start_from_msg_id"),
        )
        await callback.message.edit_text("<b>✅ Pair Created!</b>", reply_markup=main_menu_kb(True, user_id in ADMIN_IDS), parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logger.error(f"Create failed: {e}")
        await callback.message.answer("⚠️ Database error. Try clicking Confirm again.", reply_markup=confirm_pair_kb())

# --- DELETE LOGIC ---

@router.callback_query(F.data.startswith("del_"))
async def cb_ask_delete(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    pair_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        f"<b>⚠️ Delete Pair #{pair_id}?</b>\n\nThis cannot be undone.",
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