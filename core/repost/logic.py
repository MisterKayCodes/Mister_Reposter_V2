"""
CORE: REPOST LOGIC
Pure functions for text processing. 
Handles the actual cleaning, stripping, and replacing of text.
"""
import re

class MessageCleaner:
    # Rule 11: Pre-compile regex for speed and precision
    # This specifically targets TG links and usernames without swallowing surrounding punctuation
    _LINK_PATTERN = re.compile(
        r'(?:https?://)?t\.me/(?:joinchat/|\+)?[\w_-]+/?(?:\d+)?|@[\w_]+', 
        re.IGNORECASE
    )

    @staticmethod
    def clean(text: str, mode: int, replacement: str = None) -> str:
        """
        Modes: 0 = As Is, 1 = Remove, 2 = Replace
        """
        if not text or mode == 0:
            return text

        cleaned_text = text
        
        # Rule 3: Single Responsibility - Handle matching in one pass
        if mode == 1:
            # Delete matches
            cleaned_text = MessageCleaner._LINK_PATTERN.sub('', cleaned_text)
        elif mode == 2:
            # Swap matches for custom link
            rep = replacement if replacement else ""
            cleaned_text = MessageCleaner._LINK_PATTERN.sub(rep, cleaned_text)

        # Rule 14: Final Polish
        # Remove triple+ newlines, double spaces, and lead/trail whitespace
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        
        return cleaned_text.strip()

def sanitize_channel_id(input_string: str) -> str:
    """
    Strips prefixes to get raw username or ID.
    Used for storage in the Vault.
    """
    if not input_string:
        return ""
        
    clean = input_string.strip()
    # Rule 4: Efficient prefix stripping
    prefixes = ["https://t.me/+", "https://t.me/joinchat/", "https://t.me/", "http://t.me/", "t.me/", "@"]
    
    for p in prefixes:
        if clean.startswith(p):
            clean = clean[len(p):] # Slice is more precise than replace()
            break # Only strip the first matching prefix
    
    return clean.rstrip("/")