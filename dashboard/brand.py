"""Identidade visual Velotax para o dashboard."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND_PATH = ROOT / "config" / "brand.json"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "velotax-logo.svg"


@lru_cache(maxsize=1)
def load_brand() -> dict:
    data = json.loads(BRAND_PATH.read_text(encoding="utf-8"))
    return data


def colors() -> dict[str, str]:
    return load_brand()["colors"]


def logo_svg_inline() -> str:
    if LOGO_PATH.exists():
        return LOGO_PATH.read_text(encoding="utf-8").strip()
    company = load_brand()["company"]
    primary = colors()["primary"]
    return (
        f'<span style="font-size:1.6rem;font-weight:800;color:{primary};'
        f'letter-spacing:-0.02em">{company}</span>'
    )


def page_title() -> str:
    brand = load_brand()
    return f"{brand['company']} — {brand['product']}"


def css() -> str:
    c = colors()
    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }}
    h1, h2, h3, .velo-product {{
        font-family: 'Sora', 'Inter', system-ui, sans-serif;
    }}

    .block-container {{
        padding-top: 0.8rem;
        max-width: 1400px;
    }}

    .velo-header {{
        background: linear-gradient(135deg, {c['navy_deep']} 0%, {c['navy']} 35%, {c['primary']} 100%);
        border-radius: 16px;
        padding: 1.1rem 1.4rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        box-shadow: 0 8px 24px rgba(22, 52, 255, 0.18);
        position: relative;
        overflow: hidden;
    }}
    .velo-header-left {{
        display: flex;
        align-items: center;
        gap: 14px;
        min-width: 0;
    }}
    .velo-logo svg {{ height: 58px; width: auto; display: block; flex-shrink: 0; }}
    .velo-logo svg text {{ fill: #ffffff !important; }}
    .velo-title-block {{ display: flex; flex-direction: column; gap: 2px; }}
    .velo-product {{
        color: #ffffff;
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.2;
        letter-spacing: -0.02em;
    }}
    .velo-tagline {{
        color: rgba(255, 255, 255, 0.88);
        font-size: 0.88rem;
        font-weight: 500;
    }}
    .velo-badge {{
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.28);
        color: #fff;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 6px 10px;
        border-radius: 999px;
        white-space: nowrap;
    }}

    div[data-testid="stDataFrame"] {{
        border: 1px solid {c['border']};
        border-radius: 12px;
        overflow: hidden;
    }}
    div[data-testid="stDataFrame"] td:first-child {{
        color: {c['text']} !important;
        font-weight: 600;
    }}

    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{
        color: {c['primary']} !important;
        border-bottom-color: {c['primary']} !important;
    }}

    div[data-testid="stSegmentedControl"] {{
        background: {c['background']};
        border: 1px solid {c['border']};
        border-radius: 12px;
        padding: 4px;
    }}

    .stButton > button[kind="primary"] {{
        background: {c['primary']} !important;
        border-color: {c['primary_dark']} !important;
        font-weight: 600;
    }}
    .stButton > button[kind="primary"]:hover {{
        background: {c['primary_dark']} !important;
        border-color: {c['primary_dark']} !important;
    }}

    .kpi-card {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 14px;
        padding: 1rem 1.1rem;
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 92px;
        box-shadow: 0 2px 8px rgba(0, 0, 88, 0.06);
    }}
    .kpi-icon {{
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}
    .kpi-icon svg {{ width: 24px; height: 24px; }}
    .kpi-icon.cpc {{ background: {c['primary_light']}; color: {c['primary']}; }}
    .kpi-icon.acordos {{ background: {c['success_light']}; color: {c['success']}; }}
    .kpi-icon.reversao {{ background: {c['accent_light']}; color: {c['accent_dark']}; }}
    .kpi-icon.finalizadas {{ background: {c['background']}; color: {c['text_muted']}; }}
    .kpi-body {{ display: flex; flex-direction: column; gap: 2px; }}
    .kpi-label {{
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: {c['text_muted']};
    }}
    .kpi-value {{
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
        color: {c['text']};
    }}

    .squad-banner {{
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin: 0.2rem 0 0.8rem 0;
        font-size: 0.95rem;
        font-weight: 600;
    }}
    .squad-banner.todos {{
        background: {c['background']};
        border: 1px solid {c['border']};
        color: {c['text_muted']};
    }}
    .squad-banner.over90 {{
        background: {c['primary_light']};
        border: 1px solid #B8C8FF;
        color: {c['primary_dark']};
    }}
    .squad-banner.early {{
        background: {c['accent_light']};
        border: 1px solid #A8D8FF;
        color: {c['accent_dark']};
    }}

    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{
        background: transparent;
    }}
</style>
"""


def header_html(subtitle: str = "") -> str:
    brand = load_brand()
    logo = logo_svg_inline()
    if logo.startswith("<svg"):
        logo_block = f'<div class="velo-logo">{logo}</div>'
    else:
        logo_block = logo
    subtitle_html = (
        f'<div class="velo-tagline">{subtitle}</div>' if subtitle.strip() else ""
    )
    return f"""
<div class="velo-header">
  <div class="velo-header-left">
    {logo_block}
    <div class="velo-title-block">
      <div class="velo-product">{brand['product']}</div>
      {subtitle_html}
    </div>
  </div>
  <div class="velo-badge">{brand['company']}</div>
</div>
"""


def chart_palette() -> list[str]:
    c = colors()
    return [
        c["primary"],
        c["primary_dark"],
        c["navy"],
        c["accent"],
        c["success"],
        c["accent_dark"],
        c["navy_deep"],
        c["text_muted"],
    ]
