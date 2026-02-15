"""Pure unit tests for OTP functions — no API, no DB."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from modules.settings.otp import (
    check_otp_hash,
    generate_otp,
    hash_otp,
    invalidate_otp,
    mask_email,
    store_otp,
    verify_otp,
)


class TestOTPGeneration:
    def test_otp_is_six_digits(self):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_otp_is_string(self):
        otp = generate_otp()
        assert isinstance(otp, str)

    def test_otp_varies(self):
        """Multiple calls should produce different values (probabilistic)."""
        otps = {generate_otp() for _ in range(20)}
        assert len(otps) > 1


class TestOTPHashAndVerify:
    def test_hash_and_check_correct(self):
        otp = "123456"
        hashed = hash_otp(otp)
        assert check_otp_hash(otp, hashed) is True

    def test_hash_check_wrong_otp(self):
        otp = "123456"
        hashed = hash_otp(otp)
        assert check_otp_hash("654321", hashed) is False

    def test_hash_is_not_plaintext(self):
        otp = "123456"
        hashed = hash_otp(otp)
        assert hashed != otp
        assert len(hashed) > 20  # bcrypt hashes are long

    def test_different_otps_produce_different_hashes(self):
        h1 = hash_otp("111111")
        h2 = hash_otp("222222")
        assert h1 != h2


class TestOTPStorageAndVerification:
    @pytest.fixture
    def mock_redis(self):
        """Mock redis_client for OTP storage tests."""
        with patch("modules.settings.otp.redis_client") as mock:
            mock.setex = AsyncMock()
            mock.get = AsyncMock()
            mock.delete = AsyncMock()
            yield mock

    async def test_store_and_verify(self, mock_redis):
        cr_id = uuid.uuid4()
        otp = "123456"

        # Store OTP
        await store_otp(cr_id, otp, ttl_seconds=600)
        mock_redis.setex.assert_called_once()
        stored_hash = mock_redis.setex.call_args[0][2]

        # Verify correct OTP
        mock_redis.get.return_value = stored_hash
        result = await verify_otp(cr_id, otp)
        assert result is True

    async def test_verify_wrong_otp(self, mock_redis):
        cr_id = uuid.uuid4()

        await store_otp(cr_id, "123456")
        stored_hash = mock_redis.setex.call_args[0][2]

        mock_redis.get.return_value = stored_hash
        result = await verify_otp(cr_id, "654321")
        assert result is False

    async def test_verify_missing_key(self, mock_redis):
        mock_redis.get.return_value = None
        result = await verify_otp(uuid.uuid4(), "123456")
        assert result is False

    async def test_invalidate(self, mock_redis):
        cr_id = uuid.uuid4()
        await invalidate_otp(cr_id)
        mock_redis.delete.assert_called_once_with(f"otp:{cr_id}")


class TestEmailMasking:
    def test_normal_email(self):
        assert mask_email("admin@demo.co") == "ad***@demo.co"

    def test_single_char_local(self):
        assert mask_email("a@demo.co") == "a***@demo.co"

    def test_no_at_sign(self):
        assert mask_email("invalid") == "invalid"

    def test_two_char_local(self):
        assert mask_email("ab@test.com") == "ab***@test.com"

    def test_long_local(self):
        assert mask_email("verylongemail@test.com") == "ve***@test.com"
