"""Diagnóstico: compara CSV manual vs API e mostra por que produção pode dar zero."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

load_dotenv()

from src.api_3cplus import PRODUCTION_QUALIFICATION, aggregate_production, normalize_call

API_BASE = os.getenv("THREECPLUS_API_BASE", "https://app.3c.plus/api/v1")
API_TOKEN = os.getenv("THREECPLUS_API_TOKEN", "")


def csv_production(csv_path: Path, target_day: date | None = None) -> dict:
    target_day = target_day or date.today()
    day_prefix = target_day.strftime("%d/%m/%Y")

    rows = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            call_date = (row.get("call_date") or "").strip()
            if call_date.startswith(day_prefix):
                rows.append(row)

    normalized = [normalize_call(r) for r in rows]
    finalized = [c for c in normalized if c["readable_status_text"] == "Finalizada"]
    production = [c for c in finalized if c["qualification_name"] == PRODUCTION_QUALIFICATION]

    # também conta por qualification_conversion no CSV bruto
    conv = [
        r
        for r in rows
        if (r.get("qualification_name") or "").strip() == PRODUCTION_QUALIFICATION
    ]

    return {
        "source": str(csv_path),
        "rows_today": len(rows),
        "finalized": len(finalized),
        "production_strict": len(production),
        "production_by_name_only": len(conv),
        "qualifications": Counter(
            (r.get("qualification_name") or "").strip()
            for r in rows
            if (r.get("qualification_name") or "").strip()
        ).most_common(10),
        "statuses": Counter(
            (r.get("readable_status_text") or "").strip() for r in rows
        ).most_common(10),
    }


def try_api(params: dict) -> dict:
    r = requests.get(
        f"{API_BASE}/calls",
        params={"api_token": API_TOKEN, **params},
        timeout=120,
    )
    out = {"params": params, "status": r.status_code}
    try:
        payload = r.json()
    except Exception as exc:
        out["error"] = str(exc)
        out["text"] = r.text[:500]
        return out

    if isinstance(payload, dict):
        batch = payload.get("data") or payload.get("calls") or []
        meta = payload.get("meta") or payload.get("pagination") or {}
    else:
        batch = payload if isinstance(payload, list) else []
        meta = {}

    out["count"] = len(batch)
    out["meta"] = meta
    if batch:
        sample = batch[0]
        out["sample_keys"] = sorted(sample.keys())[:40]
        out["sample"] = sample
        normalized = [normalize_call(c) for c in batch]
        out["production_current_logic"] = sum(1 for c in normalized if c["is_production"] and c["readable_status_text"] == "Finalizada")
        out["production_name_only"] = sum(1 for c in normalized if c["qualification_name"] == PRODUCTION_QUALIFICATION)
        out["statuses"] = Counter(c["readable_status_text"] for c in normalized).most_common()
        out["qualifications"] = Counter(c["qualification_name"] for c in normalized if c["qualification_name"]).most_common()
    return out


def main() -> None:
    today = date.today()
    print("=== DIAGNÓSTICO PRODUÇÃO ===")
    print(f"Data: {today.isoformat()}\n")

    csv_path = Path(os.getenv("DEBUG_CSV_PATH", r"C:\Users\usuario\Downloads\c90F1HGeHbK6p4PpGBAQ8BLEq2VND0y6_AZDa68dEbU.csv"))
    if csv_path.exists():
        csv_stats = csv_production(csv_path, today)
        print("CSV manual (referência):")
        print(json.dumps(csv_stats, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"CSV não encontrado: {csv_path}")

    print("\n--- Tentativas API ---")
    start_iso = datetime.combine(today, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end_iso = datetime.combine(today, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")
    start_br = today.strftime("%d/%m/%Y 00:00:00")
    end_br = today.strftime("%d/%m/%Y 23:59:59")

    attempts = [
        {"start_date": start_iso, "end_date": end_iso, "limit": 100, "page": 1},
        {"start": start_iso, "end": end_iso, "limit": 100, "page": 1},
        {"date_start": start_iso, "date_end": end_iso, "limit": 100, "page": 1},
        {"start_date": start_br, "end_date": end_br, "limit": 100, "page": 1},
        {"limit": 100, "page": 1},
    ]

    for params in attempts:
        result = try_api(params)
        print(json.dumps({k: v for k, v in result.items() if k != "sample"}, ensure_ascii=False, indent=2, default=str))
        if result.get("sample"):
            print("  sample qualification_name:", result["sample"].get("qualification_name"))
            print("  sample readable_status_text:", result["sample"].get("readable_status_text"))
            print("  sample status:", result["sample"].get("status"))
        print()

    current = aggregate_production([])
    print("Lógica atual no código exige:")
    print("  - readable_status_text == 'Finalizada'")
    print(f"  - qualification_name == '{PRODUCTION_QUALIFICATION}'")


if __name__ == "__main__":
    main()
