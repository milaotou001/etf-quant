"""市场状态面板 + 不做清单纪律提醒"""
import pandas as pd
import numpy as np
from indicators import sma, rsi, macd, bbands, adx
from instruments import InstrumentSpec, get_instrument
from etf_shares import SHARE_OBSERVATION_ENABLED

RSI_THRESHOLDS = {"563360": 35, "510300": 35, "518880": 30, "588000": 25, "513180": 30, "159920": 30}


def get_rsi_threshold(symbol: str = "563360") -> int:
    return RSI_THRESHOLDS.get(symbol, 35)


def compute_indicators(df: pd.DataFrame, instrument: InstrumentSpec | None = None) -> pd.DataFrame:
    """计算全部技术指标，返回带指标列的 DataFrame"""
    attrs = df.attrs.copy()
    base_cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    df = df[base_cols].copy()
    df.attrs.update(attrs)
    df["ma5"] = sma(df["close"], 5)
    df["ma10"] = sma(df["close"], 10)
    df["ma20"] = sma(df["close"], 20)
    df["ma60"] = sma(df["close"], 60)
    df["rsi"] = rsi(df["close"], 14)

    macd_df = macd(df["close"])
    df = pd.concat([df, macd_df], axis=1)

    bb_df = bbands(df["close"])
    df = pd.concat([df, bb_df], axis=1)

    adx_df = adx(df["high"], df["low"], df["close"])
    df = pd.concat([df, adx_df], axis=1)

    amount_verified = bool(attrs.get("amount_verified", "amount" in df.columns))
    has_verified_amount = (
        "amount" in df.columns
        and not df["amount"].dropna().empty
        and amount_verified
    )
    if has_verified_amount:
        df["amount_ma20"] = sma(df["amount"], 20)
        df["rvol"] = df["amount"] / df["amount_ma20"].replace(0, np.nan)
        df.attrs.update(attrs)
        df.attrs["rvol_available"] = True
        df.attrs["rvol_type"] = "成交额RVOL"
    else:
        df["amount_ma20"] = np.nan
        df["rvol"] = np.nan
        df.attrs.update(attrs)
        df.attrs["rvol_available"] = False
        df.attrs["rvol_type"] = "暂不可用"
        df.attrs["rvol_missing_reason"] = "缺少可验证的成交额数据"
    df["chg"] = df["close"].pct_change() * 100

    return df


# ── 列名查找 ──
def _col(df: pd.DataFrame, prefix: str) -> str:
    for c in df.columns:
        if c.startswith(prefix):
            return c
    return ""


def _macd_cols(df: pd.DataFrame) -> tuple[str, str, str]:
    return _col(df, "MACD_"), _col(df, "MACDs_"), _col(df, "MACDh_")


def _price_step(row: pd.Series, prev: pd.Series = None) -> tuple[str, str]:
    close = row["close"]
    ma5 = row["ma5"]
    ma10 = row["ma10"]
    ma20 = row["ma20"]
    mas = [("MA5", ma5), ("MA10", ma10), ("MA20", ma20)]
    valid = [(name, value) for name, value in mas if not pd.isna(value)]
    above = [name for name, value in valid if close > value]
    below = [name for name, value in valid if close <= value]

    if len(valid) < 3:
        state = "样本不足"
        note = "均线样本不足，先不判断价格结构。"
    elif close > ma5 > ma10 > ma20:
        state = "多头排列"
        note = "收盘价站上 MA5/10/20，且 MA5 > MA10 > MA20，短期趋势偏强；继续看量能是否确认。"
    elif close > ma5 and close > ma10 and close > ma20:
        state = "均线上方"
        note = "收盘价在 MA5/10/20 上方，结构偏强，但均线排序还不是完整多头。"
    elif close < ma10 and close > ma20:
        state = "回踩区间"
        note = "收盘价跌破 MA10 但仍在 MA20 上方，属于短线回落，重点看 MA20 附近能否稳住。"
    elif close < ma20:
        # 区分刚跌破 vs 持续在下方
        if prev is not None and not pd.isna(prev["ma20"]) and prev["close"] >= prev["ma20"]:
            state = "跌破MA20"
            note = "收盘价今日跌破 MA20，中期参考位转弱，先进入风险观察。"
        else:
            state = "MA20下方"
            note = "收盘价持续在 MA20 下方运行，中期参考位偏弱，先观察止跌和修复。"
    else:
        state = "均线之间"
        note = f"价格夹在短均线之间，高于 {'/'.join(above) if above else '无'}，低于 {'/'.join(below) if below else '无'}，短期方向还不干净。"

    detail = " | ".join(f"{name} {value:.4f}" for name, value in valid)
    return state, f"{note} ({detail})"


def _rvol_step(row: pd.Series, df: pd.DataFrame = None) -> tuple[str, str]:
    rvol = row["rvol"] if "rvol" in row.index and not pd.isna(row["rvol"]) else np.nan
    chg = row["chg"]
    rvol_label = "RVOL"
    if df is not None and df.attrs.get("rvol_type"):
        rvol_label = df.attrs["rvol_type"]
    if pd.isna(rvol):
        return "暂不可用", "缺少可验证的成交额数据，RVOL 暂不可用，本项不参与正式观察。"

    if rvol < 0.7:
        state = "明显缩量"
        if chg < 0:
            note = "明显缩量下跌，未出现恐慌抛售，但趋势仍弱，等止跌信号。"
        else:
            note = "明显缩量，价格变化缺少量能确认；上涨可以存在，但不是高质量放量突破，后续若要确认突破，最好看到 RVOL > 1.2。"
    elif rvol < 1.0:
        state = "偏缩量"
        if chg < 0:
            note = "偏缩量下跌，资金出逃压力不大，但趋势偏弱，先等止跌。"
        else:
            note = "偏缩量，趋势可以存在，但资金确认不强；上涨可以存在，但不是高质量放量突破，后续若要确认突破，最好看到 RVOL > 1.2。"
    elif rvol < 1.2:
        state = "正常量"
        if chg < 0:
            note = "量能正常，下跌有一定卖压但不极端，继续观察。"
        else:
            note = "量能正常，价格变化没有明显异常成交量；若要确认突破，最好看到 RVOL > 1.2。"
    elif rvol < 1.5:
        state = "温和放量"
        direction = "上涨" if chg >= 0 else "下跌"
        note = f"温和放量{direction}，有一定资金/情绪参与，但还不算强确认。"
    elif rvol < 2.0:
        state = "明显放量"
        direction = "上涨" if chg >= 0 else "下跌"
        note = f"明显放量{direction}，说明今天的价格变化有资金/情绪参与；只作确认，不作买入条件。"
    else:
        state = "异常放量"
        direction = "上涨" if chg >= 0 else "下跌"
        note = f"异常放量{direction}，情绪和噪音都很大，先分辨是恐慌、抢筹还是消息驱动。"

    return state, f"{rvol_label} {rvol:.2f}，{note}"


def _macd_step(row: pd.Series, prev: pd.Series, df: pd.DataFrame) -> tuple[str, str]:
    macd_col, signal_col, hist_col = _macd_cols(df)
    if not macd_col or not signal_col or not hist_col:
        return "样本不足", "MACD 暂无足够样本。"

    hist = row[hist_col]
    prev_hist = prev[hist_col] if prev is not None else np.nan
    macd_val = row[macd_col]
    signal_val = row[signal_col]
    if pd.isna(hist) or pd.isna(prev_hist):
        return "样本不足", "MACD 暂无足够样本。"

    if hist > 0 and prev_hist < 0:
        state = "金叉"
        note = "DIF 上穿 DEA 形成金叉，趋势转多信号，关注是否持续。"
    elif hist > 0 and hist > prev_hist:
        state = "红柱放大"
        note = "上涨动能增强。"
    elif hist > 0:
        state = "红柱为正"
        note = "上涨动能占优，但没有继续增强。"
        # DIF 回落逼近 DEA → 预警死叉风险
        if prev is not None:
            prev_dif = prev[macd_col] if macd_col else np.nan
            if not pd.isna(prev_dif) and macd_val < prev_dif and (macd_val - signal_val) < 0.001:
                note += " DIF 快速回落逼近 DEA，关注是否死叉。"
    elif hist < 0 and prev_hist > 0:
        state = "死叉"
        note = f"DIF 下穿 DEA 形成死叉，趋势转弱信号，关注是否持续。"
    elif hist < 0 and hist > prev_hist:
        state = "绿柱缩短"
        note = "下跌动能衰弱。"
    elif hist < 0:
        state = "绿柱放大"
        note = "下跌动能增强。"
    else:
        state = "零轴附近"
        note = "动能接近平衡，方向确认不足。"

    return state, f"DIF {macd_val:+.4f} / DEA {signal_val:+.4f} / HIST {hist:+.4f}，{note}"


