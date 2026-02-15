"""
CORE: CHANNEL RESOLVER
Pure functions for detecting and normalizing channel input formats.
"""
import re

_PUBLIC_LINK = re.compile(r"(?:https?://)?t\.me/([A-Za-z][\w]{3,})(?:/(\d+))?$")
_PRIVATE_INVITE = re.compile(r"(?:https?://)?t\.me/\+([A-Za-z0-9_-]+)$")
_LEGACY_INVITE = re.compile(r"(?:https?://)?t\.me/joinchat/([A-Za-z0-9_-]+)$")
_PRIVATE_POST = re.compile(r"(?:https?://)?t\.me/c/(\d+)(?:/(\d+))?$")
_USERNAME = re.compile(r"^@?([A-Za-z][\w]{3,})$") # Rule: Optional @ for flexibility

def resolve_channel_input(text: str | None, forwarded_chat=None) -> dict:
    empty = {"identifier": None, "kind": None, "invite_hash": None, "msg_id": None}

    if forwarded_chat:
        chat_id = getattr(forwarded_chat, "id", None)
        if chat_id:
            return {"identifier": str(chat_id), "kind": "forwarded", "invite_hash": None, "msg_id": None}
        return empty

    if not text:
        return empty

    raw = text.strip()

    # 1. Matches links (Private/Legacy Invites)
    for regex, kind in [(_PRIVATE_INVITE, "invite"), (_LEGACY_INVITE, "invite")]:
        m = regex.match(raw)
        if m:
            return {"identifier": raw, "kind": kind, "invite_hash": m.group(1), "msg_id": None}

    # 2. Private Post Link (t.me/c/12345/678)
    m = _PRIVATE_POST.match(raw)
    if m:
        channel_id = m.group(1)
        # Rule: Only prefix if not already present
        clean_id = f"-100{channel_id}" if not channel_id.startswith("-100") else channel_id
        return {
            "identifier": clean_id,
            "kind": "private_id",
            "invite_hash": None,
            "msg_id": int(m.group(2)) if m.group(2) else None,
        }

    # 3. Public Post Link or Username
    m = _PUBLIC_LINK.match(raw)
    if m:
        return {
            "identifier": m.group(1),
            "kind": "username",
            "invite_hash": None,
            "msg_id": int(m.group(2)) if m.group(2) else None,
        }

    # 4. Numeric ID (Raw)
    clean = raw.lstrip("@").strip("/")
    if clean.replace("-", "").isdigit():
        return {"identifier": clean, "kind": "numeric", "invite_hash": None, "msg_id": None}

    # 5. Strict Username Match
    m = _USERNAME.match(raw)
    if m:
        return {"identifier": m.group(1), "kind": "username", "invite_hash": None, "msg_id": None}

    return empty