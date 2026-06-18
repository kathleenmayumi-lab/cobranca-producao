"""Lê export CSV do 3C Plus (relatório de finalização)."""

from __future__ import annotations

import csv
import os
from datetime import date
from pathlib import Path
from typing import Any

HEADER_MARKERS = ("qualification_name", "agent_name", "call_date")


def _is_dialer_export(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader, [])
    except OSError:
        return False
    joined = ";".join(header).lower()
    return all(marker in joined for marker in HEADER_MARKERS)


def find_latest_csv(folder: Path) -> Path | None:
    if not folder.exists():
        return None

    candidates = [
        p
        for p in folder.glob("*.csv")
        if p.is_file() and _is_dialer_export(p)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


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


def load_calls_from_config() -> tuple[list[dict[str, Any]], str]:
    folder = Path(os.getenv("CSV_IMPORT_FOLDER", r"C:\Users\usuario\Downloads"))
    explicit = os.getenv("CSV_FILE", "").strip()

    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"CSV_FILE não encontrado: {path}")
        return load_calls_from_csv(path), str(path)

    latest = find_latest_csv(folder)
    if not latest:
        raise FileNotFoundError(
            f"Nenhum CSV do 3C Plus encontrado em {folder}. "
            "Exporte o relatório de finalização ou defina CSV_FILE no .env."
        )
    return load_calls_from_csv(latest), str(latest)
