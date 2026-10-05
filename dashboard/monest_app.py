"""Base de acordos Monest."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from dashboard import brand
from src.monest import STATUS_EM_ANDAMENTO, STATUS_QUEBRADO, acordos, load_base, resumo

st.set_page_config(
    page_title="Monest — acordos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(brand.css(), unsafe_allow_html=True)


def _money_br(value) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(iso or "")


def _status_label(status: str | None) -> str:
    return status or "Incompleto"


base = load_base()
rows = acordos()
totais = resumo(rows)

st.markdown(
    """
<div class="velo-header">
  <div class="velo-header-left">
    <div class="velo-product">Monest</div>
    <div class="velo-company" style="color:#ffffff;">Base de acordos</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.caption(
    f"Atualização { _data_br(base.get('atualizado_em', '')) } · "
    "a data é a coluna que veio entre o CPF e o valor."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Acordos", f"{totais['n']} · {_money_br(totais['valor_total'])}")
c2.metric("Em andamento", f"{totais['em_andamento']} · {_money_br(totais['valor_em_andamento'])}")
c3.metric("Quebrados", f"{totais['quebrado']} · {_money_br(totais['valor_quebrado'])}")
c4.metric("Incompletos", f"{totais['incompleto']} · {_money_br(totais['valor_incompleto'])}")

incompletos = [r for r in rows if not r.get("status") or not r.get("ccb")]
if incompletos:
    nomes = ", ".join(r["cliente"] for r in incompletos)
    st.warning(f"Sem CCB ou sem status: {nomes}. Esses campos não foram completados.")

filtro = st.selectbox(
    "Status",
    options=["Todos", STATUS_EM_ANDAMENTO, STATUS_QUEBRADO, "Incompleto"],
)
busca = st.text_input("Busca", placeholder="Cliente, CPF ou CCB")

view = rows
if filtro == "Incompleto":
    view = [r for r in view if not r.get("status") or not r.get("ccb")]
elif filtro != "Todos":
    view = [r for r in view if r.get("status") == filtro]

q = "".join(ch for ch in (busca or "") if ch.isalnum()).casefold()
if q:
    filtrados = []
    for r in view:
        blob = "".join(
            [
                str(r.get("cliente") or ""),
                str(r.get("cpf") or ""),
                str(r.get("ccb") or ""),
            ]
        )
        blob = "".join(ch for ch in blob if ch.isalnum()).casefold()
        if q in blob:
            filtrados.append(r)
    view = filtrados

tabela = pd.DataFrame(
    [
        {
            "Cliente": r["cliente"],
            "CPF": r["cpf"],
            "Data": _data_br(r["data"]),
            "Valor": _money_br(r["valor"]),
            "CCB": r.get("ccb") or "—",
            "Status": _status_label(r.get("status")),
        }
        for r in view
    ]
)

if tabela.empty:
    st.info("Nenhum acordo neste filtro.")
else:
    st.dataframe(tabela, hide_index=True, use_container_width=True)
    st.caption(f"{len(view)} acordo(s) neste filtro.")
