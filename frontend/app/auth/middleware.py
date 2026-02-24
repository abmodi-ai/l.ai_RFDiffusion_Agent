"""
Ligant.ai Streamlit Authentication Middleware

Provides ``require_auth()`` -- call it at the top of every protected page
to gate access behind login.  Also exposes ``logout()`` for the sidebar.

Cookie-based sessions use JWT tokens stored in a browser cookie managed
by ``extra-streamlit-components``.
"""

import logging
from typing import Optional

import streamlit as st
from extra_streamlit_components import CookieManager

from ..config import get_settings
from ..db.audit import log_login, log_logout, log_register
from ..db.connection import get_db
from ..db.models import User
from .utils import (
    authenticate_user,
    create_jwt,
    create_session,
    decode_jwt,
    register_user,
    revoke_session,
    verify_session,
)

logger = logging.getLogger(__name__)


# ── Cookie manager singleton ─────────────────────────────────────────────────


def get_cookie_manager() -> CookieManager:
    """
    Return a singleton ``CookieManager`` instance.

    The manager is stored in ``st.session_state`` so that only one instance
    exists per Streamlit browser session, preventing duplicate component
    registration errors.
    """
    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = CookieManager()
    return st.session_state["cookie_manager"]


# ── Main auth gate ────────────────────────────────────────────────────────────


def require_auth() -> Optional[User]:
    """
    Enforce authentication on the current page.

    Call this at the very top of a Streamlit page script.  It returns the
    authenticated ``User`` object if a valid session exists, or ``None``
    after rendering login / register forms so the caller can ``st.stop()``.

    Flow
    ----
    1. Read the JWT from the session cookie.
    2. Decode the JWT to extract the ``session_token``.
    3. Verify the session against the database.
    4. If everything checks out, cache the user in session state and return it.
    5. On any failure, clear stale state and show the auth forms.
    """
    settings = get_settings()
    cookie_mgr = get_cookie_manager()

    # Read the JWT cookie
    jwt_cookie = cookie_mgr.get(settings.SESSION_COOKIE_NAME)

    if not jwt_cookie:
        _show_auth_forms()
        return None

    # Decode the JWT
    payload = decode_jwt(jwt_cookie, settings)
    if payload is None:
        # Token is invalid or expired -- clear it
        cookie_mgr.delete(settings.SESSION_COOKIE_NAME)
        _show_auth_forms()
        return None

    session_token = payload.get("sub")
    if not session_token:
        cookie_mgr.delete(settings.SESSION_COOKIE_NAME)
        _show_auth_forms()
        return None

    # Verify the database session
    with get_db() as db:
        user = verify_session(db, session_token)

    if user is None:
        cookie_mgr.delete(settings.SESSION_COOKIE_NAME)
        if "authenticated_user" in st.session_state:
            del st.session_state["authenticated_user"]
        _show_auth_forms()
        return None

    # Success -- cache in session state
    st.session_state["authenticated_user"] = user
    return user


# ── Auth forms ────────────────────────────────────────────────────────────────


def _show_auth_forms() -> None:
    """
    Render Login and Register tabs inside a centered column.

    On successful form submission the JWT cookie is set and the page
    is rerun so that ``require_auth()`` picks up the new session.
    """
    settings = get_settings()
    cookie_mgr = get_cookie_manager()

    login_tab, register_tab = st.tabs(["Login", "Register"])

    # ── Login tab ─────────────────────────────────────────────────────────
    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            st.subheader("Sign in to your account")
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input(
                "Password", type="password", key="login_password"
            )
            login_submitted = st.form_submit_button(
                "Sign in", use_container_width=True
            )

        if login_submitted:
            if not login_email or not login_password:
                st.error("Please enter both email and password.")
                return

            with get_db() as db:
                user = authenticate_user(db, login_email, login_password)
                if user is None:
                    st.error("Invalid email or password.")
                    return

                # Create a DB session row
                session_obj = create_session(db, user.id)

                # Build JWT and set the cookie
                jwt_token = create_jwt(
                    session_token=session_obj.session_token,
                    user_id=str(user.id),
                    settings=settings,
                )
                cookie_mgr.set(
                    settings.SESSION_COOKIE_NAME,
                    jwt_token,
                    expires_at=session_obj.expires_at,
                    key="set_login_cookie",
                )

                # Audit
                log_login(db, user.id)

            st.success("Signed in successfully.")
            st.rerun()

    # ── Register tab ──────────────────────────────────────────────────────
    with register_tab:
        with st.form("register_form", clear_on_submit=False):
            st.subheader("Create a new account")
            reg_display_name = st.text_input("Display name", key="reg_display_name")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input(
                "Password", type="password", key="reg_password"
            )
            reg_confirm = st.text_input(
                "Confirm password", type="password", key="reg_confirm"
            )
            register_submitted = st.form_submit_button(
                "Create account", use_container_width=True
            )

        if register_submitted:
            # ── Validation ────────────────────────────────────────────────
            if not reg_email or not reg_password or not reg_display_name:
                st.error("All fields are required.")
                return
            if reg_password != reg_confirm:
                st.error("Passwords do not match.")
                return
            if len(reg_password) < 8:
                st.error("Password must be at least 8 characters.")
                return

            with get_db() as db:
                try:
                    user = register_user(
                        db, reg_email, reg_password, reg_display_name
                    )
                except ValueError as exc:
                    st.error(str(exc))
                    return

                # Create a DB session row
                session_obj = create_session(db, user.id)

                # Build JWT and set the cookie
                jwt_token = create_jwt(
                    session_token=session_obj.session_token,
                    user_id=str(user.id),
                    settings=settings,
                )
                cookie_mgr.set(
                    settings.SESSION_COOKIE_NAME,
                    jwt_token,
                    expires_at=session_obj.expires_at,
                    key="set_register_cookie",
                )

                # Audit
                log_register(db, user.id)

            st.success("Account created! Signing you in...")
            st.rerun()


# ── Logout ────────────────────────────────────────────────────────────────────


def logout() -> None:
    """
    Revoke the current session, clear the cookie and session state, and
    force a page rerun to return to the login screen.

    Safe to call even if the user is not currently authenticated.
    """
    settings = get_settings()
    cookie_mgr = get_cookie_manager()

    jwt_cookie = cookie_mgr.get(settings.SESSION_COOKIE_NAME)
    if jwt_cookie:
        payload = decode_jwt(jwt_cookie, settings)
        if payload:
            session_token = payload.get("sub")
            user_id = payload.get("user_id")
            if session_token and user_id:
                with get_db() as db:
                    revoke_session(db, session_token, user_id)
                    log_logout(db, user_id)

    # Clear the cookie
    cookie_mgr.delete(settings.SESSION_COOKIE_NAME, key="delete_session_cookie")

    # Clear Streamlit session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()
