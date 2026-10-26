"""Public authentication pages."""

from __future__ import annotations

import logging

import streamlit as st

from coursegen.errors import CourseGenError
from coursegen.services.auth_service import AuthService, get_auth_service
from coursegen.ui import state
from coursegen.ui.dialogs import show_error
from coursegen.ui.theme import render_hero

logger = logging.getLogger(__name__)


def _auth() -> AuthService:
    return get_auth_service()


def _unexpected(exc: Exception, action: str) -> None:
    logger.exception("Unexpected error while %s: %s", action, exc)
    show_error(f"Something unexpected went wrong while {action}. Please try again.")


def login_page() -> None:
    render_hero()
    info, form_column = st.columns([1.1, 1])

    with info:
        st.markdown("### Learn from any book")
        st.markdown(
            "Upload a PDF or describe a course, and the app builds a slide deck, "
            "a narrated video, and an AI lecturer you can question."
        )
        st.markdown(
            """
            <div class="cg-card">
                <h4>What you get</h4>
                <p>Structured lectures, narrated videos, downloadable PowerPoint decks,
                and a lecturer that answers questions about the generated material.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with form_column:
        with st.container(border=True):
            st.subheader("Sign in")
            with st.form("cg_login_form"):
                identifier = st.text_input("Email or name")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

            if submitted:
                try:
                    account = _auth().login(identifier, password)
                except CourseGenError as exc:
                    show_error(str(exc))
                else:
                    state.set_account(account)
                    state.flash(f"Welcome back, {account.name}.")
                    state.navigate("app")

            columns = st.columns(2)
            if columns[0].button("Create account", use_container_width=True):
                state.navigate("register")
            if columns[1].button("Forgot password", use_container_width=True):
                state.navigate("forgot")


def register_page() -> None:
    render_hero("Create an account to start generating courses.")
    with st.container(border=True):
        st.subheader("Create account")
        with st.form("cg_register_form"):
            name = st.text_input("Name", help="Letters only, without spaces or special characters.")
            email = st.text_input("Email")
            age = st.number_input("Age", min_value=15, max_value=100, value=20)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            password = st.text_input("Password", type="password")
            confirmation = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Register", type="primary", use_container_width=True)

        if submitted:
            try:
                with st.spinner("Sending verification email..."):
                    pending, code = _auth().register(
                        name, email, int(age), gender, password, confirmation
                    )
            except CourseGenError as exc:
                show_error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive UI boundary
                _unexpected(exc, "creating your account")
            else:
                st.session_state[state.PENDING_REGISTRATION] = pending
                st.session_state[state.REGISTRATION_CODE] = code
                state.navigate("verification")

        if st.button("Back to sign in"):
            state.navigate("login")


def verification_page() -> None:
    render_hero("Confirm your email address.")
    pending = st.session_state.get(state.PENDING_REGISTRATION)
    if pending is None:
        st.warning("Your registration session expired. Please register again.")
        if st.button("Go to registration"):
            state.navigate("register")
        return

    with st.container(border=True):
        st.subheader("Email verification")
        st.caption(f"We sent a code to {pending.email}.")
        st.write(f"Name: {pending.name}")
        st.write(f"Email: {pending.email}")
        st.write(f"Age: {pending.age}")
        st.write(f"Gender: {pending.gender}")

        code = st.text_input("Verification code", key="cg_registration_code_input")
        if st.button("Verify", type="primary"):
            try:
                account = _auth().complete_registration(
                    pending,
                    code.strip(),
                    st.session_state.get(state.REGISTRATION_CODE, ""),
                )
            except CourseGenError as exc:
                show_error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive UI boundary
                _unexpected(exc, "verifying your account")
            else:
                st.session_state[state.PENDING_REGISTRATION] = None
                st.session_state[state.REGISTRATION_CODE] = ""
                state.set_account(account)
                state.flash("Your account is ready. Welcome aboard!")
                state.navigate("app")

    if st.button("Back to registration"):
        st.session_state[state.PENDING_REGISTRATION] = None
        st.session_state[state.REGISTRATION_CODE] = ""
        state.navigate("register")


def forgot_password_page() -> None:
    render_hero("Reset your password.")
    with st.container(border=True):
        st.subheader("Forgot password")
        email = st.text_input("Registered email", key="cg_forgot_email")
        if st.button("Send reset code", type="primary"):
            try:
                with st.spinner("Sending reset code..."):
                    code = _auth().request_password_reset(email)
            except CourseGenError as exc:
                show_error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive UI boundary
                _unexpected(exc, "sending the reset code")
            else:
                st.session_state[state.RESET_EMAIL] = email.strip()
                st.session_state[state.RESET_CODE] = code
                state.navigate("reset_code")

    if st.button("Back to sign in"):
        state.navigate("login")


def reset_code_page() -> None:
    render_hero("Enter the code we emailed you.")
    email = st.session_state.get(state.RESET_EMAIL, "")
    if not email:
        st.warning("Start the password reset again.")
        if st.button("Forgot password"):
            state.navigate("forgot")
        return

    with st.container(border=True):
        st.caption(f"Code sent to {email}.")
        code = st.text_input("Reset code", key="cg_reset_code_input")
        if st.button("Continue", type="primary"):
            try:
                _auth().verify_code(code.strip(), st.session_state.get(state.RESET_CODE, ""))
            except CourseGenError as exc:
                show_error(str(exc))
            else:
                state.navigate("reset_password")


def reset_password_page() -> None:
    render_hero("Choose a new password.")
    email = st.session_state.get(state.RESET_EMAIL, "")
    if not email:
        st.warning("Start the password reset again.")
        if st.button("Forgot password"):
            state.navigate("forgot")
        return

    with st.container(border=True):
        st.caption(f"Resetting the password for {email}.")
        password = st.text_input("New password", type="password", key="cg_reset_password")
        confirmation = st.text_input(
            "Confirm new password", type="password", key="cg_reset_confirmation"
        )
        if st.button("Reset password", type="primary"):
            try:
                _auth().reset_password(email, password, confirmation)
            except CourseGenError as exc:
                show_error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive UI boundary
                _unexpected(exc, "resetting your password")
            else:
                st.session_state[state.RESET_EMAIL] = ""
                st.session_state[state.RESET_CODE] = ""
                state.flash("Your password was reset. Sign in with the new one.")
                state.navigate("login")
