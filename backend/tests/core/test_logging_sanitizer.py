from backend.core.logging.sanitizer import (
    preview_text,
    sanitize_database_url,
    sanitize_mapping,
    sanitize_message,
)


def test_sanitize_message_hides_tokens_api_keys_and_database_passwords():
    value = (
        "Authorization: Bearer abc.def.ghi "
        "api_key=plain-secret "
        "postgresql://admin:db-secret@localhost/private "
        "auth_session=session-secret"
    )

    sanitized = sanitize_message(value)

    assert "abc.def.ghi" not in sanitized
    assert "plain-secret" not in sanitized
    assert "db-secret" not in sanitized
    assert "session-secret" not in sanitized
    assert "Bearer ********" in sanitized
    assert "postgresql://admin:****@localhost/private" in sanitized


def test_sanitize_database_url_masks_password():
    sanitized = sanitize_database_url(
        "postgresql+asyncpg://user:secret@db.example.com:5432/requirement_space"
    )

    assert sanitized == "postgresql+asyncpg://user:****@db.example.com:5432/requirement_space"


def test_sanitize_mapping_masks_sensitive_keys_and_nested_values():
    sanitized = sanitize_mapping(
        {
            "LLM_API_KEY": "secret-key",
            "headers": {"Authorization": "Bearer token-value"},
            "database_url": "postgresql://user:secret@localhost/db",
        }
    )

    assert sanitized["LLM_API_KEY"] == "********"
    assert sanitized["headers"]["Authorization"] == "********"
    assert sanitized["database_url"] == "postgresql://user:****@localhost/db"


def test_preview_text_sanitizes_and_truncates():
    preview = preview_text("api_key=secret-token " + "x" * 50, max_chars=20)

    assert "secret-token" not in preview
    assert len(preview) == 20
