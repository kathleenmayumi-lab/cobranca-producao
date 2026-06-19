"""Mescla produção WhatsApp no summary do painel."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from src.wpp_loader import load_wpp_production_for_day


def _normalize_agent_stats(agent_stats: list) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in agent_stats:
        if isinstance(row, dict):
            normalized.append(dict(row))
            continue
        if isinstance(row, (list, tuple)) and len(row) >= 3:
            item = {
                "agent": row[0],
                "cpc": int(row[1]),
                "acordos": int(row[2]),
                "finalizadas": int(row[3]) if len(row) >= 4 else 0,
            }
            normalized.append(item)
    return normalized


def _discador_baseline(summary: dict[str, Any]) -> dict[str, Any]:
    """Remove merge WPP anterior para recalcular a partir do discador."""
    base = dict(summary)
    if "total_production_discador" in base:
        base["total_production"] = int(base["total_production_discador"])
    stats = _normalize_agent_stats(base.get("agent_stats", []))
    for row in stats:
        row["acordos"] = int(row.get("acordos_discador", row.get("acordos", 0)))
    base["agent_stats"] = stats
    base.pop("wpp_production_rows", None)
    base.pop("total_wpp_production", None)
    return base


def merge_wpp_into_summary(summary: dict[str, Any], wpp_rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged = _discador_baseline(summary)
    wpp_counts = Counter(row.get("agent_name") or "Sem agente" for row in wpp_rows)

    stats = _normalize_agent_stats(merged.get("agent_stats", []))
    agents_in_stats = {row["agent"] for row in stats}

    for row in stats:
        row["acordos_discador"] = int(row.get("acordos", 0))
        row["acordos_wpp"] = int(wpp_counts.get(row["agent"], 0))

    for agent, count in wpp_counts.items():
        if agent in agents_in_stats:
            continue
        stats.append(
            {
                "agent": agent,
                "cpc": 0,
                "acordos": 0,
                "acordos_discador": 0,
                "acordos_wpp": int(count),
                "finalizadas": 0,
            }
        )

    total_discador = int(merged.get("total_production", 0))
    total_wpp = len(wpp_rows)
    merged["agent_stats"] = stats
    merged["wpp_production_rows"] = wpp_rows
    merged["total_production_discador"] = total_discador
    merged["total_wpp_production"] = total_wpp
    merged["total_production"] = total_discador + total_wpp
    return merged


def apply_wpp_to_summary(
    summary: dict[str, Any],
    target_day: date | None = None,
) -> tuple[dict[str, Any], list[str]]:
    day = target_day
    if day is None and summary.get("date"):
        try:
            day = date.fromisoformat(str(summary["date"]))
        except ValueError:
            day = date.today()
    day = day or date.today()
    from src.wpp_loader import wpp_configured

    if not wpp_configured():
        return summary, []

    wpp_rows, warnings = load_wpp_production_for_day(day)
    return merge_wpp_into_summary(summary, wpp_rows), warnings
