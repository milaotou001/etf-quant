"""技术指标纯 pandas/numpy 实现，零外部依赖"""
import pandas as pd
import numpy as np


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({
        'MACD_12_26_9': macd_line,
        'MACDs_12_26_9': signal_line,
        'MACDh_12_26_9': histogram,
    }, index=close.index)


def bbands(close: pd.Series, length: int = 20, std: int = 2) -> pd.DataFrame:
    ma = sma(close, length)
    stdev = close.rolling(window=length).std()
    return pd.DataFrame({
        f'BBL_{length}_{std}.0': ma - std * stdev,
        f'BBM_{length}_{std}.0': ma,
        f'BBU_{length}_{std}.0': ma + std * stdev,
        f'BBB_{length}_{std}.0': (ma + std * stdev) - (ma - std * stdev),  # bandwidth
        f'BBP_{length}_{std}.0': (close - (ma - std * stdev)) / ((ma + std * stdev) - (ma - std * stdev)) * 100,  # %b
    }, index=close.index)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.DataFrame:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    up = high.diff()
    dn = -low.diff()

    dmp = pd.Series(np.where((up > dn) & (up > 0), up, 0), index=close.index)
    dmn = pd.Series(np.where((dn > up) & (dn > 0), dn, 0), index=close.index)

    atr = tr.ewm(alpha=1/length, adjust=False).mean()
    sm_dmp = dmp.ewm(alpha=1/length, adjust=False).mean()
    sm_dmn = dmn.ewm(alpha=1/length, adjust=False).mean()

    pdi = 100 * sm_dmp / atr.replace(0, np.nan)
    ndi = 100 * sm_dmn / atr.replace(0, np.nan)

    dx = (100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan))
    adx_val = dx.ewm(alpha=1/length, adjust=False).mean()

    return pd.DataFrame({
        f'ADX_{length}': adx_val,
        f'DMP_{length}': pdi,
        f'DMN_{length}': ndi,
    }, index=close.index)
