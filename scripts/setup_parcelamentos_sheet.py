"""Cria a planilha Google de parcelamentos e grava o ID em config/parcelamentos.json."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.parcelamentos import ensure_workbook, load_config, spreadsheet_configured


def main() -> int:
    """
    Preferência (quota da service account costuma ser 0):
    1) Crie uma planilha vazia no SEU Google Drive
    2) Compartilhe como Editor com o e-mail da service account (credentials/service_account.json → client_email)
    3) Cole o ID da URL em config/parcelamentos.json → spreadsheet_id
    4) Rode este script de novo (só cria abas Acordos/Parcelas + cabeçalhos)
    """
    if spreadsheet_configured():
        cfg = load_config()
        sid = cfg.get("spreadsheet_id", "")
        print(f"Configurado: {sid}")
        result = ensure_workbook(create_if_missing=False)
        print(f"Abas Acordos/Parcelas ok: {result['url']}")
        return 0

    print("Nenhum spreadsheet_id em config/parcelamentos.json.")
    print()
    print("A conta de serviço geralmente NÃO consegue criar planilha (quota Drive 403).")
    print("Faça assim (1 min):")
    print("  1. Abra https://sheets.new e renomeie para «Controle Parcelamentos»")
    print("  2. Compartilhar → cole o client_email da service account → Editor")
    print("  3. Copie o ID da URL (entre /d/ e /edit)")
    print("  4. Cole em config/parcelamentos.json no campo spreadsheet_id")
    print("  5. Rode de novo: py -3 scripts/setup_parcelamentos_sheet.py")
    print()
    print("Enquanto isso o painel já grava em data/parcelamentos_local.json (modo local).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
