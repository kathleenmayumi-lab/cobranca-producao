"""Recalcula vencimentos das parcelas RETRO: dia fixo da planilha origem, +1 mês após entrada."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gspread

from scripts.import_parcelamentos_retroativo import (
    SOURCE_SPREADSHEET_ID,
    SOURCE_WORKSHEET,
    _get,
    _parcelas_vencimentos,
    _parse_dd_mm,
    _row_map,
    load_source_rows,
)
from src.parcelamentos import (
    ACORDOS_HEADERS,
    PARCELAS_HEADERS,
    _clean_cell,
    _client,
    _ensure_worksheet,
    _fmt_date,
    _parse_date,
    load_config,
)
from src.wpp_loader import _api_retry
from src.parcelamentos import add_months  # noqa: F401


def main() -> int:
    config = load_config()
    source = load_source_rows()
    # ccb -> (data_entrada, dia_venc, n)
    by_ccb: dict[str, tuple] = {}
    for row in source:
        ccb = _get(row, "CCB")
        if not ccb:
            continue
        formalizacao = _parse_dd_mm(_get(row, "Data formalização", "Data formalizacao"))
        data_entrada = _parse_dd_mm(_get(row, "Data entrada")) or formalizacao
        if not data_entrada:
            continue
        try:
            n = int(re.sub(r"\D", "", _get(row, "Parcelas")) or "0")
        except ValueError:
            n = 0
        if n < 1:
            continue
        dia = int(re.sub(r"\D", "", _get(row, "Vencimentos")) or str(data_entrada.day))
        by_ccb[ccb] = (data_entrada, dia, n, formalizacao)

    ss = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws_p = _ensure_worksheet(ss, str(config.get("parcelas_worksheet") or "Parcelas"), PARCELAS_HEADERS)
    ws_a = _ensure_worksheet(ss, str(config.get("acordos_worksheet") or "Acordos"), ACORDOS_HEADERS)
    vals_p = _api_retry(ws_p.get_all_values)
    vals_a = _api_retry(ws_a.get_all_values)
    hp = [h.strip() for h in vals_p[0]]
    ha = [h.strip() for h in vals_a[0]]
    ip_aid = hp.index("acordo_id")
    ip_ccb = hp.index("ccb")
    ip_tipo = hp.index("tipo")
    ip_num = hp.index("numero")
    ip_venc = hp.index("vencimento")
    ip_form = hp.index("formalizacao")
    ia_id = ha.index("acordo_id")
    ia_form = ha.index("formalizacao")
    ia_entrada = ha.index("data_entrada")

    # mapa acordo_id -> ccb
    aid_ccb = {}
    for raw in vals_a[1:]:
        aid = _clean_cell(raw[ia_id] if ia_id < len(raw) else "")
        # ccb from parcelas later
        if aid:
            aid_ccb[aid] = aid  # placeholder

    updates = []
    fixed = 0
    # group parcel rows by acordo
    by_aid: dict[str, list[tuple[int, list[str]]]] = {}
    for row_num, raw in enumerate(vals_p[1:], start=2):
        aid = _clean_cell(raw[ip_aid] if ip_aid < len(raw) else "")
        if not aid.startswith("RETRO-"):
            continue
        by_aid.setdefault(aid, []).append((row_num, raw))

    for aid, items in by_aid.items():
        ccb = _clean_cell(items[0][1][ip_ccb] if ip_ccb < len(items[0][1]) else "")
        meta = by_ccb.get(ccb)
        if not meta:
            # fallback: usa formalizacao da linha + dia do vencimento atual da P1 ou 22
            form = None
            for _rn, raw in items:
                form = _parse_dd_mm(_clean_cell(raw[ip_form] if ip_form < len(raw) else ""))
                if form:
                    break
            if not form:
                continue
            dia = 22
            for _rn, raw in items:
                tipo = _clean_cell(raw[ip_tipo] if ip_tipo < len(raw) else "").lower()
                num = _clean_cell(raw[ip_num] if ip_num < len(raw) else "")
                if tipo == "parcela" or num not in {"", "0"}:
                    v = _parse_date(raw[ip_venc] if ip_venc < len(raw) else "")
                    if v:
                        dia = v.day
                        break
            n = sum(
                1
                for _rn, raw in items
                if _clean_cell(raw[ip_tipo] if ip_tipo < len(raw) else "").lower() == "parcela"
                or _clean_cell(raw[ip_num] if ip_num < len(raw) else "") not in {"", "0"}
            )
            data_entrada = form
            vencs = _parcelas_vencimentos(data_entrada, dia, n)
        else:
            data_entrada, dia, n, formalizacao = meta
            vencs = _parcelas_vencimentos(data_entrada, dia, n)

        # atualiza formalizacao nas parcelas (mantém) e vencimento só das parcelas (não entrada)
        pi = 0
        for row_num, raw in items:
            tipo = _clean_cell(raw[ip_tipo] if ip_tipo < len(raw) else "").lower()
            num = _clean_cell(raw[ip_num] if ip_num < len(raw) else "")
            if tipo == "entrada" or num == "0":
                # entrada: vencimento = data_entrada; formalizacao permanece
                if meta:
                    updates.append(
                        {
                            "range": gspread.utils.rowcol_to_a1(row_num, ip_venc + 1),
                            "values": [[_fmt_date(data_entrada)]],
                        }
                    )
                    updates.append(
                        {
                            "range": gspread.utils.rowcol_to_a1(row_num, ip_form + 1),
                            "values": [[_fmt_date(meta[3] or data_entrada)]],
                        }
                    )
                continue
            if pi >= len(vencs):
                continue
            updates.append(
                {
                    "range": gspread.utils.rowcol_to_a1(row_num, ip_venc + 1),
                    "values": [[_fmt_date(vencs[pi])]],
                }
            )
            if meta and meta[3]:
                updates.append(
                    {
                        "range": gspread.utils.rowcol_to_a1(row_num, ip_form + 1),
                        "values": [[_fmt_date(meta[3])]],
                    }
                )
            pi += 1
            fixed += 1

    # também corrige data_entrada / formalizacao na aba Acordos quando houver meta
    for row_num, raw in enumerate(vals_a[1:], start=2):
        aid = _clean_cell(raw[ia_id] if ia_id < len(raw) else "")
        if not aid.startswith("RETRO-"):
            continue
        # extract ccb from aid RETRO-{ccb}-{yyyymmdd}
        parts = aid.split("-")
        ccb = parts[1] if len(parts) >= 2 else ""
        meta = by_ccb.get(ccb)
        if not meta:
            continue
        data_entrada, _dia, _n, formalizacao = meta
        if formalizacao:
            updates_a = [
                {
                    "range": f"Acordos!{gspread.utils.rowcol_to_a1(row_num, ia_form + 1)}",
                    "values": [[_fmt_date(formalizacao)]],
                },
                {
                    "range": f"Acordos!{gspread.utils.rowcol_to_a1(row_num, ia_entrada + 1)}",
                    "values": [[_fmt_date(data_entrada)]],
                },
            ]
            # batch on acordos separately below
            pass

    print(f"parcelas a corrigir (updates): {len(updates)} | linhas parcela: {fixed}")

    def flush(ws, batch):
        for i in range(0, len(batch), 80):
            chunk = batch[i : i + 80]
            _api_retry(lambda c=chunk: ws.batch_update(c, value_input_option="USER_ENTERED"))
            time.sleep(1.2)

    # Só atualiza Parcelas aqui (ranges relativos à aba)
    flush(ws_p, updates)

    # Acordos
    a_updates = []
    for row_num, raw in enumerate(vals_a[1:], start=2):
        aid = _clean_cell(raw[ia_id] if ia_id < len(raw) else "")
        if not aid.startswith("RETRO-"):
            continue
        parts = aid.split("-")
        ccb = parts[1] if len(parts) >= 2 else ""
        meta = by_ccb.get(ccb)
        if not meta:
            continue
        data_entrada, _dia, _n, formalizacao = meta
        if formalizacao:
            a_updates.append(
                {"range": gspread.utils.rowcol_to_a1(row_num, ia_form + 1), "values": [[_fmt_date(formalizacao)]]}
            )
        a_updates.append(
            {"range": gspread.utils.rowcol_to_a1(row_num, ia_entrada + 1), "values": [[_fmt_date(data_entrada)]]}
        )
    flush(ws_a, a_updates)
    print(f"OK: {fixed} vencimentos de parcela recalculados; {len(a_updates)} campos em Acordos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
