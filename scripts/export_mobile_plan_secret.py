"""Create an ignored Streamlit Secrets payload from the current private plan."""
from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mobile_view import encode_plan_snapshot
from purchase_plan import PURCHASE_PLAN_PATH, load_purchase_plan


DEFAULT_TARGET = PROJECT_ROOT / "private_data" / "mobile_streamlit_secrets.toml"


def build_secrets_toml(plan: dict) -> str:
    encoded = encode_plan_snapshot(plan)
    return f'MOBILE_READ_ONLY = "true"\nPURCHASE_PLAN_B64 = "{encoded}"\n'


def export_secret_file(source: Path, target: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"purchase_plan not found: {source}")
    plan = load_purchase_plan(str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(build_secrets_toml(plan), encoding="utf-8")
    os.replace(temporary, target)
    return target


def main() -> None:
    target = export_secret_file(Path(PURCHASE_PLAN_PATH), DEFAULT_TARGET)
    print(f"Streamlit Secret 已生成：{target}")


if __name__ == "__main__":
    main()
