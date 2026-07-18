"""电网、稀土、港股创新药与电池候补的半年报检查日期。"""

from __future__ import annotations

from datetime import date


CHECKPOINTS = (
    {
        "date": date(2026, 7, 20),
        "label": "业绩预告检查",
        "action": "查看电网、稀土与电池候补的业绩预告和已公布的经营提示",
    },
    {
        "date": date(2026, 8, 15),
        "label": "第一批半年业绩",
        "action": "查看电网、稀土、港股创新药与电池候补第一批半年业绩",
    },
    {
        "date": date(2026, 9, 1),
        "label": "统一复盘",
        "action": "统一复盘四个方向，比较创新药与电池候补的第三席",
    },
)

DISCLOSURE_NOTES = (
    "电网、稀土、电池候补：A股半年报最迟8月31日披露",
    "港股创新药：初步中期业绩最迟8月31日，详细中期报告最迟9月30日",
)

CANDIDATE_NOTE = "电池只作为第一候补参与复核，暂不加入买入计划。"


def _display_date(value: date) -> str:
    return f"{value.month}月{value.day}日"


def build_financial_report_check(as_of: date) -> dict:
    """Return the financial-report reminder state for a calendar date."""
    final_checkpoint = CHECKPOINTS[-1]
    if as_of >= final_checkpoint["date"]:
        return {
            "status": "due",
            "headline": "本轮统一复盘已到期：请检查电网、稀土、港股创新药与电池候补半年业绩",
            "next_date": None,
            "checkpoints": CHECKPOINTS,
            "disclosure_notes": DISCLOSURE_NOTES,
            "candidate_note": CANDIDATE_NOTE,
        }

    for checkpoint in CHECKPOINTS:
        checkpoint_date = checkpoint["date"]
        if as_of == checkpoint_date:
            return {
                "status": "today",
                "headline": f"今天检查：{checkpoint['label']} · {checkpoint['action']}",
                "next_date": checkpoint_date,
                "checkpoints": CHECKPOINTS,
                "disclosure_notes": DISCLOSURE_NOTES,
                "candidate_note": CANDIDATE_NOTE,
            }
        if as_of < checkpoint_date:
            return {
                "status": "upcoming",
                "headline": (
                    f"下一检查点：{_display_date(checkpoint_date)} · "
                    f"{checkpoint['label']} · {checkpoint['action']}"
                ),
                "next_date": checkpoint_date,
                "checkpoints": CHECKPOINTS,
                "disclosure_notes": DISCLOSURE_NOTES,
                "candidate_note": CANDIDATE_NOTE,
            }

    raise RuntimeError("无法确定财报检查日期")
