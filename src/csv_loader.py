"""Lê export CSV do 3C Plus (relatório de finalização)."""

from __future__ import annotations

import csv
import os
from datetime import date
from pathlib import Path
from typing import Any

HEADER_MARKERS = ("qualification_name", "agent_name", "call_date")

DEFAULT_BATCH_WINDOW_MINUTES = 30


def _is_dialer_export(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader, [])
    except OSError:
        return False
    joined = ";".join(header).lower()
    return all(marker in joined for marker in HEADER_MARKERS)


def _dialer_csv_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        [p for p in folder.glob("*.csv") if p.is_file() and _is_dialer_export(p)],
        key=lambda p: p.stat().st_mtime,
    )


def find_latest_csv(folder: Path) -> Path | None:
    candidates = _dialer_csv_files(folder)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_csv_batch(folder: Path, window_minutes: int | None = None) -> list[Path]:
    """
    Retorna CSVs do 3C Plus exportados juntos (mesmo lote na pasta Downloads).
    Usa janela de tempo a partir do arquivo mais recente.
    """
    candidates = _dialer_csv_files(folder)
    if not candidates:
        return []

    window = window_minutes
    if window is None:
        window = int(os.getenv("CSV_BATCH_WINDOW_MINUTES", DEFAULT_BATCH_WINDOW_MINUTES))

    newest_mtime = max(p.stat().st_mtime for p in candidates)
    cutoff = newest_mtime - (window * 60)
    batch = [p for p in candidates if p.stat().st_mtime >= cutoff]
    return sorted(batch, key=lambda p: p.stat().st_mtime)


def _row_key(row: dict[str, Any]) -> tuple:
    for key in ("id", "call_id", "uuid"):
        value = row.get(key)
        if value not in (None, ""):
            return ("id", str(value).strip())
    return (
        "row",
        str(row.get("call_date", "")).strip(),
        str(row.get("agent_name", "")).strip(),
        str(row.get("number", "")).strip(),
        str(row.get("qualification_name", "")).strip(),
        str(row.get("identifier", "") or row.get("contract_number", "")).strip(),
    )


def load_calls_from_csv(
    csv_path: Path,
    target_day: date | None = None,
) -> list[dict[str, Any]]:
    target_day = target_day or date.today()
    day_prefix = target_day.strftime("%d/%m/%Y")

    rows: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            call_date = (row.get("call_date") or "").strip()
            if call_date.startswith(day_prefix):
                rows.append(dict(row))
    return rows


def load_calls_from_csv_files(
    csv_paths: list[Path],
    target_day: date | None = None,
) -> list[dict[str, Any]]:
    """Carrega vários CSVs e remove duplicatas."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for path in csv_paths:
        for row in load_calls_from_csv(path, target_day):
            key = _row_key(row)
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return merged


def _csv_load_mode() -> str:
    return os.getenv("CSV_LOAD_MODE", "batch").strip().lower()


def load_calls_from_config() -> tuple[list[dict[str, Any]], str]:
    folder = Path(os.getenv("CSV_IMPORT_FOLDER", r"C:\Users\usuario\Downloads"))
    explicit = os.getenv("CSV_FILE", "").strip()

    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"CSV_FILE não encontrado: {path}")
        return load_calls_from_csv(path), str(path)

    mode = _csv_load_mode()
    if mode == "latest":
        latest = find_latest_csv(folder)
        if not latest:
            raise FileNotFoundError(
                f"Nenhum CSV do 3C Plus encontrado em {folder}. "
                "Exporte o relatório de finalização ou defina CSV_FILE no .env."
            )
        return load_calls_from_csv(latest), str(latest)

    batch = find_csv_batch(folder)
    if not batch:
        raise FileNotFoundError(
            f"Nenhum CSV do 3C Plus encontrado em {folder}. "
            "Exporte o relatório de finalização ou defina CSV_FILE no .env."
        )

    rows = load_calls_from_csv_files(batch)
    if len(batch) == 1:
        origin = str(batch[0])
    else:
        names = ", ".join(p.name for p in batch)
        origin = f"{len(batch)} arquivos ({names})"
    return rows, origin
