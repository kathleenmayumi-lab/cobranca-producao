"""Regras de métricas: CPC e produção."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "metrics.json"

DEFAULT_PRODUCTION = "Acordo formalizado"


def load_metrics_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"cpc_qualifications": [], "production_qualification": DEFAULT_PRODUCTION}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def cpc_qualifications() -> set[str]:
    return set(cpc_qualifications_ordered())


def cpc_qualifications_ordered() -> list[str]:
    data = load_metrics_config()
    return [str(q).strip() for q in data.get("cpc_qualifications", []) if str(q).strip()]


def production_qualification() -> str:
    data = load_metrics_config()
    return str(data.get("production_qualification", DEFAULT_PRODUCTION)).strip()
