"""
CORE: CHANNEL RESOLVER
Pure functions for detecting and normalizing channel input formats.
No network calls, no imports from database or bot layers.

Supported formats:
  - @username
  - t.me/username
  - t.me/+invite_hash  (private invite)
  - t.me/joinchat/hash  (legacy private invite)
  - t.me/c/channel_id/msg_id  (private group post link)
  - t.me/username/msg_id  (public post link)
  - Numeric channel ID  (raw integer or -100 prefixed)
  - Forwarded message  (via forwarded_chat object)
"""
import re

_PUBLIC_LINK = re.compile(
    r"(?:https?://)?t\.me/([A-Za-z][\w]{3,})(?:/(\d+))?$"
)
_PRIVATE_INVITE = re.compile(
    r"(?:https?://)?t\.me/\+([A-Za-z0-9_-]+)$"
)
_LEGACY_INVITE = re.compile(
    r"(?:https?://)?t\.me/joinchat/([A-Za-z0-9_-]+)$"
)
_PRIVATE_POST = re.compile(
    r"(?:https?://)?t\.me/c/(\d+)(?:/(\d+))?$"
)
_USERNAME = re.compile(r"^@([A-Za-z][\w]{3,})$")


def resolve_channel_input(text: str | None, forwarded_chat=None) -> dict:
    """
    Parses a user-provided channel identifier into a normalized result.

    Returns:
        {
            "identifier": str or None,
            "kind": "username" | "invite" | "private_id" | "numeric" | "forwarded",
            "invite_hash": str or None,
            "msg_id": int or None,
        }
    """
    empty = {"identifier": None, "kind": None, "invite_hash": None, "msg_id": None}

    if forwarded_chat:
        chat_id = getattr(forwarded_chat, "id", None)
        if chat_id:
            return {
                "identifier": str(chat_id),
                "kind": "forwarded",
                "invite_hash": None,
                "msg_id": None,
            }
        return empty

    if not text:
        return empty

    raw = text.strip()

    m = _PRIVATE_INVITE.match(raw)
    if m:
        return {
            "identifier": raw,
            "kind": "invite",
            "invite_hash": m.group(1),
            "msg_id": None,
        }

    m = _LEGACY_INVITE.match(raw)
    if m:
        return {
            "identifier": raw,
            "kind": "invite",
            "invite_hash": m.group(1),
            "msg_id": None,
        }

    m = _PRIVATE_POST.match(raw)
    if m:
        channel_id = m.group(1)
        msg_id = int(m.group(2)) if m.group(2) else None
        return {
            "identifier": f"-100{channel_id}",
            "kind": "private_id",
            "invite_hash": None,
            "msg_id": msg_id,
        }

    m = _PUBLIC_LINK.match(raw)
    if m:
        username = m.group(1)
        msg_id = int(m.group(2)) if m.group(2) else None
        return {
            "identifier": username,
            "kind": "username",
            "invite_hash": None,
            "msg_id": msg_id,
        }

    m = _USERNAME.match(raw)
    if m:
        return {
            "identifier": m.group(1),
            "kind": "username",
            "invite_hash": None,
            "msg_id": None,
        }

    clean = raw.lstrip("@").strip("/")
    if clean.replace("-", "").isdigit():
        return {
            "identifier": clean,
            "kind": "numeric",
            "invite_hash": None,
            "msg_id": None,
        }

    if clean and not clean.startswith("/"):
        return {
            "identifier": clean,
            "kind": "username",
            "invite_hash": None,
            "msg_id": None,
        }

    return empty
