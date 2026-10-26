"""Streamlit entry point for the Course Generator application."""

from __future__ import annotations

import streamlit as st

from coursegen.config import get_settings
from coursegen.logging_config import configure_logging
from coursegen.ui.router import run

st.set_page_config(
    page_title="Course Generator",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

configure_logging()
get_settings().ensure_workspace()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
