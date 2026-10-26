"""Page registry and authentication guard.

Pages are imported lazily so signing in does not pay for loading torch,
transformers, or moviepy before the user reaches the workspace.
"""

from __future__ import annotations

import importlib
import logging
from typing import Callable

import streamlit as st

from coursegen.ui import state
from coursegen.ui.theme import inject_css

logger = logging.getLogger(__name__)

_PAGE_LOADERS: dict[str, tuple[str, str]] = {
    "login": ("coursegen.ui.pages.auth_pages", "login_page"),
    "register": ("coursegen.ui.pages.auth_pages", "register_page"),
    "verification": ("coursegen.ui.pages.auth_pages", "verification_page"),
    "forgot": ("coursegen.ui.pages.auth_pages", "forgot_password_page"),
    "reset_code": ("coursegen.ui.pages.auth_pages", "reset_code_page"),
    "reset_password": ("coursegen.ui.pages.auth_pages", "reset_password_page"),
    "app": ("coursegen.ui.pages.course_page", "course_page"),
    "profile": ("coursegen.ui.pages.profile_pages", "profile_page"),
    "email_verification": ("coursegen.ui.pages.profile_pages", "email_verification_page"),
}

_PROTECTED = {"app", "profile", "email_verification"}
_PUBLIC_AUTH = {"login", "register", "verification", "forgot", "reset_code", "reset_password"}


def _resolve(page: str) -> Callable[[], None]:
    module_name, attribute = _PAGE_LOADERS[page]
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def run() -> None:
    state.initialize_state()
    inject_css()
    state.render_flash()

    page = st.session_state.get(state.PAGE, "login")
    if page not in _PAGE_LOADERS:
        page = "login"

    if page in _PROTECTED and not state.is_authenticated():
        page = "login"
    elif page in _PUBLIC_AUTH and state.is_authenticated():
        page = "app"

    st.session_state[state.PAGE] = page
    try:
        _resolve(page)()
    except Exception as exc:  # pragma: no cover - last-resort UI boundary
        logger.exception("Unhandled page error on %s: %s", page, exc)
        st.error("This page ran into an unexpected problem. Check the application logs.")
