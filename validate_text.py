"""文案-数据一致性智能验证模块。每次页面加载自动检查文案与数据的一致性。"""
import re
import numpy as np
import pandas as pd
from dashboard import _macd_cols, _col, RSI_THRESHOLDS

# ══════════════════════════════════════════════
# 同义词映射 — 避免文案换词误报
# ══════════════════════════════════════════════

SYNONYMS = {
    "红柱为正": {"红柱为正", "上涨动能占优", "动能偏多但未增强"},
    "MACD偏多": {"MACD偏多", "DIF在DEA上方", "DIF>DEA", "MACD多头"},
    "金叉": {"金叉", "DIF上穿DEA", "形成金叉"},
    "死叉": {"死叉", "DIF下穿DEA", "形成死叉"},
    "放量": {"放量", "成交量放大", "量能确认", "有量"},
    "缩量": {"缩量", "量能不足", "无量", "缩量回踩"},
}

SYNONYM_MAP = {}
for canonical, variants in SYNONYMS.items():
    for v in variants:
        SYNONYM_MAP[v] = canonical


def _canonical(label: str) -> str:
    return SYNONYM_MAP.get(label, label)


# ══════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════

def validate(df: pd.DataFrame, analysis: dict, checklist: dict | None,
             reminders: list[str], symbol: str = "563360") -> list[str]:
    """返回警告列表。空列表 = 全部通过。"""
    warnings = []
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    d = _extract_data(df, latest, prev, symbol)
    if pd.isna(d["close"]):
        return warnings

    # ── 强校验 ──
    warnings.extend(_v_state_label(analysis["state_label"], d))
    warnings.extend(_v_steps(analysis["steps"], d))
    warnings.extend(_v_one_liner(analysis["state_label"], analysis["one_liner"], d))
    warnings.extend(_v_reminders(reminders, d))
    warnings.extend(_v_checklist(checklist, df, symbol, d))
    warnings.extend(_v_position_notes(analysis["state_label"], analysis["position_notes"], d))

    # ── 弱提醒：关键词扫描 ──
    all_text = _collect_text(analysis, checklist, reminders)
    warnings.extend(_v_keywords(all_text, d))

    return warnings


# ══════════════════════════════════════════════
# 数据提取
# ══════════════════════════════════════════════

def _extract_data(df: pd.DataFrame, latest: pd.Series, prev: pd.Series | None,
                  symbol: str) -> dict:
    macd_col, signal_col, hist_col = _macd_cols(df)
    rsi_threshold = RSI_THRESHOLDS.get(symbol, 35)

    close = latest["close"]
    ma5 = latest.get("ma5", np.nan)
    ma10 = latest.get("ma10", np.nan)
    ma20 = latest.get("ma20", np.nan)
    ma60 = latest.get("ma60", np.nan)
    rsi_val = latest.get("rsi", np.nan)
    rvol_val = latest.get("rvol", np.nan)
    chg = latest.get("chg", np.nan) if "chg" in latest.index else np.nan
    dif = latest[macd_col] if macd_col else np.nan
    dea = latest[signal_col] if signal_col else np.nan
    hist = latest[hist_col] if hist_col else np.nan
    prev_hist = prev[hist_col] if prev is not None and hist_col else np.nan
    prev_close = prev["close"] if prev is not None else np.nan
    prev_ma20 = prev.get("ma20", np.nan) if prev is not None else np.nan

    price_strong = _is_price_strong(close, ma5, ma10, ma20)
    near_ma5_ma10 = _is_near_ma(close, ma5, ma10)
    recent_high_5 = df["close"].iloc[-6:-1].max() if len(df) >= 6 else close
    pullback_from_recent_high = close < recent_high_5 * 0.99
    recent_high_20 = df["close"].iloc[-21:-1].max() if len(df) >= 21 else close
    is_breakout = close > recent_high_20
    is_pullback = chg < 0 or (not pd.isna(prev_close) and close < prev_close)

    adx_col = _col(df, "ADX")
    adx_val = latest[adx_col] if adx_col else np.nan

    return {
        "close": close, "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "rsi": rsi_val, "rvol": rvol_val, "chg": chg,
        "dif": dif, "dea": dea, "hist": hist, "prev_hist": prev_hist,
        "prev_close": prev_close, "prev_ma20": prev_ma20,
        "adx": adx_val,
        "price_strong": price_strong,
        "near_ma5_ma10": near_ma5_ma10,
        "pullback_from_recent_high": pullback_from_recent_high,
        "is_breakout": is_breakout,
        "is_pullback": is_pullback,
        "rsi_threshold": rsi_threshold,
        "df": df,
    }


