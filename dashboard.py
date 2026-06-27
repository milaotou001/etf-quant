"""市场状态面板 + 不做清单纪律提醒"""
import pandas as pd
import numpy as np
from datetime import datetime
from indicators import sma, rsi, macd, bbands, adx


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算全部技术指标，返回带指标列的 DataFrame"""
    df = df.copy()
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

    df["vol_ma20"] = sma(df["volume"], 20)
    df["chg"] = df["close"].pct_change() * 100

    return df


# ── 列名查找 ──
def _col(df: pd.DataFrame, prefix: str) -> str:
    for c in df.columns:
        if c.startswith(prefix):
            return c
    return ""


# ── 市场状态描述 ──
def _market_state(row: pd.Series, df: pd.DataFrame, rsi_buy_threshold: int = 35) -> tuple:
    """返回 (简单判断, 一句话总结)"""
    rsi = row["rsi"]
    adx_col = _col(df, "ADX")
    adx_val = row[adx_col] if adx_col else 0
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")

    at_lower = bb_lower and row["close"] <= row[bb_lower] * 1.02
    at_upper = bb_upper and row["close"] >= row[bb_upper] * 0.98
    in_trend = adx_val >= 25

    if not pd.isna(rsi) and rsi < rsi_buy_threshold:
        verdict = "便宜"
    elif not pd.isna(rsi) and rsi > 70:
        verdict = "贵"
    else:
        verdict = "正常"

    if pd.isna(rsi):
        return verdict, f"收盘 {row['close']:.4f}"

    if rsi < 25:
        flag = "极端超卖"
    elif rsi < rsi_buy_threshold:
        flag = "超卖(买入区间)" if rsi_buy_threshold == 30 else "偏弱(买入区间)"
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
def _reminders(row: pd.Series, df: pd.DataFrame, has_position: bool = False, buy_fraction: str = "1/3", rsi_buy_threshold: int = 35) -> list[str]:
    """根据当前行情返回匹配的纪律提醒"""
    reminders = []
    rsi = row["rsi"]
    adx_col = _col(df, "ADX")
    adx_val = row[adx_col] if adx_col else 0
    bb_upper = _col(df, "BBU")
    bb_lower = _col(df, "BBL")
    vol_ratio = row["volume"] / row["vol_ma20"] if row["vol_ma20"] > 0 else 1

    if not pd.isna(rsi):
        if rsi < rsi_buy_threshold:
            # 查距上次同类信号多少天
            prev_signal = None
            for i in range(len(df)-2, -1, -1):
                pr = df['rsi'].iloc[i]
                if not pd.isna(pr) and pr < rsi_buy_threshold:
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
            elif rsi < rsi_buy_threshold:
                reminders.append(f"RSI={rsi:.0f} 买入区间 → 投现金池{buy_fraction} | {tag}")

            if days_since > 30 and prev_signal is not None:
                reminders.append(f"  上次信号: {prev_signal.strftime('%Y-%m-%d')} (距今天 {days_since} 天)")
        elif rsi > 80:
            reminders.append("RSI > 80 — 严重超买。持有不动，不加仓。历史数据：RSI>70后动量强，卖=踏空。")
        elif rsi > 70:
            reminders.append("RSI > 70 — 偏贵。持有不动，不加仓。不卖——动量效应下卖了容易踏空。")

    # 持仓止损提醒：回落15%铁律
    if has_position:
        # 找买入以来最高点
        if len(df) >= 2:
            recent = df.iloc[-60:] if len(df) >= 60 else df  # 最近60天
            peak = recent['close'].max()
            current = row['close']
            pullback = (current / peak - 1) * 100
            if pullback <= -15:
                reminders.append(f"!!! 止损触发：从高点{peak:.4f}已回落{pullback:.1f}%，触及15%止损线，立即卖出！")
            elif pullback <= -10:
                reminders.append(f"⚠ 注意：从高点{peak:.4f}已回落{pullback:.1f}%，接近15%止损线。")

    # 布林带提醒
    if bb_upper and row["close"] >= row[bb_upper] * 0.99:
        reminders.append("价格在布林上轨 — 偏贵，不加仓。")
    if bb_lower and row["close"] <= row[bb_lower] * 1.01:
        reminders.append("价格在布林下轨 — 便宜，可以关注买入机会。")

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
        uptrend = ma60 and row['close'] > ma60
        if adx_val >= 40:
            if uptrend:
                reminders.append(f"ADX={adx_val:.0f} — 极端强趋势上涨。持有不动，别追高。")
            else:
                reminders.append(f"ADX={adx_val:.0f} — 极端强趋势下跌。RSI 可能低位钝化，信号慎重。")
        elif adx_val >= 25:
            if uptrend:
                reminders.append(f"ADX={adx_val:.0f} — 趋势上涨中。回调再买，不追。")
            else:
                reminders.append(f"ADX={adx_val:.0f} — 趋势下跌中。RSI 低位不是底，是趋势，别接飞刀。")

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

    # ═══ 第二层：纪律提醒 ═══
    reminders = _reminders(latest, df, has_position=False)
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
