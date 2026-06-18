"""Dashboard web — Cobrança (Streamlit)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from run import load_calls
from src.api_3cplus import aggregate_production
from datetime import date

from src.snapshot import (
    breakdown_total,
    build_cloud_snapshot_payload,
    build_snapshot_payload,
    enrich_summary_improdutivas,
    load_snapshot,
    merge_improdutivas_from,
    save_snapshot,
    summary_has_improdutiva_data,
)
from src.snapshot_remote import download_snapshot as download_snapshot_drive
from src.snapshot_remote import remote_snapshot_configured as drive_snapshot_configured
from src.snapshot_remote import upload_snapshot as upload_snapshot_drive
from src.snapshot_sheets import download_snapshot as download_snapshot_sheets
from src.snapshot_sheets import remote_snapshot_configured, upload_snapshot as upload_snapshot_sheets
from src.squads import agents_for_squad, filter_summary, squad_labels

from dashboard import brand

st.set_page_config(
    page_title=brand.page_title(),
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(brand.css(), unsafe_allow_html=True)

_BRAND = brand.colors()

MASCOTE_CDN = "https://velotax.com.br/images/mascote/velo-afirmativo.png"
LOGO_CDN = "https://velotax.com.br/images/logos/velotax-logo-branco.png"
_CHART_LABEL_COLOR = "#000000"
_CHART_TEXT = "#000000"
_REV_META_PCT = 70.0


def _build_header_html() -> str:
    """Monta o header sem depender da assinatura de brand.header_html no Cloud."""
    product = "Painel de Cobrança"
    company = "Velotax"
    mascote = MASCOTE_CDN
    wordmark = LOGO_CDN
    try:
        cfg = brand.load_brand()
        product = str(cfg.get("product") or product)
        company = str(cfg.get("company") or company)
    except Exception:
        pass
    for attr, fallback in (("mascote_url", MASCOTE_CDN), ("logo_url", LOGO_CDN)):
        try:
            fn = getattr(brand, attr, None)
            if callable(fn):
                value = fn()
                if isinstance(value, str) and value.strip():
                    if attr == "mascote_url":
                        mascote = value
                    else:
                        wordmark = value
        except Exception:
            pass
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


def _fmt_num(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _kpi_card(label: str, value: str, icon_class: str, icon_svg: str) -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-icon {icon_class}">{icon_svg}</div>
        <div class="kpi-body">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
    </div>
    """


ICON_CPC = """
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
  <circle cx="12" cy="7" r="4"/>
</svg>
"""

ICON_ACORDOS = """
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M20 6L9 17l-5-5"/>
</svg>
"""

ICON_REVERSAO = """
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
  <polyline points="17 6 23 6 23 12"/>
</svg>
"""

ICON_FINALIZADAS = """
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07
           19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72
           12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45
           12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
</svg>
"""


def _chart_theme(title: str, height: int = 500) -> dict:
    return dict(
        template=None,
        title=dict(
            text=title,
            font=dict(size=17, color=_CHART_TEXT, family="Inter, Segoe UI, system-ui"),
            x=0,
            xanchor="left",
        ),
        height=height,
        margin=dict(l=12, r=24, t=52, b=12),
        plot_bgcolor=_BRAND["background"],
        paper_bgcolor=_BRAND["surface"],
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=12, color=_CHART_TEXT),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
            font=dict(color=_CHART_TEXT, size=12),
        ),
        hoverlabel=dict(bgcolor=_BRAND["primary_dark"], font_size=12, font_color="#fff"),
    )


