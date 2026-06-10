import pytest
from backend.core.security.passwords import hash_password, verify_password


def test_password_hashing():
    pwd = "my_secure_password"
    pwd_hash = hash_password(pwd)

    assert pwd_hash != pwd
    assert pwd_hash.startswith("$argon2id$")

    # Verification
    assert verify_password(pwd, pwd_hash) is True
    assert verify_password("wrong_password", pwd_hash) is False
    assert verify_password("", pwd_hash) is False


def test_password_empty():
    with pytest.raises(ValueError):
        hash_password("")
