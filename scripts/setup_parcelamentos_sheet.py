"""Cria a planilha Google de parcelamentos e grava o ID em config/parcelamentos.json."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.parcelamentos import ensure_workbook, load_config, spreadsheet_configured


def main() -> int:
    if spreadsheet_configured():
        cfg = load_config()
        sid = cfg.get("spreadsheet_id", "")
        print(f"Já configurado: {sid}")
        print(f"URL: https://docs.google.com/spreadsheets/d/{sid}")
        print("Para recriar, limpe spreadsheet_id em config/parcelamentos.json e rode de novo.")
        # Ainda garante abas/cabeçalhos
        result = ensure_workbook(create_if_missing=False)
        print(f"Abas ok: {result['url']}")
        return 0

    print("Criando planilha de parcelamentos na conta de serviço…")
    result = ensure_workbook(create_if_missing=True)
    print("OK")
    print(f"ID: {result['spreadsheet_id']}")
    print(f"URL: {result['url']}")
    print()
    print("Importante: compartilhe a planilha com quem for operar (editores),")
    print("ou mova para um Drive compartilhado da operação.")
    print("A service account já é dona do arquivo criado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
