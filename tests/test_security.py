from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, hash_token



def test_password_hash_and_verify():
    hashed = hash_password("CorrectHorse123")
    assert verify_password(hashed, "CorrectHorse123") is True


def test_password_verify_rejects_wrong_password():
    hashed = hash_password("CorrectHorse123")
    assert verify_password(hashed, "WrongPassword") is False


def test_access_token_roundtrip():
    token = create_access_token(user_id="11111111-1111-1111-1111-111111111111", role="user")
    payload = decode_access_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["role"] == "user"


def test_hash_token_is_deterministic():
    raw = "some-refresh-token-value"
    assert hash_token(raw) == hash_token(raw)