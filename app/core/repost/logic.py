"""
CORE: REPOST LOGIC
Pure functions for text processing. 
Handles the actual cleaning, stripping, and replacing of text.
"""
import re

class MessageCleaner:
    # Rule 11: Pre-compile regex for speed and precision
    # Matches:
    # 1. Protocols: http://, https://
    # 2. www. prefixes
    # 3. Known / common naked domain links (e.g. bit.ly/xxx, x.com/xxx, t.me/xxx, youtube.com/xxx)
    # 4. Telegram handles: @username
    _REMOVE_PATTERN = re.compile(
        r'(?:https?://[^\s]+|www\.[^\s]+|(?:[a-zA-Z0-9-]+\.)+(?:com|me|org|net|io|co|ly|ai|app|link|xyz|info|biz|dev|site|online|store|gg|ru|br|uk|de|tv)(?:/[^\s]*)?|@[\w_]+)',
        re.IGNORECASE
    )
    _TRAILING_PUNCT = re.compile(r'[.,;:!?)]+$')

    @staticmethod
    def clean(text: str, mode: int, replacement: str = None) -> str:
        """
        Modes: 
        0 = As Is (Keep Original)
        1 = Remove All Links & Handles
        2 = Replace with Custom Link / @Username
        3 = Nuke & Replace (Complete message replacement)
        """
        if not text or mode == 0:
            return text

        # Mode 3: Nuke & Replace (Rule 11: Total control)
        if mode == 3:
            return replacement if replacement else ""

        def _replace_match(match):
            raw = match.group(0)
            punct = ""
            m_punct = MessageCleaner._TRAILING_PUNCT.search(raw)
            if m_punct:
                punct = m_punct.group(0)
                raw = raw[:-len(punct)]
                
            if mode == 1:
                return punct
            elif mode == 2:
                rep = replacement.strip() if replacement else ""
                if rep:
                    return f"{rep}{punct}"
                return punct
            return raw + punct

        cleaned = MessageCleaner._REMOVE_PATTERN.sub(_replace_match, text)

        # Rule 14: Final Polish
        # Remove empty comma sequences, triple+ newlines, double spaces, and lead/trail whitespace
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r' +([.,;:!?])', r'\1', cleaned)
        cleaned = re.sub(r',\s*,+', ',', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        return cleaned.strip()

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