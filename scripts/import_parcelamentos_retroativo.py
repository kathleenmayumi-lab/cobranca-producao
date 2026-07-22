"""Importa acordos retroativos da planilha Controle Geral para Acordos/Parcelas.

Todos os status de parcela ficam 'pendente' — baixas manuais depois.
Uso:
  py -3 scripts/import_parcelamentos_retroativo.py
  py -3 scripts/import_parcelamentos_retroativo.py --dry-run
"""

from __future__ import annotations

import argparse
import calendar
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gspread

from src.google_credentials import get_google_credentials
from src.parcelamentos import (
    ACORDOS_HEADERS,
    PARCELAS_HEADERS,
    STATUS_PENDENTE,
    TIPO_ENTRADA,
    TIPO_PARCELA,
    _append_acordo_sheets,
    _fmt_date,
    _fmt_money,
    _money,
    _parse_money,
    ensure_workbook,
    formatar_cpf,
    load_acordos,
    load_config,
    normalizar_cpf,
    spreadsheet_configured,
)
from src.wpp_loader import _api_retry, _clean_cell

SOURCE_SPREADSHEET_ID = "14jUMoci3im_AzbbB3aGMT9mpl2Y5SxTtWe72LGNk4Vk"
SOURCE_WORKSHEET = "Parcelamentos"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _add_months(d: date, months: int) -> date:
    m0 = d.month - 1 + months
    year = d.year + m0 // 12
    month = m0 % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _parse_dd_mm(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    raw = _clean_cell(text)
    if not raw:
        return None
    # dd/mm/yyyy or dd/mm
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})/(\d{1,2})$", raw)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12 or day < 1 or day > 31:
        return None
    for year in (today.year, today.year - 1):
        last = calendar.monthrange(year, month)[1]
        if day > last:
            continue
        cand = date(year, month, day)
        # Prefere data não muito no futuro
        if cand <= today + timedelta(days=150):
            return cand
    try:
        return date(today.year, month, min(day, calendar.monthrange(today.year, month)[1]))
    except ValueError:
        return None


def _first_parcela_due(data_entrada: date, dia_venc: int) -> date:
    """1ª parcela: sempre +1 mês após a entrada, no dia fixo da planilha."""
    from src.parcelamentos import add_months

    return add_months(data_entrada, 1, day=max(1, min(int(dia_venc), 31)))


def _parcelas_vencimentos(data_entrada: date, dia_venc: int, n: int) -> list[date]:
    from src.parcelamentos import vencimentos_mensais

    return vencimentos_mensais(
        ancora=data_entrada,
        dia_vencimento=dia_venc,
        n_parcelas=n,
        primeiro_apos_meses=1,
    )


def _cpf_import(value: str) -> str:
    digits = normalizar_cpf(value)
    if len(digits) == 11:
        return formatar_cpf(digits)
    if 0 < len(digits) < 11:
        return formatar_cpf(digits.zfill(11))
    return _clean_cell(value) or "000.000.000-00"


def _row_map(headers: list[str], raw: list[str]) -> dict[str, str]:
    return {headers[i]: _clean_cell(raw[i] if i < len(raw) else "") for i in range(len(headers))}


def _get(row: dict[str, str], *names: str) -> str:
    lower = {k.strip().casefold(): v for k, v in row.items()}
    for name in names:
        key = name.strip().casefold()
        if key in lower and lower[key]:
            return lower[key]
        # prefix match (headers com espaços)
        for k, v in lower.items():
            if k.startswith(key) and v:
                return v
    return ""


def load_source_rows() -> list[dict[str, str]]:
    client = gspread.authorize(get_google_credentials(scopes=SCOPES))
    ss = _api_retry(lambda: client.open_by_key(SOURCE_SPREADSHEET_ID))
    ws = _api_retry(lambda: ss.worksheet(SOURCE_WORKSHEET))
    values = _api_retry(ws.get_all_values)
    if not values:
        return []
    headers = [_clean_cell(h) for h in values[0]]
    rows: list[dict[str, str]] = []
    for raw in values[1:]:
        if not any(_clean_cell(c) for c in raw):
            continue
        rows.append(_row_map(headers, raw))
    return rows


