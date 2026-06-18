"""Salva snapshot JSON para o dashboard web."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "latest.json"


def save_snapshot(summary: dict[str, Any]) -> Path:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": summary["updated_at"],
        "date": summary["date"],
        "total_calls": summary["total_calls"],
        "total_finalized": summary["total_finalized"],
        "total_cpc": summary["total_cpc"],
        "total_production": summary["total_production"],
        "agent_stats": [
            {
                "agent": agent,
                "cpc": cpc,
                "acordos": acordos,
                "finalizadas": finalizadas,
            }
            for agent, cpc, acordos, finalizadas in summary.get("agent_stats", [])
        ],
        "cpc_by_type": {
            qual: [{"agent": agent, "count": count} for agent, count in rows]
            for qual, rows in summary.get("cpc_by_type", {}).items()
        },
        "production_rows": summary.get("production_rows", []),
        "cpc_rows": summary.get("cpc_rows", []),
    }
    SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return SNAPSHOT_PATH


def load_snapshot() -> dict[str, Any] | None:
    if not SNAPSHOT_PATH.exists():
        return None
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
