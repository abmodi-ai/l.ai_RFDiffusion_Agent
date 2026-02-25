"""Tests for auth utility functions (password hashing, JWT, user management)."""

import uuid

import pytest

from app.auth_utils import (
    authenticate_user,
    create_jwt,
    create_session,
    decode_jwt,
    hash_password,
    register_user,
    verify_password,
    verify_session,
)


class TestPasswordHashing:
    def test_hash_and_verify_correct_password(self):
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_not_plaintext(self):
        password = "test123"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$2")  # bcrypt prefix


class TestJWT:
    def test_create_and_decode_jwt(self, settings):
        token = create_jwt("session-token-abc", "user-id-123", settings)
        payload = decode_jwt(token, settings)
        assert payload is not None
        assert payload["sub"] == "session-token-abc"
        assert payload["user_id"] == "user-id-123"

    def test_decode_invalid_token(self, settings):
        payload = decode_jwt("invalid.token.here", settings)
        assert payload is None

    def test_decode_wrong_secret(self, settings):
        token = create_jwt("sess", "user", settings)

        class WrongSettings:
            JWT_SECRET_KEY = "wrong-secret"
            JWT_ALGORITHM = "HS256"

        payload = decode_jwt(token, WrongSettings())
        assert payload is None


class TestUserRegistration:
    def test_register_creates_user(self, db_session):
        user = register_user(db_session, "new@example.com", "Password123!", "New User")
        assert user.email_lower == "new@example.com"
        assert user.display_name == "New User"
        assert user.id is not None

    def test_register_duplicate_email_raises(self, db_session, test_user):
        with pytest.raises(ValueError, match="already exists"):
            register_user(db_session, "test@example.com", "Pass123!", "Duplicate")

    def test_register_case_insensitive_email(self, db_session, test_user):
        with pytest.raises(ValueError):
            register_user(db_session, "TEST@EXAMPLE.COM", "Pass123!", "Dup")


class TestAuthentication:
    def test_authenticate_valid_credentials(self, db_session, test_user):
        user = authenticate_user(db_session, "test@example.com", "TestPass123!")
        assert user is not None
        assert str(user.id) == str(test_user.id)

    def test_authenticate_wrong_password(self, db_session, test_user):
        user = authenticate_user(db_session, "test@example.com", "WrongPassword")
        assert user is None

    def test_authenticate_nonexistent_email(self, db_session):
        user = authenticate_user(db_session, "nobody@example.com", "Pass123!")
        assert user is None


class TestSessionManagement:
    def test_create_and_verify_session(self, db_session, test_user):
        session_obj = create_session(db_session, test_user.id, ip_address="127.0.0.1")
        assert session_obj.session_token is not None

        user = verify_session(db_session, session_obj.session_token)
        assert user is not None
        assert str(user.id) == str(test_user.id)

    def test_verify_nonexistent_session(self, db_session):
        user = verify_session(db_session, "nonexistent-token")
        assert user is None

    def test_verify_revoked_session(self, db_session, test_user):
        session_obj = create_session(db_session, test_user.id)
        session_obj.is_revoked = True
        db_session.flush()

        user = verify_session(db_session, session_obj.session_token)
        assert user is None
