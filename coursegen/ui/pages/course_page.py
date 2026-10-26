"""The main authenticated workspace: generate, review, and publish courses."""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

from coursegen.ai.lecture_generator import LectureGenerator
from coursegen.config import get_settings
from coursegen.errors import CourseGenError
from coursegen.services.course_service import CourseService, get_course_service
from coursegen.services.pdf_service import PdfService, get_pdf_service
from coursegen.ui import components, state
from coursegen.ui.dialogs import complete, progress_steps, show_error
from coursegen.ui.theme import render_account_chip, render_hero

logger = logging.getLogger(__name__)

_MENU_STYLES = {
    "container": {
        "background-color": "#14201d",
        "border": "1px solid rgba(230, 230, 250, 0.12)",
        "border-radius": "12px",
        "padding": "4px",
    },
    "icon": {"color": "#6fd3b5", "font-size": "16px"},
    "nav-link": {"color": "#e6e6fa", "font-size": "15px", "--hover-color": "#1a2a26"},
    "nav-link-selected": {"background-color": "#3f8f7c", "color": "#06110e"},
}


def course_page() -> None:
    account = state.current_account()
    if account is None:
        state.navigate("login")
        return

    settings = get_settings()
    service = get_course_service()

    render_hero(f"Welcome back, {account.name}. What are we teaching today?")
    header = st.columns([5, 1, 1])
    with header[0]:
        render_account_chip(account)
    if header[1].button("Profile", use_container_width=True):
        state.navigate("profile")
    if header[2].button("Log out", use_container_width=True):
        state.logout()

    if not settings.conversation_pickle.is_file():
        st.warning(
            "The reference file `conversation.pkl` was not found. Course generation needs it; "
            f"place it at `{settings.conversation_pickle}`."
        )

    components.render_library(account, service)

    task = option_menu(
        menu_title=None,
        options=["Upload a book", "Type a course"],
        icons=["cloud-arrow-up-fill", "pen"],
        orientation="horizontal",
        styles=_MENU_STYLES,
        key="cg_task_menu",
    )

    if task == "Upload a book":
        _book_flow(service, settings)
        active = state.TASK_BOOK
    else:
        _typed_flow(service)
        active = state.TASK_TYPED

    artifacts = state.get_artifacts(active)
    if artifacts is None:
        return

    st.divider()
    st.markdown("### Generated course")
    components.render_artifacts(active, artifacts, account, service)

    if st.button("Clear this result", key=f"cg_clear_{active}"):
        state.clear_artifacts(active)
        st.rerun()


# --------------------------------------------------------------------- book
def _book_flow(service: CourseService, settings) -> None:
    pdf_service: PdfService = get_pdf_service()
    uploaded = st.file_uploader("Upload your book (PDF)", type=["pdf"], key="cg_book_upload")

    if uploaded is None:
        if st.session_state.get(state.BOOK_SIGNATURE):
            st.session_state[state.BOOK_SIGNATURE] = ""
            st.session_state[state.BOOK_CHAPTERS] = []
            st.session_state[state.BOOK_PATH] = ""
        st.caption("The book needs a table of contents so chapters can be detected.")
        return

    signature = f"{uploaded.name}:{uploaded.size}"
    if signature != st.session_state.get(state.BOOK_SIGNATURE):
        st.session_state[state.BOOK_SIGNATURE] = signature
        st.session_state[state.BOOK_CHAPTERS] = []
        st.session_state[state.BOOK_PATH] = ""
        state.clear_artifacts(state.TASK_BOOK)
        try:
            with st.spinner("Reading the book outline..."):
                path = pdf_service.save_upload(uploaded)
                chapters = pdf_service.extract_chapters(path)
        except CourseGenError as exc:
            state.flash(str(exc), "error")
            st.rerun()
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            logger.exception("Could not process the uploaded book: %s", exc)
            state.flash("The book could not be processed. Check the logs.", "error")
            st.rerun()
        else:
            st.session_state[state.BOOK_PATH] = str(path)
            st.session_state[state.BOOK_CHAPTERS] = chapters

    chapters = st.session_state.get(state.BOOK_CHAPTERS) or []
    path = st.session_state.get(state.BOOK_PATH) or ""
    if not chapters or not path:
        st.info("No chapter outline was found. Try a PDF whose bookmarks list its chapters.")
        return

    titles = [chapter.title for chapter in chapters]
    with st.expander("Detected chapters", expanded=False):
        for chapter in chapters:
            st.write(f"{chapter.title} - pages {chapter.start_page} to {chapter.end_page}")

    selected = st.multiselect(
        "Select chapters",
        titles,
        default=titles,
        key=state.next_key("cg_book_selection", signature),
    )
    st.caption(f"Course name: {pdf_service.course_name_for(uploaded)}")

    if st.button(
        "Generate course",
        type="primary",
        disabled=not selected,
        use_container_width=True,
    ):
        step, status = progress_steps("Preparing your course...")
        try:
            extracted = pdf_service.extract_text(Path(path), chapters, selected)
            artifacts = service.generate_from_book(
                extracted,
                pdf_service.course_name_for(uploaded),
                step=step,
            )
        except CourseGenError as exc:
            complete(status, "Generation failed.")
            show_error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            complete(status, "Generation failed.")
            logger.exception("Unexpected course generation error: %s", exc)
            show_error("Something unexpected went wrong while generating the course. Check the logs.")
            return
        complete(status, "Course generated.")
        state.set_artifacts(state.TASK_BOOK, artifacts)
        state.flash("Your course is ready. Scroll down to review it.")
        st.rerun()


