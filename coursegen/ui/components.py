"""Reusable Streamlit widgets: library, artifacts, presentation studio, chat."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import streamlit as st
import streamlit.components.v1 as components

from coursegen.config import get_settings
from coursegen.errors import CourseGenError
from coursegen.media.fonts import FONT_FILES
from coursegen.media.presentation_builder import FontPreviewer, TemplateLibrary
from coursegen.models import CourseArtifacts, PresentationStyle, UserAccount
from coursegen.services.course_service import CourseService
from coursegen.ui import state
from coursegen.ui.dialogs import complete, progress_steps, show_error
from coursegen.ui.theme import render_message
from coursegen.utils import safe_filename

logger = logging.getLogger(__name__)

_PREVIEW = "cg_library_preview"


# ------------------------------------------------------------------- library
def render_library(account: UserAccount, service: CourseService) -> None:
    """Render the media library and its actions in the sidebar."""
    with st.sidebar:
        st.markdown("### Your library")
        try:
            library = service.library(account)
        except CourseGenError as exc:
            st.caption(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            logger.exception("Could not load the media library: %s", exc)
            st.caption("The library is unavailable right now.")
            return

        _render_media_group(
            title="Videos",
            names=list(library.videos),
            lookup=library.videos,
            kind="video",
            account=account,
            delete=service.delete_video,
        )
        _render_media_group(
            title="Presentations",
            names=list(library.presentations),
            lookup=library.presentations,
            kind="presentation",
            account=account,
            delete=service.delete_presentation,
        )

        preview = st.session_state.get(_PREVIEW)
        if preview:
            kind, url, name = preview
            st.divider()
            st.caption(name)
            if kind == "video":
                st.video(url)
            else:
                components.iframe(url, height=420)
            if st.button("Close preview", key="cg_library_close", use_container_width=True):
                st.session_state.pop(_PREVIEW, None)
                st.rerun()


def _render_media_group(
    title: str,
    names: List[str],
    lookup: dict,
    kind: str,
    account: UserAccount,
    delete,
) -> None:
    with st.expander(f"{title} ({len(names)})", expanded=False):
        if not names:
            st.caption("Nothing saved yet.")
            return
        selected = st.multiselect(
            f"Select {title.lower()}",
            names,
            key=f"cg_library_{kind}_select_{account.id}",
        )
        columns = st.columns(2)
        if columns[0].button(
            "Show",
            key=f"cg_library_{kind}_show",
            disabled=not selected,
            use_container_width=True,
        ):
            chosen = selected[-1]
            st.session_state[_PREVIEW] = (kind, lookup[chosen], chosen)
            st.rerun()
        if columns[1].button(
            "Delete",
            key=f"cg_library_{kind}_delete",
            disabled=not selected,
            use_container_width=True,
        ):
            for name in selected:
                try:
                    delete(account, name)
                except CourseGenError as exc:
                    show_error(str(exc))
                    return
            st.session_state.pop(_PREVIEW, None)
            st.rerun()


# --------------------------------------------------------------- presentation
def presentation_style_controls(task: str) -> PresentationStyle:
    settings = get_settings()
    templates = TemplateLibrary(settings)

    st.markdown("#### Presentation style")
    template = st.selectbox(
        "Background template",
        templates.names,
        key=f"cg_{task}_template",
    )

    background_path: Optional[str] = None
    if template == "Default":
        uploaded = st.file_uploader(
            "Upload a background image",
            type=["png", "jpg", "jpeg", "jfif"],
            key=f"cg_{task}_background",
        )
        if uploaded is not None:
            suffix = Path(uploaded.name).suffix.lower() or ".png"
            stem = safe_filename(Path(uploaded.name).stem, "background")
            destination = settings.images_dir / f"{task}_{stem}{suffix}"
            destination.write_bytes(uploaded.getbuffer())
            background_path = str(destination)
            st.image(uploaded, caption="Your background", use_column_width=True)
        else:
            st.caption("Optional: upload a custom background image.")
    else:
        preview = templates.path_for(template)
        if preview is not None:
            st.image(str(preview), caption=f"Template: {template}", use_column_width=True)
            background_path = str(preview)
        else:
            st.warning("The selected template image is missing; the deck will use a plain background.")

    title_size = st.slider(
        "Title font size", min_value=20, max_value=30, value=24, key=f"cg_{task}_title_size"
    )
    content_size = st.slider(
        "Content font size", min_value=15, max_value=22, value=18, key=f"cg_{task}_content_size"
    )
    fonts = list(FONT_FILES)
    font_name = st.selectbox("Font", fonts, key=f"cg_{task}_font")
    st.image(
        FontPreviewer.render(font_name, content_size),
        caption=f"Font preview: {font_name}",
        width=300,
    )

    columns = st.columns(2)
    title_color = columns[0].color_picker("Title colour", "#000000", key=f"cg_{task}_title_color")
    content_color = columns[1].color_picker(
        "Content colour", "#1A1A1A", key=f"cg_{task}_content_colour"
    )

    return PresentationStyle(
        title_font_size=title_size,
        content_font_size=content_size,
        font_name=font_name,
        title_color=title_color,
        content_color=content_color,
        background_path=background_path,
        template=template,
    )


def render_publish_tab(task: str, artifacts: CourseArtifacts, account: UserAccount, service: CourseService) -> None:
    if artifacts.video_link:
        st.success("This course is published.")
        columns = st.columns(2)
        if artifacts.video_link:
            with columns[0]:
                st.caption("Hosted video")
                st.video(artifacts.video_link)
        if artifacts.presentation_link:
            with columns[1]:
                st.caption("Hosted presentation")
                st.link_button("Open in Google Drive", artifacts.presentation_link)
        st.divider()

    style = presentation_style_controls(task)

    settings = get_settings()
    missing = []
    if not settings.bunny_api_key or not settings.bunny_storage_zone:
        missing.append("BunnyCDN (BUNNY_STORAGE_API_KEY, BUNNY_STORAGE_ZONE)")
    if not settings.google_drive_folder_id:
        missing.append("Google Drive (GOOGLE_DRIVE_FOLDER_ID)")
    if missing:
        st.info("Publishing also uploads to: " + ", ".join(missing) + ". Set these in `.env` to enable it.")

    if st.button(
        "Create presentation and publish",
        key=f"cg_{task}_publish",
        type="primary",
        use_container_width=True,
    ):
        step, status = progress_steps("Publishing your course...")
        try:
            service.publish(artifacts, style, account, step=step)
        except CourseGenError as exc:
            complete(status, "Publishing failed.")
            show_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            complete(status, "Publishing failed.")
            logger.exception("Unexpected publishing error: %s", exc)
            show_error("Something unexpected went wrong while publishing. Check the logs.")
        else:
            complete(status, "Published.")
            state.flash("Presentation created and your course was published.")
            st.rerun()

    _render_local_presentation(artifacts)


def _render_local_presentation(artifacts: CourseArtifacts) -> None:
    path = artifacts.presentation_path
    if not path:
        return
    file_path = Path(path)
    if not file_path.is_file():
        return
    st.caption("PowerPoint built locally")
    st.download_button(
        "Download PowerPoint",
        data=file_path.read_bytes(),
        file_name=file_path.name,
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        key=f"cg_download_{file_path.stem}",
    )


# ------------------------------------------------------------------ lecturer
def render_lecturer(artifacts: CourseArtifacts, service: CourseService) -> None:
    st.markdown("#### Ask the lecturer")
    if artifacts.conversation is None:
        st.info("The lecturer becomes available after a course is generated.")
        return

    if not artifacts.chat_history:
        st.caption("Ask anything about the generated course material.")

    for message in artifacts.chat_history:
        role = "user" if getattr(message, "type", "") == "human" else "bot"
        render_message(role, getattr(message, "content", ""))

    with st.form("cg_lecturer_form", clear_on_submit=True):
        question = st.text_input("Your question", placeholder="What should I revise first?")
        submitted = st.form_submit_button("Ask", type="primary")
    if submitted:
        if not question.strip():
            st.warning("Type a question first.")
            return
        try:
            CourseService.ask(artifacts, question.strip())
        except CourseGenError as exc:
            show_error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            logger.exception("Lecturer failed: %s", exc)
            show_error("The lecturer could not answer that question. Check the logs.")
            return
        st.rerun()


# ----------------------------------------------------------------- artifacts
def render_artifacts(task: str, artifacts: CourseArtifacts, account: UserAccount, service: CourseService) -> None:
    lecture_count = len(artifacts.slides)
    slide_count = sum(len(slides) for slides in artifacts.slides.values())
    audio_count = sum(
        len(clips) for sections in artifacts.audio_paths.values() for clips in sections.values()
    )

    st.markdown(
        f"""
        <div class="cg-card">
            <h4>{_escape(artifacts.course_name)}</h4>
            <p>Your course is generated and ready to review.</p>
            <div class="cg-meta">
                <span>{lecture_count} lecture(s)</span>
                <span>{slide_count} slide topic(s)</span>
                <span>{audio_count} narration clip(s)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["Video", "Lesson plan", "Narration", "Lecturer", "Publish"])
    with tabs[0]:
        _render_video(artifacts)
    with tabs[1]:
        _render_lesson_plan(artifacts)
    with tabs[2]:
        _render_narration(artifacts)
    with tabs[3]:
        render_lecturer(artifacts, service)
    with tabs[4]:
        render_publish_tab(task, artifacts, account, service)


