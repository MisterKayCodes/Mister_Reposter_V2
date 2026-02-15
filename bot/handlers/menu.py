"""
BOT: MENU HANDLERS
Entry point (/start) and main menu navigation.
Delete-all confirmation flow lives here too.
"""
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.keyboards import main_menu_kb, delete_all_confirm_kb
from bot.handlers.utils import render_main_menu, render_pairs_view, repost_service

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await repost_service.register_user(message.from_user.id, message.from_user.username)
    await render_main_menu(message, user_id=message.from_user.id, edit=False)


@router.callback_query(F.data == "main")
async def cb_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await render_main_menu(callback.message, user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "pairs")
async def cb_view_pairs(callback: types.CallbackQuery):
    await render_pairs_view(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "delall")
async def cb_delete_all(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Delete all pairs?\n"
        "\n"
        "This will remove every repost rule. Cannot be undone.",
        reply_markup=delete_all_confirm_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "delall_yes")
async def cb_confirm_delete_all(callback: types.CallbackQuery):
    count = await repost_service.delete_all_user_pairs(callback.from_user.id)
    await callback.answer(f"Removed {count} pairs.")
    await render_main_menu(callback.message, user_id=callback.from_user.id)
