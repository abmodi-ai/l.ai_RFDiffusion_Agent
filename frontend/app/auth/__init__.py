"""
Ligant.ai Authentication Package

Public API:
    require_auth  -- gate a Streamlit page behind authentication
    logout        -- revoke session, clear cookie, rerun
    render_login_page -- render the branded login/register page
"""

from .middleware import logout, require_auth  # noqa: F401
from .utils import (  # noqa: F401
    authenticate_user,
    create_session,
    hash_password,
    register_user,
    revoke_session,
    verify_password,
    verify_session,
)
