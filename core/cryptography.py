"""A few simple functions to handle encrypting data"""

import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet


def _get_raw_key() -> bytes:
    """Gets the raw key from the environment.

    Raises:
        AttributeError: Raised if no key is present.

    Returns:
        bytes: The raw encryption key.
    """
    env_file_key = os.environ.get("DATA_ENCRYPT_KEY")
    if not env_file_key:
        raise AttributeError("Missing data encryption key, data cannot be secure")

    return env_file_key.encode("utf-8")


def _get_key() -> bytes:
    """Processes the raw key into a format that Fernet accepts.

    Returns:
        bytes: A Fernet-compatible key.
    """
    digest = hashlib.sha256(_get_raw_key()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(text: str) -> str:
    """Encrypts plaintext.

    Args:
        text (str): The plaintext to encrypt.

    Returns:
        str: The encrypted text.
    """
    f = Fernet(_get_key())
    token = f.encrypt(text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypts encrypted text.

    Args:
        token (str): The encrypted text to decrypt.

    Returns:
        str: The decrypted plaintext.
    """
    f = Fernet(_get_key())
    return f.decrypt(token.encode("utf-8")).decode("utf-8")


def hash_text(text: str) -> str:
    """Creates a deterministic hash suitable for equality checks.

    This should be stored alongside encrypted data to support
    duplicate detection and lookups.

    Args:
        text (str): The plaintext to hash.

    Returns:
        str: The hexadecimal HMAC digest.
    """
    return hmac.new(
        _get_raw_key(),
        text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
