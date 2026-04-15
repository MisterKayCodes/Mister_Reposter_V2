"""
BOT: LOGS HANDLER
Displays recent application logs via the Logs button.
Admin-only access — non-admin users are denied.
Follows architecture rules: callback-only, keyboard from keyboards.py.
"""
from aiogram import Router, types, F
from app.bot.keyboards import logs_kb
from app.utils.log_buffer import log_buffer
from app.core.config import ADMIN_IDS

router = Router()


@router.callback_query(F.data == "logs")
async def cb_view_logs(callback: types.CallbackQuery):
    from app.services.singleton import repost_service
    if not await repost_service.is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return

    raw = log_buffer.get_logs(25)
    if len(raw) > 4000:
        raw = raw[-4000:]

    await callback.message.edit_text(
        f"Recent Logs\n\n{raw}",
        reply_markup=logs_kb()
    )
    await callback.answer()