def _is_price_strong(close, ma5, ma10, ma20) -> bool:
    if any(pd.isna(v) for v in [close, ma5, ma10, ma20]):
        return False
    return (close > ma5 > ma10 > ma20) or (close > ma5 and close > ma10 and close > ma20)


def _is_near_ma(close, ma5, ma10) -> bool:
    return ((not pd.isna(ma5) and abs(close / ma5 - 1) <= 0.01)
            or (not pd.isna(ma10) and abs(close / ma10 - 1) <= 0.01))


# ══════════════════════════════════════════════
# 1. 状态标签 vs 数据 (Type B) — 用预期状态对比
# ══════════════════════════════════════════════

def derive_expected_state(d: dict) -> str | None:
    """按 _classify_market_state 优先级重新推导应得状态标签。"""
    c, ma5, ma10, ma20 = d["close"], d["ma5"], d["ma10"], d["ma20"]
    rvol, rsi, chg = d["rvol"], d["rsi"], d["chg"]
    dif, dea, hist, ph = d["dif"], d["dea"], d["hist"], d["prev_hist"]
    prev_close = d["prev_close"]

    if any(pd.isna(v) for v in [c, ma5, ma10, ma20, rsi]):
        return None

    price_strong = _is_price_strong(c, ma5, ma10, ma20)
    rvol_confirmed = not pd.isna(rvol) and rvol >= 1.2
    rvol_quiet = not pd.isna(rvol) and rvol < 1
    macd_bullish = not pd.isna(dif) and not pd.isna(dea) and dif > dea
    hist_positive = not pd.isna(hist) and hist > 0
    hist_negative_and_growing = (not pd.isna(hist) and hist < 0
                                 and not pd.isna(ph) and hist <= ph)
    hist_shrinking = not pd.isna(hist) and not pd.isna(ph) and hist > ph
    macd_not_obviously_bearish = macd_bullish or hist_positive or hist_shrinking
    macd_green_shrinking_or_red = hist_positive or (
        not pd.isna(hist) and hist < 0 and not pd.isna(ph) and hist > ph
    )

    near_ma = _is_near_ma(c, ma5, ma10)
    is_pullback = (not pd.isna(chg) and chg < 0) or (
        not pd.isna(prev_close) and c < prev_close)
    pullback_from_high = d["pullback_from_recent_high"]
    is_healthy_pullback = near_ma and is_pullback and pullback_from_high
    is_breakout = d["is_breakout"]

    # 优先级 1: 放量破位（MA20在前，避免被MA10子句抢先）
    if not pd.isna(c) and not pd.isna(ma20) and c < ma20 and rvol_confirmed and not pd.isna(chg) and chg < 0:
        return "放量破位警戒"
    if not pd.isna(c) and not pd.isna(ma10) and c < ma10 and rvol_confirmed and not pd.isna(chg) and chg < 0:
        return "短线放量转弱"

    # 优先级 2: 高位过热
    if price_strong and not pd.isna(rsi) and rsi >= 80:
        return "严重过热"
    if price_strong and not pd.isna(rsi) and rsi >= 70 and rvol_confirmed:
        return "高位放量过热"
    if price_strong and not pd.isna(rsi) and rsi >= 70:
        return "偏热强势"

    # 优先级 3: 强势放量
    if price_strong and rvol_confirmed and macd_bullish and hist_positive and not pd.isna(rsi) and rsi < 70:
        if is_breakout:
            return "强势放量突破"
        return "强势放量"

    # 优先级 4: 缩量偏强
    if price_strong and rvol_quiet and macd_bullish and not pd.isna(rsi) and rsi < 70:
        return "缩量偏强"

    # 优先级 5: 健康回踩
    if (is_healthy_pullback and not pd.isna(ma20) and c > ma20
            and rvol_quiet and not pd.isna(rsi) and 45 <= rsi <= 60
            and macd_not_obviously_bearish):
        return "健康回踩"

    # 优先级 6-8: MA20 下方
    if not pd.isna(ma20) and c < ma20:
        if hist_negative_and_growing:
            return "弱势下行"
        # 尝试修复优先于趋势偏弱：收涨 + MACD改善
        if not pd.isna(chg) and chg > 0 and macd_green_shrinking_or_red:
            return "尝试修复"
        if not pd.isna(dif) and not pd.isna(dea) and dif < dea:
            return "趋势偏弱"
        if not pd.isna(chg) and chg < 0:
            return "弱势延续"

    return "中性观察"


