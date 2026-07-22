"""App Streamlit apartado — parcelamentos Over 90 + IRPF (porta 8503)."""

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
    page_title="Parcelamentos — Over 90 / IRPF",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(brand.css(), unsafe_allow_html=True)

st.markdown(
    """
<div class="velo-header">
  <div class="velo-header-left">
    <div class="velo-product">Parcelamentos</div>
    <div class="velo-company" style="color:#ffffff;">Over 90 · IRPF — entrada + boletos</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

render_parcelamentos()
