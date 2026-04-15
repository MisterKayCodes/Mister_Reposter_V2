"""
CORE: REPOST LOGIC
Pure functions for text processing. 
Handles the actual cleaning, stripping, and replacing of text.
"""
import re

class MessageCleaner:
    # Rule 11: Pre-compile regex for speed and precision
    # This specifically targets TG links and usernames without swallowing surrounding punctuation
    _REMOVE_PATTERN = re.compile(
        r'(?:https?://)?t\.me/(?:joinchat/|\+)?[\w_-]+/?(?:\d+)?|@[\w_]+', 
        re.IGNORECASE
    )
    _REPLACE_PATTERN = re.compile(
        r'(?:https?://)?t\.me/(?:joinchat/|\+)?[\w_-]+/?(?:\d+)?', 
        re.IGNORECASE
    )

    # This is like a 'Bouncers' checklist at a club. 
    # It scans every message and either keeps it as-is, deletes links/usernames, 
    # or swaps them for something else. We also perform a 'Final Polish' to 
    # remove extra spaces and messy formatting.
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
            # Delete matches (including @usernames)
            cleaned_text = MessageCleaner._REMOVE_PATTERN.sub('', cleaned_text)
        elif mode == 2:
            # Swap matches for custom link (including @usernames for cross-promotion)
            rep = replacement if replacement else ""
            cleaned_text = MessageCleaner._REMOVE_PATTERN.sub(rep, cleaned_text)

        # Rule 14: Final Polish
        # Remove triple+ newlines, double spaces, and lead/trail whitespace
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        
        return cleaned_text.strip()

# Think of this like 'Cleaning the mud off a shoe' before entering the house.
# We strip off link prefixes like 'https://t.me/' so we're left with just 
# the raw channel name or ID that our database (the Vault) expects.
def sanitize_channel_id(input_string: str) -> str:
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