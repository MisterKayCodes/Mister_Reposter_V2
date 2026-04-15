"""
BOT: SESSION HANDLERS
Upload session flow (file or string).
"""
import os
import uuid
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from app.services.session_manager import SessionService, SESSIONS_DIR
from app.bot.states import SessionUpload
from app.bot.keyboards import back_kb, cancel_kb, main_menu_kb
from app.bot.handlers.utils import repost_service
from app.core.config import ADMIN_IDS

logger = logging.getLogger(__name__)

router = Router()

session_service = SessionService()


@router.callback_query(F.data == "upload")
async def cb_upload_session(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await repost_service.is_admin(user_id):
        await callback.answer("Admin only feature.", show_alert=True)
        return

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
    is_admin = await repost_service.is_admin(user_id)
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
        # success is now a tuple (bool, target_id)
        is_ok, target_id = success
        from app.data.database import async_session as db_session
        from app.data.repository import UserRepository
        
        async with db_session() as ds:
            target_user = await UserRepository(ds).get_user(target_id)
            target_name = f"@{target_user.username}" if target_user and target_user.username else f"ID: {target_id}"
            target_admin = target_user.is_admin if target_user else False

        msg_body = f"✅ <b>Linked Account:</b> {target_name}\n\n"
        if target_id == user_id:
            msg_body += "Your personal account is now ready! Returning to menu."
        else:
            msg_body += f"This session belongs to a different account. That user can now /start the bot to see their own dashboard."

        await message.answer(
            msg_body,
            reply_markup=main_menu_kb(has_session=True, is_admin=is_admin or target_admin),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Session setup failed. Please check your data and try again from the menu.",
            reply_markup=main_menu_kb(has_session=False, is_admin=is_admin)
        )


@router.callback_query(F.data == "get_session")
async def cb_get_session(callback: types.CallbackQuery):
    """Privately DM the user their own session string on request."""
    from app.data.database import async_session as db_session
    from app.data.repository import UserRepository

    user_id = callback.from_user.id
    if not await repost_service.is_admin(user_id):
        await callback.answer("Admin only feature.", show_alert=True)
        return

    await callback.answer()

    async with db_session() as ds:
        user = await UserRepository(ds).get_user(user_id)

    if not user or not user.session_string:
        return await callback.message.answer(
            "❌ No session found. Please upload one first.",
            reply_markup=back_kb()
        )

    try:
        await callback.message.bot.send_message(
            user_id,
            f"🔑 <b>Your Session String</b>\n\n"
            f"<code>{user.session_string}</code>\n\n"
            f"⚠️ <i>Keep this private. Anyone with this string can access your account.</i>",
            parse_mode="HTML"
        )
        await callback.message.answer("✅ Session string sent to your DMs!")
    except Exception:
        # Fallback: send inline if DM fails (bot not started in private)
        await callback.message.answer(
            f"🔑 <b>Your Session String</b>\n\n"
            f"<code>{user.session_string}</code>\n\n"
            f"⚠️ <i>Keep this private. Anyone with this string can access your account.</i>",
            parse_mode="HTML"
        )