def _rsi_market_step(row: pd.Series) -> tuple[str, str]:
    value = row["rsi"]
    if pd.isna(value):
        return "样本不足", "RSI 暂无足够样本。"

    if value >= 80:
        return "严重过热", f"RSI {value:.0f} 严重过热，位置偏热，追涨风险较高。"
    if value >= 70:
        return "偏热", f"RSI {value:.0f} 偏热，趋势仍可能强，但不适合追涨。"
    if value >= 50:
        return "正常偏强", f"RSI {value:.0f} 正常偏强，暂未过热。"
    if value >= 45:
        return "正常", f"RSI {value:.0f} 中性偏正常，冷热程度不极端。"
    return "偏弱", f"RSI {value:.0f} 偏弱，说明价格动能仍需观察。"


def _scan_steps(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    price_state, price_note = _price_step(latest, prev)
    rvol_state, rvol_note = _rvol_step(latest, df)
    macd_state, macd_note = _macd_step(latest, prev, df)
    rsi_state, rsi_note = _rsi_market_step(latest)
    return [
        ("价格位置", price_state, price_note),
        ("RVOL", rvol_state, rvol_note),
        ("MACD", macd_state, macd_note),
        ("RSI", rsi_state, rsi_note),
    ]


def _observation_summary(steps: list[tuple[str, str, str]]) -> str:
    return "；".join(f"{name}[{state}]" for name, state, _ in steps)


def _latest_states(steps: list[tuple[str, str, str]]) -> dict[str, str]:
    return {name: state for name, state, _ in steps}


def _classify_market_state(df: pd.DataFrame, steps: list[tuple[str, str, str]]) -> tuple[str, str]:
    states = _latest_states(steps)
    latest = df.iloc[-1]
    price = states.get("价格位置", "")
    prev = df.iloc[-2] if len(df) >= 2 else None
    macd_col, signal_col, hist_col = _macd_cols(df)
    close = latest["close"]
    ma5 = latest["ma5"]
    ma10 = latest["ma10"]
    ma20 = latest["ma20"]
    rvol_value = latest["rvol"] if "rvol" in latest.index and not pd.isna(latest["rvol"]) else np.nan
    rsi_value = latest["rsi"]
    chg = latest["chg"] if "chg" in latest.index and not pd.isna(latest["chg"]) else 0
    dif = latest[macd_col] if macd_col else np.nan
    dea = latest[signal_col] if signal_col else np.nan
    hist = latest[hist_col] if hist_col else np.nan
    prev_hist = prev[hist_col] if prev is not None and hist_col else np.nan
    prev_close = prev["close"] if prev is not None else np.nan

    price_strong = price in ("多头排列", "均线上方")
    rvol_confirmed = not pd.isna(rvol_value) and rvol_value >= 1.2
    rvol_quiet = not pd.isna(rvol_value) and rvol_value < 1
    macd_bullish = not pd.isna(dif) and not pd.isna(dea) and dif > dea
    hist_positive = not pd.isna(hist) and hist > 0
    hist_negative_and_growing = not pd.isna(hist) and hist < 0 and not pd.isna(prev_hist) and hist <= prev_hist
    hist_shrinking = not pd.isna(hist) and not pd.isna(prev_hist) and hist > prev_hist
    macd_not_obviously_bearish = macd_bullish or hist_positive or hist_shrinking
    macd_green_shrinking_or_red = hist_positive or (not pd.isna(hist) and hist < 0 and hist > prev_hist)

    near_ma5_ma10 = (
        (not pd.isna(ma5) and abs(close / ma5 - 1) <= 0.01)
        or (not pd.isna(ma10) and abs(close / ma10 - 1) <= 0.01)
    )
    is_pullback = chg < 0 or (not pd.isna(prev_close) and close < prev_close)
    recent_high_5 = df["close"].iloc[-6:-1].max()
    pullback_from_recent_high = close < recent_high_5 * 0.99
    is_healthy_pullback = near_ma5_ma10 and is_pullback and pullback_from_recent_high

    recent_high_20 = df["close"].iloc[-21:-1].max()
    is_breakout = close > recent_high_20

    # ── 优先级从高到低 ──

    # 1. 放量破位（MA20在前，避免被MA10子句抢先）
    if close < ma20 and rvol_confirmed and chg < 0:
        return "放量破位警戒", "价格跌破 MA20 且成交量放大，中短期趋势可能被破坏。"
    if close < ma10 and rvol_confirmed and chg < 0:
        return "短线放量转弱", "价格跌破 MA10 且成交量放大，短线结构开始转弱；继续观察 MA20 是否守住。"

    # 2. 高位过热（三级细分）
    if price_strong and not pd.isna(rsi_value) and rsi_value >= 80:
        return "严重过热", "RSI 严重过热，当前位置不适合任何新增操作，追涨风险极高。"
    if price_strong and not pd.isna(rsi_value) and rsi_value >= 70 and rvol_confirmed:
        return "高位放量过热", "RSI 偏热且放量，趋势可能仍强但位置偏高、情绪参与度高，不适合追涨。"
    if price_strong and not pd.isna(rsi_value) and rsi_value >= 70:
        return "偏热强势", "趋势仍可能强，但位置偏热，不适合追涨。"

    # 3. 强势放量（有突破前高才叫突破）
    if price_strong and rvol_confirmed and macd_bullish and hist_positive and rsi_value < 70:
        if is_breakout:
            return "强势放量突破", "趋势偏强，量能确认，动能配合，突破近期前高，重点观察能否站稳。"
        return "强势放量", "趋势偏强，量能确认，动能配合，但未突破近期前高，观察能否进一步突破。"

    # 4. 缩量偏强
    if price_strong and rvol_quiet and macd_bullish and rsi_value < 70:
        return "缩量偏强", "趋势偏强，MACD偏多，RSI正常，但RVOL偏低，量能确认不足；适合持有观察，不追涨，等放量突破或缩量回踩。"

    # 5. 健康回踩（必须满足回踩条件）
    if is_healthy_pullback and close > ma20 and rvol_quiet and 45 <= rsi_value <= 60 and macd_not_obviously_bearish:
        return "健康回踩", "趋势回踩但量能不大，观察是否缩量不破。"

    # 6. MA20 下方：弱势下行 / 趋势偏弱
    if close < ma20 and hist_negative_and_growing:
        # 区分死叉首日 vs 绿柱持续放大
        is_death_cross = not pd.isna(prev_hist) and prev_hist > 0
        if is_death_cross:
            if not pd.isna(rsi_value) and rsi_value < 45:
                return "弱势下行", "价格在 MA20 下方，DIF 下穿 DEA 形成死叉，趋势转弱；RSI 偏低叠加死叉，弱势确认，先等止跌。"
            return "弱势下行", "价格在 MA20 下方，DIF 下穿 DEA 形成死叉，趋势转弱；死叉确认弱势，先等止跌，不急于判断底部。"
        if not pd.isna(rsi_value) and rsi_value < 45:
            return "弱势下行", "价格在 MA20 下方，MACD 绿柱继续放大，下跌动能仍在增强；RSI 偏低，但先观察止跌和趋势修复，不因 RSI 低就直接买。"
        return "弱势下行", "价格在 MA20 下方，MACD 绿柱继续放大，下跌动能仍在增强；先观察止跌和趋势修复，不急于判断底部。"
    # 7. 尝试修复（MA20下方收涨 + MACD改善）— 优先于趋势偏弱
    if close < ma20 and chg > 0 and macd_green_shrinking_or_red:
        return "尝试修复", "价格仍在 MA20 下方但 MACD 在改善，先看能否持续修复并站回 MA20。"

    if close < ma20 and not pd.isna(dif) and not pd.isna(dea) and dif < dea:
        return "趋势偏弱", "价格在 MA20 下方，趋势尚未修复，先观察能否站回 MA20。"

    # 8. 弱势延续（MA20下方收跌，但MACD未到弱势下行程度）
    if close < ma20 and chg < 0:
        return "弱势延续", "价格在 MA20 下方继续走弱，MACD 尚未明显恶化，但趋势偏弱，先观察止跌。"

    return "中性观察", "价格、RVOL、MACD、RSI 没有形成清晰共振，按固定顺序继续观察。"


def _position_notes(state_label: str, states: dict[str, str]) -> dict[str, str]:
    notes = {
        "已持有": "按当前结构继续观察，重点看价格、RVOL、MACD 和 RSI 是否继续同向确认。",
        "新买入": "当前没有清晰结构确认，先按看盘顺序观察，不因为单一指标动作。",
        "加仓": "没有形成明确加仓观察条件前，不因单日波动临时加仓。",
        "风险警戒": "若价格跌破关键均线且 RVOL 放大，需要提高观察级别。",
    }

    if state_label == "强势放量突破" or state_label == "强势放量":
        notes["已持有"] = "趋势、量能和动能配合，适合观察能否站稳突破位。" if state_label == "强势放量突破" else "趋势、量能和动能偏强，但未突破前高，观察后续方向。"
        notes["新买入"] = "可列为重点观察，但不等于立即买入；先看能否站稳突破位。" if state_label == "强势放量突破" else "可列为重点观察，但未突破前高，先不追涨。"
        notes["加仓"] = "已有计划时可观察，不要因单日放量冲动加仓。"
        notes["风险警戒"] = "若次日缩量跌回突破位，或 RSI 接近 70 后继续冲高，需要提高追涨风险警戒。" if state_label == "强势放量突破" else "若放量后动能不能持续，或 RSI 接近 70，需要提高观察级别。"
    elif state_label == "缩量偏强":
        notes["已持有"] = "结构还偏强，但量能确认不足，适合持有观察；重点看后续是否补量突破，或缩量回踩 MA5/MA10 不破。"
        notes["新买入"] = "当前价格结构偏强，但 RVOL 偏低，说明上涨缺少量能确认。不建议直接追涨。更合适的观察点是：放量突破，或回踩 MA5 / MA10 缩量不破。"
        notes["加仓"] = "当前不适合因为价格上涨就直接加仓。更好的加仓条件有两个：放量突破：价格突破前高，且 RVOL > 1.2；缩量回踩：价格回踩 MA5 / MA10 不破，且 RVOL < 1。"
        notes["风险警戒"] = "如果价格跌破 MA10 且 RVOL 放大，说明短线结构开始转弱；如果进一步跌破 MA20，说明中短期趋势可能被破坏；如果同时出现 MACD红柱缩短或死叉，需要提高风险警戒。"
    elif state_label == "健康回踩":
        notes["已持有"] = "回踩仍在 MA20 上方且量能不大，重点看 MA5/MA10 是否守住。"
        notes["新买入"] = "若回踩 MA5/MA10 不破且缩量，可作为观察点。"
        notes["加仓"] = "看回踩是否缩量、MACD 是否未明显转空。"
        notes["风险警戒"] = "若回踩变成放量跌破 MA10 或 MA20，健康回踩逻辑失效。"
    elif state_label == "严重过热":
        notes["新买入"] = "RSI 严重过热，完全不适合新增仓位。"
        notes["加仓"] = "绝对不适合加仓，等待 RSI 明显降温再说。"
        notes["风险警戒"] = "严重过热时任何买入都是在接飞刀，管住手。"
    elif state_label == "高位放量过热":
        notes["新买入"] = "当前位置不适合新增仓位追高，放量偏热说明情绪参与度高。"
        notes["加仓"] = "等待 RSI 降温且 RVOL 回落，当前不追。"
        notes["风险警戒"] = "放量+高位过热，注意放量滞涨、长上影等转弱信号。"
    elif state_label == "偏热强势":
        notes["新买入"] = "当前位置不适合新增仓位追高。"
        notes["加仓"] = "等待 RSI 降温或价格回到更可评估的位置。"
        notes["风险警戒"] = "关注放量滞涨、长上影、跌破 MA5/MA10 等短线转弱信号。"
    elif state_label == "短线放量转弱":
        notes["已持有"] = "短线结构开始转弱，重点观察 MA20 是否守住。"
        notes["新买入"] = "当前只做风险观察，不给新买入动作。"
        notes["加仓"] = "当前不适合加仓，先看放量下跌是否延续。"
        notes["风险警戒"] = "若继续放量并跌破 MA20，中短期结构可能进一步走坏。"
    elif state_label == "放量破位警戒":
        notes["已持有"] = "风险观察级别升高，重点看 MA20 能否重新站回，以及放量是否延续。"
        notes["新买入"] = "当前只做风险观察，不给新买入动作。"
        notes["加仓"] = "当前不适合加仓，先看价格能否重新站回 MA20。"
        notes["风险警戒"] = "跌破 MA20 且放量，说明中短期趋势可能被破坏。"
    elif state_label == "弱势下行":
        is_death_cross = states.get("MACD", "") == "死叉"
        rsi_is_low = states.get("RSI", "") == "偏弱"
        if is_death_cross:
            notes["新买入"] = "DIF 刚下穿 DEA 形成死叉，趋势转弱信号明确，先不接飞刀。"
            notes["加仓"] = "当前不适合加仓，等死叉消化、MACD 绿柱缩短或价格重新站回 MA20。"
            if rsi_is_low:
                notes["已持有"] = "DIF 刚死叉，弱势信号叠加 RSI 低位，先观察止跌，不急于补仓。"
                notes["风险警戒"] = "死叉叠加 RSI 低位，弱势结构加强，注意越跌越补的陷阱。"
            else:
                notes["已持有"] = "DIF 刚死叉，趋势转弱信号明确，先观察止跌，等 MACD 绿柱缩短再评估。"
                notes["风险警戒"] = "死叉确认弱势结构，趋势转弱初期注意越跌越补的陷阱。"
        else:
            notes["新买入"] = "MACD 绿柱继续放大，下跌趋势未止，先不接飞刀。"
            notes["加仓"] = "当前不适合加仓，等 MACD 绿柱缩短或价格重新站回 MA20。"
            if rsi_is_low:
                notes["已持有"] = "下跌动能仍在增强，先观察止跌信号，不因 RSI 低位就急于补仓。"
                notes["风险警戒"] = "弱势下行叠加 RSI 低位钝化风险，注意越跌越补的陷阱。"
            else:
                notes["已持有"] = "下跌动能仍在增强，先观察止跌信号，等 MACD 绿柱缩短再评估。"
                notes["风险警戒"] = "弱势下行趋势未止，注意越跌越补的陷阱，等止跌确认再动作。"
    elif state_label == "趋势偏弱":
        notes["已持有"] = "价格在 MA20 下方、趋势尚未修复，先观察能否站回 MA20。"
        notes["新买入"] = "趋势偏弱时先不买，等价格重新回到 MA20 上方再评估。"
        notes["加仓"] = "先看 MA20 是否收复，再看 DIF/DEA 是否改善。"
        notes["风险警戒"] = "趋势偏弱时如有 RSI 低位，注意区分是机会还是趋势延续。"
    elif state_label == "弱势延续":
        notes["已持有"] = "价格在 MA20 下方继续走弱，MACD 尚未明显恶化但趋势偏弱，先观察止跌。"
        notes["新买入"] = "弱势延续中先不买，等止跌或重新站回 MA20 再评估。"
        notes["加仓"] = "当前不适合加仓，等价格止跌且 MACD 改善。"
        macd_state = states.get("MACD", "")
        if "绿柱" in macd_state:
            notes["风险警戒"] = "若继续走弱且 MACD 绿柱放大，可能进入弱势下行。"
        else:
            notes["风险警戒"] = "价格在 MA20 下方，若 MACD 红柱转为绿柱，调整可能加深。"
    elif state_label == "尝试修复":
        notes["已持有"] = "MACD 在改善但价格仍在 MA20 下方，修复不等于趋势反转，先看能否站回 MA20。"
        notes["新买入"] = "尝试修复只列入观察，等价格重新站回 MA20 再做判断。"
        notes["加仓"] = "先看 MA20 是否收复，再看 RVOL 和 MACD 是否继续改善。"
        notes["风险警戒"] = "若修复无量或再次跌回，弱势结构仍未改变。"
    return notes


def _next_watch_items(state_label: str, states: dict[str, str]) -> list[str]:
    macd_state = states.get("MACD", "")
    rsi_state = states.get("RSI", "")

    if state_label == "缩量偏强":
        rsi_note = (
            "RSI 当前正常偏强，暂未过热，不需要等待 RSI 低位才观察。"
            if rsi_state == "正常偏强"
            else f"RSI 当前{rsi_state}，继续按价格、RVOL、MACD 结构观察。"
        )
        return [
            "看是否放量突破，最好 RVOL > 1.2。",
            "看是否回踩 MA5/MA10 时缩量不破。",
            rsi_note,
        ]
    if state_label == "强势放量突破":
        return [
            "看能否站稳突破位。",
            "看次日是否缩量跌回。",
            "RSI 若接近 70 以上，避免追涨。",
        ]
    if state_label == "强势放量":
        return [
            "看能否突破近期前高。",
            "看次日是否缩量跌回。",
            "RSI 若接近 70 以上，避免追涨。",
        ]
    if state_label in ("偏热强势", "高位放量过热", "严重过热"):
        return [
            "等 RSI 降温。",
            "看是否出现放量滞涨、长上影或跌破 MA5/MA10。",
        ]
    if state_label == "短线放量转弱":
        return [
            "看 MA20 是否守住。",
            "看 RVOL 是否继续放大。",
            "看 MACD HIST 是否缩短或死叉。",
        ]
    if state_label == "健康回踩":
        return [
            "看 MA5/MA10 是否守住。",
            "看 RVOL 是否继续低于 1。",
            "看 MACD 是否避免明显转空。",
        ]
    if state_label == "弱势下行":
        is_death_cross = states.get("MACD", "") == "死叉"
        rsi_is_low = states.get("RSI", "") == "偏弱"
        if is_death_cross:
            items = [
                "看死叉是否持续（次日 HIST 是否继续走负）。",
                "看价格是否出现止跌信号。",
            ]
        else:
            items = [
                "看 MACD 绿柱是否开始缩短。",
                "看价格是否出现止跌信号。",
            ]
        if rsi_is_low:
            items.append("不因 RSI 低位就急于判断底部。")
        else:
            items.append("等 MACD 绿柱缩短或价格止跌，再做判断。")
        return items
    if state_label == "趋势偏弱":
        return [
            "看能否站回 MA20。",
            "看 DIF/DEA 是否改善。",
        ]
    if state_label == "弱势延续":
        macd_state = states.get("MACD", "")
        if "绿柱" in macd_state:
            macd_item = "看 MACD 绿柱是否继续放大。"
        else:
            macd_item = "看 MACD 红柱能否持续，若转绿柱则调整信号更强。"
        return [
            "看是否出现止跌信号。",
            macd_item,
            "不因单日下跌就恐慌操作。",
        ]
    if state_label == "尝试修复":
        return [
            "看能否站回 MA20。",
            "看 MACD 改善是否延续。",
            "看 RVOL 是否支持修复。",
        ]
    if state_label == "放量破位警戒":
        return [
            "看能否重新站回 MA20。",
            "看 RVOL 是否继续放大。",
            "看 MACD HIST 是否继续转弱。",
        ]
    return [
        "继续按价格、RVOL、MACD、RSI 顺序观察。",
        f"当前 MACD 状态为{macd_state}，观察动能是否进一步明确。",
        f"当前 RSI 状态为{rsi_state}，观察是否过热或转弱。",
    ]


def build_market_analysis(df: pd.DataFrame) -> dict:
    """构建 CLI 和 Streamlit 共用的状态化看盘分析。"""
    steps = _scan_steps(df)
    states = _latest_states(steps)
    state_label, one_liner = _classify_market_state(df, steps)
    return {
        "state_label": state_label,
        "one_liner": one_liner,
        "steps": steps,
        "summary": _observation_summary(steps),
        "position_notes": _position_notes(state_label, states),
        "next_watch": _next_watch_items(state_label, states),
    }


def build_rsi_cash_plan(df: pd.DataFrame, rsi_buy_threshold: int, buy_fraction: str = "1/3") -> list[str]:
    """RSI 低位现金池纪律提醒。只在 RSI 进入低位观察区时输出。"""
    latest = df.iloc[-1]
    value = latest["rsi"]
    if pd.isna(value) or value >= rsi_buy_threshold:
        return []

    prev_signal = None
    for i in range(len(df) - 2, -1, -1):
        prev_value = df["rsi"].iloc[i]
        if not pd.isna(prev_value) and prev_value < rsi_buy_threshold:
            prev_signal = df.index[i]
            break

    if prev_signal is None:
        interval_note = "此前无同类低位信号"
    else:
        days_since = (df.index[-1] - prev_signal).days
        interval_note = f"距上次低位信号 {days_since} 天"

    return [
        f"RSI={value:.0f} 进入低位观察区（阈值 {rsi_buy_threshold}），{interval_note}；可按现金池计划评估 {buy_fraction} 节奏。"
    ]


def build_campaign_observation(df: pd.DataFrame, instrument: InstrumentSpec) -> dict | None:
    """返回预设三段战役的观察事实，不生成交易指令。"""
    if not instrument.supports_campaign or len(df) < 2:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    rsi_val = latest.get("rsi", np.nan)
    hist_col = _col(df, "MACDh_")
    hist = latest.get(hist_col, np.nan) if hist_col else np.nan
    prev_hist = prev.get(hist_col, np.nan) if hist_col else np.nan
    macd_improving = not pd.isna(hist) and not pd.isna(prev_hist) and hist > prev_hist

    lookback = df["rsi"].iloc[max(0, len(df) - 30):]
    reached_second_entry = (lookback <= instrument.rsi_second_entry).any()
    first_observation = not pd.isna(rsi_val) and rsi_val <= instrument.rsi_first_entry
    second_observation = not pd.isna(rsi_val) and rsi_val <= instrument.rsi_second_entry
    right_confirmation = (
        reached_second_entry
        and not pd.isna(rsi_val)
        and rsi_val >= instrument.rsi_confirmation
        and macd_improving
    )

    if right_confirmation:
        phase = "右侧确认观察"
        summary = (
            f"RSI 已回到 {rsi_val:.0f}，MACD 动能较前一日改善；"
            "预设战役的右侧确认已出现，是否执行由达达结合市场背景决定。"
        )
    elif second_observation:
        phase = "第二观察位"
        summary = (
            f"RSI={rsi_val:.0f} 已进入第二观察位；"
            "总预算和批次保持预设，最后一笔继续等待右侧确认。"
        )
    elif first_observation:
        phase = "第一观察位"
        summary = (
            f"RSI={rsi_val:.0f} 已进入第一观察位；"
            "这是有限观察仓的条件，不改变本轮固定总预算。"
        )
    elif reached_second_entry:
        phase = "等待右侧确认"
        summary = (
            f"近期 RSI 曾进入第二观察位，当前 RSI={rsi_val:.0f}；"
            "最后一笔继续留在现金池，等待 RSI 回到确认线且 MACD 改善。"
        )
    else:
        phase = "等待观察位"
        summary = (
            f"当前 RSI={rsi_val:.0f}，尚未进入本标的的第一观察位 "
            f"({instrument.rsi_first_entry})。"
        )

    conditions = [
        {
            "label": "第一观察位",
            "ok": first_observation or reached_second_entry,
            "detail": f"RSI ≤ {instrument.rsi_first_entry}",
        },
        {
            "label": "第二观察位",
            "ok": reached_second_entry,
            "detail": f"RSI ≤ {instrument.rsi_second_entry}",
        },
        {
            "label": "右侧确认",
            "ok": right_confirmation,
            "detail": f"RSI ≥ {instrument.rsi_confirmation} 且 MACD 动能改善",
        },
    ]
    return {
        "phase": phase,
        "summary": summary,
        "conditions": conditions,
        "right_confirmation": right_confirmation,
    }


# ── 买入条件检查（三套场景） ──

# ── 统一风险否决 ──
def _risk_veto(close: float, ma20: float, ma60: float, rvol_val: float,
               rsi_val: float, dif: float, dea: float,
               hist: float, prev_hist: float, chg: float) -> str | None:
    """任一风险条件触发则返回否决原因，全部通过返回 None"""
    # 1. 放量破位
    if (not pd.isna(close) and not pd.isna(ma20) and close < ma20
            and not pd.isna(rvol_val) and rvol_val >= 1.2
            and not pd.isna(chg) and chg < 0):
        return f"放量破位：收盘跌破MA20，RVOL {rvol_val:.2f}，放量下跌，暂不展示买入清单"

    # 2. 弱势下行（绿柱放大）
    if (not pd.isna(close) and not pd.isna(ma20) and close < ma20
            and not pd.isna(hist) and not pd.isna(prev_hist)
            and hist < 0 and hist < prev_hist):
        return "弱势下行：收盘在MA20下方，MACD绿柱仍在放大，趋势未稳，暂不展示买入清单"

    # 3. 严重过热
    if not pd.isna(rsi_val) and rsi_val >= 80:
        return f"严重过热：RSI {rsi_val:.0f}，极端超买，暂不展示买入清单"

    # 4. 高位放量过热
    if (not pd.isna(rsi_val) and rsi_val >= 70
            and not pd.isna(rvol_val) and rvol_val >= 1.2):
        return f"高位放量过热：RSI {rsi_val:.0f} + RVOL {rvol_val:.2f}，追高风险大，暂不展示买入清单"

    # 5. MA60 下方趋势未修复
    if (not pd.isna(ma60) and not pd.isna(close) and close < ma60
            and not pd.isna(dif) and not pd.isna(dea) and dif < dea):
        return "MA60下方趋势未修复：收盘在MA60下方且DIF<DEA，中长期偏空，暂不展示买入清单"

    return None


def _make_cond(label: str, ok: bool, ok_text: str) -> dict:
    return {"label": label, "ok": ok, "ok_text": ok_text}


def build_buy_checklist(df: pd.DataFrame, rsi_buy_threshold: int, rsi_low_lookback: int = 10) -> dict | None:
    """根据当前状态自动选择买入场景，返回对应检查清单。
    优先级：健康回踩 → RSI低位修复 → 放量突破。风险否决优先于所有场景。"""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    macd_col, signal_col, hist_col = _macd_cols(df)

    close = latest["close"]
    ma5 = latest["ma5"]
    ma10 = latest["ma10"]
    ma20 = latest["ma20"]
    ma60 = latest["ma60"] if "ma60" in latest.index and not pd.isna(latest["ma60"]) else np.nan
    rsi_val = latest["rsi"]
    rvol_val = latest["rvol"] if "rvol" in latest.index and not pd.isna(latest["rvol"]) else np.nan
    chg = latest["chg"] if "chg" in latest.index and not pd.isna(latest["chg"]) else 0

    dif = latest[macd_col] if macd_col else np.nan
    dea = latest[signal_col] if signal_col else np.nan
    hist = latest[hist_col] if hist_col else np.nan
    prev_hist = prev[hist_col] if prev is not None and hist_col else np.nan

    # ═══ 统一风险否决 ═══
    veto = _risk_veto(close, ma20, ma60, rvol_val, rsi_val, dif, dea, hist, prev_hist, chg)
    if veto is not None:
        return None

    # ── 场景检测用变量 ──
    price_strong = not pd.isna(close) and not pd.isna(ma5) and not pd.isna(ma10) and not pd.isna(ma20) and (
        (close > ma5 > ma10 > ma20) or (close > ma5 and close > ma10 and close > ma20))
    rvol_confirmed = not pd.isna(rvol_val) and rvol_val >= 1.2
    macd_bullish = not pd.isna(dif) and not pd.isna(dea) and dif > dea
    hist_positive = not pd.isna(hist) and hist > 0
    near_ma5_ma10 = (
        (not pd.isna(ma5) and abs(close / ma5 - 1) <= 0.01)
        or (not pd.isna(ma10) and abs(close / ma10 - 1) <= 0.01))
    recent_high_5 = df["close"].iloc[-6:-1].max()
    pullback_from_recent_high = close < recent_high_5 * 0.99
    recent_high_20 = df["close"].iloc[-21:-1].max()
    is_breakout = close > recent_high_20

    # ═══ 场景选择（健康回踩 > RSI低位修复 > 放量突破） ═══

    # 1. 健康回踩（不再要求当日收跌）
    if (near_ma5_ma10 and pullback_from_recent_high
            and close > ma20
            and not pd.isna(rvol_val) and rvol_val < 1
            and not pd.isna(rsi_val) and 45 <= rsi_val <= 60
            and (macd_bullish or hist_positive or (not pd.isna(hist) and not pd.isna(prev_hist) and hist > prev_hist))):
        return _checklist_pullback(close, ma20, ma5, ma10, rvol_val, dif, dea, hist, prev_hist, rsi_val)

    # 2. RSI 低位修复：过去 N 日曾低位 + 当前修复确认
    lookback_start = max(0, len(df) - 1 - rsi_low_lookback)
    lookback_end = len(df) - 1  # 不含今天
    rsi_was_low = False
    if lookback_start < lookback_end:
        rsi_window = df["rsi"].iloc[lookback_start:lookback_end]
        rsi_was_low = any(not pd.isna(v) and v < rsi_buy_threshold for v in rsi_window)

    if rsi_was_low and not pd.isna(rsi_val):
        return _checklist_rsi_low_recovery(df, rsi_buy_threshold, rsi_low_lookback, rsi_val, close, ma20, dif, dea, hist, prev_hist, rvol_val)

    # 3. 放量突破
    if price_strong and rvol_confirmed and macd_bullish and hist_positive and not pd.isna(rsi_val) and rsi_val < 70:
        return _checklist_breakout(close, ma20, rvol_val, dif, dea, hist, rsi_val, is_breakout)

    return None


def _checklist_rsi_low_recovery(df, rsi_buy_threshold, rsi_low_lookback, rsi_val, close, ma20, dif, dea, hist, prev_hist, rvol_val):
    """RSI 低位修复买入条件检查：过去N日曾低位 + 当前修复确认"""
    green_shrinking = not pd.isna(hist) and not pd.isna(prev_hist) and hist < 0 and hist > prev_hist
    hist_turning_red = not pd.isna(hist) and not pd.isna(prev_hist) and hist > 0 and prev_hist <= 0
    hist_red_growing = not pd.isna(hist) and not pd.isna(prev_hist) and hist > 0 and hist > prev_hist
    macd_bullish = not pd.isna(dif) and not pd.isna(dea) and dif > dea
    macd_ok = green_shrinking or hist_turning_red or (macd_bullish and hist > 0)
    if hist_turning_red:
        macd_text = "MACD 已改善：金叉（绿转红）"
    elif green_shrinking:
        macd_text = "MACD 已改善：绿柱缩短，下跌衰竭"
    elif macd_bullish and hist_red_growing:
        macd_text = "MACD 已改善：红柱放大"
    elif macd_bullish and hist > 0:
        macd_text = "MACD 已改善：DIF>DEA，红柱为正"
    elif not pd.isna(hist) and hist < 0:
        macd_text = "MACD 未改善：绿柱仍在放大"
    else:
        macd_text = "MACD 已在零轴上方"

    panic_sell = not pd.isna(rvol_val) and rvol_val >= 1.2
    if pd.isna(rvol_val):
        rvol_text = "RVOL 暂不可用"
    elif not panic_sell:
        rvol_text = f"RVOL={rvol_val:.2f}，未出现放量恐慌抛售"
    else:
        rvol_text = f"RVOL={rvol_val:.2f}，放量中，注意是否恐慌"

    # RSI 回升：当前 RSI > 过去 N 日最低 RSI
    start_idx = max(0, len(df) - 1 - rsi_low_lookback)
    lookback_rsi = df["rsi"].iloc[start_idx:len(df) - 1]
    min_rsi_in_window = lookback_rsi.min() if len(lookback_rsi) > 0 else np.nan
    rsi_recovering = not pd.isna(min_rsi_in_window) and not pd.isna(rsi_val) and rsi_val > min_rsi_in_window
    if rsi_recovering:
        rsi_recovery_text = f"RSI 已从低位 {min_rsi_in_window:.0f} 回升至 {rsi_val:.0f}"
    elif not pd.isna(min_rsi_in_window):
        rsi_recovery_text = f"RSI={rsi_val:.0f}，仍在低位附近（近期最低 {min_rsi_in_window:.0f}），尚未回升"
    else:
        rsi_recovery_text = "RSI 回升情况暂无足够数据判断"

    conditions = [
        _make_cond("曾入低位", True, f"过去{rsi_low_lookback}日内RSI曾低于阈值{rsi_buy_threshold}，已进入修复观察期"),
        _make_cond("MACD 改善", macd_ok, macd_text),
        _make_cond("无量恐慌", not panic_sell, rvol_text),
        _make_cond("RSI 回升", rsi_recovering, rsi_recovery_text),
    ]
    met = sum(1 for c in conditions if c["ok"])
    return {
        "scenario": "RSI低位修复买入",
        "conditions": conditions,
        "met": met,
        "total": len(conditions),
        "progress": f"买入条件满足 {met}/{len(conditions)}",
    }


def _checklist_pullback(close, ma20, ma5, ma10, rvol_val, dif, dea, hist, prev_hist, rsi_val):
    """健康回踩买入条件检查：近期从高点回落 + 靠近均线 + 缩量"""
    price_ok = close > ma20
    price_text = f"收盘 {close:.4f} 在 MA20（{ma20:.4f}）上方" if price_ok else f"收盘 {close:.4f} 跌破 MA20"

    near_ma = (abs(close / ma5 - 1) <= 0.01 or abs(close / ma10 - 1) <= 0.01) if not pd.isna(ma5) and not pd.isna(ma10) else False
    near_text = f"价格接近 MA5（{ma5:.4f}）或 MA10（{ma10:.4f}）" if near_ma else "价格未靠近 MA5/MA10"

    rvol_ok = not pd.isna(rvol_val) and rvol_val < 1
    if pd.isna(rvol_val):
        rvol_text = "RVOL 暂不可用"
    elif rvol_ok:
        rvol_text = f"RVOL={rvol_val:.2f}，回踩缩量"
    else:
        rvol_text = f"RVOL={rvol_val:.2f}，回踩未缩量"

    macd_not_bearish = (not pd.isna(dif) and not pd.isna(dea) and dif > dea) or (not pd.isna(hist) and not pd.isna(prev_hist) and hist > prev_hist) or (not pd.isna(hist) and hist > 0)
    if macd_not_bearish:
        macd_text = "MACD 未明显转空"
    elif not pd.isna(hist) and hist < 0:
        macd_text = "MACD 绿柱，动能偏弱"
    else:
        macd_text = "MACD 状态一般"

    conditions = [
        _make_cond("骨架健康", price_ok, price_text),
        _make_cond("靠近均线", near_ma, near_text),
        _make_cond("回踩缩量", rvol_ok, rvol_text),
        _make_cond("MACD 未转空", macd_not_bearish, macd_text),
    ]
    met = sum(1 for c in conditions if c["ok"])
    return {
        "scenario": "健康回踩买入",
        "conditions": conditions,
        "met": met,
        "total": len(conditions),
        "progress": f"买入条件满足 {met}/{len(conditions)}",
    }


def _checklist_breakout(close, ma20, rvol_val, dif, dea, hist, rsi_val, is_breakout):
    """放量突破买入条件检查：真突破 + 不过热 + 不远离均线"""
    price_ok = close > ma20
    price_text = f"收盘 {close:.4f} 在 MA20（{ma20:.4f}）上方" if price_ok else "价格未站上 MA20"

    rvol_ok = not pd.isna(rvol_val) and rvol_val >= 1.2
    rvol_text = f"RVOL={rvol_val:.2f}，放量" if rvol_ok else f"RVOL={rvol_val:.2f}，未放量"

    macd_ok = not pd.isna(dif) and not pd.isna(dea) and dif > dea and not pd.isna(hist) and hist > 0
    macd_text = f"DIF {dif:+.4f} > DEA {dea:+.4f}，红柱，动能偏多" if macd_ok else "MACD 不够强"

    breakout_ok = is_breakout
    breakout_text = f"收盘 {close:.4f} 突破 20 日前高" if breakout_ok else f"收盘 {close:.4f} 未突破 20 日前高"

    rsi_ok = not pd.isna(rsi_val) and rsi_val < 70
    rsi_text = f"RSI={rsi_val:.0f}，未过热" if rsi_ok else f"RSI={rsi_val:.0f}，已过热"

    not_far = not pd.isna(ma20) and close / ma20 < 1.05
    far_pct = (close / ma20 - 1) * 100 if not pd.isna(ma20) else 0
    far_text = f"偏离MA20 {far_pct:+.1f}%，未远离均线" if not_far else f"偏离MA20 {far_pct:+.1f}%，距离过大，回调风险高"

    conditions = [
        _make_cond("骨架健康", price_ok, price_text),
        _make_cond("放量确认", rvol_ok, rvol_text),
        _make_cond("MACD 偏多", macd_ok, macd_text),
        _make_cond("突破前高", breakout_ok, breakout_text),
        _make_cond("RSI 未过热", rsi_ok, rsi_text),
        _make_cond("不远离均线", not_far, far_text),
    ]
    met = sum(1 for c in conditions if c["ok"])
    return {
        "scenario": "放量突破买入",
        "conditions": conditions,
        "met": met,
        "total": len(conditions),
        "progress": f"买入条件满足 {met}/{len(conditions)}",
    }


# ── 纪律提醒 ──
def _personalized_warnings(row: pd.Series, df: pd.DataFrame) -> list[str]:
    """达达专属提醒 — 多条件叠加，只在真正危险时触发（触发率目标10-20%）"""
    warnings = []
    close = row["close"]
    rsi_val = row["rsi"] if "rsi" in row.index and not pd.isna(row["rsi"]) else None
    chg_val = row["chg"] if "chg" in row.index and not pd.isna(row["chg"]) else 0
    hist_cols = [c for c in df.columns if c.startswith("MACDh_")]
    hist_val = row[hist_cols[0]] if hist_cols and not pd.isna(row[hist_cols[0]]) else None

    all_time_high = df["close"].max()
    ath_ratio = close / all_time_high if all_time_high > 0 else 0

    if len(df) >= 30:
        lookback = min(90, len(df))
        recent = df["close"].iloc[-lookback:]
        price_high = recent.max()
        price_low = recent.min()
        price_range = price_high - price_low
        pct_rank = (close - price_low) / price_range if price_range > 0 else 0.5
    else:
        pct_rank = 0.5

    # ── 重构规则：所有警告至少需要 价格位置 + 动量/情绪 双条件叠加 ──
    # 回测教训：单条件触发率太高（黄金79%），且牛市里"价格高位"反而收益更好

    price_extreme = pct_rank >= 0.85 or ath_ratio >= 0.95
    price_elevated = pct_rank >= 0.75 and ath_ratio >= 0.90
    momentum_warn = (rsi_val and rsi_val >= 65) or (hist_val and hist_val > 0)

    if not price_extreme and not price_elevated:
        # 价格不在危险区，只保留大涨日紧急拦截
        if chg_val > 3.0 and (pct_rank >= 0.85 or ath_ratio >= 0.95):
            warnings.append(
                f"⚠ 错题本：今日+{chg_val:.1f}%暴涨，价格在90日{int(pct_rank*100)}%分位。"
                f"高位大涨日最危险——你洛阳钼业买在21.27就是+6.1%大涨日。冷静，等明天。"
            )
        return warnings

    # ── 价格在危险区 + 动量确认 = 触发警告 ──
    if price_extreme and momentum_warn:
        # 最强：极端价格 + 过热信号
        ath_pct = (1 - ath_ratio) * 100
        if ath_ratio >= 0.95 and (rsi_val and rsi_val >= 70):
            warnings.append(
                f"⚠ 错题本：价格距全历史最高仅{ath_pct:.0f}%，RSI={rsi_val:.0f}严重过热。"
                f"洛阳钼业买在24.84全历史最高——后来跌了34%。管住手。"
            )
        elif ath_ratio >= 0.95:
            # 黄金10.92案例：RSI不高但价格在历史最高附近
            warnings.append(
                f"⚠ 错题本：价格距全历史最高仅{ath_pct:.0f}%，90日{int(pct_rank*100)}%分位。"
                f"黄金买在10.92时RSI才57，但它是历史最高——之后再没回去。现在很像。"
            )
        elif pct_rank >= 0.85:
            warnings.append(
                f"⚠ 错题本：价格在90日{int(pct_rank*100)}%分位，"
                f"{'RSI='+str(int(rsi_val)) if rsi_val else ''}{'红柱' if hist_val and hist_val > 0 else ''}。"
                f"你历史上所有大亏都起源于高位加仓。等回落。"
            )

    elif price_elevated and momentum_warn:
        # 次强：偏高价格 + 动量过热
        warnings.append(
            f"⚠ 错题本：价格在90日{int(pct_rank*100)}%分位，距历史最高{(1-ath_ratio)*100:.0f}%，"
            f"{'RSI='+str(int(rsi_val)) if rsi_val else ''}。"
            f"盈亏比差，继续等。"
        )

    # ── 大涨日拦截（强化版） ──
    if chg_val > 3.0 and (pct_rank >= 0.85 or ath_ratio >= 0.95):
        if not any("大涨" in w for w in warnings):
            warnings.append(
                f"⚠ 错题本：今日+{chg_val:.1f}%暴涨，价格在90日{int(pct_rank*100)}%分位。"
                f"高位大涨日最危险——洛阳钼业21.27买在+6.1%那天。明天再决定。"
            )

    return warnings


def _reminders(row: pd.Series, df: pd.DataFrame, buy_fraction: str = "1/3", rsi_buy_threshold: int = 35) -> list[str]:
    """根据当前行情返回匹配的纪律提醒"""
    reminders = []
    rsi = row["rsi"]
    adx_col = _col(df, "ADX")
    adx_val = row[adx_col] if adx_col else 0
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")
    vol_ratio = row["rvol"] if "rvol" in df.columns and not pd.isna(row["rvol"]) else np.nan

    if not pd.isna(rsi):
        if rsi > 80:
            reminders.append("RSI > 80 — 严重过热。当前位置不适合新增仓位追高。")
        elif rsi > 70:
            reminders.append("RSI > 70 — 偏热。趋势可能仍强，但不适合追涨。")

    # 布林带提醒
    if bb_upper and row["close"] >= row[bb_upper] * 0.99:
        reminders.append("价格在布林上轨 — 位置偏高，不适合追涨，等待放量站稳或回踩确认。")
    if bb_lower and row["close"] <= row[bb_lower] * 1.01:
        reminders.append("价格在布林下轨 — 位置偏低，可提高观察优先级，但仍需量价和动能确认。")

    # MA60 趋势提醒 — 跌破不自动卖，提示关注
    ma60_val = row['ma60'] if 'ma60' in df.columns and not pd.isna(row['ma60']) else None
    if ma60_val and row['close'] < ma60_val:
        # 检查是否刚跌破（昨天还在线上）
        prev_close = df['close'].iloc[-2] if len(df) >= 2 else None
        prev_ma60 = df['ma60'].iloc[-2] if len(df) >= 2 and 'ma60' in df.columns else None
        if prev_close is not None and prev_ma60 is not None and prev_close >= prev_ma60:
            reminders.append(f"⚠ 今日跌破 MA60 ({ma60_val:.4f}) — 趋势可能走坏，关注后续走势")
        else:
            reminders.append(f"价格在 MA60 ({ma60_val:.4f}) 下方 — 趋势偏弱，保持关注")

    # ADX 提醒
    if not pd.isna(adx_val):
        ma60 = row['ma60'] if 'ma60' in df.columns and not pd.isna(row['ma60']) else None
        dmp_col = _col(df, 'DMP')
        dmn_col = _col(df, 'DMN')
        pdi = row[dmp_col] if dmp_col else np.nan
        ndi = row[dmn_col] if dmn_col else np.nan
        # +DI > -DI 为主，MA60 为辅判断趋势方向
        uptrend = (not pd.isna(pdi) and not pd.isna(ndi) and pdi > ndi) or \
                  (bool(ma60) and row['close'] > ma60)
        chg_val = row['chg'] if 'chg' in row.index and not pd.isna(row['chg']) else 0
        # 趋势向上但短线急跌，提示矛盾
        trend_conflict = uptrend and chg_val < -3
        if adx_val >= 40:
            if uptrend:
                if trend_conflict:
                    reminders.append(f"ADX={adx_val:.0f} — 长期上升趋势极强，但今日急跌（{chg_val:.1f}%），短线与趋势冲突，保持观察不操作。")
                else:
                    reminders.append(f"ADX={adx_val:.0f} — 极端强趋势上涨。保持观察，不新增仓位。")
            else:
                if not pd.isna(rsi) and rsi < rsi_buy_threshold:
                    reminders.append(f"ADX={adx_val:.0f} — 极端强趋势下跌。RSI 可能低位钝化，信号慎重。")
                else:
                    reminders.append(f"ADX={adx_val:.0f} — 极端强趋势下跌。趋势偏弱，不急于判断底部。")
        elif adx_val >= 25:
            if uptrend:
                if trend_conflict:
                    reminders.append(f"ADX={adx_val:.0f} — 上升趋势中但短线急跌（{chg_val:.1f}%），等回落结构更清晰。")
                else:
                    reminders.append(f"ADX={adx_val:.0f} — 趋势上涨中。等待回落结构更清晰。")
            else:
                if not pd.isna(rsi) and rsi < rsi_buy_threshold:
                    reminders.append(f"ADX={adx_val:.0f} — 趋势下跌中。RSI 低位不是底，是趋势，别接飞刀。")
                else:
                    reminders.append(f"ADX={adx_val:.0f} — 趋势下跌中。等待止跌信号，不急于判断底部。")

    # 成交量异常
    if not pd.isna(vol_ratio) and vol_ratio >= 2.5:
        reminders.append(f"RVOL={vol_ratio:.1f} — 极端放量。先判断是恐慌、抢筹还是消息驱动，别盘中冲动。")
    elif not pd.isna(vol_ratio) and vol_ratio >= 1.5:
        reminders.append(f"RVOL={vol_ratio:.1f} — 明显放量。关注情绪变化，但不把放量当买入条件。")

    # 连续下跌
    if len(df) >= 3:
        last3 = df.iloc[-3:]
        if all(last3["chg"].iloc[-2:] < -1.5):
            reminders.append("连续两日大跌 — 越跌越补是陷阱，等止跌信号再动手。")

    # 单日大涨
    if row["chg"] > 3:
        reminders.append("单日大涨超过 3% — 情绪容易放大，不因单日大涨临时追涨，等待次日站稳或回踩确认。")

    return reminders


# ── 主面板 ──
def show(
    df: pd.DataFrame,
    symbol: str = "563360",
    name: str = None,
    share_observation: dict | None = None,
):
    """按价格、RVOL、MACD、RSI 顺序输出看盘面板"""
    instrument = get_instrument(symbol)
    df = compute_indicators(df, instrument)
    latest = df.iloc[-1]
    today_str = df.index[-1].strftime("%Y-%m-%d")
    label = name or symbol

    analysis = build_market_analysis(df)
    steps = analysis["steps"]

    print("=" * 55)
    print(f"  {label} — {today_str}")
    print("=" * 55)
    source = df.attrs.get("source")
    if source:
        print(f"  数据日期 {today_str} | 来源 {source}")
    if df.attrs.get("refresh_note"):
        print(f"  {df.attrs['refresh_note']}")
    if df.attrs.get("refresh_error"):
        print(f"  数据刷新失败，当前使用本地缓存：{df.attrs['refresh_error']}")
    print()
    print("  ── 当前状态 ──")
    print(f"  {analysis['state_label']}")
    print()
    print("  ── 一句话解释 ──")
    print(f"  {analysis['one_liner']}")
    print()
    print("  ── 看盘顺序 ──")
    for idx, (name, state, note) in enumerate(steps, start=1):
        print(f"  {idx}. {name} [{state}] {note}")

    print()
    print(f"  ── 下一步观察 ──")
    for item in analysis["next_watch"]:
        print(f"  - {item}")

    campaign = build_campaign_observation(df, instrument)
    if campaign is not None:
        print()
        print("  ── 战役观察 ──")
        print(f"  {campaign['phase']}")
        print(f"  {campaign['summary']}")
        for condition in campaign["conditions"]:
            icon = "✓" if condition["ok"] else "○"
            print(f"  {icon} {condition['label']}：{condition['detail']}")

    if SHARE_OBSERVATION_ENABLED and share_observation is not None:
        def _fmt_share_change(value):
            return "数据不足" if value is None or pd.isna(value) else f"{value:+.2f}%"

        freshness = (
            "已刷新" if share_observation.get("freshness") == "current" else "缓存读取"
        )
        latest_date = pd.Timestamp(share_observation["latest_date"]).strftime("%Y-%m-%d")
        print()
        print("  ── ETF 份额观察（不参与战役） ──")
        print(f"  {share_observation['state']}")
        print(
            f"  最新份额 {share_observation['latest_shares'] / 1e8:.2f}亿份"
            f" | 当日 {_fmt_share_change(share_observation.get('daily_change_pct'))}"
            f" | 近5日 {_fmt_share_change(share_observation.get('change_5d_pct'))}"
            f" | 近20日 {_fmt_share_change(share_observation.get('change_20d_pct'))}"
        )
        print(
            f"  {share_observation['source']} | 数据日 {latest_date} | {freshness}"
        )
        if share_observation.get("lag_days", 0) > 0:
            print(f"  份额数据落后行情 {share_observation['lag_days']} 天")
        print(f"  {share_observation['explanation']}")

    reminders = _reminders(latest, df, rsi_buy_threshold=instrument.rsi_second_entry or 0)
    if reminders:
        print()
        print(f"  ── 纪律提醒 ──")
        for r in reminders:
            print(f"  {r}")

    # ═══ 第三层：关键数字 + 留白 ═══
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")
    macd_col = [c for c in df.columns if c.startswith("MACD_")]
    signal_col = [c for c in df.columns if c.startswith("MACDs_")]
    hist_col = [c for c in df.columns if c.startswith("MACDh_")]
    macd_val = latest[macd_col[0]] if macd_col else None
    signal_val = latest[signal_col[0]] if signal_col else None
    hist_val = latest[hist_col[0]] if hist_col else None

    print()
    print(f"  ── 关键数字 ──")
    level_line = f"  价格 {latest['close']:.4f} | MA5 {latest['ma5']:.4f} | MA10 {latest['ma10']:.4f} | MA20 {latest['ma20']:.4f}"
    if bb_lower and bb_upper:
        level_line += f" | 布林 {latest[bb_lower]:.4f} ~ {latest[bb_upper]:.4f}"
    print(level_line)
    adx_col = _col(df, "ADX")
    adx_val = latest[adx_col] if adx_col else None
    indicator_line = f"  RSI {latest['rsi']:.0f}"
    if adx_val is not None and not pd.isna(adx_val):
        dmp_col = _col(df, 'DMP'); dmn_col = _col(df, 'DMN')
        pdi = latest[dmp_col] if dmp_col else None
        ndi = latest[dmn_col] if dmn_col else None
        if pdi is not None and ndi is not None and not pd.isna(pdi) and not pd.isna(ndi):
            indicator_line += f" | ADX {adx_val:.0f} (+DI {pdi:.0f} -DI {ndi:.0f})"
        else:
            indicator_line += f" | ADX {adx_val:.0f}"
    if macd_val is not None and signal_val is not None and hist_val is not None and not pd.isna(macd_val):
        indicator_line += f" | DIF/DEA/HIST {macd_val:+.4f}/{signal_val:+.4f}/{hist_val:+.4f}"
    rvol = latest["rvol"] if "rvol" in df.columns and not pd.isna(latest["rvol"]) else None
    amount = latest["amount"] if "amount" in df.columns and not pd.isna(latest["amount"]) else None
    indicator_line += f" | 成交量 {latest['volume']/10000:.0f}万手"
    if amount is not None:
        indicator_line += f" | 成交额 {amount/100000000:.2f}亿"
    else:
        indicator_line += " | 成交额 缺失"
    if rvol is not None:
        indicator_line += f" | RVOL {rvol:.2f}"
    else:
        indicator_line += " | RVOL 暂不可用"
    print(indicator_line)

    print()
    print(f"  >>> 你怎么看？")
    print("=" * 55)


def get_indicator_row(df: pd.DataFrame) -> dict:
    """返回最新一行的关键指标，供 chart.py 使用"""
    df = compute_indicators(df)
    latest = df.iloc[-1]
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")
    adx_col = _col(df, "ADX")
    macd_col = [c for c in df.columns if c.startswith("MACD_")]

    return {
        "close": latest["close"],
        "rsi": latest["rsi"],
        "adx": latest[adx_col] if adx_col else None,
        "bb_upper": latest[bb_upper] if bb_upper else None,
        "bb_lower": latest[bb_lower] if bb_lower else None,
        "ma20": latest["ma20"],
        "ma5": latest["ma5"],
        "macd": latest[macd_col[0]] if macd_col else None,
        "vol_ratio": latest["rvol"] if "rvol" in df.columns and not pd.isna(latest["rvol"]) else 1,
        "chg": latest["chg"],
        "today": df.index[-1],
    }
