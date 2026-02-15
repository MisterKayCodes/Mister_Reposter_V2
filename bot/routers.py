"""
BOT: ROUTERS
Connects all handler modules to the main bot dispatcher.
"""
from aiogram import Dispatcher
from .handlers.menu import router as menu_router
from .handlers.session import router as session_router
from .handlers.pairs import router as pairs_router
from .handlers.logs import router as logs_router


def register_all_routers(dp: Dispatcher):
    dp.include_router(menu_router)
    dp.include_router(session_router)
    dp.include_router(pairs_router)
    dp.include_router(logs_router)