def _v_state_label(state_label: str, d: dict) -> list[str]:
    """对比页面状态标签与数据推导的预期状态。"""
    expected = derive_expected_state(d)
    if expected is None:
        return []
    if state_label != expected:
        detail = _describe_state_mismatch(expected, state_label, d)
        return [_warn("状态标签",
            f'页面输出"{state_label}"', f'数据推导应为"{expected}"。{detail}')]
    return []


def _describe_state_mismatch(expected: str, actual: str, d: dict) -> str:
    parts = []
    c, m20, rvol, rsi, chg = d["close"], d["ma20"], d["rvol"], d["rsi"], d["chg"]
    h, ph = d["hist"], d["prev_hist"]
    if not pd.isna(c):
        parts.append(f"close={c:.4f}")
    if not pd.isna(m20):
        parts.append(f"MA20={m20:.4f}")
    if not pd.isna(rvol):
        parts.append(f"RVOL={rvol:.2f}")
    if not pd.isna(rsi):
        parts.append(f"RSI={rsi:.0f}")
    if not pd.isna(chg):
        parts.append(f"chg={chg:+.1f}%")
    if not pd.isna(h):
        parts.append(f"HIST={h:+.4f}")
    return "，".join(parts)


# ══════════════════════════════════════════════
# 2. 看盘步骤状态 vs 数据 (Type B)
# ══════════════════════════════════════════════

def _v_steps(steps: list, d: dict) -> list[str]:
    warnings = []
    for name, state, _note in steps:
        if name == "RSI":
            expected = _derive_rsi_state(d["rsi"])
            if expected and state != expected:
                warnings.append(_warn("步骤-RSI",
                    f'"{state}"', f'RSI={d["rsi"]:.0f}，预期"{expected}"'))
        elif name == "MACD":
            expected = _derive_macd_state(d["hist"], d["prev_hist"])
            if expected and state != expected:
                warnings.append(_warn("步骤-MACD",
                    f'"{state}"', f'HIST={d["hist"]:+.4f} prev_HIST={d["prev_hist"]:+.4f}，预期"{expected}"'))
        elif name == "价格位置":
            expected = _derive_price_state(d)
            if expected and state != expected:
                warnings.append(_warn("步骤-价格位置",
                    f'"{state}"',
                    f'close={d["close"]:.4f} MA5={d["ma5"]:.4f} MA10={d["ma10"]:.4f} MA20={d["ma20"]:.4f}，预期"{expected}"'))
        elif name == "RVOL":
            expected = _derive_rvol_state(d)
            if expected and state != expected:
                warnings.append(_warn("步骤-RVOL",
                    f'"{state}"', f'RVOL={d["rvol"]:.2f} chg={d["chg"]:+.1f}%，预期"{expected}"'))
    return warnings


def _derive_rsi_state(rsi: float) -> str | None:
    if pd.isna(rsi):
        return None
    if rsi >= 80:
        return "严重过热"
    if rsi >= 70:
        return "偏热"
    if rsi >= 50:
        return "正常偏强"
    if rsi >= 45:
        return "正常"
    return "偏弱"


def _derive_macd_state(hist: float, prev_hist: float) -> str | None:
    if pd.isna(hist) or pd.isna(prev_hist):
        return None
    if hist > 0 and prev_hist < 0:
        return "金叉"
    if hist > 0 and hist > prev_hist:
        return "红柱放大"
    if hist > 0:
        return "红柱为正"
    if hist < 0 and prev_hist > 0:
        return "死叉"
    if hist < 0 and hist > prev_hist:
        return "绿柱缩短"
    if hist < 0:
        return "绿柱放大"
    return "零轴附近"


