from shared.hotelmaster_common import (
    decrypt_text,
    encrypt_text,
    parallel_booking_plan,
    shard_for_hotel,
    sign_token,
    verify_token,
)


def test_security_roundtrip() -> None:
    encrypted = encrypt_text("guest passport", "demo-key")
    assert decrypt_text(encrypted, "demo-key") == "guest passport"


def test_token_roundtrip() -> None:
    token = sign_token({"sub": "FD-1", "role": "receptionist"}, "jwt-secret", exp_minutes=5)
    payload = verify_token(token, "jwt-secret")
    assert payload is not None
    assert payload["sub"] == "FD-1"


def test_assignment_helpers() -> None:
    plan = parallel_booking_plan(5000, 5)
    assert plan["workers"] >= 2
    shard = shard_for_hotel("PROP-001", 8)
    assert 0 <= shard < 8
