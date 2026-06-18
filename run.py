"""Ponto de entrada: busca ligações e atualiza Google Sheets."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.api_3cplus import aggregate_production, fetch_calls_for_day
from src.csv_loader import load_calls_from_config
from src.snapshot import build_snapshot_payload, save_snapshot
from src.snapshot_remote import SnapshotUploadError as DriveSnapshotError
from src.snapshot_remote import remote_snapshot_configured as drive_snapshot_configured
from src.snapshot_remote import service_account_email, upload_snapshot as upload_snapshot_drive
from src.snapshot_sheets import SnapshotUploadError as SheetsSnapshotError
from src.snapshot_sheets import upload_snapshot as upload_snapshot_sheets
from src.sheets import update_dashboard


def load_calls() -> tuple[list[dict], str]:
    source = os.getenv("DATA_SOURCE", "auto").strip().lower()

    if source == "csv":
        calls, origin = load_calls_from_config()
        return calls, f"CSV: {origin}"

    if source == "api":
        calls = fetch_calls_for_day()
        return calls, "API 3C Plus"

    # auto: usa o que tiver mais ligações do dia (CSV costuma ser completo)
    api_calls = fetch_calls_for_day()
    try:
        csv_calls, csv_path = load_calls_from_config()
    except FileNotFoundError:
        return api_calls, "API 3C Plus (sem CSV)"

    if len(csv_calls) >= len(api_calls):
        return csv_calls, f"CSV: {csv_path}"
    return api_calls, "API 3C Plus"


def main() -> int:
    print("Carregando ligações do dia...")
    calls, origin = load_calls()
    print(f"  Fonte: {origin}")
    print(f"  {len(calls)} ligações do dia")

    summary = aggregate_production(calls)
    print(f"  CPC: {summary['total_cpc']}")
    print(f"  Produção (Acordo formalizado): {summary['total_production']}")
    print(f"  Improdutivas: {summary.get('total_improdutiva', 0)}")

    snapshot_path = save_snapshot(summary)
    print(f"  Snapshot: {snapshot_path}")

    try:
        sheet_ref = upload_snapshot_sheets(build_snapshot_payload(summary))
    except SheetsSnapshotError as exc:
        print(f"  Aviso: snapshot na planilha (_Snapshot) não enviado.")
        print(f"  {exc}")
        sheet_ref = None
    else:
        if sheet_ref:
            print(f"  Snapshot remoto (planilha aba _Snapshot): ok")

    if drive_snapshot_configured():
        try:
            drive_file_id = upload_snapshot_drive(summary)
        except DriveSnapshotError as exc:
            print(f"  Aviso: snapshot no Drive não enviado.")
            print(f"  {exc}")
            print(
                f"  Conta de serviço: {service_account_email() or '(não identificada)'}"
            )
            print("  Dica: contas de serviço não gravam no Drive pessoal; use a aba _Snapshot.")
            drive_file_id = None
        else:
            if drive_file_id:
                print(f"  Snapshot na nuvem (Drive): {drive_file_id}")

    url = update_dashboard(summary)
    print(f"Planilha atualizada: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