def _derive_price_state(d: dict) -> str | None:
    c, ma5, ma10, ma20 = d["close"], d["ma5"], d["ma10"], d["ma20"]
    if any(pd.isna(v) for v in [c, ma5, ma10, ma20]):
        return None
    if c > ma5 > ma10 > ma20:
        return "多头排列"
    if c > ma5 and c > ma10 and c > ma20:
        return "均线上方"
    if c < ma10 and c > ma20:
        return "回踩区间"
    if c < ma20:
        prev_c, prev_m20 = d["prev_close"], d["prev_ma20"]
        if (not pd.isna(prev_c) and not pd.isna(prev_m20)
                and prev_c >= prev_m20):
            return "跌破MA20"
        return "MA20下方"
    return "均线之间"


def _derive_rvol_state(d: dict) -> str | None:
    rvol = d["rvol"]
    if pd.isna(rvol):
        return "暂不可用"
    if rvol < 0.7:
        return "明显缩量"
    if rvol < 1.0:
        return "偏缩量"
    if rvol < 1.2:
        return "正常量"
    if rvol < 1.5:
        return "温和放量"
    if rvol < 2.0:
        return "明显放量"
    return "异常放量"


# ══════════════════════════════════════════════
# 3. 一句话解释一致性 (Type B)
# ══════════════════════════════════════════════

ONE_LINER_CHECKS = {
    "放量破位警戒": ["跌破", "MA20", "放量"],
    "短线放量转弱": ["MA10", "放量"],
    "严重过热": ["过热"],
    "高位放量过热": ["过热"],
    "偏热强势": ["偏热"],
    "强势放量突破": ["突破"],
    "强势放量": ["放量"],
    "缩量偏强": ["量能", "偏强"],
    "健康回踩": ["回踩"],
    "弱势下行": ["MA20"],
    "趋势偏弱": ["MA20"],
    "尝试修复": ["MA20", "修复"],
    "弱势延续": ["MA20"],
}


def _v_one_liner(state_label: str, one_liner: str, d: dict) -> list[str]:
    expected = ONE_LINER_CHECKS.get(state_label)
    if expected is None:
        return []
    missing = [kw for kw in expected if kw not in one_liner]
    if missing:
        return [_warn("一句话解释",
            f'状态"{state_label}"但解释缺少关键词{missing}',
            f'"{one_liner}"')]
    return []


# ══════════════════════════════════════════════
# 4. 关键词断言 (Type A) — 弱提醒级别
# ══════════════════════════════════════════════

KEYWORD_RULES = [
    ("RSI偏低", lambda d: not pd.isna(d["rsi"]) and d["rsi"] < 45,
     'RSI={rsi:.0f} ≥ 45，不是"偏低"'),
    ("RSI 低位", lambda d: not pd.isna(d["rsi"]) and d["rsi"] < d["rsi_threshold"],
     'RSI={rsi:.0f} ≥ 阈值{rsi_threshold}，不是"低位"'),
    ("放量破位", lambda d: (not pd.isna(d["rvol"]) and d["rvol"] >= 1.2
                            and d["close"] < d["ma20"]),
     'RVOL={rvol:.2f} close={close:.4f} MA20={ma20:.4f}'),
    ("放量突破", lambda d: (not pd.isna(d["rvol"]) and d["rvol"] >= 1.2
                            and d["is_breakout"]),
     'RVOL={rvol:.2f}，未突破前高'),
    ("放量下跌", lambda d: (not pd.isna(d["rvol"]) and d["rvol"] >= 1.2
                            and not pd.isna(d["chg"]) and d["chg"] < 0),
     'RVOL={rvol:.2f} chg={chg:+.1f}%'),
    ("放量", lambda d: not pd.isna(d["rvol"]) and d["rvol"] >= 1.2,
     'RVOL={rvol:.2f} < 1.2，不是"放量"'),
    ("缩量", lambda d: not pd.isna(d["rvol"]) and d["rvol"] < 1.0,
     'RVOL={rvol:.2f} ≥ 1.0，不是"缩量"'),
    ("死叉", lambda d: (not pd.isna(d["hist"]) and d["hist"] < 0
                        and not pd.isna(d["prev_hist"]) and d["prev_hist"] > 0),
     'HIST={hist:+.4f} prev_HIST={prev_hist:+.4f}，不是死叉'),
    ("金叉", lambda d: (not pd.isna(d["hist"]) and d["hist"] > 0
                        and not pd.isna(d["prev_hist"]) and d["prev_hist"] < 0),
     'HIST={hist:+.4f} prev_HIST={prev_hist:+.4f}，不是金叉'),
    ("多头排列", lambda d: (not pd.isna(d["close"]) and not pd.isna(d["ma5"])
                            and not pd.isna(d["ma10"]) and not pd.isna(d["ma20"])
                            and d["close"] > d["ma5"] > d["ma10"] > d["ma20"]),
     'close={close:.4f} MA5={ma5:.4f} MA10={ma10:.4f} MA20={ma20:.4f}'),
    ("红柱放大", lambda d: (not pd.isna(d["hist"]) and d["hist"] > 0
                            and not pd.isna(d["prev_hist"]) and d["hist"] > d["prev_hist"]),
     'HIST={hist:+.4f} prev_HIST={prev_hist:+.4f}，不是红柱放大'),
    ("绿柱放大", lambda d: (not pd.isna(d["hist"]) and d["hist"] < 0
                            and not pd.isna(d["prev_hist"]) and d["hist"] <= d["prev_hist"]),
     'HIST={hist:+.4f} prev_HIST={prev_hist:+.4f}，不是绿柱放大'),
    ("绿柱缩短", lambda d: (not pd.isna(d["hist"]) and d["hist"] < 0
                            and not pd.isna(d["prev_hist"]) and d["hist"] > d["prev_hist"]),
     'HIST={hist:+.4f} prev_HIST={prev_hist:+.4f}，不是绿柱缩短'),
    ("红柱为正", lambda d: not pd.isna(d["hist"]) and d["hist"] > 0,
     'HIST={hist:+.4f} ≤ 0'),
    ("MACD偏多", lambda d: (not pd.isna(d["dif"]) and not pd.isna(d["dea"])
                            and d["dif"] > d["dea"]),
     'DIF={dif:+.4f} DEA={dea:+.4f}，DIF≤DEA'),
]

