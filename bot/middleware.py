"""
BOT: MIDDLEWARE
The 'Gatekeeper'. (Anatomy: Immune System)
"""
import os
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message

# DNA Alignment: Pointing to your actual 'data' folder
from data.database import async_session 
from data.repository import UserRepository

class SessionGuardMiddleware(BaseMiddleware):
    def __init__(self):
        # Whitelist: Commands allowed without a session
        self.allowed_commands = ["/start", "/help", "/uploadsession"]

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # 1. Skip if it's not a text message
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)

        # 2. Whitelist Check
        command = event.text.split()[0]
        if command in self.allowed_commands:
            return await handler(event, data)

        user_id = event.from_user.id
        
        # 3. Path Calculation (Absolute Vision)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        session_file = os.path.join(project_root, "data", "sessions", f"{user_id}.session")
        
        # <REACTION: If the file is right there on the disk, we let him in immediately.>
        if os.path.exists(session_file):
            return await handler(event, data)

        # 4. Database Backup (If file is missing, maybe the DB has a string)
        async with async_session() as db_session:
            repo = UserRepository(db_session)
            user = await repo.get_user(user_id)
            
            # <THINK: If the Vault has a string, we trust the Librarian.>
            if user and user.session_string:
                return await handler(event, data)

        # 5. ACCESS DENIED
        # <REACTION: Looked in the folder, looked in the Vault. Nothing. Stay out.>
        return await event.answer(
            "🚫 **Access Restricted**\n\n"
            "Your account is not connected to a session.\n"
            "Please use /uploadsession and send your file or session string first."
        )