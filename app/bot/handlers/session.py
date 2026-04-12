"""
BOT: SESSION HANDLERS
Upload session flow (file or string).
"""
import os
import uuid
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from app.services.session_manager import SessionService, SESSIONS_DIR
from app.bot.states import SessionUpload
from app.bot.keyboards import back_kb, cancel_kb, main_menu_kb
from app.core.config import ADMIN_IDS

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
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
    success = False

    if message.document:
        if not message.document.file_name.lower().endswith(".session"):
            return await message.answer("❌ That box isn't labeled 'Cookies'! Please upload a .session file.")

        await message.answer("📥 Downloading session file... please wait.")
        safe_name = f"{uuid.uuid4()}.session"
        file_path = os.path.join(SESSIONS_DIR, safe_name)
        
        try:
            await message.bot.download(message.document, destination=file_path)
            success = await session_service.validate_and_save_file(user_id, file_path)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            success = False
            
    elif message.text:
        await message.answer("Processing session string... please wait.")
        success = await session_service.validate_and_save_string(user_id, message.text.strip())

    await state.clear()
    if success:
        await message.answer(
            "✅ Session linked successfully! Returning to menu.",
            reply_markup=main_menu_kb(has_session=True, is_admin=is_admin)
        )
    else:
        await message.answer(
            "❌ Session setup failed. Please check your data and try again from the menu.",
            reply_markup=main_menu_kb(has_session=False, is_admin=is_admin)
        )
