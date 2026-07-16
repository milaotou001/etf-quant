"""政策证据的本地双确认审核状态。"""

from __future__ import annotations

import json
from pathlib import Path

from .evidence import EVIDENCE_BY_ID


REVIEW_PATH = Path(__file__).resolve().parents[1] / "private_data" / "policy_reviews.json"
VALID_DECISIONS = {"confirmed", "rejected"}


def _default_reviews() -> dict:
    return {"version": 1, "reviews": {}, "direction_reviews": {}}


def load_policy_reviews(path: str | Path = REVIEW_PATH) -> dict:
    target = Path(path)
    if not target.exists():
        return _default_reviews()
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"政策审核记录无法读取：{target}") from exc
    if not isinstance(loaded, dict) or not isinstance(loaded.get("reviews"), dict):
        raise ValueError("政策审核记录格式不正确")
    loaded.setdefault("version", 1)
    loaded.setdefault("direction_reviews", {})
    return loaded


def save_policy_reviews(state: dict, path: str | Path = REVIEW_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)


def review_evidence(
    evidence_id: str,
    decision: str,
    reviewed_on: str,
    note: str = "",
    path: str | Path = REVIEW_PATH,
) -> dict:
    if evidence_id not in EVIDENCE_BY_ID:
        raise ValueError(f"未知证据：{evidence_id}")
    if decision not in VALID_DECISIONS:
        raise ValueError(f"审核决定必须是 confirmed 或 rejected：{decision}")
    state = load_policy_reviews(path)
    state["reviews"][evidence_id] = {
        "decision": decision,
        "reviewed_on": reviewed_on,
        "note": note.strip(),
    }
    save_policy_reviews(state, path)
    return state


def resolve_evidence_status(evidence: dict, reviews: dict) -> str:
    review = reviews.get("reviews", {}).get(evidence["id"], {})
    if review.get("decision") == "rejected":
        return "已驳回"
    if review.get("decision") == "confirmed" and evidence.get("codex_verified"):
        return "正式生效"
    if evidence.get("codex_verified"):
        return "Codex已核验"
    return "待整理"


def review_direction(
    direction_id: str,
    selection_version: str,
    decision: str,
    reviewed_on: str,
    note: str = "",
    coverage_version: str = "",
    path: str | Path = REVIEW_PATH,
) -> dict:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"审核决定必须是 confirmed 或 rejected：{decision}")
    state = load_policy_reviews(path)
    state["direction_reviews"][direction_id] = {
        "selection_version": selection_version,
        "coverage_version": coverage_version,
        "decision": decision,
        "reviewed_on": reviewed_on,
        "note": note.strip(),
    }
    save_policy_reviews(state, path)
    return state
