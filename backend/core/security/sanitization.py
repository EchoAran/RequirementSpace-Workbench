import re

API_KEY_REGEX = re.compile(r"sk-[a-zA-Z0-9_\-]{8,}", re.IGNORECASE)
BEARER_REGEX = re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.\=\+]+", re.IGNORECASE)
COOKIE_REGEX = re.compile(r"auth_session=[a-zA-Z0-9_\-\.\=\+]+", re.IGNORECASE)
DB_CONN_REGEX = re.compile(r"([a-zA-Z0-9+]+://)([^:/]+):([^@/]+)(@)", re.IGNORECASE)

# Regex to match key-value assignments containing keys like api_key, secret, password, token, invite_code
# and mask their values whether they are quoted or unquoted.
ASSIGNMENT_SECRET_REGEX = re.compile(
    r"(?i)(['\"]?(?:api[-_]?key|secret|password|token|invite[-_]?code|db[-_]?url|database[-_]?url)['\"]?)(\s*[=:]+\s*)(?:(['\"])(.*?)\3|([^'\"\r\n,\s\}]{3,}))"
)

def sanitize_message(msg: str) -> str:
    """Sanitize database URLs, API keys, Bearer tokens, and cookies to prevent log leakage."""
    if not msg:
        return ""
    
    # 1. Sanitize database URLs
    msg = DB_CONN_REGEX.sub(r"\1\2:****\4", msg)
    
    # 2. Sanitize structured assignment secrets
    def repl_func(match):
        key = match.group(1)
        sep = match.group(2)
        quote = match.group(3)
        if quote:
            # Quoted secret is in group 4
            return f"{key}{sep}{quote}********{quote}"
        else:
            # Unquoted secret is in group 5
            return f"{key}{sep}********"
            
    msg = ASSIGNMENT_SECRET_REGEX.sub(repl_func, msg)
    
    # 3. Sanitize Bearer tokens
    msg = BEARER_REGEX.sub("Bearer ********", msg)
    
    # 4. Sanitize session cookies
    msg = COOKIE_REGEX.sub("auth_session=********", msg)
    
    # 5. Sanitize bare API keys matching sk-...
    msg = API_KEY_REGEX.sub("sk-********", msg)
    
    # 6. Dynamically extract current LLM config API key and replace it
    try:
        from backend.core.llm_context import current_llm_context
        ctx = current_llm_context.get()
        if ctx and ctx.api_key:
            raw_key = ctx.api_key.strip()
            if len(raw_key) >= 4 and raw_key in msg:
                msg = msg.replace(raw_key, "********")
    except Exception:
        pass
        
    # 7. Dynamically extract config credentials and replace them
    try:
        from backend.core.config import LLM_CONFIG_ENCRYPTION_KEY, ADMIN_INVITE_CODE_HASH
        if LLM_CONFIG_ENCRYPTION_KEY and len(LLM_CONFIG_ENCRYPTION_KEY) >= 4 and LLM_CONFIG_ENCRYPTION_KEY in msg:
            msg = msg.replace(LLM_CONFIG_ENCRYPTION_KEY, "********")
        if ADMIN_INVITE_CODE_HASH and len(ADMIN_INVITE_CODE_HASH) >= 4 and ADMIN_INVITE_CODE_HASH in msg:
            msg = msg.replace(ADMIN_INVITE_CODE_HASH, "********")
    except Exception:
        pass

    return msg

