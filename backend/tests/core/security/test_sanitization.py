import pytest
from backend.core.security.sanitization import sanitize_message
from backend.core.llm_context import current_llm_context, LLMRequestContext

def test_sanitize_message_standard_patterns():
    # Test sk- patterns
    assert sanitize_message("my api key is sk-123456789abc") == "my api key is sk-********"
    
    # Test DB connection strings
    assert sanitize_message("postgresql://user:password123@host:5432/dbname") == "postgresql://user:****@host:5432/dbname"
    assert sanitize_message("postgresql+asyncpg://admin:my-secret-pass@localhost/db") == "postgresql+asyncpg://admin:****@localhost/db"
    
    # Test Bearer header
    assert sanitize_message("Authorization: Bearer my_jwt_token_here") == "Authorization: Bearer ********"
    
    # Test Cookie header
    assert sanitize_message("Cookie: auth_session=session_token_123;") == "Cookie: auth_session=********;"

def test_sanitize_message_plain_key_assignments():
    # Test plain key assignments
    assert sanitize_message("api_key=plain-secret") == "api_key=********"
    assert sanitize_message("api-key=plain-secret") == "api-key=********"
    assert sanitize_message("api_key = 'plain-secret'") == "api_key = '********'"
    assert sanitize_message('"api_key": "mysecretkey"') == '"api_key": "********"'
    assert sanitize_message("secret = plain-secret") == "secret = ********"
    assert sanitize_message("invite_code = admin123") == "invite_code = ********"
    assert sanitize_message("password: plain-secret") == "password: ********"

def test_sanitize_message_dynamic_context():
    # Set context
    ctx = LLMRequestContext(
        api_url="http://localhost",
        api_key="my-super-secret-key-12345",
        model_name="gpt-4"
    )
    token = current_llm_context.set(ctx)
    try:
        # Traceback contains the actual key as a variable value or message
        msg = "Exception: Failed to connect with my-super-secret-key-12345 to OpenAI."
        assert "my-super-secret-key-12345" not in sanitize_message(msg)
        assert sanitize_message(msg) == "Exception: Failed to connect with ******** to OpenAI."
    finally:
        current_llm_context.reset(token)

def test_sanitize_message_dynamic_settings():
    # Dynamically gets LLM_CONFIG_ENCRYPTION_KEY and ADMIN_INVITE_CODE_HASH
    from backend.core.config import LLM_CONFIG_ENCRYPTION_KEY
    if LLM_CONFIG_ENCRYPTION_KEY:
        msg = f"Failed to decrypt with key: {LLM_CONFIG_ENCRYPTION_KEY}"
        assert LLM_CONFIG_ENCRYPTION_KEY not in sanitize_message(msg)
        assert "********" in sanitize_message(msg)
