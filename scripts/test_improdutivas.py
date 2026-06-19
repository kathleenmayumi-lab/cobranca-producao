"""Testa agregação de improdutivas e grava resultado em data/test_improdutivas.json."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from run import load_calls
from src.api_3cplus import aggregate_production, normalize_call, _is_improdutiva_row
from src.snapshot import build_snapshot_payload, save_snapshot

OUT = ROOT / "data" / "test_improdutivas.json"


def main() -> int:
    calls, origin = load_calls()
    summary = aggregate_production(calls)
    save_snapshot(summary)
    payload = build_snapshot_payload(summary)

    normalized = [normalize_call(c) for c in calls]
    improd_samples = Counter()
    for row in normalized:
        if _is_improdutiva_row(row):
            qual = row.get("qualification_name") or row.get("readable_status_text") or "?"
            improd_samples[qual] += 1

    result = {
        "origin": origin,
        "calls": len(calls),
        "total_improdutiva": summary.get("total_improdutiva", 0),
        "tipos": list(payload.get("improdutivas_by_type", {}).keys()),
        "tipos_total": len(payload.get("improdutivas_by_type", {})),
        "top_samples": improd_samples.most_common(15),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
