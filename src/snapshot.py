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
        agent_counts = buckets.setdefault(qualification, {})
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

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


def merge_improdutivas_from(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Copia improdutivas de outro snapshot quando o principal não tem."""
    if summary_has_improdutiva_data(target):
        return target
    if not summary_has_improdutiva_data(source):
        return target
    merged = dict(target)
    merged["improdutivas_by_type"] = source.get("improdutivas_by_type", {})
    merged["total_improdutiva"] = source.get("total_improdutiva", breakdown_total(merged["improdutivas_by_type"]))
    if source.get("improdutiva_rows"):
        merged["improdutiva_rows"] = source["improdutiva_rows"]
    return merged


def summary_has_wpp_data(summary: dict[str, Any]) -> bool:
    if int(summary.get("total_wpp_production", 0)) > 0:
        return True
    for row in summary.get("agent_stats", []):
        if isinstance(row, dict) and int(row.get("acordos_wpp", 0)) > 0:
            return True
    return False


def enrich_summary_wpp(summary: dict[str, Any]) -> dict[str, Any]:
    """Garante campos discador/WPP mesmo em snapshots antigos."""
    enriched = dict(summary)
    stats: list[dict[str, Any]] = []
    for row in enriched.get("agent_stats", []):
        if isinstance(row, dict):
            item = dict(row)
            item["acordos_discador"] = int(item.get("acordos_discador", item.get("acordos", 0)))
            item["acordos_wpp"] = int(item.get("acordos_wpp", 0))
            stats.append(item)
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            stats.append(
                {
                    "agent": row[0],
                    "cpc": int(row[1]),
                    "acordos": int(row[2]),
                    "finalizadas": int(row[3]) if len(row) >= 4 else 0,
                    "acordos_discador": int(row[2]),
                    "acordos_wpp": 0,
                }
            )
    enriched["agent_stats"] = stats
    total_disc = sum(int(row.get("acordos_discador", 0)) for row in stats)
    total_wpp = sum(int(row.get("acordos_wpp", 0)) for row in stats)
    enriched["total_production_discador"] = int(
        enriched.get("total_production_discador", total_disc)
    )
    enriched["total_wpp_production"] = int(enriched.get("total_wpp_production", total_wpp))
    enriched["total_production"] = (
        enriched["total_production_discador"] + enriched["total_wpp_production"]
    )
    return enriched


def merge_wpp_from(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Copia produção WPP de outro snapshot quando o principal não tem."""
    target = enrich_summary_wpp(target)
    if summary_has_wpp_data(target):
        return target
    if not summary_has_wpp_data(source):
        return target

    merged = dict(target)
    source_by_agent: dict[str, dict[str, Any]] = {}
    for row in source.get("agent_stats", []):
        if isinstance(row, dict):
            source_by_agent[row["agent"]] = row

    stats: list[dict[str, Any]] = []
    for row in merged.get("agent_stats", []):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        src = source_by_agent.get(item.get("agent", ""), {})
        item["acordos_discador"] = int(item.get("acordos_discador", item.get("acordos", 0)))
        item["acordos_wpp"] = int(src.get("acordos_wpp", item.get("acordos_wpp", 0)))
        stats.append(item)

    merged["agent_stats"] = stats
    merged["total_production_discador"] = int(
        source.get("total_production_discador", merged.get("total_production_discador", 0))
    )
    merged["total_wpp_production"] = int(source.get("total_wpp_production", 0))
    merged["total_production"] = (
        merged["total_production_discador"] + merged["total_wpp_production"]
    )
    if source.get("wpp_production_rows"):
        merged["wpp_production_rows"] = source["wpp_production_rows"]
    return enrich_summary_wpp(merged)


def build_cloud_snapshot_payload(summary: dict[str, Any]) -> dict[str, Any]:
    """Payload enxuto para aba _Snapshot (sem listas enormes de linhas)."""
    payload = build_snapshot_payload(summary)
    payload.pop("improdutiva_rows", None)
    payload.pop("wpp_production_rows", None)
    return payload


def build_snapshot_payload(summary: dict[str, Any]) -> dict[str, Any]:
    """Normaliza o summary para JSON (local, planilha remota e dashboard)."""
    agent_stats = []
    for row in summary.get("agent_stats", []):
        if isinstance(row, dict):
            item = {
                "agent": row["agent"],
                "cpc": int(row["cpc"]),
                "acordos": int(row["acordos"]),
                "finalizadas": int(row.get("finalizadas", 0)),
            }
            if "acordos_discador" in row:
                item["acordos_discador"] = int(row["acordos_discador"])
            if "acordos_wpp" in row:
                item["acordos_wpp"] = int(row["acordos_wpp"])
            agent_stats.append(item)
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
        "total_production_discador": summary.get(
            "total_production_discador", summary["total_production"]
        ),
        "total_wpp_production": summary.get("total_wpp_production", 0),
        "total_improdutiva": summary.get("total_improdutiva", 0),
        "agent_stats": agent_stats,
        "cpc_by_type": cpc_by_type,
        "improdutivas_by_type": improdutivas_by_type,
        "production_rows": summary.get("production_rows", []),
        "cpc_rows": summary.get("cpc_rows", []),
        "improdutiva_rows": summary.get("improdutiva_rows", []),
        "wpp_production_rows": summary.get("wpp_production_rows", []),
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
