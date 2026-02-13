"""
CORE: REPOST LOGIC
Pure functions for text processing. 
Handles the actual cleaning, stripping, and replacing of text.
"""
import re

class MessageCleaner:
    @staticmethod
    def clean(text: str, mode: int, replacement: str = None) -> str:
        """
        Input: Raw text and filtering rules.
        Output: Sanitized text based on user preference.
        
        Modes: 0 = As Is, 1 = Remove, 2 = Replace
        """
        if not text or mode == 0:
            return text

        # Regex patterns for Telegram links and usernames
        # This catches: t.me/link, https://t.me/+, and @usernames
        patterns = [
            r'https?://t\.me/[\w\+/_]+', 
            r't\.me/[\w\+/_]+',
            r'@[\w_]+'
        ]

        cleaned_text = text
        
        for pattern in patterns:
            if mode == 1:
                # Mode 1: Delete the match entirely
                cleaned_text = re.sub(pattern, '', cleaned_text)
            elif mode == 2:
                # Mode 2: Swap the match for the user's custom link
                # If no replacement is provided, it defaults to an empty string
                rep = replacement if replacement else ""
                cleaned_text = re.sub(pattern, rep, cleaned_text)

        # Cleanup: Remove double spaces and empty lines left behind by deletions
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
        
        return cleaned_text.strip()

def sanitize_channel_id(input_string: str) -> str:
    """
    Strips 'https://t.me/' or '@' to get the raw username or ID.
    """
    if not input_string:
        return ""
        
    clean = input_string.strip()
    prefixes = ["https://t.me/+", "https://t.me/", "http://t.me/", "t.me/", "@"]
    
    for p in prefixes:
        if clean.startswith(p):
            clean = clean.replace(p, "")
    
    return clean.rstrip("/")