"""Salva snapshot JSON para o dashboard web."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "latest.json"


def _normalize_type_breakdown(by_type: dict) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    for qual, rows in by_type.items():
        normalized_rows: list[dict[str, Any]] = []
        if isinstance(rows, dict):
            normalized_rows = [{"agent": agent, "count": int(count)} for agent, count in rows.items()]
        else:
            for row in rows:
                if isinstance(row, dict):
                    normalized_rows.append({"agent": row["agent"], "count": int(row["count"])})
                elif isinstance(row, (list, tuple)) and len(row) >= 2:
                    normalized_rows.append({"agent": row[0], "count": int(row[1])})
        normalized[qual] = normalized_rows
    return normalized


def breakdown_total(by_type: dict) -> int:
    total = 0
    for rows in by_type.values():
        if isinstance(rows, dict):
            total += sum(int(count) for count in rows.values())
            continue
        for row in rows:
            if isinstance(row, dict):
                total += int(row["count"])
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                total += int(row[1])
    return total


def breakdown_from_rows(rows: list) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        qual = (row.get("qualification_name") or "").strip()
        status = (row.get("readable_status_text") or "").strip()
        if qual:
            qualification = qual
        elif status and status != "Finalizada":
            qualification = status
        else:
            qualification = "Sem finalização"
        agent = row.get("agent_name") or "Sem agente"
        buckets.setdefault(qualification, {})[agent] = buckets[qualification].get(agent, 0) + 1

    ordered = sorted(
        buckets.keys(),
        key=lambda qual: (-sum(buckets[qual].values()), qual),
    )
    return {
        qualification: [
            {"agent": agent, "count": count}
            for agent, count in sorted(
                buckets[qualification].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        for qualification in ordered
    }


def summary_has_improdutiva_data(summary: dict[str, Any]) -> bool:
    if summary.get("improdutiva_rows"):
        return True
    by_type = summary.get("improdutivas_by_type")
    return bool(by_type) and breakdown_total(by_type) > 0


def enrich_summary_improdutivas(summary: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(summary)
    by_type = enriched.get("improdutivas_by_type")
    if by_type and breakdown_total(by_type) > 0:
        return enriched
    rows = enriched.get("improdutiva_rows") or []
    if rows:
        enriched["improdutivas_by_type"] = breakdown_from_rows(rows)
    return enriched


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

    cpc_by_type = _normalize_type_breakdown(summary.get("cpc_by_type", {}))
    improdutivas_by_type = _normalize_type_breakdown(summary.get("improdutivas_by_type", {}))

    return {
        "updated_at": summary["updated_at"],
        "date": summary["date"],
        "total_calls": summary["total_calls"],
        "total_finalized": summary["total_finalized"],
        "total_cpc": summary["total_cpc"],
        "total_production": summary["total_production"],
        "total_improdutiva": summary.get("total_improdutiva", 0),
        "agent_stats": agent_stats,
        "cpc_by_type": cpc_by_type,
        "improdutivas_by_type": improdutivas_by_type,
        "production_rows": summary.get("production_rows", []),
        "cpc_rows": summary.get("cpc_rows", []),
        "improdutiva_rows": summary.get("improdutiva_rows", []),
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
