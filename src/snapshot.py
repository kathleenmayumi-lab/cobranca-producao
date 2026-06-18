"""Salva snapshot JSON para o dashboard web."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "latest.json"


def build_snapshot_payload(summary: dict[str, Any]) -> dict[str, Any]:
    """Normaliza o summary para JSON (local, planilha remota e dashboard)."""
    agent_stats = []
    for row in summary.get("agent_stats", []):
        if isinstance(row, dict):
            agent_stats.append(
                {
                    "agent": row["agent"],
                    "cpc": int(row["cpc"]),
                    "acordos": int(row["acordos"]),
                    "finalizadas": int(row.get("finalizadas", 0)),
                }
            )
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            agent_stats.append(
                {
                    "agent": row[0],
                    "cpc": int(row[1]),
                    "acordos": int(row[2]),
                    "finalizadas": int(row[3]) if len(row) >= 4 else 0,
                }
            )

    cpc_by_type: dict[str, list[dict[str, Any]]] = {}
    for qual, rows in summary.get("cpc_by_type", {}).items():
        normalized_rows: list[dict[str, Any]] = []
        if isinstance(rows, dict):
            normalized_rows = [{"agent": agent, "count": int(count)} for agent, count in rows.items()]
        else:
            for row in rows:
                if isinstance(row, dict):
                    normalized_rows.append({"agent": row["agent"], "count": int(row["count"])})
                elif isinstance(row, (list, tuple)) and len(row) >= 2:
                    normalized_rows.append({"agent": row[0], "count": int(row[1])})
        cpc_by_type[qual] = normalized_rows

    return {
        "updated_at": summary["updated_at"],
        "date": summary["date"],
        "total_calls": summary["total_calls"],
        "total_finalized": summary["total_finalized"],
        "total_cpc": summary["total_cpc"],
        "total_production": summary["total_production"],
        "agent_stats": agent_stats,
        "cpc_by_type": cpc_by_type,
        "production_rows": summary.get("production_rows", []),
        "cpc_rows": summary.get("cpc_rows", []),
    }


def save_snapshot(summary: dict[str, Any]) -> Path:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = build_snapshot_payload(summary)
    SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return SNAPSHOT_PATH


def load_snapshot() -> dict[str, Any] | None:
    if not SNAPSHOT_PATH.exists():
        return None
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
