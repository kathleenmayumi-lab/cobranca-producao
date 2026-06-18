"""Mapeamento de agentes por squad e filtro de métricas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SQUADS_PATH = Path(__file__).resolve().parent.parent / "config" / "squads.json"


def _normalize_name(name: str) -> str:
    return " ".join(str(name or "").lower().split())


def agent_matches(agent: str, patterns: list[str]) -> bool:
    normalized = _normalize_name(agent)
    if not normalized:
        return False
    for pattern in patterns:
        target = _normalize_name(pattern)
        if not target:
            continue
        if normalized == target or normalized.startswith(f"{target} "):
            return True
    return False


def load_squads_config() -> list[dict[str, Any]]:
    if not SQUADS_PATH.exists():
        return [{"id": "todos", "label": "Todos"}]
    data = json.loads(SQUADS_PATH.read_text(encoding="utf-8"))
    return data.get("squads", [])


def squad_labels() -> list[str]:
    return [squad["label"] for squad in load_squads_config()]


def _squad_by_label(label: str) -> dict[str, Any] | None:
    for squad in load_squads_config():
        if squad.get("label") == label:
            return squad
    return None


def _agents_from_summary(summary: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for row in summary.get("agent_stats", []):
        if isinstance(row, dict):
            names.add(row.get("agent", ""))
        elif isinstance(row, (list, tuple)) and row:
            names.add(str(row[0]))
    for key in ("cpc_rows", "production_rows", "improdutiva_rows"):
        for row in summary.get(key, []):
            names.add(row.get("agent_name", ""))
    return {name for name in names if name}


def agents_for_squad(label: str, summary: dict[str, Any]) -> set[str] | None:
    """Retorna None para «Todos» (sem filtro)."""
    if label == "Todos":
        return None

    squad = _squad_by_label(label)
    if not squad:
        return None

    all_agents = _agents_from_summary(summary)

    if squad.get("agents"):
        return {agent for agent in all_agents if agent_matches(agent, squad["agents"])}

    exclude_id = squad.get("exclude_squad")
    if exclude_id:
        excluded: set[str] = set()
        for other in load_squads_config():
            if other.get("id") == exclude_id and other.get("agents"):
                excluded = {agent for agent in all_agents if agent_matches(agent, other["agents"])}
                break
        return all_agents - excluded

    return all_agents


def _filter_agent_stats(agent_stats: list, agents: set[str]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in agent_stats:
        if isinstance(row, dict):
            agent = row.get("agent", "")
            if agent in agents:
                filtered.append(dict(row))
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            agent = str(row[0])
            if agent in agents:
                item = {"agent": agent, "cpc": int(row[1]), "acordos": int(row[2])}
                if len(row) >= 4:
                    item["finalizadas"] = int(row[3])
                filtered.append(item)
    return filtered


def _filter_breakdown_by_type(by_type: dict, agents: set[str]) -> dict:
    filtered: dict = {}
    for qual, rows in by_type.items():
        if isinstance(rows, dict):
            block = {agent: count for agent, count in rows.items() if agent in agents}
        else:
            block = [
                row for row in rows
                if (row.get("agent") if isinstance(row, dict) else row[0]) in agents
            ]
        if block:
            filtered[qual] = block
    return filtered


def _breakdown_total(by_type: dict) -> int:
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


def filter_summary(summary: dict[str, Any], squad_label: str) -> dict[str, Any]:
    agents = agents_for_squad(squad_label, summary)
    if agents is None:
        return summary

    agent_stats = _filter_agent_stats(summary.get("agent_stats", []), agents)
    cpc_rows = [row for row in summary.get("cpc_rows", []) if row.get("agent_name") in agents]
    production_rows = [
        row for row in summary.get("production_rows", []) if row.get("agent_name") in agents
    ]
    improdutiva_rows = [
        row for row in summary.get("improdutiva_rows", []) if row.get("agent_name") in agents
    ]
    cpc_by_type = _filter_breakdown_by_type(summary.get("cpc_by_type", {}), agents)
    improdutivas_by_type = _filter_breakdown_by_type(summary.get("improdutivas_by_type", {}), agents)

    total_cpc = sum(int(row["cpc"]) for row in agent_stats)
    total_production = sum(int(row["acordos"]) for row in agent_stats)
    total_improdutiva = (
        len(improdutiva_rows)
        if improdutiva_rows
        else _breakdown_total(improdutivas_by_type)
    )
    if agent_stats and all("finalizadas" in row for row in agent_stats):
        total_finalized = sum(int(row["finalizadas"]) for row in agent_stats)
    else:
        total_finalized = len(cpc_rows) + len(production_rows)

    filtered = dict(summary)
    filtered.update(
        {
            "agent_stats": agent_stats,
            "cpc_rows": cpc_rows,
            "production_rows": production_rows,
            "improdutiva_rows": improdutiva_rows,
            "cpc_by_type": cpc_by_type,
            "improdutivas_by_type": improdutivas_by_type,
            "total_cpc": total_cpc,
            "total_production": total_production,
            "total_improdutiva": total_improdutiva,
            "total_finalized": total_finalized,
            "squad": squad_label,
        }
    )
    return filtered
