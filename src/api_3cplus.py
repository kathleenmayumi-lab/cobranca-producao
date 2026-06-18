"""Cliente da API 3C Plus — histórico de ligações."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

from src.metrics_config import cpc_qualifications, cpc_qualifications_ordered, production_qualification

API_BASE = os.getenv("THREECPLUS_API_BASE", "https://app.3c.plus/api/v1")
API_TOKEN = os.getenv("THREECPLUS_API_TOKEN", "")

PRODUCTION_QUALIFICATION = production_qualification()


def _headers() -> dict[str, str]:
    return {"Accept": "application/json"}


def _params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"api_token": API_TOKEN}
    if extra:
        params.update(extra)
    return params


def fetch_calls_for_day(target_day: date | None = None, page_limit: int = 500) -> list[dict[str, Any]]:
    """Busca ligações do dia via GET /calls (com paginação)."""
    if not API_TOKEN:
        raise ValueError("THREECPLUS_API_TOKEN não configurado no arquivo .env")

    target_day = target_day or date.today()
    start = datetime.combine(target_day, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end = datetime.combine(target_day, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")

    all_calls: list[dict[str, Any]] = []
    page = 1

    while True:
        response = requests.get(
            f"{API_BASE}/calls",
            headers=_headers(),
            params=_params(
                {
                    "start_date": start,
                    "end_date": end,
                    "page": page,
                    "limit": page_limit,
                }
            ),
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            batch = payload.get("data") or payload.get("calls") or []
            meta = payload.get("meta") or {}
        elif isinstance(payload, list):
            batch = payload
            meta = {}
        else:
            batch = []
            meta = {}

        if not batch:
            break

        all_calls.extend(batch)
        last_page = meta.get("last_page") or meta.get("total_pages")
        if last_page and page >= last_page:
            break
        if len(batch) < page_limit:
            break
        page += 1

    return all_calls


def normalize_call(raw: dict[str, Any]) -> dict[str, Any]:
    """Normaliza campos vindos da API ou CSV exportado."""
    qualification_obj = raw.get("qualification")
    if isinstance(qualification_obj, dict):
        qualification = (qualification_obj.get("name") or "").strip()
        conversion = qualification_obj.get("conversion")
    else:
        qualification = (raw.get("qualification_name") or "").strip()
        conversion = raw.get("qualification_conversion")

    agent = (raw.get("agent_name") or "").strip()
    if not agent and isinstance(raw.get("agent"), dict):
        agent = (raw["agent"].get("name") or "").strip()

    status = (
        raw.get("readable_status_text")
        or raw.get("status_text")
        or raw.get("status_name")
        or ""
    )
    if isinstance(status, (int, float)):
        status = str(status)
    status = str(status).strip()

    raw_status = str(raw.get("status", "")).strip()
    if status in ("7", "7.0") or (not status and raw_status == "7"):
        status = "Finalizada"

    call_date = raw.get("call_date") or raw.get("created_at") or ""
    contract_number = _extract_contract_number(raw)

    is_production = qualification == PRODUCTION_QUALIFICATION
    if not is_production and str(conversion).strip() in {"1", "true", "True"}:
        is_production = qualification == PRODUCTION_QUALIFICATION

    is_cpc = qualification in cpc_qualifications()

    return {
        "agent_name": agent,
        "qualification_name": qualification,
        "readable_status_text": status,
        "call_date": call_date,
        "campaign_name": raw.get("campaign_name") or "",
        "number": raw.get("number") or "",
        "contract_number": contract_number,
        "is_production": is_production,
        "is_cpc": is_cpc,
    }


def _extract_contract_number(raw: dict[str, Any]) -> str:
    """Extrai número do contrato do export 3C Plus (coluna identifier / mailing)."""
    for key in ("identifier", "contract", "contract_number", "contract_id", "ccb"):
        value = raw.get(key)
        if value not in (None, ""):
            return str(value).strip()

    mailing = raw.get("mailing_data")
    if isinstance(mailing, dict):
        data = mailing.get("data") or {}
        if isinstance(data, dict):
            for key in ("contract", "contrato", "ccb", "identifier", "id"):
                value = data.get(key)
                if value not in (None, ""):
                    return str(value).strip()

    for key, value in raw.items():
        lowered = key.lower()
        if ("contract" in lowered or "contrato" in lowered or lowered.endswith(".ccb")) and value not in (
            None,
            "",
        ):
            return str(value).strip()

    return ""


def _count_by_agent(rows: list[dict[str, Any]], flag: str) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        if not row.get(flag):
            continue
        agent = row["agent_name"] or "Sem agente"
        counts[agent] = counts.get(agent, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _merge_agent_stats(
    cpc_ranking: list[tuple[str, int]],
    acordos_ranking: list[tuple[str, int]],
    finalized_ranking: list[tuple[str, int]],
) -> list[tuple[str, int, int, int]]:
    agents = (
        {agent for agent, _ in cpc_ranking}
        | {agent for agent, _ in acordos_ranking}
        | {agent for agent, _ in finalized_ranking}
    )
    cpc_map = dict(cpc_ranking)
    acordos_map = dict(acordos_ranking)
    finalized_map = dict(finalized_ranking)
    merged = [
        (
            agent,
            cpc_map.get(agent, 0),
            acordos_map.get(agent, 0),
            finalized_map.get(agent, 0),
        )
        for agent in agents
    ]
    return sorted(merged, key=lambda item: (-item[2], -item[1], item[0]))


def _is_finalized_row(row: dict[str, Any]) -> bool:
    return (
        row["readable_status_text"] == "Finalizada"
        or row["is_production"]
        or row["is_cpc"]
    )


def _improdutiva_type_label(row: dict[str, Any]) -> str:
    qual = (row.get("qualification_name") or "").strip()
    if qual:
        return qual
    status = (row.get("readable_status_text") or "").strip()
    if status and status != "Finalizada":
        return status
    return "Sem finalização"


def _is_improdutiva_row(row: dict[str, Any]) -> bool:
    """Finalizações que não são CPC — alinhado ao CPC por tipo (com agente)."""
    if row.get("is_cpc"):
        return False
    qual = (row.get("qualification_name") or "").strip()
    agent = (row.get("agent_name") or "").strip()
    if qual:
        return True
    if _is_finalized_row(row):
        return True
    status = (row.get("readable_status_text") or "").strip()
    if status and status != "Finalizada":
        return bool(agent)
    return str(row.get("status", "")).strip() == "7" and bool(agent)


def _count_finalized_by_agent(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        if not _is_finalized_row(row):
            continue
        agent = row["agent_name"] or "Sem agente"
        counts[agent] = counts.get(agent, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _cpc_breakdown_by_type(normalized: list[dict[str, Any]]) -> dict[str, list[tuple[str, int]]]:
    """Contagem de CPC por tipo de finalização e por agente."""
    buckets: dict[str, dict[str, int]] = {qual: {} for qual in cpc_qualifications_ordered()}

    for row in normalized:
        if not row.get("is_cpc"):
            continue
        qualification = row["qualification_name"]
        if qualification not in buckets:
            continue
        agent = row["agent_name"] or "Sem agente"
        buckets[qualification][agent] = buckets[qualification].get(agent, 0) + 1

    breakdown: dict[str, list[tuple[str, int]]] = {}
    for qualification in cpc_qualifications_ordered():
        ranking = sorted(buckets[qualification].items(), key=lambda item: (-item[1], item[0]))
        breakdown[qualification] = ranking
    return breakdown


def _improdutiva_breakdown_by_type(
    normalized: list[dict[str, Any]],
) -> dict[str, list[tuple[str, int]]]:
    """Contagem de finalizações improdutivas (não CPC) por tipo e por agente."""
    buckets: dict[str, dict[str, int]] = {}

    for row in normalized:
        if not _is_improdutiva_row(row):
            continue
        qualification = _improdutiva_type_label(row)
        agent = row["agent_name"] or "Sem agente"
        buckets.setdefault(qualification, {})[agent] = buckets[qualification].get(agent, 0) + 1

    ordered = sorted(
        buckets.keys(),
        key=lambda qual: (-sum(buckets[qual].values()), qual),
    )
    return {
        qualification: sorted(
            buckets[qualification].items(),
            key=lambda item: (-item[1], item[0]),
        )
        for qualification in ordered
    }


def aggregate_production(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega CPC e produção (Acordo formalizado) por agente."""
    normalized = [normalize_call(c) for c in calls]

    production = [c for c in normalized if c["is_production"]]
    cpc = [c for c in normalized if c["is_cpc"]]
    finalized = [c for c in normalized if _is_finalized_row(c)]
    improdutiva = [c for c in normalized if _is_improdutiva_row(c)]

    cpc_ranking = _count_by_agent(normalized, "is_cpc")
    acordos_ranking = _count_by_agent(normalized, "is_production")
    finalized_ranking = _count_finalized_by_agent(normalized)
    agent_stats = _merge_agent_stats(cpc_ranking, acordos_ranking, finalized_ranking)
    cpc_by_type = _cpc_breakdown_by_type(normalized)
    improdutivas_by_type = _improdutiva_breakdown_by_type(normalized)

    return {
        "date": date.today().isoformat(),
        "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_calls": len(normalized),
        "total_finalized": len(finalized),
        "total_cpc": len(cpc),
        "total_production": len(production),
        "total_improdutiva": len(improdutiva),
        "by_agent": acordos_ranking,
        "cpc_by_agent": cpc_ranking,
        "agent_stats": agent_stats,
        "cpc_by_type": cpc_by_type,
        "improdutivas_by_type": improdutivas_by_type,
        "cpc_rows": cpc,
        "production_rows": production,
        "improdutiva_rows": improdutiva,
    }
