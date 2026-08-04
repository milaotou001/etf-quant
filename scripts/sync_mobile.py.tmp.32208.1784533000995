"""Sync desktop plan data to mobile snapshot files — then just git push."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mobile_view import _validate_plan, _normalize_trade_snapshot, TRADE_SNAPSHOT_VERSION
from purchase_plan import PURCHASE_PLAN_PATH, load_purchase_plan
from trades import load_trade_cache


MOBILE_DIR = PROJECT_ROOT / "mobile"
PLAN_FILE = MOBILE_DIR / "plan_snapshot.json"
TRADES_FILE = MOBILE_DIR / "trades_snapshot.json"


def main() -> None:
    plan = load_purchase_plan(str(PURCHASE_PLAN_PATH))
    validated = _validate_plan(plan)
    trades = load_trade_cache()
    trade_snapshot = _normalize_trade_snapshot(trades)

    MOBILE_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_FILE.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")
    TRADES_FILE.write_text(json.dumps(trade_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已生成：{PLAN_FILE}")
    print(f"已生成：{TRADES_FILE}")
    print("git add mobile/ && git commit -m 'sync: mobile snapshots' && git push 即可同步到手机")


if __name__ == "__main__":
    main()
