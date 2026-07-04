import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Resolve project root and load .env file
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Centralized Settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./requirement_space.db").strip("'\" ")

ADMIN_INVITE_CODE_HASH = os.getenv("ADMIN_INVITE_CODE_HASH", "").strip()

# Load and validate LLM_CONFIG_ENCRYPTION_KEY
LLM_CONFIG_ENCRYPTION_KEY = os.getenv("LLM_CONFIG_ENCRYPTION_KEY", "").strip()

if not LLM_CONFIG_ENCRYPTION_KEY:
    raise ValueError(
        "CRITICAL CONFIG ERROR: 'LLM_CONFIG_ENCRYPTION_KEY' environment variable is missing. "
        "It must be configured in .env as a 32-byte URL-safe base64-encoded key for credential encryption."
    )

try:
    # Attempt to initialize Fernet to validate the key format
    Fernet(LLM_CONFIG_ENCRYPTION_KEY.encode())
except Exception as e:
    raise ValueError(
        f"CRITICAL CONFIG ERROR: 'LLM_CONFIG_ENCRYPTION_KEY' is invalid: {str(e)}. "
        "A valid key must be 32 URL-safe base64-encoded bytes. "
        "You can generate one using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

# Session config
try:
    AUTH_SESSION_EXPIRE_DAYS = int(os.getenv("AUTH_SESSION_EXPIRE_DAYS", "30").strip())
except ValueError:
    AUTH_SESSION_EXPIRE_DAYS = 30

AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() in ("true", "1", "yes")
ENV = os.getenv("ENV", "development").strip().lower()

if ENV == "production" and not AUTH_COOKIE_SECURE:
    raise ValueError("AUTH_COOKIE_SECURE must be true in production")

AUTH_COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "").strip()
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()

# Knowledge Base Settings
KNOWLEDGE_STORAGE_DIR = os.getenv("KNOWLEDGE_STORAGE_DIR", "storage/knowledge").strip()
try:
    KNOWLEDGE_MAX_FILE_SIZE_MB = int(os.getenv("KNOWLEDGE_MAX_FILE_SIZE_MB", "25").strip())
except ValueError:
    KNOWLEDGE_MAX_FILE_SIZE_MB = 25

allowed_exts_str = os.getenv("KNOWLEDGE_ALLOWED_EXTENSIONS", ".pdf,.docx,.pptx,.xlsx,.md,.txt,.csv,.json,.html").strip()
KNOWLEDGE_ALLOWED_EXTENSIONS = [ext.strip().lower() for ext in allowed_exts_str.split(",") if ext.strip()]

try:
    KNOWLEDGE_MAX_PROJECT_STORAGE_MB = int(os.getenv("KNOWLEDGE_MAX_PROJECT_STORAGE_MB", "200").strip())
except ValueError:
    KNOWLEDGE_MAX_PROJECT_STORAGE_MB = 200

# Feature Flag
KNOWLEDGE_BASE_ENABLED = os.getenv("KNOWLEDGE_BASE_ENABLED", "true").strip().lower() in ("true", "1", "yes")
