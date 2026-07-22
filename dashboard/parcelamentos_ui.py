"""UI Streamlit — registro e cobrança de parcelamentos (entrada + boletos)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src import parcelamentos as parc


def _money_br(value: float | Decimal | int) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


_STATUS_PARCELA_STYLE = {
    "atrasado": ("#FFF3CD", "#856404", "Em atraso"),
    "pendente": ("#E8F7EF", "#1B7A4E", "Em dia"),
    "pago": ("#E8F1FF", "#1A4B9C", "Pago"),
    "cancelado": ("#FDECEA", "#C0392B", "Cancelado"),
}

_ALERTA_STYLE = {
    parc.ALERTA_EM_DIA: ("#E8F7EF", "#1B7A4E", "#C6EBD5", "Em dia"),
    parc.ALERTA_EM_ATRASO: ("#FFF6D6", "#9A7B0A", "#F5E6A8", "Em atraso"),
    parc.ALERTA_A_VENCER: ("#E8F1FF", "#1A4B9C", "#C5D6F5", "A vencer"),
    parc.ALERTA_CANCELADO: ("#FDECEA", "#C0392B", "#F5C6C2", "Cancelado"),
}


def _label_status_parcela(status: str) -> str:
    key = (status or "").strip().lower()
    return _STATUS_PARCELA_STYLE.get(key, ("#EEF2F6", "#334155", status or "—"))[2]


def _df_parcelas(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    data = []
    for r in rows:
        st_eff = str(r.get("status_efetivo", ""))
        data.append(
            {
                "Vencimento": r.get("vencimento", ""),
                "Status": _label_status_parcela(st_eff),
                "_status_key": st_eff.strip().lower(),
                "Tipo": r.get("rotulo", ""),
                "CCB": r.get("ccb", ""),
                "CPF": r.get("cpf", ""),
                "Produto": r.get("produto", ""),
                "Valor": _money_br(r.get("valor_num", 0)),
                "Agente": r.get("agente", ""),
                "Formalização": r.get("formalizacao", ""),
            }
        )
    return pd.DataFrame(data)


def _style_parcelas_df(df: pd.DataFrame):
    if df.empty or "_status_key" not in df.columns:
        return df.drop(columns=["_status_key"], errors="ignore")

    keys = df["_status_key"].tolist()
    view = df.drop(columns=["_status_key"])

    def _row_style(row: pd.Series) -> list[str]:
        idx = row.name
        key = str(keys[idx] if isinstance(idx, int) and idx < len(keys) else "").strip().lower()
        bg, fg, _ = _STATUS_PARCELA_STYLE.get(key, ("#FFFFFF", "#111827", ""))
        styles = [f"background-color: {bg}"] * len(row)
        cols = list(row.index)
        if "Status" in cols:
            styles[cols.index("Status")] = f"background-color: {bg}; color: {fg}; font-weight: 700"
        return styles

    return view.style.apply(_row_style, axis=1)


def _status_badge_html(alerta: str, label: str) -> str:
    bg, fg, border, _lab = _ALERTA_STYLE.get(alerta, ("#EEF2F6", "#334155", "#D0D7E2", label))
    return (
        f'<span style="display:inline-block;padding:0.25rem 0.65rem;border-radius:999px;'
        f'background:{bg};color:{fg};border:1px solid {border};font-weight:800;'
        f'font-size:0.85rem">{escape(label)}</span>'
    )


def _show_parcelas_table(rows: list[dict]) -> None:
    df = _df_parcelas(rows)
    if df.empty:
        return
    st.dataframe(_style_parcelas_df(df), hide_index=True, use_container_width=True)


def _filter_ccb(rows: list[dict], ccb_q: str) -> list[dict]:
    q = "".join(ch for ch in (ccb_q or "") if ch.isalnum()).casefold()
    if not q:
        return rows
    out = []
    for r in rows:
        ccb = str(r.get("ccb", "")).casefold().replace(" ", "")
        if q in ccb:
            out.append(r)
    return out


def _storage_banner() -> None:
    if parc.spreadsheet_configured():
        cfg = parc.load_config()
        sid = str(cfg.get("spreadsheet_id", "")).strip()
        st.caption(
            f"Armazenamento: Google Sheets · "
            f"[abrir planilha](https://docs.google.com/spreadsheets/d/{sid})"
        )
    else:
        st.info(
            "Modo local (ainda sem planilha Google). Os acordos ficam em "
            "`data/parcelamentos_local.json`. Para produção, rode "
            "`python scripts/setup_parcelamentos_sheet.py` e compartilhe a planilha "
            "com a conta de serviço."
        )


def _produto_por_agente(agente: str) -> str:
    nome = (agente or "").casefold()
    if "douglas" in nome or "marina" in nome:
        return "Over 90"
    return "IR"


def _render_novo_acordo() -> None:
    st.subheader("Novo acordo de parcelamento")
    st.caption(
        "Campos: formalização, CPF, CCB, produto (automático pelo agente), data/valor entrada, "
        "valor igual das demais parcelas, vencimento da 1ª parcela e agente. "
        "Valor total = entrada + (parcelas × valor). Demais vencimentos: a cada 30 dias."
    )

    agents = parc.list_agents()
    cfg = parc.load_config()
    max_parc = int(cfg.get("max_parcelas", 5))

    c1, c2 = st.columns(2)
    with c1:
        if agents:
            agente = st.selectbox("Agente *", options=agents)
        else:
            agente = st.text_input("Agente *")
        produto = _produto_por_agente(str(agente))
        st.text_input(
            "Produto *",
            value=produto,
            disabled=True,
            help="Douglas/Marina → Over 90 · demais → IR",
        )
        formalizacao = st.date_input("Data de formalização *", value=date.today())
        cpf = st.text_input("CPF *", placeholder="000.000.000-00")
        ccb = st.text_input("CCB *", placeholder="Número do contrato")
    with c2:
        n_parcelas = st.selectbox(
            "Qtd. parcelas após a entrada *",
            options=list(range(1, max_parc + 1)),
            index=min(2, max_parc - 1),
        )
        valor_entrada = st.number_input(
            "Valor da entrada (R$) *",
            min_value=0.0,
            value=0.0,
            step=50.0,
            format="%.2f",
        )
        data_entrada = st.date_input("Data da entrada *", value=formalizacao)
        valor_demais = st.number_input(
            "Valor de cada parcela (demais) (R$) *",
            min_value=0.0,
            value=0.0,
            step=50.0,
            format="%.2f",
            help="Todas as parcelas após a entrada têm o mesmo valor.",
        )
        venc_primeira = st.date_input(
            "Vencimento da 1ª parcela *",
            value=parc.add_months(formalizacao, 1),
            help="Demais parcelas: mesmo dia, mês a mês (+1 mês).",
        )

    n = int(n_parcelas)
    valor_total = float(valor_entrada) + float(valor_demais) * n
    st.metric(
        "Valor total do acordo",
        _money_br(valor_total),
        help="Calculado automaticamente: entrada + (qtd. parcelas × valor de cada parcela).",
    )
    if n >= 1 and valor_demais > 0:
        preview_venc = [
            parc.add_months(venc_primeira, i).strftime("%d/%m/%Y") for i in range(n)
        ]
        st.caption("Vencimentos das parcelas (mensal): " + " · ".join(preview_venc))

    cliente = st.text_input("Cliente (opcional)")
    observacao = st.text_area("Observação (opcional)", height=68)
    salvar = st.button("Salvar acordo", type="primary", use_container_width=True)

    if not salvar:
        return

    missing: list[str] = []
    if not str(agente).strip():
        missing.append("agente")
    if not str(cpf).strip():
        missing.append("CPF")
    if not str(ccb).strip():
        missing.append("CCB")
    if not str(produto).strip():
        missing.append("produto")
    if valor_entrada <= 0:
        missing.append("valor da entrada")
    if valor_demais <= 0:
        missing.append("valor das demais parcelas")
    if valor_total <= 0:
        missing.append("valor total do acordo")
    if missing:
        st.error("Preencha os obrigatórios: " + ", ".join(missing))
        return

    valores_parcelas = [valor_demais] * n
    vencimentos = [parc.add_months(venc_primeira, i) for i in range(n)]

    try:
        result = parc.criar_acordo(
            agente=str(agente),
            cpf=str(cpf),
            ccb=str(ccb),
            produto=str(produto),
            valor_total=valor_total,
            valor_entrada=valor_entrada,
            valores_parcelas=valores_parcelas,
            data_entrada=data_entrada,
            vencimentos_parcelas=vencimentos,
            formalizacao=formalizacao,
            n_parcelas=n,
            cliente=cliente,
            observacao=observacao,
        )
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")
        return

    acordo = result["acordo"]
    st.success(
        f"Salvo — CPF {acordo['cpf']} · CCB {acordo['ccb']} · "
        f"{acordo['produto']} · total {acordo['valor_total']} · "
        f"entrada {acordo['valor_entrada']} + {acordo['n_parcelas']}x de {acordo['valor_parcela']}"
    )
    st.dataframe(_df_parcelas([parc.enrich_parcela(p) for p in result["parcelas"]]), hide_index=True)


def _render_cobranca() -> None:
    st.subheader("Cobrança das parcelas")
    today = date.today()
    agents = ["Todos"] + parc.list_agents()

    f0, f1, f2, f3, f4 = st.columns([1.3, 1.2, 1, 1, 1.1])
    with f0:
        ccb_q = st.text_input("Buscar CCB", placeholder="Ex.: 3030037", key="parc_cob_ccb")
    with f1:
        agente_sel = st.selectbox("Agente", options=agents, key="parc_cob_agente")
    with f2:
        horizonte = st.selectbox(
            "Próximos",
            options=[7, 15, 30, 45, 60],
            index=2,
            format_func=lambda d: f"{d} dias",
            key="parc_cob_dias",
        )
    _meses = (
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    )
    with f3:
        mes = st.selectbox(
            "Mês",
            options=list(range(1, 13)),
            index=today.month - 1,
            format_func=lambda m: _meses[m - 1],
            key="parc_cob_mes",
        )
    with f4:
        ano = st.number_input("Ano", min_value=2024, max_value=2100, value=today.year, step=1, key="parc_cob_ano")

    agente = None if agente_sel == "Todos" else agente_sel

    atrasadas = _filter_ccb(parc.parcelas_atrasadas(agente=agente, today=today), ccb_q)
    a_vencer = _filter_ccb(parc.parcelas_a_vencer(dias=int(horizonte), agente=agente, today=today), ccb_q)
    do_mes = _filter_ccb(
        parc.listar_parcelas_enriquecidas(
            agente=agente,
            mes=int(mes),
            ano=int(ano),
            only_open=False,
            today=today,
        ),
        ccb_q,
    )

    leg1, leg2, leg3, leg4 = st.columns(4)
    leg1.markdown(
        '<div style="background:#FFF3CD;color:#856404;padding:0.55rem 0.75rem;border-radius:10px;'
        'border:1px solid #F5E6A8;font-weight:700;text-align:center">Em atraso</div>',
        unsafe_allow_html=True,
    )
    leg2.markdown(
        '<div style="background:#E8F7EF;color:#1B7A4E;padding:0.55rem 0.75rem;border-radius:10px;'
        'border:1px solid #C6EBD5;font-weight:700;text-align:center">Em dia</div>',
        unsafe_allow_html=True,
    )
    leg3.markdown(
        '<div style="background:#E8F1FF;color:#1A4B9C;padding:0.55rem 0.75rem;border-radius:10px;'
        'border:1px solid #C5D6F5;font-weight:700;text-align:center">Pago</div>',
        unsafe_allow_html=True,
    )
    leg4.markdown(
        '<div style="background:#FDECEA;color:#C0392B;padding:0.55rem 0.75rem;border-radius:10px;'
        'border:1px solid #F5C6C2;font-weight:700;text-align:center">Cancelado</div>',
        unsafe_allow_html=True,
    )

    k1, k2, k3 = st.columns(3)
    k1.metric("Atrasadas", len(atrasadas), help="Vencidas e ainda não pagas")
    k2.metric(f"A vencer ({horizonte}d)", len(a_vencer))
    k3.metric(
        f"No mês {int(mes):02d}/{int(ano)}",
        len(do_mes),
        help="Todas as parcelas com vencimento no mês (abertas e pagas)",
    )

    tab_atr, tab_venc, tab_mes = st.tabs(["Atrasadas", "A vencer", "Do mês"])
    with tab_atr:
        if not atrasadas:
            st.success("Nenhuma parcela atrasada neste filtro.")
        else:
            _show_parcelas_table(atrasadas)
    with tab_venc:
        if not a_vencer:
            st.info("Nada a vencer no horizonte selecionado.")
        else:
            _show_parcelas_table(a_vencer)
    with tab_mes:
        if not do_mes:
            st.info("Sem parcelas com vencimento neste mês.")
        else:
            _show_parcelas_table(do_mes)


def _render_baixas() -> None:
    st.subheader("Baixa de pagamento")
    st.caption("Marque a parcela como paga após confirmar o boleto/comprovante.")

    abertas = parc.listar_parcelas_enriquecidas(only_open=True)
    if not abertas:
        st.info("Não há parcelas em aberto.")
        return

    labels = {
        r["parcela_id"]: (
            f"{r.get('vencimento')} · {r.get('rotulo')} · CCB {r.get('ccb')} · "
            f"CPF {r.get('cpf')} · {_money_br(r.get('valor_num', 0))} · "
            f"{r.get('agente')} · [{_label_status_parcela(str(r.get('status_efetivo', '')))}]"
        )
        for r in abertas
    }
    escolha = st.selectbox(
        "Parcela",
        options=list(labels.keys()),
        format_func=lambda pid: labels.get(pid, pid),
    )
    pago_em = st.date_input("Data do pagamento", value=date.today(), key="parc_pago_em")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Marcar como pago", type="primary", use_container_width=True):
            try:
                parc.marcar_pago(escolha, pago_em=pago_em)
                st.success("Parcela marcada como paga.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with c2:
        if st.button("Reabrir (pendente)", use_container_width=True):
            try:
                parc.marcar_pendente(escolha)
                st.success("Parcela reaberta.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _alerta_card_html(alerta: str, count: int) -> str:
    bg, fg, border, label = _ALERTA_STYLE[alerta]
    return (
        f'<div style="background:{bg};color:{fg};border:2px solid {border};border-radius:12px;'
        f'padding:0.85rem 1rem;text-align:center">'
        f'<div style="font-size:0.8rem;font-weight:700;opacity:0.9;text-transform:uppercase">'
        f'{escape(label)}</div>'
        f'<div style="font-size:1.6rem;font-weight:800;line-height:1.2;margin-top:0.2rem">{count}</div>'
        f"</div>"
    )


def _render_historico_alertas() -> None:
    st.subheader("Histórico de acordos")
    st.caption("Em dia (verde) · Em atraso (amarelo) · Cancelado (vermelho). Busque por CCB.")

    agents = ["Todos"] + parc.list_agents()
    resumo_all = parc.resumo_acordos()
    hist_agents = sorted({r.get("agente", "") for r in resumo_all if r.get("agente")})
    for name in hist_agents:
        if name and name not in agents:
            agents.append(name)

    f0, f1, f2 = st.columns([1.4, 1.4, 1])
    with f0:
        ccb_q = st.text_input("Buscar CCB", placeholder="Ex.: 3030037", key="parc_hist_ccb")
    with f1:
        agente_sel = st.selectbox("Agente", options=agents, key="parc_hist_agente")
    with f2:
        filtro = st.selectbox(
            "Alerta",
            options=["Todos", "Em dia", "Em atraso", "A vencer", "Cancelado"],
            key="parc_hist_alerta",
        )

    agente = None if agente_sel == "Todos" else agente_sel
    rows = parc.resumo_acordos(agente=agente)
    rows = _filter_ccb(rows, ccb_q)
    if filtro != "Todos":
        mapa = {
            "Em dia": parc.ALERTA_EM_DIA,
            "Em atraso": parc.ALERTA_EM_ATRASO,
            "A vencer": parc.ALERTA_A_VENCER,
            "Cancelado": parc.ALERTA_CANCELADO,
        }
        rows = [r for r in rows if r["alerta"] == mapa[filtro]]

    n_dia = sum(1 for r in resumo_all if r["alerta"] == parc.ALERTA_EM_DIA)
    n_atr = sum(1 for r in resumo_all if r["alerta"] == parc.ALERTA_EM_ATRASO)
    n_venc = sum(1 for r in resumo_all if r["alerta"] == parc.ALERTA_A_VENCER)
    n_can = sum(1 for r in resumo_all if r["alerta"] == parc.ALERTA_CANCELADO)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_alerta_card_html(parc.ALERTA_EM_DIA, n_dia), unsafe_allow_html=True)
    c2.markdown(_alerta_card_html(parc.ALERTA_EM_ATRASO, n_atr), unsafe_allow_html=True)
    c3.markdown(_alerta_card_html(parc.ALERTA_A_VENCER, n_venc), unsafe_allow_html=True)
    c4.markdown(_alerta_card_html(parc.ALERTA_CANCELADO, n_can), unsafe_allow_html=True)

    st.markdown("")

    if not rows:
        st.info("Nenhum acordo neste filtro.")
        return

    body_rows = []
    for r in rows:
        alerta = r["alerta"]
        bg, fg, border, label = _ALERTA_STYLE.get(
            alerta, ("#FFFFFF", "#111827", "#E6EAF0", r.get("alerta_label", ""))
        )
        badge = _status_badge_html(alerta, label)
        body_rows.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border}'>{badge}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border};font-weight:700'>"
            f"{escape(str(r.get('ccb','')))}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border}'>"
            f"{escape(str(r.get('cpf','')))}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border}'>"
            f"{escape(str(r.get('produto','')))}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border}'>"
            f"{escape(str(r.get('agente','')))}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border}'>"
            f"{escape(str(r.get('formalizacao','')))}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border};text-align:right'>"
            f"{escape(str(r.get('valor_total','')))}</td>"
            f"<td style='padding:0.55rem 0.65rem;border-bottom:1px solid {border};text-align:right;"
            f"color:{fg};font-weight:700'>"
            f"{r.get('parcelas_atrasadas',0)} atrasadas</td>"
            "</tr>"
        )

    html = f"""
    <div style="font-family:Inter,Segoe UI,sans-serif;border:1px solid #E6EAF0;border-radius:12px;overflow:auto">
      <table style="width:100%;border-collapse:collapse;font-size:0.92rem">
        <thead>
          <tr style="background:#0F1B3D;color:#fff;text-align:left">
            <th style="padding:0.65rem">Alerta</th>
            <th style="padding:0.65rem">CCB</th>
            <th style="padding:0.65rem">CPF</th>
            <th style="padding:0.65rem">Produto</th>
            <th style="padding:0.65rem">Agente</th>
            <th style="padding:0.65rem">Formalização</th>
            <th style="padding:0.65rem;text-align:right">Total</th>
            <th style="padding:0.65rem;text-align:right">Atrasadas</th>
          </tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    </div>
    """
    # components.html garante CSS/cores (markdown do Streamlit às vezes limpa estilo)
    height = min(120 + len(rows) * 42, 720)
    components.html(html, height=height, scrolling=True)


def render_parcelamentos() -> None:
    st.caption("Ferramenta aparte do painel de produção · uso: Over 90 e IRPF")
    _storage_banner()

    tab_novo, tab_cob, tab_hist, tab_baixa = st.tabs(
        ["Novo acordo", "Cobrança do mês", "Histórico / Alertas", "Baixas"]
    )
    with tab_novo:
        _render_novo_acordo()
    with tab_cob:
        _render_cobranca()
    with tab_hist:
        _render_historico_alertas()
    with tab_baixa:
        _render_baixas()
