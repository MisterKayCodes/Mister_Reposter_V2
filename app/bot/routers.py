"""
BOT: ROUTERS
Connects all handler modules to the main bot dispatcher.
"""
from aiogram import Dispatcher, Router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.session import router as session_router
from app.bot.handlers.pairs import router as pairs_router
from app.bot.handlers.pairs_manage import router as pairs_manage_router
from app.bot.handlers.pairs_client import router as pairs_client_router
from app.bot.handlers.admin_users import router as admin_users_router
from app.bot.handlers.admin_settings import router as admin_settings_router
from app.bot.handlers.logs import router as logs_router
from app.bot.handlers.stats import router as stats_router
from app.bot.handlers.alertbot import router as alert_router


def register_all_routers(dp: Dispatcher):
    dp.include_router(menu_router)
    dp.include_router(session_router)
    dp.include_router(pairs_router)
    dp.include_router(pairs_manage_router)
    dp.include_router(pairs_client_router)
    dp.include_router(admin_users_router)
    dp.include_router(admin_settings_router)
    dp.include_router(logs_router)
    dp.include_router(stats_router)
    dp.include_router(alert_router)
