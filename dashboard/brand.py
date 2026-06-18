"""Identidade visual Velotax para o dashboard."""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND_PATH = ROOT / "config" / "brand.json"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# Assets oficiais (velotax.com.br)
MASCOTE_URL = "https://velotax.com.br/images/mascote/velo-afirmativo.png"
LOGO_BRANCO_URL = "https://velotax.com.br/images/logos/velotax-logo-branco.png"


@lru_cache(maxsize=1)
def load_brand() -> dict:
    data = json.loads(BRAND_PATH.read_text(encoding="utf-8"))
    return data


def colors() -> dict[str, str]:
    return load_brand()["colors"]


def _asset_src(filename: str, remote_url: str, mime: str = "image/png") -> str:
    local = ASSETS_DIR / filename
    if local.exists():
        encoded = base64.b64encode(local.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    return remote_url


def mascote_url() -> str:
    return _asset_src("velo-mascote.png", MASCOTE_URL)


def logo_url() -> str:
    return _asset_src("velotax-logo-branco.png", LOGO_BRANCO_URL)


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
        padding: 1rem 1.4rem;
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
        gap: 16px;
        min-width: 0;
    }}
    .velo-mascote {{
        height: 84px;
        width: auto;
        display: block;
        flex-shrink: 0;
        object-fit: contain;
    }}
    .velo-wordmark {{
        height: 42px;
        width: auto;
        display: block;
        flex-shrink: 0;
        object-fit: contain;
    }}
    .velo-title-block {{ display: flex; flex-direction: column; gap: 2px; }}
    .velo-product {{
        color: #ffffff;
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.15;
        letter-spacing: -0.02em;
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

    .agent-macro-wrap {{
        border: 1px solid {c['border']};
        border-radius: 14px;
        overflow: hidden;
        background: {c['surface']};
        box-shadow: 0 2px 10px rgba(0, 0, 88, 0.05);
        margin-bottom: 1rem;
    }}
    .agent-macro-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.92rem;
    }}
    .agent-macro-table thead th {{
        background: linear-gradient(135deg, {c['navy_deep']} 0%, {c['navy']} 55%, {c['primary']} 100%);
        color: #ffffff;
        font-family: 'Sora', 'Inter', system-ui, sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        padding: 0.85rem 1rem;
        text-align: left;
        white-space: nowrap;
    }}
    .agent-macro-table thead th.num {{
        text-align: right;
    }}
    .agent-macro-table tbody td {{
        padding: 0.8rem 1rem;
        border-bottom: 1px solid {c['border']};
        color: {c['text']};
        vertical-align: middle;
    }}
    .agent-macro-table tbody tr:nth-child(even) td {{
        background: {c['background']};
    }}
    .agent-macro-table tbody tr:hover td {{
        background: {c['primary_light']};
    }}
    .agent-macro-table td.agent-name {{
        font-weight: 700;
        color: {c['text']};
        min-width: 180px;
    }}
    .agent-macro-table td.num {{
        text-align: right;
        font-variant-numeric: tabular-nums;
        font-weight: 600;
        width: 14%;
    }}
    .macro-cell {{
        position: relative;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        min-height: 28px;
        border-radius: 8px;
        overflow: hidden;
        background: {c['background']};
    }}
    .macro-cell span {{
        position: relative;
        z-index: 1;
        padding: 0 0.5rem;
        color: {c['text']};
        font-weight: 700;
    }}
    .macro-fill {{
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        border-radius: 8px;
        opacity: 0.9;
    }}
    .agent-macro-table tfoot td {{
        background: {c['primary_light']};
        border-top: 2px solid {c['primary']};
        font-weight: 800;
        color: {c['text']};
        padding: 0.85rem 1rem;
    }}
    .agent-macro-table tfoot td.num {{
        text-align: right;
        font-variant-numeric: tabular-nums;
    }}

    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{
        background: transparent;
    }}

    /* Plotly: força todos os textos do gráfico em preto */
    [data-testid="stPlotlyChart"] svg text {{
        fill: #000000 !important;
    }}
</style>
"""


def header_html(*_args: object, **_kwargs: object) -> str:
    """HTML do cabeçalho. Aceita qualquer assinatura (compatibilidade)."""
    try:
        brand_data = load_brand()
        product = str(brand_data.get("product") or "Painel de Cobrança")
        company = str(brand_data.get("company") or "Velotax")
        mascote = mascote_url()
        wordmark = logo_url()
    except Exception:
        product, company = "Painel de Cobrança", "Velotax"
        mascote, wordmark = MASCOTE_URL, LOGO_BRANCO_URL
    return f"""
<div class="velo-header">
  <div class="velo-header-left">
    <img class="velo-mascote" src="{mascote}" alt="Velo, mascote oficial do Velotax" />
    <div class="velo-title-block">
      <div class="velo-product">{product}</div>
    </div>
  </div>
  <img class="velo-wordmark" src="{wordmark}" alt="{company}" />
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
