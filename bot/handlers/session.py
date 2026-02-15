"""
BOT: SESSION HANDLERS
Upload session flow (file or string).
"""
import os
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from services.session_manager import SessionService
from bot.states import SessionUpload
from bot.keyboards import back_kb, cancel_kb, main_menu_kb
from config import ADMIN_IDS

router = Router()

session_service = SessionService()


@router.callback_query(F.data == "upload")
async def cb_upload_session(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    session_file = os.path.join("data", "sessions", f"{user_id}.session")

    if os.path.exists(session_file):
        await callback.message.edit_text(
            "Session Already Active\n"
            "\n"
            "You already have a session linked.\n"
            "Use Delete All if you need to reset.",
            reply_markup=back_kb()
        )
        await callback.answer()
        return

    await state.set_state(SessionUpload.waiting_for_input)
    await callback.message.edit_text(
        "Send your session string or upload the .session file.\n"
        "\n"
        "Press Cancel to go back.",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(SessionUpload.waiting_for_input)
async def process_session_input(message: types.Message, state: FSMContext):
    await message.answer("Processing session... please wait.")
    await session_service.handle_session_input(message)
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer(
        "Session linked successfully!",
        reply_markup=main_menu_kb(has_session=True, is_admin=is_admin)
    )
