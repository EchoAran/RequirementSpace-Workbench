import os
import sys
import importlib
import pytest

def test_production_cookie_enforcement():
    # Save original env variables
    orig_env = os.environ.get("ENV")
    orig_secure = os.environ.get("AUTH_COOKIE_SECURE")
    
    try:
        # 1. Setup invalid production config (Cookie not secure)
        os.environ["ENV"] = "production"
        os.environ["AUTH_COOKIE_SECURE"] = "false"
        
        # Import config module
        from backend.core import config
        
        with pytest.raises(ValueError) as excinfo:
            importlib.reload(config)
            
        assert "AUTH_COOKIE_SECURE must be true in production" in str(excinfo.value)
        
        # 2. Setup valid production config (Cookie secure)
        os.environ["ENV"] = "production"
        os.environ["AUTH_COOKIE_SECURE"] = "true"
        
        # This reload should succeed
        importlib.reload(config)
        assert config.AUTH_COOKIE_SECURE is True
        
    finally:
        # Restore original env variables
        if orig_env is not None:
            os.environ["ENV"] = orig_env
        else:
            os.environ.pop("ENV", None)
            
        if orig_secure is not None:
            os.environ["AUTH_COOKIE_SECURE"] = orig_secure
        else:
            os.environ.pop("AUTH_COOKIE_SECURE", None)
            
        # Reload to restore original config module state
        from backend.core import config
        importlib.reload(config)
