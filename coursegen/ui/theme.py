"""Branding and CSS shared by every page."""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

from coursegen.models import UserAccount

_CSS = """
<style>
:root {
    --cg-bg: #0d1513;
    --cg-surface: #14201d;
    --cg-surface-2: #1a2a26;
    --cg-border: rgba(230, 230, 250, 0.12);
    --cg-text: #e6e6fa;
    --cg-muted: #9db2ac;
    --cg-accent: #6fd3b5;
    --cg-accent-strong: #3f8f7c;
    --cg-warning: #f0b96b;
}

#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
[data-testid="stToolbar"], [data-testid="stDecoration"] {visibility: hidden; height: 0;}

.stApp {
    background:
        radial-gradient(1200px 500px at 10% -10%, rgba(111, 211, 181, 0.10), transparent 60%),
        radial-gradient(900px 400px at 100% 0%, rgba(47, 79, 79, 0.35), transparent 55%),
        var(--cg-bg);
}

.block-container {padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1180px;}

h1, h2, h3 {letter-spacing: -0.02em;}

.cg-hero {
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 22px 26px;
    border-radius: 18px;
    border: 1px solid var(--cg-border);
    background: linear-gradient(135deg, rgba(111, 211, 181, 0.12), rgba(20, 32, 29, 0.9));
    margin-bottom: 22px;
}
.cg-hero .cg-mark {
    width: 54px; height: 54px;
    display: grid; place-items: center;
    font-size: 28px;
    border-radius: 16px;
    background: rgba(111, 211, 181, 0.14);
    border: 1px solid rgba(111, 211, 181, 0.35);
}
.cg-hero h1 {font-size: 1.65rem; margin: 0; color: var(--cg-text);}
.cg-hero p {margin: 2px 0 0; color: var(--cg-muted); font-size: 0.92rem;}

.cg-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid var(--cg-border);
    background: var(--cg-surface);
    color: var(--cg-muted);
    font-size: 0.82rem;
}

.cg-card {
    padding: 18px 20px;
    border-radius: 16px;
    border: 1px solid var(--cg-border);
    background: var(--cg-surface);
    margin-bottom: 14px;
}
.cg-card h4 {margin: 0 0 6px; color: var(--cg-text);}
.cg-card p {margin: 0; color: var(--cg-muted); font-size: 0.9rem;}

.cg-meta {display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0 14px;}
.cg-meta span {
    padding: 5px 10px;
    border-radius: 8px;
    background: var(--cg-surface-2);
    border: 1px solid var(--cg-border);
    color: var(--cg-muted);
    font-size: 0.8rem;
}

.cg-bubble {
    padding: 10px 15px;
    border-radius: 16px;
    margin-bottom: 10px;
    line-height: 1.55;
    font-size: 0.95rem;
    border: 1px solid var(--cg-border);
    max-width: 92%;
    word-break: break-word;
}
.cg-bubble.user {
    background: rgba(111, 211, 181, 0.14);
    border-color: rgba(111, 211, 181, 0.35);
    margin-left: auto;
}
.cg-bubble.bot {background: var(--cg-surface-2);}

.cg-quiet {color: var(--cg-muted); font-size: 0.88rem;}

div[data-testid="stForm"] {
    border: 1px solid var(--cg-border);
    border-radius: 16px;
    padding: 18px;
    background: rgba(20, 32, 29, 0.65);
}

.stButton > button, .stFormSubmitButton > button {
    border-radius: 10px;
    border: 1px solid rgba(111, 211, 181, 0.4);
    font-weight: 600;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--cg-accent), var(--cg-accent-strong));
    color: #06110e;
    border: none;
}

div[data-testid="stSidebar"] {
    border-right: 1px solid var(--cg-border);
    background: rgba(13, 21, 19, 0.92);
}
div[data-testid="stSidebar"] .block-container {padding-top: 1.4rem;}

[data-testid="stMetricValue"] {color: var(--cg-accent);}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_hero(subtitle: str = "Turn books and ideas into narrated, interactive courses.") -> None:
    st.markdown(
        f"""
        <div class="cg-hero">
            <div class="cg-mark">&#128218;</div>
            <div>
                <h1>Course Generator</h1>
                <p>{html.escape(subtitle)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_account_chip(account: Optional[UserAccount]) -> None:
    if account is None:
        return
    st.markdown(
        f'<span class="cg-chip">&#128100; {html.escape(account.name)} &middot; '
        f'{html.escape(account.email)}</span>',
        unsafe_allow_html=True,
    )


def render_message(role: str, message: str) -> None:
    """Render one chat bubble. Content is escaped before it reaches the DOM."""
    safe = html.escape(str(message)).replace("\n", "<br>")
    bubble = "user" if role == "user" else "bot"
    st.markdown(f'<div class="cg-bubble {bubble}">{safe}</div>', unsafe_allow_html=True)
