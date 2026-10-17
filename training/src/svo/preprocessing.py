import hashlib
import re
import unicodedata


def normalize(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a nonempty string")
    if len(text) > 10000:
        raise ValueError("text exceeds 10000 characters")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def text_hash(text):
    return hashlib.sha256(normalize(text).encode()).hexdigest()
