import pytest
from backend.core.security.tokens import generate_session_token, hash_session_token


def test_generate_session_token():
    token1 = generate_session_token()
    token2 = generate_session_token()

    assert len(token1) == 64  # 32 bytes in hex = 64 characters
    assert token1 != token2  # Unique


def test_hash_session_token():
    token = generate_session_token()
    h1 = hash_session_token(token)
    h2 = hash_session_token(token)

    assert len(h1) == 64  # SHA-256 is 64 hex characters
    assert h1 == h2  # Stable / deterministic

    # Hash of different token should be different
    token2 = generate_session_token()
    h3 = hash_session_token(token2)
    assert h1 != h3


def test_hash_session_token_empty():
    with pytest.raises(ValueError):
        hash_session_token("")
