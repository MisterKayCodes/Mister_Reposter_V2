"""
BOT: PAIR CREATION FLOW (FSM)
Refactored to meet line limits (Rule 3).
Handles the step-by-step setup of new repost pairs.
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from app.bot.states import CreatePair, FastLaunch
from app.bot.keyboards import (
    MAX_PAIRS, cancel_kb, filter_kb, schedule_kb,
    session_required_kb, limit_reached_kb, main_menu_kb, 
    start_msg_kb, confirm_pair_kb, FILTER_LABELS, SCHEDULE_LABELS
)
from app.bot.handlers.utils import (
    repost_service, safe_callback_answer, handle_channel_input
)
from app.services.session_manager import SessionService
from app.data.database import async_session
from app.data.repository import UserRepository
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

    data = await state.get_data()
    target_id = data.get("target_user_id", message.from_user.id)
    raw_id = resolved["identifier"]

    # Upfront resolution check
    status_msg = await message.answer(f"🔍 Resolving <code>{resolved['display_name']}</code>...", parse_mode="HTML")
    numeric_id = await repost_service.resolve_channel_id(target_id, raw_id)
    
    if numeric_id:
        await state.update_data(source_id=numeric_id)
        await status_msg.edit_text(
            f"✅ <b>Source Resolved:</b> {resolved['display_name']} (<code>{numeric_id}</code>)\n\n"
            f"<b>Create Pair (2/5)</b>\n\nSend the destination channel (Link, @Username, or Forward a message).",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
    else:
        # Fallback: retain raw identifier if resolution was not possible immediately, but notify user
        await status_msg.edit_text(
            f"⚠️ <b>Source Saved:</b> {resolved['display_name']}\n"
            f"<i>(Note: Channel couldn't be resolved to numeric ID upfront. Auto-healer will attempt resolution in background.)</i>\n\n"
            f"<b>Create Pair (2/5)</b>\n\nSend the destination channel.",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )

    await state.set_state(CreatePair.waiting_for_destination)

@router.message(CreatePair.waiting_for_destination)
async def process_destination(message: types.Message, state: FSMContext):
    resolved = await handle_channel_input(message, state, "destination")
    if not resolved: return

    data = await state.get_data()
    target_id = data.get("target_user_id", message.from_user.id)
    raw_id = resolved["identifier"]

    status_msg = await message.answer(f"🔍 Resolving <code>{resolved['display_name']}</code>...", parse_mode="HTML")
    numeric_id = await repost_service.resolve_channel_id(target_id, raw_id)

    if numeric_id:
        await state.update_data(destination_id=numeric_id)
        await status_msg.edit_text(
            f"✅ <b>Destination Resolved:</b> {resolved['display_name']} (<code>{numeric_id}</code>)\n\n"
            f"<b>Create Pair (3/5)</b>\n\nChoose a filter mode:",
            reply_markup=filter_kb(),
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            f"<b>Create Pair (3/5)</b>\n\nChoose a filter mode:",
            reply_markup=filter_kb(),
            parse_mode="HTML"
        )

    await state.set_state(CreatePair.waiting_for_filter)

@router.callback_query(F.data.startswith("setfilt_"), CreatePair.waiting_for_filter)
async def process_filter_choice(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    filter_mode = int(callback.data.split("_")[1])
    await state.update_data(filter_type=filter_mode)

    if filter_mode in [2, 3]:
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


# --- EXPRESS FAST LAUNCH WIZARD (2-STEP SETUP) ---

def fast_launch_cancel_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="❌ Cancel Launch", callback_data="main")
    return b.as_markup()

def fast_launch_step2_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="🔙 Back to Step 1", callback_data="fast_launch")
    b.button(text="❌ Cancel", callback_data="main")
    b.adjust(1, 1)
    return b.as_markup()

def fast_launch_success_kb(pair_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="📊 Open Live Status Card", callback_data=f"pview_{pair_id}")
    b.button(text="🚀 Launch Another Pair", callback_data="fast_launch")
    b.button(text="🏠 Main Menu", callback_data="main")
    b.adjust(1, 2)
    return b.as_markup()

@router.callback_query(F.data == "fast_launch")
async def cb_fast_launch_start(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback, "🚀 Fast Launch...")
    user_id = callback.from_user.id
    is_admin = await repost_service.is_admin(user_id)

    if not is_admin:
        await callback.answer("Please contact support to add new channels.", show_alert=True)
        return

    pairs = await repost_service.get_user_pairs(user_id)
    if len(pairs) >= MAX_PAIRS:
        return await callback.message.edit_text(f"Limit Reached ({MAX_PAIRS})", reply_markup=limit_reached_kb())

    await state.clear()
    await state.set_state(FastLaunch.waiting_for_source)

    text = (
        "🚀 <b>FAST LAUNCH • STEP 1 OF 2</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Send me your <b>SOURCE channel</b> where content is reposted from.\n\n"
        "<b>3 Ways to Connect:</b>\n"
        "1️⃣ <b>Public Username:</b> e.g. <code>@MySourceChannel</code>\n"
        "2️⃣ <b>Private Invite Link:</b> e.g. <code>https://t.me/+AbCdEf123456</code>\n"
        "3️⃣ <b>Forward Post:</b> Simply forward any message from the source channel here.\n\n"
        "<i>Worker accounts will automatically join or attach via Telethon/Session.</i>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=fast_launch_cancel_kb(),
        parse_mode="HTML"
    )

@router.message(FastLaunch.waiting_for_source)
async def process_fast_launch_source(message: types.Message, state: FSMContext):
    resolved = await handle_channel_input(message, state, "source")
    if not resolved:
        return

    source_disp = resolved.get("display_name") or resolved["identifier"]
    await state.update_data(
        fast_source_id=resolved["identifier"],
        fast_source_display=source_disp
    )

    await state.set_state(FastLaunch.waiting_for_destination)

    text = (
        "🚀 <b>FAST LAUNCH • STEP 2 OF 2</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Source verified: <code>{source_disp}</code> ✅\n\n"
        "Now send the <b>DESTINATION channel</b> (where reposts will land):\n\n"
        "<b>Guidelines:</b>\n"
        "1️⃣ Send username: <code>@MyDestinationChannel</code> or invite link.\n"
        "2️⃣ Ensure this bot (or the assigned Worker) is added as <b>Admin with Post Messages</b> rights."
    )

    await message.answer(
        text,
        reply_markup=fast_launch_step2_kb(),
        parse_mode="HTML"
    )

@router.message(FastLaunch.waiting_for_destination)
async def process_fast_launch_destination(message: types.Message, state: FSMContext):
    resolved = await handle_channel_input(message, state, "destination")
    if not resolved:
        return

    dest_disp = resolved.get("display_name") or resolved["identifier"]
    data = await state.get_data()
    source_id = data.get("fast_source_id")
    source_disp = data.get("fast_source_display") or source_id
    user_id = message.from_user.id

    # Auto-worker discovery: find least loaded worker or fallback to user
    worker_service = SessionService()
    worker_user = await worker_service.get_least_loaded_worker(niche="nsfw", max_capacity=15)

    assigned_user_id = worker_user.id if worker_user else user_id
    worker_label = worker_user.username if worker_user and worker_user.username else f"Worker-{assigned_user_id}"

    # Calculate capacity
    async with async_session() as ds:
        repo = UserRepository(ds)
        assigned_pairs = await repo.get_user_pairs(assigned_user_id)
        assigned_load = sum(1 for p in assigned_pairs if p.is_active) + 1

        new_pair = await repo.add_repost_pair(
            user_id=assigned_user_id,
            source=source_id,
            destination=resolved["identifier"],
            source_display=source_disp,
            destination_display=dest_disp,
            filter_type=1,
            schedule_interval=240,  # 4h default for monetization
            stars_price_short=15,
            stars_price_long=50,
            stars_cadence=4,
            active_preset="monetization"
        )

    await state.clear()

    confirm_text = (
        "🎉 <b>CHANNEL PAIR CREATED &amp; ACTIVATED!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Route:</b> <code>{source_disp}</code> ➜ <code>{dest_disp}</code>\n"
        "⚙️ <b>Strategy:</b> 💰 Monetization Beast (Default)\n"
        f"🤖 <b>Worker Auto-Assigned:</b> <code>{worker_label}</code> (Capacity: {assigned_load}/15)\n"
        "🟢 <b>Status:</b> Listening for new posts &amp; media queue...\n\n"
        "First sync check scheduled in <b>4 hours</b> or upon next incoming media."
    )

    await message.answer(
        confirm_text,
        reply_markup=fast_launch_success_kb(new_pair.id),
        parse_mode="HTML"
    )

