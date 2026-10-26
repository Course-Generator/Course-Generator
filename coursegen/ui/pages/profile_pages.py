"""Profile, credential, and email-change pages."""

from __future__ import annotations

import logging

import streamlit as st

from coursegen.errors import CourseGenError
from coursegen.services.auth_service import AuthService, get_auth_service
from coursegen.ui import state
from coursegen.ui.dialogs import show_error
from coursegen.ui.theme import render_hero

logger = logging.getLogger(__name__)

_GENDERS = ["Male", "Female", "Other"]


def _auth() -> AuthService:
    return get_auth_service()


def _account():
    return state.current_account()


def _unexpected(exc: Exception, action: str) -> None:
    logger.exception("Unexpected error while %s: %s", action, exc)
    show_error(f"Something unexpected went wrong while {action}. Please try again.")


def profile_page() -> None:
    account = _account()
    if account is None:
        state.navigate("login")
        return

    render_hero(f"Signed in as {account.name}.")
    top = st.columns([1, 1, 1, 1])
    if top[0].button("Back to courses", use_container_width=True):
        state.navigate("app")
    if top[3].button("Log out", use_container_width=True):
        state.logout()

    if not st.session_state.get(state.PROFILE_UNLOCKED):
        _render_unlock(account)
        return

    details, security, email = st.tabs(["Profile details", "Password", "Email address"])
    with details:
        _render_details(account)
    with security:
        _render_password(account)
    with email:
        _render_email(account)


def _render_unlock(account) -> None:
    with st.container(border=True):
        st.subheader("Confirm your password")
        st.caption("Your profile is locked to keep your account safe.")
        password = st.text_input("Password", type="password", key="cg_profile_unlock_password")
        if st.button("Unlock profile", type="primary"):
            if _auth().verify_password(account, password):
                st.session_state[state.PROFILE_UNLOCKED] = True
                st.rerun()
            else:
                show_error("Wrong password.")


def _render_details(account) -> None:
    st.markdown("#### Your details")
    with st.form("cg_profile_details"):
        name = st.text_input("Name", value=account.name)
        age = st.number_input("Age", min_value=15, max_value=100, value=int(account.age))
        gender = st.selectbox(
            "Gender",
            _GENDERS,
            index=_GENDERS.index(account.gender) if account.gender in _GENDERS else 0,
        )
        submitted = st.form_submit_button("Save changes", type="primary")
    if submitted:
        try:
            _auth().update_profile(account, name, int(age), gender)
        except CourseGenError as exc:
            show_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            _unexpected(exc, "saving your profile")
        else:
            state.flash("Your details were saved.")
            st.rerun()


def _render_password(account) -> None:
    st.markdown("#### Change password")
    with st.form("cg_profile_password", clear_on_submit=True):
        password = st.text_input("New password", type="password")
        confirmation = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password", type="primary")
    if submitted:
        try:
            _auth().change_password(account, password, confirmation)
        except CourseGenError as exc:
            show_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            _unexpected(exc, "changing your password")
        else:
            state.flash("Your password was updated.")
            st.rerun()


def _render_email(account) -> None:
    st.markdown("#### Change email")
    st.caption(f"Current email: {account.email}")
    new_email = st.text_input("New email", key="cg_profile_new_email")
    if st.button("Send verification code", type="primary"):
        try:
            with st.spinner("Sending verification code..."):
                code = _auth().request_email_change(account, new_email)
        except CourseGenError as exc:
            show_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            _unexpected(exc, "starting the email change")
        else:
            st.session_state[state.EMAIL_CHANGE_VALUE] = new_email.strip()
            st.session_state[state.EMAIL_CHANGE_CODE] = code
            state.navigate("email_verification")


def email_verification_page() -> None:
    account = _account()
    if account is None:
        state.navigate("login")
        return

    render_hero("Confirm your new email address.")
    new_email = st.session_state.get(state.EMAIL_CHANGE_VALUE, "")
    if not new_email:
        st.warning("Start the email change again from your profile.")
        if st.button("Go to profile"):
            state.navigate("profile")
        return

    with st.container(border=True):
        st.caption(f"We sent a code to {new_email}.")
        code = st.text_input("Verification code", key="cg_email_change_code_input")
        if st.button("Confirm email", type="primary"):
            try:
                _auth().confirm_email_change(
                    account,
                    new_email,
                    code.strip(),
                    st.session_state.get(state.EMAIL_CHANGE_CODE, ""),
                )
            except CourseGenError as exc:
                show_error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive UI boundary
                _unexpected(exc, "confirming your email")
            else:
                st.session_state[state.EMAIL_CHANGE_VALUE] = ""
                st.session_state[state.EMAIL_CHANGE_CODE] = ""
                state.flash("Your email address was updated.")
                state.navigate("profile")

    if st.button("Cancel"):
        st.session_state[state.EMAIL_CHANGE_VALUE] = ""
        st.session_state[state.EMAIL_CHANGE_CODE] = ""
        state.navigate("profile")
