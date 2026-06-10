import os
from cryptography.fernet import Fernet

# Generate a temporary valid Fernet key and set it in environment before importing modules
# This guarantees configuration validation passes during test runs
TEST_KEY = Fernet.generate_key().decode()
os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = TEST_KEY

from backend.core.security.encryption import encrypt_llm_api_key, decrypt_llm_api_key
import pytest


def test_api_key_encryption_decryption():
    key = "sk-proj-test12345"
    enc = encrypt_llm_api_key(key)
    assert enc != key

    dec = decrypt_llm_api_key(enc)
    assert dec == key


def test_encryption_empty():
    with pytest.raises(ValueError):
        encrypt_llm_api_key("")
    with pytest.raises(ValueError):
        decrypt_llm_api_key("")


def test_decryption_invalid():
    with pytest.raises(ValueError):
        decrypt_llm_api_key("invalid_encrypted_data")