def build_acordo_from_row(row: dict[str, str], *, today: date | None = None) -> dict | None:
    today = today or date.today()
    ccb = _get(row, "CCB")
    if not ccb:
        return None

    formalizacao = _parse_dd_mm(_get(row, "Data formalização", "Data formalizacao"), today) or today
    data_entrada = _parse_dd_mm(_get(row, "Data entrada"), today) or formalizacao
    try:
        n_parcelas = int(re.sub(r"\D", "", _get(row, "Parcelas")) or "0")
    except ValueError:
        n_parcelas = 0
    if n_parcelas < 1:
        return None

    valor_entrada = _parse_money(_get(row, "Valor entrada"))
    valor_parcela = _parse_money(_get(row, "Valor parcelas", "Valor parcela"))
    valor_total_sheet = _parse_money(_get(row, "Valor total acordo"))
    if valor_entrada <= 0 or valor_parcela <= 0:
        return None

    valor_total = valor_total_sheet if valor_total_sheet > 0 else _money(valor_entrada + valor_parcela * n_parcelas)

    dia_venc_raw = re.sub(r"\D", "", _get(row, "Vencimentos")) or str(data_entrada.day)
    dia_venc = int(dia_venc_raw)
    # Formalização = data do acordo; parcelas = dia fixo da planilha, +1 mês após a entrada, depois mensal
    venc_final = _parcelas_vencimentos(data_entrada, dia_venc, n_parcelas)

    produto = _get(row, "Produto") or "IR"
    if produto.upper() == "EP":
        produto = "EP"
    elif produto.upper() in {"IR", "IRPF"}:
        produto = "IR"

    agente = _get(row, "Agente") or "Importado"
    cpf = _cpf_import(_get(row, "CPF"))
    obs_parts = [
        p
        for p in (
            _get(row, "OBS"),
            f"Status origem: {_get(row, 'Status')}" if _get(row, "Status") else "",
            f"Negativação: {_get(row, 'Negativação', 'Negativacao')}" if _get(row, "Negativação", "Negativacao") else "",
        )
        if p
    ]
    observacao = " | ".join(obs_parts)

    acordo_id = f"RETRO-{ccb}-{formalizacao.strftime('%Y%m%d')}"
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pct = _money(valor_entrada * Decimal("100") / valor_total) if valor_total else Decimal("0")

    acordo = {
        "acordo_id": acordo_id,
        "created_at": now,
        "formalizacao": _fmt_date(formalizacao),
        "agente": agente,
        "cpf": cpf,
        "ccb": ccb,
        "produto": produto,
        "cliente": "",
        "telefone": "",
        "valor_total": _fmt_money(valor_total),
        "pct_entrada": str(pct).replace(".", ","),
        "valor_entrada": _fmt_money(valor_entrada),
        "data_entrada": _fmt_date(data_entrada),
        "n_parcelas": str(n_parcelas),
        "valor_parcela": _fmt_money(valor_parcela),
        "status_acordo": "ativo",
        "observacao": observacao[:500],
    }

    parcelas = [
        {
            "parcela_id": f"{acordo_id}-E",
            "acordo_id": acordo_id,
            "agente": agente,
            "cpf": cpf,
            "ccb": ccb,
            "produto": produto,
            "cliente": "",
            "telefone": "",
            "tipo": TIPO_ENTRADA,
            "numero": "0",
            "vencimento": _fmt_date(data_entrada),
            "valor": _fmt_money(valor_entrada),
            "status": STATUS_PENDENTE,
            "pago_em": "",
            "formalizacao": _fmt_date(formalizacao),
            "observacao": "import retroativo",
            "created_at": now,
        }
    ]
    for i, venc in enumerate(venc_final, start=1):
        parcelas.append(
            {
                "parcela_id": f"{acordo_id}-P{i}",
                "acordo_id": acordo_id,
                "agente": agente,
                "cpf": cpf,
                "ccb": ccb,
                "produto": produto,
                "cliente": "",
                "telefone": "",
                "tipo": TIPO_PARCELA,
                "numero": str(i),
                "vencimento": _fmt_date(venc),
                "valor": _fmt_money(valor_parcela),
                "status": STATUS_PENDENTE,
                "pago_em": "",
                "formalizacao": _fmt_date(formalizacao),
                "observacao": "import retroativo",
                "created_at": now,
            }
        )

    return {"acordo": acordo, "parcelas": parcelas}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not spreadsheet_configured():
        print("Planilha destino nao configurada em config/parcelamentos.json")
        return 1

    ensure_workbook(create_if_missing=False)
    existing = {str(a.get("acordo_id", "")).strip() for a in load_acordos()}
    source = load_source_rows()
    print(f"Origem: {len(source)} linha(s)")

    to_write: list[dict] = []
    skipped = 0
    errors: list[str] = []
    for idx, row in enumerate(source, start=2):
        try:
            built = build_acordo_from_row(row)
        except Exception as exc:
            errors.append(f"L{idx}: {exc}")
            continue
        if not built:
            skipped += 1
            continue
        aid = built["acordo"]["acordo_id"]
        if aid in existing:
            skipped += 1
            continue
        to_write.append(built)
        existing.add(aid)

    print(f"Novos: {len(to_write)} | ignorados/vazios/duplicados: {skipped} | erros: {len(errors)}")
    for e in errors[:10]:
        print(" ", e)

    if args.dry_run:
        if to_write:
            a = to_write[0]["acordo"]
            print("Preview:", a["acordo_id"], a["ccb"], a["agente"], a["valor_total"], "parcelas", a["n_parcelas"])
            print("  entrada", to_write[0]["parcelas"][0]["vencimento"], "P1", to_write[0]["parcelas"][1]["vencimento"])
        return 0

    from src.parcelamentos import _client, _ensure_worksheet, _api_retry as retry

    config = load_config()
    spreadsheet = retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws_a = _ensure_worksheet(spreadsheet, str(config.get("acordos_worksheet") or "Acordos"), ACORDOS_HEADERS)
    ws_p = _ensure_worksheet(spreadsheet, str(config.get("parcelas_worksheet") or "Parcelas"), PARCELAS_HEADERS)

    acordo_rows = [[str(item["acordo"].get(h, "")) for h in ACORDOS_HEADERS] for item in to_write]
    parcela_rows: list[list[str]] = []
    for item in to_write:
        for p in item["parcelas"]:
            parcela_rows.append([str(p.get(h, "")) for h in PARCELAS_HEADERS])

    # lotes para evitar payload grande
    def _chunks(items: list, size: int = 50):
        for i in range(0, len(items), size):
            yield items[i : i + size]

    for batch in _chunks(acordo_rows, 40):
        retry(lambda b=batch: ws_a.append_rows(b, value_input_option="USER_ENTERED"))
    for batch in _chunks(parcela_rows, 80):
        retry(lambda b=batch: ws_p.append_rows(b, value_input_option="USER_ENTERED"))

    sid = config.get("spreadsheet_id", "")
    print(f"OK: {len(to_write)} acordo(s) / {len(parcela_rows)} parcela(s) importados (tudo pendente).")
    print(f"https://docs.google.com/spreadsheets/d/{sid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
