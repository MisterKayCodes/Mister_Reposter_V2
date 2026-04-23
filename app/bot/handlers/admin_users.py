"""
BOT: ADMIN USER MANAGEMENT HANDLERS
Allows admins to promote other users, grant premium, and view user stats.
"""
import logging
from aiogram import Router, F, types
from datetime import datetime

from app.bot.keyboards import back_kb
from app.bot.keyboards_admin import admin_users_kb, user_detail_kb
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
    await render_pairs_view(callback.message, user_id, is_remote=True)

@router.callback_query(F.data.startswith("ustat_"))
async def cb_ustat(callback: types.CallbackQuery):
    """Admins viewing user stats list."""
    if not await _check_admin(callback.from_user.id): return
    
    user_id = int(callback.data.split("_")[1])
    from app.bot.keyboards_admin import admin_stats_pairs_kb
    pairs = await repost_service.get_user_pairs(user_id)
    
    if not pairs:
        return await callback.message.edit_text("<b>No pairs yet.</b>", reply_markup=back_kb(f"uview_{user_id}"), parse_mode="HTML")
    
    await callback.message.edit_text(
        f"<b>📊 Stats Dashboard: {user_id}</b>",
        reply_markup=admin_stats_pairs_kb(user_id, pairs),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("ustp_"))
async def cb_ustp(callback: types.CallbackQuery):
    """Admins viewing specific user pair stats."""
    if not await _check_admin(callback.from_user.id): return
    
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    
    from app.bot.handlers.utils import generate_stats_lines
    from app.bot.keyboards_admin import admin_stats_detail_kb
    
    stats = await repost_service.get_effective_stats(user_id, pair_id)
    if not stats: return await safe_callback_answer(callback, "Stats not found.", show_alert=True)
    
    # Calculate local index for display
    pairs = await repost_service.get_user_pairs(user_id)
    local_idx = 1
    for i, p in enumerate(pairs, 1):
        if p.id == pair_id:
            local_idx = i
            break

    lines = generate_stats_lines(stats, local_idx)
    # Customize the header to remind them they are viewing REMOTE stats
    lines[0] = f"<b>📊 Remote Stats: User {user_id} (Pair #{local_idx})</b>"
    
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_stats_detail_kb(user_id, pair_id),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("uref_"))
async def cb_uref(callback: types.CallbackQuery):
    """Refresh remote stats."""
    if not await _check_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    user_id, pair_id = int(parts[1]), int(parts[2])
    
    await safe_callback_answer(callback, "⏳ Refreshing...")
    await repost_service.sync_pair_stats(user_id, pair_id)
    callback.data = f"ustp_{user_id}_{pair_id}"
    await cb_ustp(callback)

@router.callback_query(F.data.startswith("ureconn_"))
async def cb_ureconn(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id): return
    user_id = int(callback.data.split("_")[1])
    
    async with async_session() as ds:
        user = await UserRepository(ds).get_user(user_id)
        if not user or not user.session_string:
            return await safe_callback_answer(callback, "❌ No session string to reconnect.", show_alert=True)
            
    await safe_callback_answer(callback, "🔄 Revalidating session...")
    is_valid, tid, uname = await repost_service.telethon.validate_session(user.session_string)
    
    async with async_session() as ds:
        repo = UserRepository(ds)
        db_user = await repo.get_user(user_id)
        db_user.has_active_session = is_valid
        await ds.commit()
        
    status = "✅ Session Valid" if is_valid else "❌ Session Invalid/Blocked"
    await safe_callback_answer(callback, status, show_alert=True)
    await _render_user_detail(callback.message, user_id)

@router.callback_query(F.data.startswith("uacc_confirm_"))
async def cb_udconfirm(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id): return
    user_id = int(callback.data.split("_")[2])
    from app.bot.keyboards_admin import delete_user_confirm_kb
    await callback.message.edit_text(
        f"<b>⚠️ Nuclear Warning: User {user_id}</b>\n\n"
        "Deleting this user will:\n"
        "1. Wipe all their repost pairs\n"
        "2. Stop all their active listeners\n"
        "3. Remove them from the database\n\n"
        "This is irreversible. Proceed?",
        reply_markup=delete_user_confirm_kb(user_id),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("uacc_del_"))
async def cb_udel(callback: types.CallbackQuery):
    if not await _check_admin(callback.from_user.id): return
    user_id = int(callback.data.split("_")[2])
    
    if user_id == callback.from_user.id:
        return await safe_callback_answer(callback, "❌ You cannot delete yourself.", show_alert=True)
        
    await safe_callback_answer(callback, "🧨 Executing cleanup...")
    await repost_service.delete_user(user_id)
    
    await safe_callback_answer(callback, f"✅ User {user_id} and all their data removed.", show_alert=True)
    await cb_admin_users(callback)
