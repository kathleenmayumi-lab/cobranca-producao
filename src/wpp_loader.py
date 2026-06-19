"""Lê produção WhatsApp das planilhas individuais dos agentes."""

from __future__ import annotations

import json
import os
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import gspread

from src.google_credentials import get_google_credentials

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "wpp_sheets.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CONTRACT_HEADER_HINTS = (
    "contrato",
    "ccb",
    "identifier",
    "nº contrato",
    "numero contrato",
    "n° contrato",
)


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.strip().lower().split())


def load_wpp_config() -> dict[str, Any]:
    path = Path(os.getenv("WPP_SHEETS_CONFIG", str(CONFIG_PATH)))
    if not path.exists():
        return {"worksheet": "", "agents": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _client() -> gspread.Client:
    return gspread.authorize(get_google_credentials(scopes=SCOPES))


def _parse_row_date(value: Any, target_day: date) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    day_prefix = target_day.strftime("%d/%m/%Y")
    if text.startswith(day_prefix):
        return True
    if text.startswith(target_day.isoformat()):
        return True
    for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text[:19], fmt)
            return parsed.date() == target_day
        except ValueError:
            continue
    return False


def _is_whatsapp_channel(value: Any) -> bool:
    canal = _normalize_text(str(value or ""))
    if not canal:
        return False
    return "whatsapp" in canal or canal in {"wpp", "zap", "whats"}


def _find_header(values: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for row_idx, row in enumerate(values[:25]):
        columns: dict[str, int] = {}
        for col_idx, cell in enumerate(row):
            header = _normalize_text(cell)
            if not header:
                continue
            if header == "data" or header.startswith("data "):
                columns["data"] = col_idx
            if header == "canal":
                columns["canal"] = col_idx
            if any(hint in header for hint in CONTRACT_HEADER_HINTS):
                columns.setdefault("contract", col_idx)
        if "data" in columns and "canal" in columns:
            return row_idx, columns
    return None


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index]).strip()


def _rows_from_worksheet(
    values: list[list[str]],
    *,
    agent_name: str,
    target_day: date,
) -> list[dict[str, Any]]:
    located = _find_header(values)
    if not located:
        return []

    header_idx, columns = located
    rows: list[dict[str, Any]] = []
    for raw in values[header_idx + 1 :]:
        if not any(str(cell).strip() for cell in raw):
            continue
        data_val = _cell(raw, columns.get("data"))
        canal_val = _cell(raw, columns.get("canal"))
        if not _parse_row_date(data_val, target_day):
            continue
        if not _is_whatsapp_channel(canal_val):
            continue
        contract = _cell(raw, columns.get("contract"))
        rows.append(
            {
                "agent_name": agent_name,
                "contract_number": contract,
                "qualification_name": "Acordo formalizado",
                "call_date": data_val,
                "campaign_name": "",
                "number": "",
                "channel": "whatsapp",
                "source": "wpp",
                "is_production": True,
                "is_cpc": False,
            }
        )
    return rows


def _load_agent_sheet(
    client: gspread.Client,
    *,
    agent_name: str,
    spreadsheet_id: str,
    worksheet_name: str,
    target_day: date,
) -> list[dict[str, Any]]:
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheets = []
    if worksheet_name:
        worksheets = [spreadsheet.worksheet(worksheet_name)]
    else:
        worksheets = spreadsheet.worksheets()

    collected: list[dict[str, Any]] = []
    for ws in worksheets:
        values = ws.get_all_values()
        if not values:
            continue
        collected.extend(_rows_from_worksheet(values, agent_name=agent_name, target_day=target_day))
        if collected and worksheet_name:
            break
    return collected


def load_wpp_production_for_day(target_day: date | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Retorna linhas de produção WPP do dia e avisos de configuração."""
    target_day = target_day or date.today()
    config = load_wpp_config()
    agents = config.get("agents", [])
    worksheet_name = str(config.get("worksheet", "") or "").strip()
    warnings: list[str] = []
    if not agents:
        return [], ["Nenhum agente configurado em config/wpp_sheets.json"]

    configured = [item for item in agents if str(item.get("spreadsheet_id", "")).strip()]
    if not configured:
        return [], ["Nenhuma planilha WPP configurada (spreadsheet_id vazio em config/wpp_sheets.json)"]

    try:
        client = _client()
    except Exception as exc:
        return [], [f"Credenciais Google indisponíveis para WPP: {exc}"]

    all_rows: list[dict[str, Any]] = []
    for item in configured:
        agent_name = str(item.get("agent", "")).strip()
        spreadsheet_id = str(item.get("spreadsheet_id", "")).strip()
        if not agent_name or not spreadsheet_id:
            continue
        try:
            rows = _load_agent_sheet(
                client,
                agent_name=agent_name,
                spreadsheet_id=spreadsheet_id,
                worksheet_name=worksheet_name,
                target_day=target_day,
            )
            all_rows.extend(rows)
        except Exception as exc:
            warnings.append(f"{agent_name}: {exc}")

    return all_rows, warnings


def wpp_configured() -> bool:
    config = load_wpp_config()
    return any(str(item.get("spreadsheet_id", "")).strip() for item in config.get("agents", []))
