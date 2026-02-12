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


def sanitize_channel_id(input_string: str) -> str:
    """
    The Sanitizer: Strips 'https://t.me/' or 't.me/' from links.
    Example: 'https://t.me/my_channel' -> 'my_channel'
    """
    if not input_string:
        return ""
        
    clean = input_string.strip()
    
    # List of "web skin" prefixes to peel off
    prefixes = ["https://t.me/+", "https://t.me/", "http://t.me/", "t.me/", "@"]
    
    for p in prefixes:
        if clean.startswith(p):
            clean = clean.replace(p, "")
    
    # Remove trailing slashes (e.g., 'my_channel/' -> 'my_channel')
    return clean.rstrip("/")