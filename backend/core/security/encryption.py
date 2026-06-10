from cryptography.fernet import Fernet
from backend.core.config import LLM_CONFIG_ENCRYPTION_KEY

# Initialize the Fernet cipher suite
# Any invalid key format will cause failure on module load/startup (fail fast)
cipher_suite = Fernet(LLM_CONFIG_ENCRYPTION_KEY.encode())


def encrypt_llm_api_key(api_key: str) -> str:
    """Encrypt an API key using symmetric Fernet encryption."""
    if not api_key:
        raise ValueError("API key to encrypt cannot be empty")
    return cipher_suite.encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_llm_api_key(encrypted_api_key: str) -> str:
    """Decrypt an API key using symmetric Fernet decryption."""
    if not encrypted_api_key:
        raise ValueError("Encrypted API key cannot be empty")
    try:
        return cipher_suite.decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
