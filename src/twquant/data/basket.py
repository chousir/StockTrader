"""跨頁交易籃 — session-level 暫存，不寫 DB"""
from __future__ import annotations
import streamlit as st

_KEY = "g_basket"


def add_to_basket(sid: str) -> None:
    if _KEY not in st.session_state:
        st.session_state[_KEY] = []
    if sid not in st.session_state[_KEY]:
        st.session_state[_KEY].append(sid)


def remove_from_basket(sid: str) -> None:
    if _KEY in st.session_state:
        st.session_state[_KEY] = [s for s in st.session_state[_KEY] if s != sid]


def clear_basket() -> None:
    st.session_state[_KEY] = []


def get_basket() -> list[str]:
    return list(st.session_state.get(_KEY, []))
