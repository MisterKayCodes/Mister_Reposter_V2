"""
BOT: MIDDLEWARE
The 'Gatekeeper'. (Anatomy: Immune System)
Now simplified for the callback-only UI.
Only /start is whitelisted as a slash command.
Non-command text passes through for FSM state handlers.
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message


class SessionGuardMiddleware(BaseMiddleware):
    def __init__(self):
        self.allowed_commands = ["/start"]

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)

        if not event.text.startswith("/"):
            return await handler(event, data)

        command = event.text.split()[0]
        if command in self.allowed_commands:
            return await handler(event, data)

        return await event.answer(
            "Use the menu buttons to navigate.\nSend /start to open the menu."
        )
