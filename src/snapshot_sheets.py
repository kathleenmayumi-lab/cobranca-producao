"""Publica e lê snapshot JSON na planilha Google Sheets (aba _Snapshot)."""

from __future__ import annotations

import base64
import gzip
import json
import os
from typing import Any

import gspread

from src.google_credentials import get_google_credentials

WORKSHEET = "_Snapshot"
CHUNK_SIZE = 45000
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SnapshotUploadError(RuntimeError):
    """Falha ao enviar snapshot para a planilha."""


def _setting(key: str) -> str:
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return os.getenv(key, "").strip()


def remote_snapshot_configured() -> bool:
    return bool(_setting("GOOGLE_SHEETS_ID"))


def _sheet_id() -> str:
    return _setting("GOOGLE_SHEETS_ID")


def _client() -> gspread.Client:
    credentials = get_google_credentials(scopes=SCOPES)
    return gspread.authorize(credentials)


def _pack(summary: dict[str, Any]) -> str:
    raw = json.dumps(summary, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii")


def _unpack(payload: str) -> dict[str, Any]:
    raw = gzip.decompress(base64.b64decode(payload.encode("ascii")))
    return json.loads(raw.decode("utf-8"))


def _worksheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(WORKSHEET)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(WORKSHEET, rows=50, cols=3)


def upload_snapshot(summary: dict[str, Any]) -> str | None:
    """Grava snapshot compactado na aba _Snapshot. Retorna o sheet_id."""
    sheet_id = _sheet_id()
    if not sheet_id:
        return None

    spreadsheet = _client().open_by_key(sheet_id)
    ws = _worksheet(spreadsheet)

    payload = _pack(summary)
    chunks = [payload[i : i + CHUNK_SIZE] for i in range(0, len(payload), CHUNK_SIZE)] or [""]
    rows: list[list[Any]] = [["partes", len(chunks), summary.get("updated_at", "")]]
    for index, chunk in enumerate(chunks, start=1):
        rows.append([index, chunk])

    ws.clear()
    ws.update(rows, value_input_option="RAW")
    return sheet_id


def download_snapshot() -> dict[str, Any] | None:
    """Lê snapshot da aba _Snapshot."""
    sheet_id = _sheet_id()
    if not sheet_id:
        return None

    spreadsheet = _client().open_by_key(sheet_id)
    try:
        ws = spreadsheet.worksheet(WORKSHEET)
    except gspread.WorksheetNotFound:
        return None

    values = ws.get_all_values()
    if len(values) < 2:
        return None

    try:
        parts_count = int(values[0][1])
    except (IndexError, TypeError, ValueError):
        return None

    payload = "".join(row[1] for row in values[1 : 1 + parts_count] if len(row) > 1)
    if not payload:
        return None

    try:
        return _unpack(payload)
    except Exception as exc:
        raise SnapshotUploadError(f"Snapshot da planilha inválido: {exc}") from exc
