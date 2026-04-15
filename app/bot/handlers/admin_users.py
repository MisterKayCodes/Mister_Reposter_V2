"""
BOT: ADMIN USER MANAGEMENT HANDLERS
Allows admins to promote other users, grant premium, and view user stats.
"""
import logging
from aiogram import Router, F, types
from datetime import datetime

from app.bot.keyboards import admin_users_kb, user_detail_kb, back_kb
from app.bot.handlers.utils import (
    repost_service, safe_callback_answer, render_pairs_view
)
from app.data.database import async_session
from app.data.repository import UserRepository

logger = logging.getLogger(__name__)
router = Router()

async def _check_admin(user_id: int) -> bool:
    """Helper to verify admin status from DB."""
    async with async_session() as ds:
        user = await UserRepository(ds).get_user(user_id)
        return user.is_admin if user else False

async def _render_user_detail(message: types.Message, user_id: int):
    """Refactored rendering to satisfy Pydantic's frozen model constraints."""
    async with async_session() as ds:
        repo = UserRepository(ds)
        user = await repo.get_user(user_id)
        if not user: 
            return await message.answer("User not found.", reply_markup=back_kb("admin_users"))
        
        pairs = await repo.get_user_pairs(user_id)
        
        lines = [
            f"<b>👤 User Detail: {user_id}</b>",
            f"Username: @{user.username or 'N/A'}",
            f"Joined: {user.created_at.strftime('%Y-%m-%d')}",
            "──────────────────",
            f"Status: {'👑 Admin' if user.is_admin else '👤 User'}",
            f"Premium: {'💎 Yes' if user.is_premium else '❌ No'}",
        ]
        if user.is_premium and user.premium_until:
            lines.append(f"Expires: {user.premium_until.strftime('%Y-%m-%d')}")
            
        lines.append(f"\nPairs: {len(pairs)}")
        lines.append(f"Session: {'✅ Linked' if user.has_active_session else '❌ Missing'}")
        
        await message.edit_text(
            "\n".join(lines),
            reply_markup=user_detail_kb(user_id, user.is_admin, user.is_premium),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "❌ Admin access required.", show_alert=True)
        
    await safe_callback_answer(callback)
    async with async_session() as ds:
        users = await UserRepository(ds).get_all_users()
        await callback.message.edit_text(
            f"<b>👤 User Management ({len(users)})</b>\n\nSelect a user to manage their permissions:",
            reply_markup=admin_users_kb(users),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("uview_"))
async def cb_uview(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id): return
    
    user_id = int(callback.data.split("_")[1])
    await _render_user_detail(callback.message, user_id)
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("uprom_"))
async def cb_uprom(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id): return
    
    user_id = int(callback.data.split("_")[1])
    async with async_session() as ds:
        repo = UserRepository(ds)
        user = await repo.get_user(user_id)
        new_status = not user.is_admin
        await repo.promote_user(user_id, new_status)
        await safe_callback_answer(callback, f"User {'promoted' if new_status else 'demoted'}.")
    
    # Peak-End Rule: Don't modify frozen data, just call the renderer directly.
    await _render_user_detail(callback.message, user_id)

@router.callback_query(F.data.startswith("uprem_"))
async def cb_uprem(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id): return
    
    user_id = int(callback.data.split("_")[1])
    async with async_session() as ds:
        await UserRepository(ds).grant_premium(user_id, months=1)
        await safe_callback_answer(callback, "💎 Premium granted for 1 month.")
    
    await _render_user_detail(callback.message, user_id)

@router.callback_query(F.data.startswith("upairs_"))
async def cb_upairs(callback: types.CallbackQuery):
    """Allows admin to see exactly what pairs a user has."""
    if not await _check_admin(callback.from_user.id): return
    
    user_id = int(callback.data.split("_")[1])
    await render_pairs_view(callback.message, user_id)
