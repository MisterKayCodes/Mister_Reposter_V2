"""
BOT: MIDDLEWARE
The 'Gatekeeper'. (Anatomy: Immune System)
Includes Network Resilience (Retry Shield) and Session Guard.
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramNetworkError

logger = logging.getLogger(__name__)

class NetworkRetryMiddleware(BaseMiddleware):
    """
    The 'Shield': Catches network timeouts and retries the request.
    Specifically addresses the 'Semaphore Timeout' and 'Request Timeout' issues.
    """
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        max_retries = 3
        retry_delay = 2.0  # Seconds to wait before retrying

        for attempt in range(max_retries):
            try:
                return await handler(event, data)
            except TelegramNetworkError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Network lag (Attempt {attempt + 1}). Retrying in {retry_delay}s... Error: {e}")
                    
                    # Optional: Notify user if it's a slow response
                    if attempt == 0:
                        try:
                            if isinstance(event, CallbackQuery):
                                await event.answer("📶 Connection slow... retrying!", show_alert=False)
                            elif isinstance(event, Message):
                                await event.answer("📶 Slow network detected. Still trying...")
                        except Exception:
                            pass # Don't let the notification itself crash the retry

                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"❌ Network failed after {max_retries} attempts.")
                    # Final attempt failed - user needs to know
                    try:
                        error_msg = "❌ Connection lost. Please check your internet and try again."
                        if isinstance(event, CallbackQuery):
                            await event.answer(error_msg, show_alert=True)
                        elif isinstance(event, Message):
                            await event.answer(error_msg)
                    except Exception:
                        pass
                    raise e


class SessionGuardMiddleware(BaseMiddleware):
    def __init__(self):
        self.allowed_commands = ["/start"]

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Pass non-message updates (like callbacks) through immediately
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)

        # Allow FSM state text (e.g., when the user sends a channel link or replacement text)
        if not event.text.startswith("/"):
            return await handler(event, data)

        # Whitelist specific commands
        command = event.text.split()[0]
        if command in self.allowed_commands:
            return await handler(event, data)

        return await event.answer(
            "Use the menu buttons to navigate.\nSend /start to open the menu."
        )