def _render_video(artifacts: CourseArtifacts) -> None:
    path = artifacts.video_path
    if not path:
        st.info("No video was produced for this course.")
        return
    if not Path(path).is_file():
        st.warning("The generated video file is no longer on disk.")
        return
    st.video(path)
    st.caption(Path(path).name)


def _render_lesson_plan(artifacts: CourseArtifacts) -> None:
    if not artifacts.slides:
        st.info("The lesson plan is empty.")
        return
    for lecture, slides in artifacts.slides.items():
        with st.expander(lecture, expanded=lecture == next(iter(artifacts.slides))):
            if not slides:
                st.caption("No slides for this lecture.")
                continue
            for title, points in slides.items():
                st.markdown(f"**{title}**")
                for point in points:
                    st.markdown(f"- {point}")
                st.write("")


def _render_narration(artifacts: CourseArtifacts) -> None:
    if not artifacts.audio_paths:
        st.info("Narration is not available for this course.")
        return
    for lecture, sections in artifacts.audio_paths.items():
        clip_count = sum(len(paths) for paths in sections.values())
        with st.expander(f"{lecture} ({clip_count} clips)"):
            if not sections:
                st.caption("No audio for this lecture.")
                continue
            for title, paths in sections.items():
                st.markdown(f"**{title}**")
                for index, path in enumerate(paths, start=1):
                    if Path(path).is_file():
                        st.audio(path)
                    else:
                        st.caption(f"Clip {index} of {title} is missing from disk.")


def _escape(value: str) -> str:
    from html import escape

    return escape(str(value))