_NEGATE_RE = re.compile(r'(不是|而非|并非|不|没有|未出现|未|无)')
_FORWARD_RE = re.compile(r'(等|看|观察|关注|先|等待|期待)')


def _keyword_in_assertion(text: str, keyword: str) -> bool:
    idx = 0
    while True:
        idx = text.find(keyword, idx)
        if idx == -1:
            return False
        prefix = text[max(0, idx - 15):idx]
        if _NEGATE_RE.search(prefix):
            idx += 1
            continue
        if _FORWARD_RE.search(prefix):
            idx += 1
            continue
        return True


def _v_keywords(all_text: str, d: dict) -> list[str]:
    """弱提醒：关键词扫描，辅助级别。"""
    warnings = []
    for keyword, condition, fail_fmt in KEYWORD_RULES:
        if not _keyword_in_assertion(all_text, keyword):
            continue
        try:
            if not condition(d):
                detail = fail_fmt.format(**d)
                warnings.append(_warn("弱提醒",
                    f'文中出现"{keyword}"', f"{detail}"))
        except Exception:
            pass
    return warnings


# ══════════════════════════════════════════════
# 5. 纪律提醒 vs 数据 (Type B)
# ══════════════════════════════════════════════

def _v_reminders(reminders: list[str], d: dict) -> list[str]:
    warnings = []
    for r in reminders:
        m = re.search(r'RSI\s*>\s*(\d+)', r)
        if m:
            threshold = int(m.group(1))
            if not pd.isna(d["rsi"]) and d["rsi"] <= threshold:
                warnings.append(_warn("提醒-RSI",
                    f'"{r}"', f"实际 RSI={d['rsi']:.0f}，未超过 {threshold}"))

        m = re.search(r'RVOL\s*=\s*([\d.]+)', r)
        if m:
            claimed = float(m.group(1))
            if not pd.isna(d["rvol"]) and abs(d["rvol"] - claimed) > 0.15:
                warnings.append(_warn("提醒-RVOL",
                    f'声称 RVOL={claimed:.1f}', f"实际 RVOL={d['rvol']:.2f}"))

        m = re.search(r'ADX\s*=\s*([\d.]+)', r)
        if m:
            claimed = float(m.group(1))
            if not pd.isna(d["adx"]) and abs(d["adx"] - claimed) > 2:
                warnings.append(_warn("提醒-ADX",
                    f'声称 ADX={claimed:.0f}', f"实际 ADX={d['adx']:.0f}"))

        m = re.search(r'急跌[（(]\s*([+-]?[\d.]+)\s*%', r)
        if m:
            claimed = float(m.group(1))
            if not pd.isna(d["chg"]) and abs(d["chg"] - claimed) > 1.0:
                warnings.append(_warn("提醒-涨跌幅",
                    f'声称急跌{claimed:+.1f}%', f"实际 chg={d['chg']:+.1f}%"))

        if "单日大涨" in r and "3%" in r:
            if not pd.isna(d["chg"]) and d["chg"] <= 3:
                warnings.append(_warn("提醒-涨跌幅",
                    f'"{r}"', f"实际 chg={d['chg']:+.1f}%，未超过 3%"))

    return warnings


