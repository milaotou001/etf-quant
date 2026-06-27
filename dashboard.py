"""市场状态面板 + 不做清单纪律提醒"""
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算全部技术指标，返回带指标列的 DataFrame"""
    df = df.copy()
    df["ma5"] = ta.sma(df["close"], length=5)
    df["ma10"] = ta.sma(df["close"], length=10)
    df["ma20"] = ta.sma(df["close"], length=20)
    df["ma60"] = ta.sma(df["close"], length=60)
    df["rsi"] = ta.rsi(df["close"], length=14)

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    bb = ta.bbands(df["close"], length=20, std=2)
    df = pd.concat([df, bb], axis=1)

    adx_df = ta.adx(df["high"], df["low"], df["close"], length=14)
    df = pd.concat([df, adx_df], axis=1)

    df["vol_ma20"] = ta.sma(df["volume"], length=20)
    df["chg"] = df["close"].pct_change() * 100

    return df


# ── 列名查找 ──
def _col(df: pd.DataFrame, prefix: str) -> str:
    for c in df.columns:
        if c.startswith(prefix):
            return c
    return ""


# ── 市场状态描述 ──
def _market_state(row: pd.Series, df: pd.DataFrame) -> tuple:
    """返回 (简单判断, 一句话总结)"""
    rsi = row["rsi"]
    adx_col = _col(df, "ADX")
    adx_val = row[adx_col] if adx_col else 0
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")

    at_lower = bb_lower and row["close"] <= row[bb_lower] * 1.02
    at_upper = bb_upper and row["close"] >= row[bb_upper] * 0.98
    in_trend = adx_val >= 25

    # 简单判断 — RSI<35 黄金坑，投现金池1/3（最终策略）
    if not pd.isna(rsi) and rsi < 35:
        verdict = "便宜"
    elif not pd.isna(rsi) and rsi > 70:
        verdict = "贵"
    else:
        verdict = "正常"

    # 一句话总结
    if pd.isna(rsi):
        return verdict, f"收盘 {row['close']:.4f}"

    if rsi < 25:
        flag = "极端超卖"
    elif rsi < 30:
        flag = "超卖"
    elif rsi < 35:
        flag = "偏弱(买入区间)"
    elif rsi > 75:
        flag = "极端超买"
    elif rsi > 70:
        flag = "超买"
    else:
        flag = "正常"

    if in_trend:
        trend_note = " 趋势市"
    else:
        trend_note = ""
    summary = f"RSI {rsi:.0f} ({flag}) | ADX {adx_val:.0f}{trend_note} | 收盘 {row['close']:.4f} ({row['chg']:+.1f}%)"
    return verdict, summary


# ── 纪律提醒 ──
def _reminders(row: pd.Series, df: pd.DataFrame, has_position: bool = False, buy_fraction: str = "1/3") -> list[str]:
    """根据当前行情返回匹配的纪律提醒"""
    reminders = []
    rsi = row["rsi"]
    adx_col = _col(df, "ADX")
    adx_val = row[adx_col] if adx_col else 0
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")
    vol_ratio = row["volume"] / row["vol_ma20"] if row["vol_ma20"] > 0 else 1

    # RSI 提醒 — 最终策略：RSI<35 黄金坑，投现金池1/3
    if not pd.isna(rsi):
        if rsi < 35:
            # 查距上次 RSI<35 信号多少天
            prev_signal = None
            for i in range(len(df)-2, -1, -1):
                pr = df['rsi'].iloc[i]
                if not pd.isna(pr) and pr < 35:
                    prev_signal = df.index[i]
                    break

            today = df.index[-1]
            if prev_signal is not None:
                days_since = (today - prev_signal).days
            else:
                days_since = 999

            if days_since > 30:
                tag = "[可以买入]"
            else:
                tag = f"[同一波段 距上次仅{days_since}天 不操作]"

            if rsi < 25:
                reminders.append(f"RSI={rsi:.0f} 极端超卖 黄金坑 → 投现金池{buy_fraction} | {tag}")
            elif rsi < 30:
                reminders.append(f"RSI={rsi:.0f} 超卖区间 黄金坑 → 投现金池{buy_fraction} | {tag}")
            else:
                reminders.append(f"RSI={rsi:.0f} 买入区间 → 投现金池{buy_fraction} | {tag}")

            if days_since > 30 and prev_signal is not None:
                reminders.append(f"  上次信号: {prev_signal.strftime('%Y-%m-%d')} (距今天 {days_since} 天)")
        elif rsi > 80:
            reminders.append("RSI > 80 — 严重超买。持有不动，不加仓。历史数据：RSI>70后动量强，卖=踏空。")
        elif rsi > 70:
            reminders.append("RSI > 70 — 偏贵。持有不动，不加仓。不卖——动量效应下卖了容易踏空。")

    # 布林带提醒
    if bb_upper and row["close"] >= row[bb_upper] * 0.99:
        reminders.append("价格在布林上轨 — 偏贵，不加仓。")
    if bb_lower and row["close"] <= row[bb_lower] * 1.01:
        reminders.append("价格在布林下轨 — 便宜，可以关注买入机会。")

    # ADX 提醒
    if not pd.isna(adx_val):
        if adx_val >= 40:
            reminders.append(f"ADX={adx_val:.0f} — 极端趋势。RSI<35 信号需谨慎，可能趋势中钝化。")
        elif adx_val >= 25:
            reminders.append(f"ADX={adx_val:.0f} — 趋势市。注意：下跌趋势中 RSI<35 不是底，是趋势。")

    # 成交量异常
    if vol_ratio >= 2:
        reminders.append("成交量异常放大 — 别跟风，确认是不是消息驱动。")

    # 连续下跌
    if len(df) >= 3:
        last3 = df.iloc[-3:]
        if all(last3["chg"].iloc[-2:] < -1.5):
            reminders.append("连续两日大跌 — 越跌越补是陷阱，等止跌信号再动手。")

    # 单日大涨
    if row["chg"] > 3:
        reminders.append("单日大涨超过 3% — 别嫉妒别人赚钱，追涨 = 高位接盘。")

    return reminders


# ── 主面板 ──
def show(df: pd.DataFrame, symbol: str = "563360", name: str = None,
         entry_price: float = None, entry_date: str = None):
    """输出三层信息面板"""
    df = compute_indicators(df)
    latest = df.iloc[-1]
    today_str = df.index[-1].strftime("%Y-%m-%d")
    label = name or symbol

    # ═══ 第一层：大势 ═══
    verdict, summary = _market_state(latest, df)

    print("=" * 55)
    print(f"  {label} — {today_str}")
    print("=" * 55)
    print()
    print(f"  {summary}")

    if verdict == "便宜":
        print(f"  >>> 便宜 — 可加仓 <<<")
    elif verdict == "贵":
        print(f"  >>> 偏贵 — 持有不动，不加仓 <<<")
    else:
        print(f"  正常 — 不动")

    # ═══ 持仓信息（如有）═══
    if entry_price is not None and entry_date is not None:
        print()
        print(f"  ── 持仓 ──")
        pnl_pct = (latest["close"] / entry_price - 1) * 100
        stop_price = entry_price * 0.95
        dist_to_stop = (latest["close"] / stop_price - 1) * 100
        hold_days = (df.index[-1] - pd.to_datetime(entry_date)).days
        time_left = max(0, 7 - hold_days)

        pnl_flag = "+" if pnl_pct >= 0 else ""
        print(f"  买入价 {entry_price:.4f} | 买入日 {entry_date}")
        print(f"  当前盈亏 {pnl_flag}{pnl_pct:.1f}% | 止损线 {stop_price:.4f} (距当前 {dist_to_stop:+.1f}%)")
        if time_left > 0:
            print(f"  时间止损剩余 {time_left} 个交易日")
        else:
            print(f"  ⚠ 时间止损已到期 ({hold_days}天)，建议评估是否离场")

    # ═══ 第二层：纪律提醒 ═══
    reminders = _reminders(latest, df, has_position=(entry_price is not None))
    if reminders:
        print()
        print(f"  ── 纪律提醒 ──")
        for r in reminders:
            print(f"  {r}")

    # ═══ 第三层：关键数字 + 留白 ═══
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")
    macd_col = [c for c in df.columns if c.startswith("MACD") and not c.endswith("_12_26_9") and not c.endswith("s") and not c.endswith("h")]
    macd_val = latest[macd_col[0]] if macd_col else None

    print()
    print(f"  ── 关键数字 ──")
    level_line = f"  价格 {latest['close']:.4f} | MA20 {latest['ma20']:.4f}"
    if bb_lower and bb_upper:
        level_line += f" | 布林 {latest[bb_lower]:.4f} ~ {latest[bb_upper]:.4f}"
    print(level_line)
    indicator_line = f"  RSI {latest['rsi']:.0f}"
    if macd_val is not None and not pd.isna(macd_val):
        indicator_line += f" | MACD {macd_val:+.4f}"
    indicator_line += f" | 成交量 {latest['volume']/10000:.0f}万手"
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
    macd_col = [c for c in df.columns if c.startswith("MACD") and not c.endswith("s") and not c.endswith("h")]

    return {
        "close": latest["close"],
        "rsi": latest["rsi"],
        "adx": latest[adx_col] if adx_col else None,
        "bb_upper": latest[bb_upper] if bb_upper else None,
        "bb_lower": latest[bb_lower] if bb_lower else None,
        "ma20": latest["ma20"],
        "ma5": latest["ma5"],
        "macd": latest[macd_col[0]] if macd_col else None,
        "vol_ratio": latest["volume"] / latest["vol_ma20"] if latest["vol_ma20"] > 0 else 1,
        "chg": latest["chg"],
        "today": df.index[-1],
    }