def _finalize_chart(fig: go.Figure) -> go.Figure:
    """Garante título, eixos, legenda e rótulos em preto."""
    if not fig.data:
        return fig
    fig.update_layout(
        template=None,
        font=dict(color=_CHART_TEXT),
        title_font=dict(color=_CHART_TEXT),
        legend=dict(font=dict(color=_CHART_TEXT)),
    )
    fig.update_xaxes(
        tickfont=dict(color=_CHART_TEXT, size=12),
        title_font=dict(color=_CHART_TEXT, size=12),
    )
    fig.update_yaxes(
        tickfont=dict(color=_CHART_TEXT, size=12),
        title_font=dict(color=_CHART_TEXT, size=12),
    )
    for trace in fig.data:
        trace_type = getattr(trace, "type", None)
        if trace_type == "pie":
            trace.update(
                textfont=dict(color=_CHART_LABEL_COLOR, size=11),
                outsidetextfont=dict(color=_CHART_LABEL_COLOR, size=11),
                insidetextfont=dict(color=_CHART_LABEL_COLOR, size=11),
            )
        elif trace_type == "bar":
            trace.update(
                textfont=dict(color=_CHART_LABEL_COLOR, size=11),
                textposition="outside",
            )
    return fig


def _share_chart(df: pd.DataFrame, squad: str = "Todos") -> go.Figure:
    """Donut — participação de cada agente na produção total."""
    active = df[df["Acordos"] > 0].sort_values("Acordos", ascending=False)
    if active.empty:
        return go.Figure()

    top = active.head(8)
    others = int(active["Acordos"].iloc[8:].sum()) if len(active) > 8 else 0
    labels = list(top["Agente"])
    values = list(top["Acordos"])
    if others > 0:
        labels.append("Outros")
        values.append(others)

    palette = brand.chart_palette()
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker=dict(colors=palette[: len(labels)], line=dict(color="#fff", width=2)),
            textinfo="percent",
            textposition="outside",
            textfont=dict(color=_CHART_LABEL_COLOR, size=11),
            outsidetextfont=dict(size=11, color=_CHART_LABEL_COLOR),
            hovertemplate="<b>%{label}</b><br>%{value} acordos · %{percent}<extra></extra>",
        )
    )
    total = sum(values)
    share_title = "Participação na produção"
    if squad != "Todos":
        share_title = f"{share_title} · {squad}"
    layout = _chart_theme(share_title, height=420)
    layout["showlegend"] = False
    layout["annotations"] = [
        dict(
            text=f"<b>{total}</b><br><span style='font-size:12px;color:{_BRAND['text_muted']}'>acordos</span>",
            x=0.5,
            y=0.5,
            font=dict(size=22, color=_BRAND["text"]),
            showarrow=False,
        )
    ]
    fig.update_layout(**layout)
    return _finalize_chart(fig)


def _short_agent_label(name: str, *, max_len: int = 26) -> str:
    label = str(name or "").strip()
    if len(label) <= max_len:
        return label
    parts = label.split()
    if len(parts) >= 2:
        short = f"{parts[0]} {parts[-1][0]}."
        if len(short) <= max_len:
            return short
    return label[: max_len - 1] + "…"


