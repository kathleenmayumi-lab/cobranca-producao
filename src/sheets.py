"""Atualiza painel de produção no Google Sheets."""

from __future__ import annotations

import os
from typing import Any

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

from src.sheet_styles import style_cpc_matrix, style_cpc_por_tipo, style_detail_table, style_resumo

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _client() -> gspread.Client:
    sheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")

    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_ID não configurado no .env")
    if not os.path.exists(creds_file):
        raise FileNotFoundError(
            f"Arquivo de credenciais não encontrado: {creds_file}\n"
            "Siga o README para criar a conta de serviço Google."
        )

    credentials = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    return gspread.authorize(credentials)


def _build_cpc_by_type_rows(summary: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = [
        ["CPC por tipo de finalização"],
        ["Atualizado em", summary["updated_at"]],
        ["Data referência", summary["date"]],
        [],
    ]

    cpc_by_type: dict[str, list[tuple[str, int]]] = summary.get("cpc_by_type", {})
    for qualification, agent_counts in cpc_by_type.items():
        total = sum(count for _, count in agent_counts)
        rows.append([qualification])
        rows.append(["Agente", "Ligações"])
        if agent_counts:
            rows.extend([[agent, count] for agent, count in agent_counts])
        else:
            rows.append(["—", 0])
        rows.append(["TOTAL", total])
        rows.append([])

    return rows


def _build_cpc_matrix_rows(summary: dict[str, Any]) -> list[list[Any]]:
    """Matriz agente x tipo de CPC + totais por linha/coluna."""
    cpc_by_type: dict[str, list[tuple[str, int]]] = summary.get("cpc_by_type", {})
    qualifications = list(cpc_by_type.keys())
    if not qualifications:
        return [["Sem tipos de CPC configurados"]]

    agent_totals: dict[str, int] = {}
    qual_totals: dict[str, int] = {qual: 0 for qual in qualifications}
    matrix: dict[str, dict[str, int]] = {}

    for qualification, agent_counts in cpc_by_type.items():
        for agent, count in agent_counts:
            matrix.setdefault(agent, {})[qualification] = count
            agent_totals[agent] = agent_totals.get(agent, 0) + count
            qual_totals[qualification] = qual_totals.get(qualification, 0) + count

    agents = sorted(agent_totals.keys(), key=lambda name: (-agent_totals[name], name))
    rows: list[list[Any]] = [
        ["Visão geral — CPC por agente e tipo"],
        ["Atualizado em", summary["updated_at"]],
        [],
        ["Agente", *qualifications, "Total CPC"],
    ]

    for agent in agents:
        row_counts = [matrix.get(agent, {}).get(qual, 0) for qual in qualifications]
        rows.append([agent, *row_counts, agent_totals[agent]])

    rows.append(["TOTAL GERAL", *[qual_totals[qual] for qual in qualifications], summary.get("total_cpc", 0)])
    return rows


def _reversion_rate(cpc: int, acordos: int) -> str:
    """Percentual de acordos sobre CPC entregue."""
    if cpc <= 0:
        return "—"
    pct = (acordos / cpc) * 100
    return f"{pct:.1f}%".replace(".", ",")


def update_dashboard(summary: dict[str, Any]) -> str:
    """Escreve resumo e detalhes na planilha."""
    sheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    client = _client()
    spreadsheet = client.open_by_key(sheet_id)

    try:
        resumo = spreadsheet.worksheet("Resumo")
    except gspread.WorksheetNotFound:
        resumo = spreadsheet.add_worksheet("Resumo", rows=50, cols=10)

    try:
        detalhes = spreadsheet.worksheet("Detalhes")
    except gspread.WorksheetNotFound:
        detalhes = spreadsheet.add_worksheet("Detalhes", rows=1000, cols=10)

    try:
        cpc_detalhes = spreadsheet.worksheet("CPC")
    except gspread.WorksheetNotFound:
        cpc_detalhes = spreadsheet.add_worksheet("CPC", rows=1000, cols=10)

    try:
        cpc_por_tipo = spreadsheet.worksheet("CPC por tipo")
    except gspread.WorksheetNotFound:
        cpc_por_tipo = spreadsheet.add_worksheet("CPC por tipo", rows=500, cols=10)

    try:
        cpc_matriz = spreadsheet.worksheet("CPC matriz")
    except gspread.WorksheetNotFound:
        cpc_matriz = spreadsheet.add_worksheet("CPC matriz", rows=200, cols=20)

    agent_stats = summary.get("agent_stats", [])
    total_cpc = summary.get("total_cpc", 0)
    total_acordos = summary["total_production"]

    total_reversao = _reversion_rate(total_cpc, total_acordos)

    resumo.clear()
    resumo.update(
        [
            ["Painel de Produção — Cobrança"],
            ["Atualizado em", summary["updated_at"]],
            ["Data referência", summary["date"]],
            [],
            ["Métrica", "Valor"],
            ["Total de ligações (dia)", summary["total_calls"]],
            ["Chamadas finalizadas", summary["total_finalized"]],
            ["CPC (Contato positivo)", total_cpc],
            ["Acordos formalizados", total_acordos],
            ["Taxa de reversão geral", total_reversao],
            [],
            ["Agente", "CPC", "Acordos", "% Reversão"],
            *[
                [agent, cpc, acordos, _reversion_rate(cpc, acordos)]
                for row in agent_stats
                for agent, cpc, acordos in [
                    (
                        row["agent"],
                        row["cpc"],
                        row["acordos"],
                    )
                    if isinstance(row, dict)
                    else (row[0], row[1], row[2])
                ]
            ],
            [],
            ["TOTAL GERAL", total_cpc, total_acordos, total_reversao],
        ],
        value_input_option="USER_ENTERED",
    )

    detalhes.clear()
    detalhes.update(
        [
            ["Agente", "Nº Contrato", "Finalização", "Data/Hora", "Campanha", "Telefone"],
            *[
                [
                    row["agent_name"],
                    row["contract_number"],
                    row["qualification_name"],
                    row["call_date"],
                    row["campaign_name"],
                    row["number"],
                ]
                for row in summary["production_rows"]
            ],
        ],
        value_input_option="USER_ENTERED",
    )

    cpc_detalhes.clear()
    cpc_detalhes.update(
        [
            ["Agente", "Nº Contrato", "Finalização", "Data/Hora", "Campanha", "Telefone"],
            *[
                [
                    row["agent_name"],
                    row["contract_number"],
                    row["qualification_name"],
                    row["call_date"],
                    row["campaign_name"],
                    row["number"],
                ]
                for row in summary.get("cpc_rows", [])
            ],
        ],
        value_input_option="USER_ENTERED",
    )

    cpc_por_tipo.clear()
    cpc_por_tipo.update(_build_cpc_by_type_rows(summary), value_input_option="USER_ENTERED")

    cpc_matriz.clear()
    matrix_rows = _build_cpc_matrix_rows(summary)
    cpc_matriz.update(matrix_rows, value_input_option="USER_ENTERED")

    # Formatação dashboard
    try:
        style_resumo(spreadsheet, resumo, len(agent_stats))
        style_detail_table(spreadsheet, detalhes, len(summary["production_rows"]))
        style_detail_table(spreadsheet, cpc_detalhes, len(summary.get("cpc_rows", [])))
        style_cpc_por_tipo(cpc_por_tipo, spreadsheet)
        if matrix_rows and len(matrix_rows) > 1:
            num_cols = len(matrix_rows[3]) if len(matrix_rows) > 3 else 2
            num_agents = max(0, len(matrix_rows) - 5)
            style_cpc_matrix(spreadsheet, cpc_matriz, num_cols, num_agents)
    except Exception as exc:
        print(f"  Aviso: formatação visual parcial — {exc}")

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"