# ══════════════════════════════════════════════
# 6. 买入清单 vs 数据 (Type B)
# ══════════════════════════════════════════════

def _risk_veto_check(d: dict) -> bool:
    """独立复算风险否决是否触发。返回 True 表示被否决。"""
    c, m20, m60 = d["close"], d["ma20"], d["ma60"]
    rvol, rsi, chg = d["rvol"], d["rsi"], d["chg"]
    dif, dea, hist, ph = d["dif"], d["dea"], d["hist"], d["prev_hist"]

    if (not pd.isna(c) and not pd.isna(m20) and c < m20
            and not pd.isna(rvol) and rvol >= 1.2
            and not pd.isna(chg) and chg < 0):
        return True
    if (not pd.isna(c) and not pd.isna(m20) and c < m20
            and not pd.isna(hist) and not pd.isna(ph)
            and hist < 0 and hist < ph):
        return True
    if not pd.isna(rsi) and rsi >= 80:
        return True
    if (not pd.isna(rsi) and rsi >= 70
            and not pd.isna(rvol) and rvol >= 1.2):
        return True
    if (not pd.isna(m60) and not pd.isna(c) and c < m60
            and not pd.isna(dif) and not pd.isna(dea) and dif < dea):
        return True
    return False


def derive_expected_buy_scenario(df: pd.DataFrame, d: dict, symbol: str) -> str | None:
    """按 build_buy_checklist 优先级重新推导应触发的买入场景。"""
    if _risk_veto_check(d):
        return None

    rsi_threshold = RSI_THRESHOLDS.get(symbol, 35)
    c, ma5, ma10, ma20 = d["close"], d["ma5"], d["ma10"], d["ma20"]
    rvol, rsi = d["rvol"], d["rsi"]
    dif, dea, hist, ph = d["dif"], d["dea"], d["hist"], d["prev_hist"]

    price_strong = _is_price_strong(c, ma5, ma10, ma20)
    rvol_confirmed = not pd.isna(rvol) and rvol >= 1.2
    macd_bullish = not pd.isna(dif) and not pd.isna(dea) and dif > dea
    hist_positive = not pd.isna(hist) and hist > 0
    near_ma = _is_near_ma(c, ma5, ma10)
    pullback_from_high = d["pullback_from_recent_high"]
    is_breakout = d["is_breakout"]

    # 1. 健康回踩
    if (near_ma and pullback_from_high
            and not pd.isna(ma20) and c > ma20
            and not pd.isna(rvol) and rvol < 1
            and not pd.isna(rsi) and 45 <= rsi <= 60
            and (macd_bullish or hist_positive or (
                not pd.isna(hist) and not pd.isna(ph) and hist > ph))):
        return "健康回踩买入"

    # 2. RSI 低位修复
    rsi_low_lookback = 10
    lookback_start = max(0, len(df) - 1 - rsi_low_lookback)
    lookback_end = len(df) - 1
    rsi_was_low = False
    if lookback_start < lookback_end:
        rsi_window = df["rsi"].iloc[lookback_start:lookback_end]
        rsi_was_low = any(not pd.isna(v) and v < rsi_threshold for v in rsi_window)
    if rsi_was_low and not pd.isna(rsi):
        return "RSI低位修复买入"

    # 3. 放量突破
    if (price_strong and rvol_confirmed and macd_bullish and hist_positive
            and not pd.isna(rsi) and rsi < 70):
        return "放量突破买入"

    return None