def _reversion_chart(df: pd.DataFrame, squad: str = "Todos") -> go.Figure:
    """Barras horizontais — eficiência de reversão por agente."""
    chart = df[df["CPC"] >= 3].copy()
    chart = chart.dropna(subset=["% Reversão"]).sort_values("% Reversão", ascending=True).tail(10)
    if chart.empty:
        chart = df.dropna(subset=["% Reversão"]).sort_values("% Reversão", ascending=True).tail(10)
    if chart.empty:
        return go.Figure()

    values = chart["% Reversão"].astype(float).tolist()
    agents_full = chart["Agente"].tolist()
    agents = [_short_agent_label(name) for name in agents_full]
    cpcs = chart["CPC"].astype(int).tolist()
    acordos = chart["Acordos"].astype(int).tolist()
    xmax = min(110.0, max(max(values) * 1.15 + 12, 88.0))

    bar_colors = [
        _BRAND["primary"] if value >= _REV_META_PCT else "#B8C5E8"
        for value in values
    ]

    fig = go.Figure()
    fig.add_vrect(
        x0=_REV_META_PCT,
        x1=xmax,
        fillcolor="rgba(13, 122, 40, 0.06)",
        layer="below",
        line_width=0,
    )
    fig.add_trace(
        go.Bar(
            x=values,
            y=agents,
            orientation="h",
            marker=dict(color=bar_colors, cornerradius=8, line=dict(width=0)),
            text=[f"{value:.1f}%".replace(".", ",") for value in values],
            textposition="outside",
            textfont=dict(color=_CHART_TEXT, size=12),
            cliponaxis=False,
            customdata=list(zip(agents_full, cpcs, acordos, values)),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Reversão: %{customdata[3]:.1f}%<br>"
                "CPC: %{customdata[1]} · Acordos: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.add_vline(
        x=_REV_META_PCT,
        line_dash="dot",
        line_color=_BRAND["border"],
        line_width=1.5,
    )

    rev_title = "Eficiência de reversão"
    if squad != "Todos":
        rev_title = f"{rev_title} · {squad}"
    layout = _chart_theme(rev_title, height=440)
    layout["margin"] = dict(l=4, r=64, t=48, b=52)
    layout["xaxis"] = dict(
        range=[0, xmax],
        title=dict(
            text="Reversão sobre CPC (%)",
            font=dict(color=_CHART_TEXT, size=11),
            standoff=20,
        ),
        tickfont=dict(color=_CHART_TEXT, size=11),
        gridcolor="#E8EEF8",
        zeroline=False,
        dtick=20,
    )
    layout["yaxis"] = dict(
        automargin=True,
        tickfont=dict(color=_CHART_TEXT, size=12),
        tickmode="array",
        tickvals=agents,
        ticktext=agents,
    )
    layout["showlegend"] = False
    layout["annotations"] = []
    fig.update_layout(**layout)
    return _finalize_chart(fig)


def _reversion_pct(cpc: int, acordos: int) -> float | None:
    if cpc <= 0:
        return None
    return round((acordos / cpc) * 100, 1)


def _reversion_icon_html(rev: float) -> str:
    if rev < _REV_META_PCT:
        return '<span class="rev-icon alert" title="Abaixo da meta de 70%">!</span>'
    return '<span class="rev-icon ok" title="Meta de 70% atingida">✓</span>'


def _reversion_value_cell(rev: float | None) -> str:
    if rev is None or pd.isna(rev):
        return '<div class="macro-cell"><span>—</span></div>'
    rev_val = float(rev)
    pct_display = f"{rev_val:.1f}%".replace(".", ",")
    width = min(100.0, rev_val)
    fill = _BRAND["success_light"] if rev_val >= _REV_META_PCT else "#FEE2E2"
    icon = _reversion_icon_html(rev_val)
    return (
        f'<div class="macro-cell rev-cell">'
        f'<div class="macro-fill" style="width:{width:.1f}%;background:{fill};"></div>'
        f'<span class="rev-badge">{icon}<span>{pct_display}</span></span>'
        f"</div>"
    )


def _reversion_footer_cell(rev: float | None) -> str:
    if rev is None:
        return "—"
    icon = _reversion_icon_html(rev)
    pct_display = f"{rev:.1f}%".replace(".", ",")
    return f'<span class="rev-badge">{icon}<span>{pct_display}</span></span>'


def _dashboard_mode() -> str:
    try:
        mode = st.secrets.get("DASHBOARD_MODE", "")
        if mode:
            return str(mode).strip().lower()
    except Exception:
        pass
    return os.getenv("DASHBOARD_MODE", "local").strip().lower()


def _viewer_password() -> str:
    try:
        value = st.secrets.get("VIEWER_PASSWORD", "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv("VIEWER_PASSWORD", "").strip()


def _require_viewer_login() -> bool:
    password = _viewer_password()
    if not password:
        return True

    st.markdown("### Acesso ao painel")
    st.caption("Informe a senha compartilhada pela liderança para visualizar os indicadores.")
    typed = st.text_input("Senha", type="password", key="viewer_password_input")
    if typed != password:
        if typed:
            st.error("Senha incorreta.")
        st.stop()
    return True


def _apply_streamlit_secrets_env() -> None:
    try:
        if "THREECPLUS_API_TOKEN" in st.secrets:
            os.environ["THREECPLUS_API_TOKEN"] = str(st.secrets["THREECPLUS_API_TOKEN"])
        for key in ("DATA_SOURCE", "THREECPLUS_API_BASE", "CSV_IMPORT_FOLDER"):
            if key in st.secrets:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass


def _load_calls_dashboard(mode: str, ref_date: str | None = None) -> tuple[list, str]:
    _apply_streamlit_secrets_env()
    if mode == "cloud":
        from src.api_3cplus import _api_token, fetch_calls_for_day

        if not _api_token():
            raise ValueError(
                "THREECPLUS_API_TOKEN ausente nos Secrets do Streamlit. "
                'Adicione THREECPLUS_API_TOKEN e DATA_SOURCE = "api".'
            )
        target_day = date.fromisoformat(ref_date) if ref_date else date.today()
        calls = fetch_calls_for_day(target_day=target_day)
        if not calls:
            raise ValueError(f"API 3C Plus retornou 0 ligações para {target_day.isoformat()}.")
        return calls, f"API 3C Plus (nuvem · {target_day.isoformat()})"
    return load_calls()


def _upload_snapshot(summary: dict) -> str | None:
    payload = build_cloud_snapshot_payload(summary)
    upload_error: str | None = None
    try:
        upload_snapshot_sheets(payload)
    except Exception as exc:
        upload_error = f"Planilha _Snapshot: {exc}"
    if drive_snapshot_configured():
        try:
            upload_snapshot_drive(payload)
        except Exception as exc:
            upload_error = upload_error or f"Drive: {exc}"
    return upload_error


@st.cache_data(ttl=60, show_spinner=False)
def _download_remote_snapshot() -> dict | None:
    summary = download_snapshot_sheets()
    if not summary and drive_snapshot_configured():
        summary = download_snapshot_drive()
    return summary


def _reaggregate_summary(
    summary: dict,
    mode: str,
    *,
    ref_date: str | None = None,
) -> tuple[dict, str | None, str | None]:
    if summary_has_improdutiva_data(summary):
        return enrich_summary_improdutivas(summary), None, None
    try:
        calls, origin = _load_calls_dashboard(mode, ref_date=ref_date)
        fresh = aggregate_production(calls)
        if not summary_has_improdutiva_data(fresh):
            return (
                enrich_summary_improdutivas(summary),
                None,
                (
                    f"Fonte retornou {len(calls)} ligações, mas 0 improdutivas. "
                    "Rode `python run.py` no PC com o CSV do dia."
                ),
            )
        upload_error = _upload_snapshot(fresh)
        try:
            save_snapshot(fresh)
        except Exception:
            pass
        if upload_error:
            return fresh, origin, upload_error
        return fresh, origin, None
    except Exception as exc:
        bundled = load_snapshot()
        if bundled and summary_has_improdutiva_data(bundled):
            merged = merge_improdutivas_from(bundled, summary)
            return merged, "Snapshot local (data/latest.json)", None
        return enrich_summary_improdutivas(summary), None, str(exc)


def fetch_data(refresh: bool, mode: str) -> dict:
    _apply_streamlit_secrets_env()
    reload_error: str | None = None

    if mode == "cloud":
        if refresh:
            try:
                remote = _download_remote_snapshot() or {}
                ref_date = remote.get("date")
                summary, origin, err = _reaggregate_summary(remote, mode, ref_date=ref_date)
                improd = int(summary.get("total_improdutiva", 0))
                return {
                    "summary": summary,
                    "origin": f"{origin or 'API 3C Plus'} · atualizado agora · {improd} improdutivas",
                    "reload_error": err,
                }
            except Exception as exc:
                reload_error = str(exc)
                remote = _download_remote_snapshot()
                if remote:
                    bundled = load_snapshot()
                    summary = merge_improdutivas_from(bundled or {}, remote)
                    return {
                        "summary": summary,
                        "origin": "Planilha Google (visualização remota)",
                        "reload_error": reload_error,
                    }

        summary = _download_remote_snapshot()
        if not summary:
            return {
                "summary": None,
                "origin": "Planilha Google (_Snapshot) — rode run.py no PC principal",
                "reload_error": reload_error,
            }
        bundled = load_snapshot()
        summary = merge_improdutivas_from(bundled or {}, summary)
        summary, reorigin, regen_error = _reaggregate_summary(
            summary, mode, ref_date=summary.get("date")
        )
        origin = "Planilha Google (visualização remota)"
        if reorigin:
            origin = f"{reorigin} · dados atualizados"
        if regen_error and not reload_error:
            reload_error = regen_error
        return {"summary": summary, "origin": origin, "reload_error": reload_error}

    if refresh:
        calls, origin = _load_calls_dashboard(mode)
        summary = aggregate_production(calls)
        save_snapshot(summary)
        upload_err = _upload_snapshot(summary)
        return {
            "summary": summary,
            "origin": origin,
            "reload_error": upload_err,
        }

    snapshot = load_snapshot()
    if snapshot:
        summary, reorigin, regen_error = _reaggregate_summary(
            snapshot, mode, ref_date=snapshot.get("date")
        )
        origin = "Snapshot (data/latest.json)"
        if reorigin:
            origin = f"{reorigin} · snapshot atualizado"
        return {"summary": summary, "origin": origin, "reload_error": regen_error}

    if remote_snapshot_configured():
        remote = _download_remote_snapshot()
        if remote:
            summary, reorigin, regen_error = _reaggregate_summary(
                remote, mode, ref_date=remote.get("date")
            )
            origin = "Planilha Google (_Snapshot)"
            if reorigin:
                origin = f"{reorigin} · dados atualizados"
            return {"summary": summary, "origin": origin, "reload_error": regen_error}

    if drive_snapshot_configured():
        remote = download_snapshot_drive()
        if remote:
            summary, reorigin, regen_error = _reaggregate_summary(
                remote, mode, ref_date=remote.get("date")
            )
            origin = "Google Drive (snapshot)"
            if reorigin:
                origin = f"{reorigin} · dados atualizados"
            return {"summary": summary, "origin": origin, "reload_error": regen_error}

    calls, origin = _load_calls_dashboard(mode)
    summary = aggregate_production(calls)
    save_snapshot(summary)
    upload_err = _upload_snapshot(summary)
    return {"summary": summary, "origin": origin, "reload_error": upload_err}


def _squad_banner_class(squad: str) -> str:
    if squad == "Over 90 + IR":
        return "over90"
    if squad == "Early Stage":
        return "early"
    return "todos"


def _squad_banner_html(squad: str, agent_names: set[str] | None) -> str:
    if squad == "Todos":
        return (
            '<div class="squad-banner todos">Visão consolidada · todas as squads</div>'
        )
    names = ", ".join(sorted(agent_names or []))
    css = _squad_banner_class(squad)
    return f'<div class="squad-banner {css}">Squad <strong>{squad}</strong> · {len(agent_names or [])} agente(s)<br><span style="font-weight:500;font-size:0.85rem">{names}</span></div>'


def _normalize_agent_stats(rows: list) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(dict(row))
            continue
        if isinstance(row, (list, tuple)) and len(row) >= 3:
            item = {"agent": row[0], "cpc": row[1], "acordos": row[2]}
            if len(row) >= 4:
                item["finalizadas"] = row[3]
            normalized.append(item)
    return normalized


def _agents_df(summary: dict) -> pd.DataFrame:
    rows = _normalize_agent_stats(summary.get("agent_stats") or [])

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "finalizadas" not in df.columns:
        df["finalizadas"] = 0
    df["finalizadas"] = df["finalizadas"].fillna(0).astype(int)
    df["% Reversão"] = df.apply(lambda r: _reversion_pct(int(r["cpc"]), int(r["acordos"])), axis=1)
    df = df.sort_values(["acordos", "cpc", "finalizadas"], ascending=False)
    return df.rename(
        columns={
            "agent": "Agente",
            "finalizadas": "Ligações atendidas",
            "cpc": "CPC",
            "acordos": "Acordos",
        }
    )


def _macro_cell(value: int | float, max_val: float, fill_color: str, *, pct_scale: bool = False) -> str:
    if pct_scale:
        width = min(100.0, float(value))
    else:
        width = min(100.0, (float(value) / max_val * 100) if max_val > 0 else 0)
    display = _fmt_num(int(value)) if not pct_scale else f"{value:.1f}%".replace(".", ",")
    return (
        f'<div class="macro-cell">'
        f'<div class="macro-fill" style="width:{width:.1f}%;background:{fill_color};"></div>'
        f"<span>{display}</span></div>"
    )


def _agent_macro_table_html(df: pd.DataFrame, squad: str = "Todos") -> str:
    """Visão macro por agente: ligações → CPC → acordos → reversão."""
    chart = df.copy()
    if chart.empty:
        return ""

    max_lig = max(int(chart["Ligações atendidas"].max()), 1)
    max_cpc = max(int(chart["CPC"].max()), 1)
    max_aco = max(int(chart["Acordos"].max()), 1)

    rows_html: list[str] = []
    for _, row in chart.iterrows():
        rev = row["% Reversão"]
        rev_cell = _reversion_value_cell(rev if pd.notna(rev) else None)
        rows_html.append(
            "<tr>"
            f'<td class="agent-name">{row["Agente"]}</td>'
            f'<td class="num">{_macro_cell(int(row["Ligações atendidas"]), max_lig, "#E8EEF8")}</td>'
            f'<td class="num">{_macro_cell(int(row["CPC"]), max_cpc, _BRAND["primary_light"])}</td>'
            f'<td class="num">{_macro_cell(int(row["Acordos"]), max_aco, _BRAND["success_light"])}</td>'
            f"<td class=\"num\">{rev_cell}</td>"
            "</tr>"
        )

    total_lig = int(chart["Ligações atendidas"].sum())
    total_cpc = int(chart["CPC"].sum())
    total_aco = int(chart["Acordos"].sum())
    total_rev = _reversion_pct(total_cpc, total_aco)
    total_rev_cell = _reversion_footer_cell(total_rev)

    squad_note = f" · {squad}" if squad != "Todos" else ""
    return f"""
<div class="agent-macro-wrap">
  <table class="agent-macro-table">
    <thead>
      <tr>
        <th>Agente{squad_note}</th>
        <th class="num">Ligações atendidas</th>
        <th class="num">CPC</th>
        <th class="num">Acordos</th>
        <th class="num">% Reversão</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
    <tfoot>
      <tr>
        <td>Total da squad</td>
        <td class="num">{_fmt_num(total_lig)}</td>
        <td class="num">{_fmt_num(total_cpc)}</td>
        <td class="num">{_fmt_num(total_aco)}</td>
        <td class="num">{total_rev_cell}</td>
      </tr>
    </tfoot>
  </table>
</div>
"""


def _detail_row_key(row: dict) -> tuple[str, ...]:
    return (
        str(row.get("contract_number", "")).strip(),
        str(row.get("agent_name", "")).strip(),
        str(row.get("call_date", "")).strip(),
        str(row.get("qualification_name", "")).strip(),
        str(row.get("number", "")).strip(),
    )


def _all_contract_details_rows(summary: dict) -> list[dict]:
    """CPC + improdutivas em uma única lista (sem duplicar acordos/CPC)."""
    merged: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for key in ("cpc_rows", "improdutiva_rows"):
        for row in summary.get(key, []):
            if not isinstance(row, dict):
                continue
            dedupe_key = _detail_row_key(row)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            merged.append(dict(row))
    merged.sort(key=lambda item: str(item.get("call_date", "")), reverse=True)
    return merged


def _prepare_details_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "is_cpc" in df.columns:
        df["cpc_label"] = df["is_cpc"].map(lambda value: "Sim" if bool(value) else "Não")
    else:
        df["cpc_label"] = "Não"
    rename = {
        "agent_name": "Agente",
        "contract_number": "Nº Contrato",
        "cpc_label": "CPC",
        "qualification_name": "Finalização",
        "call_date": "Data/Hora",
        "campaign_name": "Campanha",
        "number": "Telefone",
    }
    cols = [c for c in rename if c in df.columns]
    out = df[cols].rename(columns=rename)
    order = ["Agente", "Nº Contrato", "CPC", "Finalização", "Data/Hora", "Campanha", "Telefone"]
    return out[[col for col in order if col in out.columns]]


def _filter_details(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if df.empty or not query.strip():
        return df
    q = query.strip().lower()
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        mask |= df[col].astype(str).str.lower().str.contains(q, na=False, regex=False)
    return df[mask]


def _agent_count_rows(agents) -> list[dict]:
    rows: list[dict[str, Any]] = []
    if isinstance(agents, dict):
        return [{"Agente": agent, "Ligações": int(count)} for agent, count in agents.items()]
    for item in agents:
        if isinstance(item, dict):
            rows.append({"Agente": item["agent"], "Ligações": int(item["count"])})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append({"Agente": item[0], "Ligações": int(item[1])})
    return rows


def _improdutivas_by_type(summary: dict) -> dict:
    summary = enrich_summary_improdutivas(summary)
    by_type = summary.get("improdutivas_by_type") or {}
    if breakdown_total(by_type) > 0:
        return by_type
    return {}


def _show_breakdown_by_type(by_type: dict, *, empty_msg: str) -> None:
    if not by_type:
        st.info(empty_msg)
        return
    cols = st.columns(2)
    for i, (qual, agents) in enumerate(by_type.items()):
        agent_rows = _agent_count_rows(agents)
        block = pd.DataFrame(agent_rows)
        total = int(block["Ligações"].sum()) if not block.empty else 0
        with cols[i % 2]:
            st.markdown(f"**{qual}** · Total: **{total}**")
            if block.empty:
                st.caption("Nenhum registro")
            else:
                st.dataframe(block.sort_values("Ligações", ascending=False), hide_index=True)


def _show_details_table(df: pd.DataFrame, empty_msg: str, search: str) -> None:
    if df.empty and not search.strip():
        st.caption(empty_msg)
        return
    if df.empty:
        st.warning(f"Nenhum resultado para «{search}».")
        return
    if search.strip():
        st.caption(f"{len(df)} registro(s) encontrado(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    mode = _dashboard_mode()
    is_cloud = mode == "cloud"

    if is_cloud:
        _require_viewer_login()

    head_l, head_r = st.columns([5, 1])
    with head_l:
        st.markdown(_build_header_html(), unsafe_allow_html=True)
    with head_r:
        st.markdown("<div style='margin-top:1.6rem'></div>", unsafe_allow_html=True)
        refresh_label = "Recarregar" if is_cloud else "Atualizar agora"
        refresh = st.button(refresh_label, type="primary", use_container_width=True)

    if refresh:
        _download_remote_snapshot.clear()
        fetch_data.clear()

    payload = fetch_data(refresh=refresh, mode=mode)
    base_summary = payload["summary"]
    origin = payload["origin"]
    reload_error = payload.get("reload_error")

    if reload_error:
        st.warning(f"Não foi possível atualizar pela API: {reload_error}")

    if not base_summary:
        st.error(
            "Nenhum dado disponível na nuvem ainda. "
            "No PC principal, configure o Google Drive no `.env`, rode `python run.py` "
            "e publique o app no Streamlit Cloud."
        )
        st.stop()

    squad_options = squad_labels()
    default_squad = "Todos" if "Todos" in squad_options else squad_options[0]
    selected_squad = st.segmented_control(
        "Squad",
        options=squad_options,
        default=default_squad,
        selection_mode="single",
    )
    selected_squad = selected_squad or default_squad
    summary = filter_summary(base_summary, selected_squad)
    squad_agents = agents_for_squad(selected_squad, base_summary)

    st.markdown(_squad_banner_html(selected_squad, squad_agents), unsafe_allow_html=True)

    updated = summary.get("updated_at", "—")
    ref_date = summary.get("date", "—")

    rev = _reversion_pct(summary.get("total_cpc", 0), summary.get("total_production", 0))
    rev_display = f"{rev:.1f}%".replace(".", ",") if rev is not None else "—"

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            _kpi_card("CPC — Contato positivo", _fmt_num(summary.get("total_cpc", 0)), "cpc", ICON_CPC),
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            _kpi_card("Acordos formalizados", _fmt_num(summary.get("total_production", 0)), "acordos", ICON_ACORDOS),
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            _kpi_card("Reversão geral", rev_display, "reversao", ICON_REVERSAO),
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            _kpi_card("Chamadas finalizadas", _fmt_num(summary.get("total_finalized", 0)), "finalizadas", ICON_FINALIZADAS),
            unsafe_allow_html=True,
        )

    st.caption(
        f"Fonte: {origin} · Atualizado: {updated} · Referência: {ref_date}"
        + (f" · Squad: {selected_squad}" if selected_squad != "Todos" else "")
    )

    df = _agents_df(summary)
    if df.empty:
        st.warning(
            "Sem dados para esta squad no dia. Tente «Todos» ou exporte o CSV do 3C Plus e rode run.py."
        )
        return

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Performance", "CPC por tipo", "Improdutivas por tipo", "Detalhes"]
    )

    with tab1:
        st.subheader("Produção por agente")
        st.caption("Funil operacional · ligações atendidas → CPC → acordos → % reversão")
        st.markdown(_agent_macro_table_html(df, selected_squad), unsafe_allow_html=True)

        c1, c2 = st.columns([1, 1])
        with c1:
            share = _share_chart(df, selected_squad)
            if len(share.data) > 0:
                st.plotly_chart(share, use_container_width=True, theme=None)
            else:
                st.caption("Sem acordos para exibir participação.")
        with c2:
            st.caption("Agentes com CPC ≥ 3 · azul = meta 70% atingida · faixa verde à direita da linha")
            rev_chart = _reversion_chart(df, selected_squad)
            if len(rev_chart.data) > 0:
                st.plotly_chart(rev_chart, use_container_width=True, theme=None)
            else:
                st.caption("Sem dados de reversão por agente.")

    with tab2:
        _show_breakdown_by_type(
            summary.get("cpc_by_type", {}),
            empty_msg="Sem breakdown de CPC.",
        )

    with tab3:
        improdutivas = _improdutivas_by_type(summary)
        if improdutivas:
            _show_breakdown_by_type(improdutivas, empty_msg="")
        elif summary_has_improdutiva_data(summary):
            st.info("Nenhuma finalização improdutiva no período.")
        else:
            st.info(
                "Dados de improdutivas ainda não disponíveis. "
                "No PC rode `powershell -File scripts/atualizar_painel.ps1`, "
                "depois **git push** e **Recarregar** aqui."
            )
            if reload_error:
                st.caption(f"Detalhe: {reload_error}")

    with tab4:
        search = st.text_input(
            "Pesquisar",
            placeholder="Ex.: contrato, agente, CPC, finalização ou telefone",
            key="detalhes_search",
        )

        all_details = _filter_details(
            _prepare_details_df(_all_contract_details_rows(summary)),
            search,
        )
        _show_details_table(all_details, "Nenhum registro no período.", search)


if __name__ == "__main__":
    main()
