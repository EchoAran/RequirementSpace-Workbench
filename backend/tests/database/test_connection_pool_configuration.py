import pytest
from backend.database.database import engine

def test_engine_connection_pool_configuration():
    """Verify pool configuration parameter mapping on the instantiated DB engine."""
    assert engine.pool is not None
    
    # SQLite and PostgreSQL both should have pre-ping enabled
    assert engine.pool._pre_ping is True

    # If it is a PostgreSQL engine, it should also have pool_recycle set to 300
    db_url = str(engine.url)
    if "postgresql" in db_url or "postgres" in db_url:
        assert engine.pool._recycle == 300
    else:
        # For SQLite, pool_recycle is not enforced to 300, but let's log or check it's either unset (-1) or not crashing
        assert hasattr(engine.pool, "_recycle")
