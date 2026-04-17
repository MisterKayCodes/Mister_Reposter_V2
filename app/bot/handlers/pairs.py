"""
BOT: PAIR CREATION FLOW (FSM)
Refactored to meet line limits (Rule 3).
Handles the step-by-step setup of new repost pairs.
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from app.bot.states import CreatePair
from app.bot.keyboards import (
    MAX_PAIRS, cancel_kb, filter_kb, schedule_kb,
    session_required_kb, limit_reached_kb, main_menu_kb, 
    start_msg_kb, confirm_pair_kb, FILTER_LABELS, SCHEDULE_LABELS
)
from app.bot.handlers.utils import (
    repost_service, safe_callback_answer, handle_channel_input
)
from app.core.config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()

# --- CREATE FLOW (FSM) ---

@router.callback_query(F.data == "create")
async def cb_create_pair(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback, "🔨 Starting setup...")
    user_id = callback.from_user.id
    is_admin = await repost_service.is_admin(user_id)

    if not is_admin:
        await callback.answer("Please contact support to add new channels.", show_alert=True)
        return

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

@router.callback_query(F.data.startswith("uaddpair_"))
async def cb_admin_create_pair(callback: types.CallbackQuery, state: FSMContext):
    """Admin entry point to create a pair for someone else."""
    await safe_callback_answer(callback, "🔨 Starting remote setup...")
    user_id = callback.from_user.id
    target_id = int(callback.data.split("_")[1])
    
    # Security check
    if not await repost_service.is_admin(user_id):
        return await callback.answer("Admin only.", show_alert=True)

    # Context setup
    await state.clear()
    await state.update_data(target_user_id=target_id)
    
    # Verify session on Target
    if not await repost_service.user_has_session(target_id):
        await callback.message.answer(f"⚠️ User {target_id} has no session linked. Cannot create pair.")
        return

    await state.set_state(CreatePair.waiting_for_source)
    await callback.message.edit_text(
        f"<b>Remote Setup: Pair for {target_id} (1/5)</b>\n\nSend source channel.",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "confirm_pair", CreatePair.waiting_for_confirmation)
async def cb_confirm_pair(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback, "⚙️ Finalizing...")
    data = await state.get_data()
    if not data: return

    admin_id = callback.from_user.id
    target_id = data.get("target_user_id", admin_id)
    
    try:
        await repost_service.add_new_pair(
            user_id=target_id,
            source=data["source_id"],
            destination=data["destination_id"],
            source_display=data.get("source_display"),
            destination_display=data.get("destination_display"),
            filter_type=data["filter_type"],
            replacement_link=data.get("replacement_link"),
            schedule_interval=data["schedule_interval"] or None,
            start_from_msg_id=data.get("start_from_msg_id"),
        )
        
        if target_id != admin_id:
            from app.bot.keyboards_admin import user_detail_kb
            from app.data.database import async_session as ds_gen
            from app.data.repository import UserRepository
            
            async with ds_gen() as ds:
                repo = UserRepository(ds)
                target_user = await repo.get_user(target_id)
                kb = user_detail_kb(target_id, target_user.is_admin, target_user.is_premium)
                
            await callback.message.edit_text(f"<b>✅ Pair Created for User {target_id}!</b>", reply_markup=kb, parse_mode="HTML")
        else:
            is_adm = await repost_service.is_admin(admin_id)
            await callback.message.edit_text("<b>✅ Pair Created!</b>", reply_markup=main_menu_kb(True, is_adm), parse_mode="HTML")
            
        await state.clear()
    except Exception as e:
        logger.error(f"Create failed: {e}")
        await callback.message.answer("⚠️ Database error. Try clicking Confirm again.", reply_markup=confirm_pair_kb())
