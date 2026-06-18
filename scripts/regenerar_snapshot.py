"""Regenera data/latest.json com improdutivas (uso local)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from run import load_calls
from src.api_3cplus import aggregate_production
from src.snapshot import build_snapshot_payload, save_snapshot

OUT = ROOT / "data" / "regenerar_snapshot_result.json"


def main() -> int:
    calls, origin = load_calls()
    summary = aggregate_production(calls)
    path = save_snapshot(summary)
    payload = build_snapshot_payload(summary)
    types = list(payload.get("improdutivas_by_type", {}).keys())
    result = {
        "origin": origin,
        "snapshot": str(path),
        "total_improdutiva": payload.get("total_improdutiva", 0),
        "tipos": types[:20],
        "tipos_total": len(types),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
