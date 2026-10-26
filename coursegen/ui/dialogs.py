"""Small UI feedback helpers that stay compatible across Streamlit versions."""

from __future__ import annotations

import contextlib
import logging
from typing import Callable, ContextManager, Iterator, Tuple

import streamlit as st

logger = logging.getLogger(__name__)

StepFactory = Callable[[str], ContextManager[None]]


def show_error(message: str) -> None:
    """Show a modal notice when dialogs are available, otherwise inline."""
    factory = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if factory is None:
        st.error(message)
        return

    @factory("Something went wrong")
    def _notice() -> None:
        st.error(message)

    _notice()


def progress_steps(label: str = "Working...") -> Tuple[StepFactory, object]:
    """Return a step factory compatible with ``CourseService`` plus its status.

    Streamlit 1.35 exposes ``st.status``. On older versions the factory falls
    back to a spinner so the service still runs unchanged.
    """
    status_factory = getattr(st, "status", None)
    if status_factory is None:
        spinner = st.spinner(label)

        @contextlib.contextmanager
        def _fallback(message: str) -> Iterator[None]:
            spinner.__enter__()
            try:
                yield
            finally:
                spinner.__exit__(None, None, None)

        return _fallback, spinner

    status = status_factory(label, expanded=True)

    @contextlib.contextmanager
    def _step(message: str) -> Iterator[None]:
        status.update(label=message, state="running")
        yield

    return _step, status


def complete(status: object, label: str = "Done.") -> None:
    update = getattr(status, "update", None)
    if callable(update):
        update(label=label, state="complete")
