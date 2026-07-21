"""UI Streamlit — registro e cobrança de parcelamentos (entrada + boletos)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

from src import parcelamentos as parc


def _money_br(value: float | Decimal | int) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _df_parcelas(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    data = []
    for r in rows:
        data.append(
            {
                "Vencimento": r.get("vencimento", ""),
                "Status": r.get("status_efetivo", ""),
                "Tipo": r.get("rotulo", ""),
                "CCB": r.get("ccb", ""),
                "CPF": r.get("cpf", ""),
                "Produto": r.get("produto", ""),
                "Valor": _money_br(r.get("valor_num", 0)),
                "Agente": r.get("agente", ""),
                "Formalização": r.get("formalizacao", ""),
                "Acordo": r.get("acordo_id", ""),
                "Parcela ID": r.get("parcela_id", ""),
            }
        )
    return pd.DataFrame(data)


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


def _render_novo_acordo() -> None:
    st.subheader("Novo acordo de parcelamento")
    st.caption(
        "Campos obrigatórios: data de formalização, CPF, CCB, produto, data entrada, "
        "valor total, valor entrada, valor parcelas, vencimento(s) e agente. "
        "Sugestão padrão: entrada 30% + restante em até 5x."
    )

    agents = parc.list_agents()
    produtos = parc.list_produtos()
    cfg = parc.load_config()
    pct_default = float(cfg.get("entrada_pct_padrao", 30))
    max_parc = int(cfg.get("max_parcelas", 5))

    c1, c2 = st.columns(2)
    with c1:
        if agents:
            agente = st.selectbox("Agente *", options=agents)
        else:
            agente = st.text_input("Agente *")
        formalizacao = st.date_input("Data de formalização *", value=date.today())
        cpf = st.text_input("CPF *", placeholder="000.000.000-00")
        ccb = st.text_input("CCB *", placeholder="Número do contrato")
        produto = st.selectbox("Produto *", options=produtos)
        if produto == "Outro":
            produto_outro = st.text_input("Descreva o produto *")
            if produto_outro.strip():
                produto = produto_outro.strip()
    with c2:
        valor_total = st.number_input(
            "Valor total do acordo (R$) *",
            min_value=0.0,
            step=100.0,
            format="%.2f",
        )
        pct_entrada = st.number_input(
            "% entrada (sugestão)",
            min_value=0.0,
            max_value=100.0,
            value=pct_default,
            step=1.0,
            help="Padrão 30%. Usado só para preencher os valores abaixo.",
        )
        n_parcelas = st.selectbox(
            "Qtd. parcelas do restante *",
            options=list(range(1, max_parc + 1)),
            index=min(2, max_parc - 1),
        )
        cliente = st.text_input("Cliente (opcional)")
        telefone = st.text_input("Telefone (opcional)")

    plano = None
    if valor_total > 0:
        try:
            plano = parc.calcular_plano(valor_total, pct_entrada, int(n_parcelas))
        except ValueError as exc:
            st.error(str(exc))

    sug_entrada = float(plano["valor_entrada"]) if plano else 0.0
    sug_parcelas = [float(v) for v in plano["valores_parcelas"]] if plano else [0.0] * int(n_parcelas)

    st.markdown("**Valores e datas obrigatórios**")
    v1, v2 = st.columns(2)
    with v1:
        valor_entrada = st.number_input(
            "Valor da entrada (R$) *",
            min_value=0.0,
            value=sug_entrada,
            step=50.0,
            format="%.2f",
            key=f"valor_entrada_{n_parcelas}_{pct_entrada}_{valor_total}",
        )
        data_entrada = st.date_input("Data da entrada *", value=formalizacao)
    with v2:
        if plano:
            st.metric("Restante a parcelar", _money_br(max(valor_total - valor_entrada, 0)))
            st.caption(f"Sugestão {int(n_parcelas)}x ≈ {_money_br(plano['valor_parcela'])}")

    st.markdown("**Parcelas (valor + vencimento) ***")
    valores_parcelas: list[float] = []
    vencimentos: list[date] = []
    for i in range(int(n_parcelas)):
        col_a, col_b = st.columns(2)
        with col_a:
            valores_parcelas.append(
                st.number_input(
                    f"Valor parcela {i + 1} (R$) *",
                    min_value=0.0,
                    value=sug_parcelas[i] if i < len(sug_parcelas) else 0.0,
                    step=50.0,
                    format="%.2f",
                    key=f"vp_{i}_{n_parcelas}_{pct_entrada}_{valor_total}",
                )
            )
        with col_b:
            vencimentos.append(
                st.date_input(
                    f"Vencimento parcela {i + 1} *",
                    value=formalizacao + timedelta(days=30 * (i + 1)),
                    key=f"vv_{i}_{n_parcelas}",
                )
            )

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
    if not str(produto).strip() or str(produto).strip() == "Outro":
        missing.append("produto")
    if valor_total <= 0:
        missing.append("valor total do acordo")
    if valor_entrada <= 0:
        missing.append("valor da entrada")
    if any(v <= 0 for v in valores_parcelas):
        missing.append("valor das parcelas")
    if missing:
        st.error("Preencha os obrigatórios: " + ", ".join(missing))
        return

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
            n_parcelas=int(n_parcelas),
            pct_entrada=pct_entrada,
            cliente=cliente,
            telefone=telefone,
            observacao=observacao,
        )
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")
        return

    acordo = result["acordo"]
    st.success(
        f"Acordo `{acordo['acordo_id']}` salvo — CPF {acordo['cpf']} · CCB {acordo['ccb']} · "
        f"{acordo['produto']} · entrada {acordo['valor_entrada']} em {acordo['data_entrada']} + "
        f"{acordo['n_parcelas']}x"
    )
    st.dataframe(_df_parcelas([parc.enrich_parcela(p) for p in result["parcelas"]]), hide_index=True)


def _render_cobranca() -> None:
    st.subheader("Cobrança das parcelas")
    today = date.today()
    agents = ["Todos"] + parc.list_agents()

    f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1.2])
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

    atrasadas = parc.parcelas_atrasadas(agente=agente, today=today)
    a_vencer = parc.parcelas_a_vencer(dias=int(horizonte), agente=agente, today=today)
    do_mes = parc.listar_parcelas_enriquecidas(
        agente=agente,
        mes=int(mes),
        ano=int(ano),
        only_open=False,
        today=today,
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
        df = _df_parcelas(atrasadas)
        if df.empty:
            st.success("Nenhuma parcela atrasada neste filtro.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)
    with tab_venc:
        df = _df_parcelas(a_vencer)
        if df.empty:
            st.info("Nada a vencer no horizonte selecionado.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)
    with tab_mes:
        df = _df_parcelas(do_mes)
        if df.empty:
            st.info("Sem parcelas com vencimento neste mês.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)


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
            f"{r.get('agente')} · [{r.get('status_efetivo')}]"
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
                st.success(f"Parcela `{escolha}` marcada como paga.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with c2:
        if st.button("Reabrir (pendente)", use_container_width=True):
            try:
                parc.marcar_pendente(escolha)
                st.success(f"Parcela `{escolha}` reaberta.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def render_parcelamentos() -> None:
    st.markdown("### Parcelamentos (entrada + boletos)")
    _storage_banner()

    tab_novo, tab_cob, tab_baixa = st.tabs(["Novo acordo", "Cobrança do mês", "Baixas"])
    with tab_novo:
        _render_novo_acordo()
    with tab_cob:
        _render_cobranca()
    with tab_baixa:
        _render_baixas()