def _v_checklist(checklist: dict | None, df: pd.DataFrame, symbol: str,
                 d: dict) -> list[str]:
    warnings = []
    expected_scenario = derive_expected_buy_scenario(df, d, symbol)

    if checklist is not None:
        scenario = checklist.get("scenario", "")
        # 场景是否匹配预期
        if expected_scenario is not None and scenario != expected_scenario:
            warnings.append(_warn("买入清单",
                f'触发场景"{scenario}"',
                f'预期应为"{expected_scenario}"（优先级不同或场景检测有偏差）'))
        if expected_scenario is None:
            warnings.append(_warn("买入清单",
                f'触发场景"{scenario}"',
                "风险否决应已成立，买入清单不应出现"))

        # 逐条复算每个条件
        for cond in checklist.get("conditions", []):
            label = cond["label"]
            ok = cond["ok"]
            recheck = _recheck_condition(label, df, d, symbol)
            if recheck is not None and recheck != ok:
                warnings.append(_warn("买入清单",
                    f'"{label}" 显示{"✓" if ok else "✗"}',
                    f"重新计算应为{'✓' if recheck else '✗'}"))
    else:
        # checklist 为 None，检查是否应该有场景
        if expected_scenario is not None:
            warnings.append(_warn("买入清单",
                f"未显示买入清单",
                f'风险否决未触发，数据满足"{expected_scenario}"条件，应展示买入清单'))

    return warnings


def _recheck_condition(label: str, df: pd.DataFrame, d: dict, symbol: str) -> bool | None:
    """对单个买入清单条件做独立复算。返回 None 表示无法验证。"""
    label_canon = _canonical(label)

    if label_canon in ("曾入低位",):
        rsi_threshold = RSI_THRESHOLDS.get(symbol, 35)
        start_idx = max(0, len(df) - 1 - 10)
        end_idx = len(df) - 1
        if start_idx >= end_idx:
            return None
        rsi_window = df["rsi"].iloc[start_idx:end_idx]
        return any(not pd.isna(v) and v < rsi_threshold for v in rsi_window)

    if label_canon == "MACD 改善":
        hist, ph = d["hist"], d["prev_hist"]
        dif, dea = d["dif"], d["dea"]
        # 金叉: hist > 0 and prev_hist <= 0
        golden = (not pd.isna(hist) and hist > 0
                  and not pd.isna(ph) and ph <= 0)
        # 绿柱缩短: hist < 0 and hist > prev_hist
        green_shrinking = (not pd.isna(hist) and hist < 0
                           and not pd.isna(ph) and hist > ph)
        # 红柱放大: hist > 0 and hist > prev_hist
        red_growing = (not pd.isna(hist) and hist > 0
                       and not pd.isna(ph) and hist > ph)
        # DIF>DEA + 红柱为正
        dif_above_dea = (not pd.isna(dif) and not pd.isna(dea) and dif > dea
                         and not pd.isna(hist) and hist > 0)
        return golden or green_shrinking or red_growing or dif_above_dea

    if label_canon == "无量恐慌":
        # not (RVOL >= 1.2 and chg < 0)
        rvol, chg = d["rvol"], d["chg"]
        if pd.isna(rvol):
            return True  # 无数据 = 无量
        panic = rvol >= 1.2 and not pd.isna(chg) and chg < 0
        return not panic

    if label_canon in ("RSI 回升",):
        start_idx = max(0, len(df) - 1 - 10)
        lookback_rsi = df["rsi"].iloc[start_idx:len(df) - 1]
        min_rsi = lookback_rsi.min() if len(lookback_rsi) > 0 else np.nan
        if pd.isna(min_rsi) or pd.isna(d["rsi"]):
            return None
        return d["rsi"] > min_rsi

    if label_canon in ("骨架健康",):
        return bool(not pd.isna(d["close"]) and not pd.isna(d["ma20"])
                    and d["close"] > d["ma20"])

    if label_canon in ("靠近均线",):
        return bool(d["near_ma5_ma10"])

    if label_canon in ("回踩缩量",):
        return bool(not pd.isna(d["rvol"]) and d["rvol"] < 1)

    if label_canon in ("MACD 未转空",):
        dif, dea = d["dif"], d["dea"]
        hist, ph = d["hist"], d["prev_hist"]
        return bool(
            (not pd.isna(dif) and not pd.isna(dea) and dif > dea)
            or (not pd.isna(hist) and not pd.isna(ph) and hist > ph)
            or (not pd.isna(hist) and hist > 0)
        )

    if label_canon in ("放量确认",):
        return bool(not pd.isna(d["rvol"]) and d["rvol"] >= 1.2)

    if label_canon in ("MACD 偏多",):
        return bool(
            not pd.isna(d["dif"]) and not pd.isna(d["dea"]) and d["dif"] > d["dea"]
            and not pd.isna(d["hist"]) and d["hist"] > 0
        )

    if label_canon in ("突破前高",):
        return bool(d["is_breakout"])

    if label_canon in ("RSI 未过热",):
        return bool(not pd.isna(d["rsi"]) and d["rsi"] < 70)

    if label_canon in ("不远离均线",):
        # 用 MA10，偏离不超过 5%
        if pd.isna(d["ma10"]) or pd.isna(d["close"]):
            return None
        return bool(d["close"] / d["ma10"] < 1.05)

    if label_canon in ("回踩确认",):
        # 已废弃但保留复算：从近期高点回落
        return bool(d["pullback_from_recent_high"])

    if label_canon in ("价格从近期高点回落",):
        return bool(d["pullback_from_recent_high"])

    return None


