"""Sync desktop plan data to mobile snapshot files — then just git push."""
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mobile_view import save_mobile_snapshots
from purchase_plan import PURCHASE_PLAN_PATH, load_purchase_plan
from trades import load_trade_cache


def main() -> None:
    plan = load_purchase_plan(str(PURCHASE_PLAN_PATH))
    trades = load_trade_cache()
    plan_path, trades_path = save_mobile_snapshots(plan, trades)
    print(f"已生成：{plan_path}")
    print(f"已生成：{trades_path}")
    print("git add mobile/ && git commit -m 'sync: mobile snapshots' && git push 即可同步到手机")


if __name__ == "__main__":
    main()
