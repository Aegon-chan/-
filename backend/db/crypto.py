"""API Key encryption/decryption utility.

Uses Fernet (AES-128-CBC + HMAC-SHA256) symmetric encryption.
Key is derived deterministically from settings.app_secret_key via SHA256.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _derive_fernet_key(secret: str) -> bytes:
    """Derive 32-byte Fernet key from secret via SHA256 -> base64 urlsafe."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_secret() -> str:
    """Return a deterministic secret for Fernet key derivation.

    Always uses settings.app_secret_key regardless of whether it is a
    placeholder value, ensuring encrypt/decrypt consistency across runs.
    """
    from backend.config import settings
    return settings.app_secret_key


_fernet = None


def get_fernet():
    global _fernet
    if _fernet is None:
        key = _derive_fernet_key(_get_secret())
        _fernet = Fernet(key)
    return _fernet


def encrypt(value: str) -> str:
    f = get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    f = get_fernet()
    return f.decrypt(token.encode("utf-8")).decode("utf-8")
