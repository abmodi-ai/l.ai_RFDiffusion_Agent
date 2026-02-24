"""
Ligant.ai Login Page Component

Renders the branded authentication page with app title, subtitle,
and the login / register tab forms provided by the auth middleware.
"""

import streamlit as st

from ..auth.middleware import _show_auth_forms


# ── Custom CSS for the login page ─────────────────────────────────────────────

_LOGIN_PAGE_CSS = """
<style>
    /* Centre the form block and limit its width */
    div[data-testid="stForm"] {
        max-width: 420px;
        margin: 0 auto;
    }

    /* Title styling */
    .login-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 700;
        margin-bottom: 0;
        padding-top: 2rem;
    }

    .login-subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #6c757d;
        margin-top: 0.2rem;
        margin-bottom: 2rem;
    }

    /* Add breathing room around the tabs */
    div[data-testid="stTabs"] {
        max-width: 480px;
        margin: 0 auto;
    }
</style>
"""


def render_login_page() -> None:
    """
    Render the full-page login / registration view.

    This function is intended to be called when ``require_auth()`` returns
    ``None``, giving unauthenticated visitors a polished landing page
    rather than a blank screen.

    Layout
    ------
    1. Application title -- "Ligant.ai"
    2. Descriptive subtitle
    3. Login / Register tabbed forms (delegated to ``_show_auth_forms``)
    4. A subtle footer with a link to documentation / support
    """
    # Inject page-level CSS
    st.markdown(_LOGIN_PAGE_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────
    st.markdown(
        '<p class="login-title">Ligant.ai</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="login-subtitle">'
        "AI-powered protein design with RFdiffusion"
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Auth forms ────────────────────────────────────────────────────────
    _show_auth_forms()

    # ── Footer ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        "By signing in you agree to the Ligant.ai Terms of Service. "
        "Need help? Contact support@ligant.ai"
    )