# -------------------------------------------------------------------- typed
def _typed_flow(service: CourseService) -> None:
    columns = st.columns([2, 1])
    course_name = columns[0].text_input(
        "Course name",
        placeholder="Introduction to astronomy",
        key="cg_typed_course_name",
    )
    lecture_count = columns[1].number_input(
        "Number of lectures",
        min_value=1,
        max_value=5,
        value=3,
        key="cg_typed_lecture_count",
    )

    if st.button("Generate lecture plan", use_container_width=True):
        try:
            with st.spinner("Planning the course..."):
                plan = LectureGenerator().generate(int(lecture_count), course_name)
        except CourseGenError as exc:
            show_error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            logger.exception("Could not generate the lecture plan: %s", exc)
            show_error("The lecture plan could not be generated. Check the logs.")
            return
        st.session_state[state.LECTURE_PLAN] = plan
        state.bump_plan_version()
        state.clear_artifacts(state.TASK_TYPED)
        st.rerun()

    plan = st.session_state.get(state.LECTURE_PLAN)
    if not plan:
        st.caption("Generate a plan first, then edit its talking points before building the course.")
        return

    version = state.get_plan_version()
    st.markdown("#### Review the lecture plan")
    st.caption("Edit the lecture titles and talking points. Put one talking point per line.")

    edited: dict[str, list[str]] = {}
    for index, (lecture, points) in enumerate(plan.items()):
        with st.container(border=True):
            title = st.text_input(
                f"Lecture {index + 1} title",
                value=lecture,
                key=state.next_key("cg_plan_title", version, index),
            )
            body = st.text_area(
                "Talking points",
                value="\n".join(points),
                height=140,
                key=state.next_key("cg_plan_points", version, index),
            )
        resolved_title = title.strip() or lecture
        unique_title = resolved_title
        suffix = 2
        while unique_title in edited:
            unique_title = f"{resolved_title} ({suffix})"
            suffix += 1
        edited[unique_title] = [line.strip() for line in body.splitlines() if line.strip()]

    if st.button(
        "Generate course",
        type="primary",
        disabled=not any(edited.values()),
        use_container_width=True,
    ):
        step, status = progress_steps("Preparing your course...")
        try:
            artifacts = service.generate_from_lectures(
                edited,
                course_name.strip() or "Generated Course",
                step=step,
            )
        except CourseGenError as exc:
            complete(status, "Generation failed.")
            show_error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            complete(status, "Generation failed.")
            logger.exception("Unexpected course generation error: %s", exc)
            show_error("Something unexpected went wrong while generating the course. Check the logs.")
            return
        complete(status, "Course generated.")
        state.set_artifacts(state.TASK_TYPED, artifacts)
        state.flash("Your course is ready. Scroll down to review it.")
        st.rerun()
