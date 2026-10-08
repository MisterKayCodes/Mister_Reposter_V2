"""
Generate a Telethon StringSession.

Place this file in your project's scripts/ folder and run from the project root:
    python scripts/get_session.py

Reads API_ID and API_HASH from .env (via python-dotenv), falling back to app.config.
"""
import asyncio
import os
import sys
from getpass import getpass
from pathlib import Path

# Project root = parent of scripts/. Needed so `app` can be imported
# (dotenv does NOT apply PYTHONPATH=. for you).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

load_dotenv(ROOT / ".env")


def get_credentials():
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    # Fallback: app/config.py
    if not api_id or not api_hash:
        try:
            from app import config

            holder = getattr(config, "settings", config)
            api_id = api_id or str(getattr(holder, "API_ID", "") or getattr(holder, "api_id", ""))
            api_hash = api_hash or str(getattr(holder, "API_HASH", "") or getattr(holder, "api_hash", ""))
        except Exception:
            pass

    if not api_id or api_id == "your_api_id":
        api_id = input("API ID: ").strip()
    if not api_hash or api_hash == "your_api_hash":
        api_hash = input("API HASH: ").strip()

    return int(api_id), api_hash


async def main():
    api_id, api_hash = get_credentials()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Phone number (with country code, e.g. +234...): ").strip()
        await client.send_code_request(phone)

        while True:
            code = input("Code sent to your Telegram: ").strip().replace(" ", "")
            try:
                await client.sign_in(phone=phone, code=code)
                break
            except PhoneCodeInvalidError:
                print("Wrong code, try again.")
            except SessionPasswordNeededError:
                print("2FA detected.")
                while True:
                    password = getpass("2FA password (hidden as you type): ")
                    try:
                        await client.sign_in(password=password)
                        break
                    except PasswordHashInvalidError:
                        print("Wrong password, try again.")
                break

    session_string = client.session.save()
    me = await client.get_me()

    print(f"\nLogged in as: {me.first_name} (@{me.username})")
    print("\n===== YOUR TELETHON STRING SESSION =====")
    print(session_string)
    print("========================================")
    print("Keep it secret: anyone with it has full access to your account.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
