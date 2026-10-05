"""Base canônica de acordos Monest. Fonte: config/monest_acordos.json."""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "monest_acordos.json"

STATUS_EM_ANDAMENTO = "Em andamento"
STATUS_QUEBRADO = "Quebrado"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def load_base() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def acordos() -> list[dict]:
    rows = load_base().get("acordos") or []
    out = []
    for row in rows:
        item = dict(row)
        item["valor"] = _money(item.get("valor") or 0)
        status = item.get("status")
        item["status"] = str(status).strip() if status else None
        ccb = item.get("ccb")
        item["ccb"] = str(ccb).strip() if ccb else None
        out.append(item)
    return out


def _soma(rows: list[dict]) -> Decimal:
    total = sum((_money(r.get("valor") or 0) for r in rows), Decimal("0.00"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resumo(rows: list[dict] | None = None) -> dict:
    base = rows if rows is not None else acordos()
    em = [r for r in base if r.get("status") == STATUS_EM_ANDAMENTO]
    quebrados = [r for r in base if r.get("status") == STATUS_QUEBRADO]
    incompletos = [r for r in base if not r.get("status") or not r.get("ccb")]
    return {
        "n": len(base),
        "em_andamento": len(em),
        "quebrado": len(quebrados),
        "incompleto": len(incompletos),
        "valor_total": _soma(base),
        "valor_em_andamento": _soma(em),
        "valor_quebrado": _soma(quebrados),
        "valor_incompleto": _soma(incompletos),
    }
