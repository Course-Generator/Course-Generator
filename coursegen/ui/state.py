"""Typed helpers around ``st.session_state``.

Widget keys are deliberately kept separate from application keys so a widget
value can never be mistaken for a domain object.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from coursegen.models import CourseArtifacts, UserAccount

PAGE = "cg_page"
ACCOUNT = "cg_account"
FLASH = "cg_flash"

PENDING_REGISTRATION = "cg_pending_registration"
REGISTRATION_CODE = "cg_registration_code"

RESET_EMAIL = "cg_reset_email"
RESET_CODE = "cg_reset_code"

EMAIL_CHANGE_VALUE = "cg_email_change_value"
EMAIL_CHANGE_CODE = "cg_email_change_code"

PROFILE_UNLOCKED = "cg_profile_unlocked"

BOOK_SIGNATURE = "cg_book_signature"
BOOK_PATH = "cg_book_path"
BOOK_CHAPTERS = "cg_book_chapters"
BOOK_ARTIFACTS = "cg_book_artifacts"

TYPED_ARTIFACTS = "cg_typed_artifacts"
LECTURE_PLAN = "cg_lecture_plan"
PLAN_VERSION = "cg_plan_version"

TASK_BOOK = "book"
TASK_TYPED = "typed"

_ARTIFACT_KEYS = {TASK_BOOK: BOOK_ARTIFACTS, TASK_TYPED: TYPED_ARTIFACTS}

_DEFAULTS = {
    PAGE: "login",
    ACCOUNT: None,
    FLASH: None,
    PENDING_REGISTRATION: None,
    REGISTRATION_CODE: "",
    RESET_EMAIL: "",
    RESET_CODE: "",
    EMAIL_CHANGE_VALUE: "",
    EMAIL_CHANGE_CODE: "",
    PROFILE_UNLOCKED: False,
    BOOK_SIGNATURE: "",
    BOOK_PATH: "",
    BOOK_CHAPTERS: [],
    BOOK_ARTIFACTS: None,
    TYPED_ARTIFACTS: None,
    LECTURE_PLAN: None,
    PLAN_VERSION: 0,
}


def initialize_state() -> None:
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def navigate(page: str) -> None:
    st.session_state[PAGE] = page
    st.rerun()


def current_account() -> Optional[UserAccount]:
    account = st.session_state.get(ACCOUNT)
    return account if isinstance(account, UserAccount) else None


def set_account(account: UserAccount) -> None:
    st.session_state[ACCOUNT] = account


def is_authenticated() -> bool:
    return current_account() is not None


def logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    initialize_state()
    st.session_state[PAGE] = "login"
    st.rerun()


# --------------------------------------------------------------------- flash
def flash(message: str, kind: str = "success") -> None:
    """Queue a message that survives the next rerun."""
    st.session_state[FLASH] = (kind, message)


def render_flash() -> None:
    pending = st.session_state.get(FLASH)
    if not pending:
        return
    st.session_state[FLASH] = None
    kind, message = pending
    renderer = {
        "success": st.success,
        "info": st.info,
        "warning": st.warning,
        "error": st.error,
    }.get(kind, st.success)
    renderer(message)


# ------------------------------------------------------------------ artifacts
def get_artifacts(task: str) -> Optional[CourseArtifacts]:
    artifacts = st.session_state.get(_ARTIFACT_KEYS[task])
    return artifacts if isinstance(artifacts, CourseArtifacts) else None


def set_artifacts(task: str, artifacts: CourseArtifacts) -> None:
    st.session_state[_ARTIFACT_KEYS[task]] = artifacts


def clear_artifacts(task: str) -> None:
    st.session_state[_ARTIFACT_KEYS[task]] = None


def get_plan_version() -> int:
    return int(st.session_state.get(PLAN_VERSION, 0) or 0)


def bump_plan_version() -> int:
    version = get_plan_version() + 1
    st.session_state[PLAN_VERSION] = version
    return version


def next_key(prefix: str, *parts: object) -> str:
    """Build a deterministic widget key scoped to a prefix."""
    return "_".join([prefix, *(str(part) for part in parts)])
