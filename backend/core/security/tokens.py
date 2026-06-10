import hashlib
import secrets


def generate_session_token() -> str:
    """Generate a secure, random 32-byte hex token (64 characters)."""
    return secrets.token_hex(32)


def hash_session_token(token: str) -> str:
    """Compute the SHA-256 hash of a session token for secure DB storage/lookup."""
    if not token:
        raise ValueError("Token cannot be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
