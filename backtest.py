"""RSI 低位买入信号质量回测"""
import pandas as pd
import numpy as np
from indicators import rsi
from instruments import InstrumentSpec


BUY_CONDITIONS = {
    'rsi35': (35, 'RSI<35'),
    'rsi30': (30, 'RSI<30'),
    'rsi25': (25, 'RSI<25'),
}

HOLDING_WINDOWS = [20, 60, 120, 250]


def _hist_column(df: pd.DataFrame) -> str:
    return next((column for column in df.columns if column.startswith("MACDh_")), "")


def simulate_campaigns(df: pd.DataFrame, instrument: InstrumentSpec) -> list[dict]:
    """模拟固定总预算下的两段观察与一段右侧确认，不产生下单指令。"""
    if not instrument.supports_campaign or df.empty:
        return []

    frame = df.copy()
    if "rsi" not in frame.columns:
        frame["rsi"] = rsi(frame["close"], 14)
    hist_col = _hist_column(frame)
    campaigns: list[dict] = []
    active: dict | None = None

    for position, (date, row) in enumerate(frame.iterrows()):
        rsi_value = row.get("rsi", np.nan)
        if pd.isna(rsi_value):
            continue

        if active is None and rsi_value <= instrument.rsi_first_entry:
            active = {
                "started_at": date,
                "status": "waiting_second_observation",
                "entries": [{"stage": "第一观察位", "date": date, "price": float(row["close"])}],
            }
            continue

        if active is None:
            continue

        if len(active["entries"]) == 1 and rsi_value <= instrument.rsi_second_entry:
            active["entries"].append({"stage": "第二观察位", "date": date, "price": float(row["close"])})
            active["status"] = "waiting_right_confirmation"
            continue

        if len(active["entries"]) != 2 or position == 0 or not hist_col:
            continue

        hist = row.get(hist_col, np.nan)
        previous_hist = frame.iloc[position - 1].get(hist_col, np.nan)
        right_confirmation = (
            rsi_value >= instrument.rsi_confirmation
            and not pd.isna(hist)
            and not pd.isna(previous_hist)
            and hist > previous_hist
        )
        if right_confirmation:
            active["entries"].append({"stage": "右侧确认", "date": date, "price": float(row["close"])})
            active["status"] = "complete"
            campaigns.append(active)
            active = None

    if active is not None:
        campaigns.append(active)
    return campaigns


def run_campaign_backtest(
    df: pd.DataFrame,
    instrument: InstrumentSpec,
    holding_windows: tuple[int, ...] = tuple(HOLDING_WINDOWS),
) -> pd.DataFrame:
    """统计完整三段战役在确认完成后的组合收益质量。"""
    if not instrument.supports_backtest:
        return pd.DataFrame()

    completed = [campaign for campaign in simulate_campaigns(df, instrument) if campaign["status"] == "complete"]
    results = []
    for window in holding_windows:
        returns: list[float] = []
        for campaign in completed:
            confirmation_date = campaign["entries"][-1]["date"]
            confirmation_idx = df.index.get_loc(confirmation_date)
            target_idx = confirmation_idx + window
            if target_idx >= len(df):
                continue
            units = sum((1 / 3) / entry["price"] for entry in campaign["entries"])
            value = units * df.iloc[target_idx]["close"]
            returns.append((value - 1) * 100)

        if returns:
            results.append({
                "观察窗口": f"确认后 {window} 个交易日",
                "完整战役": len(completed),
                "可计算战役": len(returns),
                "上涨概率": f"{sum(value > 0 for value in returns) / len(returns) * 100:.0f}%",
                "平均收益": _format_pct(float(np.mean(returns))),
                "中位收益": _format_pct(float(np.median(returns))),
                "最差": _format_pct(float(np.min(returns))),
                "最好": _format_pct(float(np.max(returns))),
            })
        else:
            results.append({
                "观察窗口": f"确认后 {window} 个交易日",
                "完整战役": len(completed),
                "可计算战役": 0,
                "上涨概率": "样本不足",
                "平均收益": "样本不足",
                "中位收益": "样本不足",
                "最差": "样本不足",
                "最好": "样本不足",
            })
    return pd.DataFrame(results)


def filter_signals_by_gap(df: pd.DataFrame, threshold: int, min_gap_days: int = 30) -> list[pd.Timestamp]:
    """只保留距上次有效信号超过 min_gap_days 的 RSI 低位日期。"""
    signal_dates = []
    last_signal = None

    for date, row in df.iterrows():
        value = row['rsi']
        if pd.isna(value) or value >= threshold:
            continue
        if last_signal is None or (date - last_signal).days > min_gap_days:
            signal_dates.append(date)
            last_signal = date

    return signal_dates


def _future_return(df: pd.DataFrame, buy_idx: int, holding_days: int) -> float | None:
    target_idx = buy_idx + holding_days
    if target_idx >= len(df):
        return None
    entry = df.iloc[buy_idx]['close']
    exit_price = df.iloc[target_idx]['close']
    return (exit_price / entry - 1) * 100


def _format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "样本不足"
    return f"{value:+.2f}%"


def run_backtest(df, buy_condition='rsi30', min_gap_days: int = 30):
    """回测 RSI 买入信号后 N 个交易日的收益表现。"""
    df = df.copy()
    if 'rsi' not in df.columns:
        df['rsi'] = rsi(df['close'], 14)

    if buy_condition not in BUY_CONDITIONS:
        raise ValueError(f"Unknown buy condition: {buy_condition}")

    threshold, cond_label = BUY_CONDITIONS[buy_condition]
    raw_count = int((df['rsi'] < threshold).sum())
    buy_dates = filter_signals_by_gap(df, threshold, min_gap_days=min_gap_days)

    results = []
    for window in HOLDING_WINDOWS:
        rets = []
        for buy_date in buy_dates:
            idx = df.index.get_loc(buy_date)
            ret = _future_return(df, idx, window)
            if ret is not None:
                rets.append(ret)

        if not rets:
            results.append({
                '观察窗口': f'{window}个交易日',
                '可计算样本': 0,
                '上涨概率': '样本不足',
                '平均收益': '样本不足',
                '中位收益': '样本不足',
                '最差': '样本不足',
                '最好': '样本不足',
            })
            continue

        wins = sum(1 for value in rets if value > 0)
        results.append({
            '观察窗口': f'{window}个交易日',
            '可计算样本': len(rets),
            '上涨概率': f"{wins/len(rets)*100:.0f}%",
            '平均收益': _format_pct(float(np.mean(rets))),
            '中位收益': _format_pct(float(np.median(rets))),
            '最差': _format_pct(float(np.min(rets))),
            '最好': _format_pct(float(np.max(rets))),
        })

    rdf = pd.DataFrame(results)
    return rdf, cond_label, len(buy_dates), raw_count
