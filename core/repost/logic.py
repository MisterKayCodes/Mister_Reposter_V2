"""
CORE: REPOST LOGIC
The 'Brain'. (Anatomy: Brain)
Pure functions only. No I/O, no DB, no Telethon. (Rule 11)
"""

def clean_message_text(text: str, remove_links: bool = False) -> str:
    """
    Input: Raw text from source.
    Output: Cleaned text for destination.
    (Rule 5: Idempotency - Same input, same result)
    """
    if not text:
        return ""
    
    # Placeholder for future logic: Link removal, ad filtering, etc.
    cleaned_text = text.strip()
    
    return cleaned_text

def should_repost(message_type: str, allowed_types: list) -> bool:
    """
    Determines if a message meets the criteria to be copied.
    """
    return message_type in allowed_types
