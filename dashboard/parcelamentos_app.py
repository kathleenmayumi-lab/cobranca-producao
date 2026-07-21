"""Entrada Streamlit só de parcelamentos (útil se o painel principal ainda não tiver a aba)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from dashboard import brand
from dashboard.parcelamentos_ui import render_parcelamentos

st.set_page_config(
    page_title=f"{brand.page_title()} — Parcelamentos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(brand.css(), unsafe_allow_html=True)
render_parcelamentos()