# ══════════════════════════════════════════════
# 7. 操作理解文案 vs 状态标签 (Type B)
# ══════════════════════════════════════════════

EXPECTED_NOTE_KEYS = {"已持有", "新买入", "加仓", "风险警戒"}


def _v_position_notes(state_label: str, notes: dict, d: dict) -> list[str]:
    warnings = []
    keys = set(notes.keys())
    if keys != EXPECTED_NOTE_KEYS:
        missing = EXPECTED_NOTE_KEYS - keys
        extra = keys - EXPECTED_NOTE_KEYS
        if missing:
            warnings.append(_warn("操作理解", f'缺少键 {missing}', ""))
        if extra:
            warnings.append(_warn("操作理解", f'多余键 {extra}', ""))

    for key in EXPECTED_NOTE_KEYS:
        text = notes.get(key, "")
        if not text or len(text) < 5:
            warnings.append(_warn("操作理解",
                f'"{key}"文案过短或缺失', f'"{text}"'))

    danger_states = {"放量破位警戒", "短线放量转弱", "严重过热", "高位放量过热",
                     "弱势下行", "趋势偏弱", "弱势延续"}
    if state_label in danger_states:
        buy_note = notes.get("新买入", "")
        optimistic_words = ["可买入", "是买点", "适合买入", "可以买", "抓紧"]
        for w in optimistic_words:
            if w in buy_note:
                warnings.append(_warn("操作理解",
                    f'高风险状态"{state_label}"的新买入文案含乐观词"{w}"',
                    f'"{buy_note}"'))

    # 状态标签与预期不一致时，提示操作理解可能用错模板
    expected_state = derive_expected_state(d)
    if expected_state is not None and expected_state != state_label:
        warnings.append(_warn("操作理解",
            f'状态为"{state_label}"但数据推导应为"{expected_state}"',
            "操作理解可能使用了错误状态分支的文案"))

    return warnings


# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════

def _collect_text(analysis: dict, checklist: dict | None, reminders: list[str]) -> str:
    """收集断言性文案，用于关键词扫描。ok=False 的条件不作为正向断言。"""
    parts = [
        analysis.get("state_label", ""),
        analysis.get("one_liner", ""),
    ]
    for _name, _state, note in analysis.get("steps", []):
        parts.append(note)
    for v in analysis.get("position_notes", {}).values():
        parts.append(v)
    for item in analysis.get("next_watch", []):
        parts.append(item)
    for r in reminders:
        parts.append(r)
    if checklist:
        parts.append(checklist.get("scenario", ""))
        for c in checklist.get("conditions", []):
            if c["ok"]:
                parts.append(f"{c['label']} {c['ok_text']}")
            else:
                parts.append(f"未满足：{c['label']}")
    return " ".join(parts)


def _warn(category: str, claim: str, reality: str) -> str:
    return f"[{category}] 声称：{claim} → 实际：{reality}"


def fmt_warnings(warnings: list[str]) -> str:
    if not warnings:
        return ""
    strong = [w for w in warnings if not w.startswith("[弱提醒]")]
    weak = [w for w in warnings if w.startswith("[弱提醒]")]
    lines = ["", "  ⚠ 一致性检查", "  " + "-" * 48]
    for w in strong:
        lines.append(f"  {w}")
    if weak:
        lines.append("  " + "-" * 48)
        lines.append("  弱提醒（关键词扫描，可能存在自然语言误报）：")
        for w in weak:
            lines.append(f"  {w}")
    return "\n".join(lines)
