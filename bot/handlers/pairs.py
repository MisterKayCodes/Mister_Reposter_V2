"""
BOT: PAIR HANDLERS
Create pair flow (5-step FSM), toggle, delete.
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

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

router = Router()


@router.callback_query(F.data.startswith("tog_"))
async def cb_toggle_pair(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    pairs = await repost_service.get_user_pairs(user_id)
    target = next((p for p in pairs if p.id == pair_id), None)

    if not target:
        await callback.answer("Pair not found.", show_alert=True)
        return

    if target.is_active:
        await repost_service.deactivate_pair(user_id, pair_id)
        await callback.answer("Pair paused.")
    else:
        await repost_service.activate_pair(user_id, pair_id)
        await callback.answer("Pair activated.")

    await render_pairs_view(callback.message, user_id)


@router.callback_query(F.data.startswith("del_"))
async def cb_delete_pair(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        f"Delete Pair #{pair_id}?\n"
        "\n"
        "This cannot be undone.",
        reply_markup=delete_confirm_kb(pair_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cdel_"))
async def cb_confirm_delete(callback: types.CallbackQuery):
    pair_id = int(callback.data.split("_")[1])
    success = await repost_service.delete_single_pair(callback.from_user.id, pair_id)

    if success:
        await callback.answer("Pair deleted.")
    else:
        await callback.answer("Pair not found.", show_alert=True)

    await render_pairs_view(callback.message, callback.from_user.id)


@router.callback_query(F.data == "create")
async def cb_create_pair(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    has_session = await repost_service.user_has_session(user_id)
    if not has_session:
        await callback.message.edit_text(
            "Session Required\n"
            "\n"
            "Link your Telegram account first before creating pairs.",
            reply_markup=session_required_kb()
        )
        await callback.answer()
        return

    pairs = await repost_service.get_user_pairs(user_id)
    if len(pairs) >= MAX_PAIRS:
        await callback.message.edit_text(
            f"Limit Reached\n"
            f"\n"
            f"Maximum {MAX_PAIRS} pairs allowed.\n"
            "Delete an existing pair to make room.",
            reply_markup=limit_reached_kb()
        )
        await callback.answer()
        return

    await state.set_state(CreatePair.waiting_for_source)
    await callback.message.edit_text(
        "Create Pair  (1/5)\n"
        "\n"
        "Send the source channel.\n"
        "\n"
        "Accepted formats:\n"
        "  @username\n"
        "  t.me/channel\n"
        "  t.me/+invite_hash\n"
        "  t.me/c/id/msg\n"
        "  Forwarded message",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(CreatePair.waiting_for_source)
async def process_source(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return await message.answer("Please provide a channel, not a command.")

    if message.forward_from_chat:
        chat = message.forward_from_chat
        resolved = resolve_channel_input(None, forwarded_chat=chat)
    else:
        resolved = resolve_channel_input(message.text)

    if not resolved["identifier"]:
        return await message.answer(
            "Could not parse that input.\n"
            "Try a link, @username, or forward a message from the channel."
        )

    await state.update_data(
        source_id=resolved["identifier"],
        source_kind=resolved["kind"],
        source_invite_hash=resolved.get("invite_hash"),
    )

    display = resolved["identifier"]
    if resolved["kind"] == "invite":
        display = f"Private invite ({resolved['invite_hash'][:8]}...)"

    await message.answer(
        f"Source: {display}\n"
        "\n"
        "Create Pair  (2/5)\n"
        "\n"
        "Send the destination channel.",
        reply_markup=cancel_kb()
    )
    await state.set_state(CreatePair.waiting_for_destination)


@router.message(CreatePair.waiting_for_destination)
async def process_destination(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return await message.answer("Please provide a channel, not a command.")

    if message.forward_from_chat:
        chat = message.forward_from_chat
        resolved = resolve_channel_input(None, forwarded_chat=chat)
    else:
        resolved = resolve_channel_input(message.text)

    if not resolved["identifier"]:
        return await message.answer(
            "Could not parse that input.\n"
            "Try a link, @username, or forward a message from the channel."
        )

    await state.update_data(
        destination_id=resolved["identifier"],
        dest_kind=resolved["kind"],
        dest_invite_hash=resolved.get("invite_hash"),
    )

    await message.answer(
        "Create Pair  (3/5)\n"
        "\n"
        "Choose a filter for this pair:",
        reply_markup=filter_kb()
    )
    await state.set_state(CreatePair.waiting_for_filter)


@router.callback_query(F.data.startswith("setfilt_"))
async def process_filter_choice(callback: types.CallbackQuery, state: FSMContext):
    filter_mode = int(callback.data.split("_")[1])
    await state.update_data(filter_type=filter_mode)

    if filter_mode == 2:
        await callback.message.edit_text(
            "Create Pair  (4/5)\n"
            "\n"
            "Send the link or text you want as a replacement.",
            reply_markup=cancel_kb()
        )
        await state.set_state(CreatePair.waiting_for_replacement)
    else:
        await callback.message.edit_text(
            "Create Pair  (5/5)\n"
            "\n"
            "Choose a repost schedule:",
            reply_markup=schedule_kb()
        )
        await state.set_state(CreatePair.waiting_for_schedule)

    await callback.answer()


@router.message(CreatePair.waiting_for_replacement)
async def process_replacement_link(message: types.Message, state: FSMContext):
    await state.update_data(replacement_link=message.text)
    await message.answer(
        "Create Pair  (5/5)\n"
        "\n"
        "Choose a repost schedule:",
        reply_markup=schedule_kb()
    )
    await state.set_state(CreatePair.waiting_for_schedule)


@router.callback_query(F.data.startswith("setsched_"))
async def process_schedule_choice(callback: types.CallbackQuery, state: FSMContext):
    interval = int(callback.data.split("_")[1])
    await state.update_data(schedule_interval=interval)
    await callback.answer()

    if interval > 0:
        await callback.message.edit_text(
            "Start From Message  (optional)\n"
            "\n"
            "Send a post link to start reposting from that message.\n"
            "Example: t.me/channel/50\n"
            "\n"
            "Or tap Skip to start from new messages only.",
            reply_markup=start_msg_kb()
        )
        await state.set_state(CreatePair.waiting_for_start_message)
    else:
        await _show_preview(callback.message, state, callback.from_user.id)


@router.callback_query(F.data == "skip_start_msg")
async def cb_skip_start_msg(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await _show_preview(callback.message, state, callback.from_user.id)


@router.message(CreatePair.waiting_for_start_message)
async def process_start_message(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return await message.answer("Please provide a post link, not a command.")

    resolved = resolve_channel_input(message.text)
    msg_id = resolved.get("msg_id")

    if not msg_id:
        text = message.text.strip() if message.text else ""
        if text.isdigit():
            msg_id = int(text)

    if not msg_id:
        return await message.answer(
            "Could not extract a message ID.\n"
            "Send a link like t.me/channel/50 or just the number."
        )

    await state.update_data(start_from_msg_id=msg_id)
    await _show_preview(message, state, message.from_user.id, is_edit=False)


async def _show_preview(message: types.Message, state: FSMContext, user_id: int, is_edit: bool = True):
    data = await state.get_data()

    schedule_interval = data.get("schedule_interval", 0)
    schedule_label = SCHEDULE_LABELS.get(schedule_interval, f"{schedule_interval} min")
    filter_label = FILTER_LABELS.get(data.get("filter_type", 1), "Unknown")
    start_msg = data.get("start_from_msg_id")

    resolved_source = await repost_service.resolve_channel_for_pair(
        user_id,
        data["source_id"],
        data.get("source_kind", "username"),
        data.get("source_invite_hash"),
    )
    resolved_dest = await repost_service.resolve_channel_for_pair(
        user_id,
        data["destination_id"],
        data.get("dest_kind", "username"),
        data.get("dest_invite_hash"),
    )

    await state.update_data(
        resolved_source=resolved_source,
        resolved_dest=resolved_dest,
    )

    lines = [
        "Review Your Pair\n",
        f"Source:     {resolved_source}",
        f"Dest:      {resolved_dest}",
        f"Filter:    {filter_label}",
        f"Schedule:  {schedule_label}",
    ]
    if start_msg:
        lines.append(f"Start Msg: #{start_msg}")
    lines.append("\nConfirm to activate this pair.")

    text = "\n".join(lines)
    await state.set_state(CreatePair.waiting_for_confirmation)
    if is_edit:
        await message.edit_text(text, reply_markup=confirm_pair_kb())
    else:
        await message.answer(text, reply_markup=confirm_pair_kb())


@router.callback_query(F.data == "confirm_pair")
async def cb_confirm_pair(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    schedule_interval = data.get("schedule_interval", 0)
    schedule_label = SCHEDULE_LABELS.get(schedule_interval, f"{schedule_interval} min")
    filter_label = FILTER_LABELS.get(data.get("filter_type", 1), "Unknown")
    start_msg = data.get("start_from_msg_id")

    resolved_source = data.get("resolved_source", data["source_id"])
    resolved_dest = data.get("resolved_dest", data["destination_id"])

    await repost_service.add_new_pair(
        user_id=user_id,
        source=resolved_source,
        destination=resolved_dest,
        filter_type=data.get("filter_type", 1),
        replacement_link=data.get("replacement_link"),
        schedule_interval=schedule_interval if schedule_interval else None,
        start_from_msg_id=start_msg,
    )

    lines = [
        "Pair Created!\n",
        f"From:      {resolved_source}",
        f"To:        {resolved_dest}",
        f"Filter:    {filter_label}",
        f"Schedule:  {schedule_label}",
    ]
    if start_msg:
        lines.append(f"Start Msg: #{start_msg}")
    lines.append("\nReturning to menu...")

    text = "\n".join(lines)
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text(text, reply_markup=main_menu_kb(has_session=True, is_admin=is_admin))
    await state.clear()
    await callback.answer("Pair activated!")
