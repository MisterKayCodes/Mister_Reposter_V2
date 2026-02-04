"""
BOT: ROUTERS
Connects all handler files to the main bot dispatcher.
"""
from aiogram import Dispatcher
from .handlers import router as session_router

def register_all_routers(dp: Dispatcher):
    dp.include_router(session_router)
