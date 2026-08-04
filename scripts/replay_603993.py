"""洛阳钼业 603993 关键错误时刻复盘"""
import sys; sys.path.insert(0, '.')
import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np
import akshare as ak
from dashboard import compute_indicators, build_market_analysis, _reminders, _personalized_warnings

df = ak.stock_zh_a_hist_tx(symbol='sh603993', start_date='20240101', end_date='20260704')
df.rename(columns={'date':'date','open':'open','high':'high','low':'low','close':'close'}, inplace=True)
df['date'] = pd.to_datetime(df['date']); df.set_index('date', inplace=True); df = df.sort_index()
if 'amount' in df.columns:
    df['volume'] = df['amount'] * 100
    df['amount'] = df['volume'] * df['close']

buys = {
    '2026-01-06': (21.27, 500, 10635),
    '2026-01-12': (22.39, 200, 4478),
    '2026-01-19': (23.23, 200, 4646),
    '2026-01-21': (23.10, 100, 2310),
    '2026-01-30': (24.84, 300, 7452),
}
# Also check sell dates
sells = {
    '2026-03-19': (18.70, 2000, 37400),
    '2026-03-23': (16.97, 1000, 16970),
}

dates = list(buys.keys()) + list(sells.keys())

for date in dates:
    end_dt = pd.Timestamp(date)
    sub = df[df.index <= end_dt].copy()
    if len(sub) < 60: continue
    sub = compute_indicators(sub)
    latest = sub.iloc[-1]
    close = latest['close']; rsi = latest.get('rsi',np.nan)
    ma20 = latest.get('ma20',np.nan); ma60 = latest.get('ma60',np.nan)
    hist_c = [c for c in sub.columns if c.startswith('MACDh_')]
    dif_c = [c for c in sub.columns if c.startswith('MACD_') and not c.startswith('MACDs_') and not c.startswith('MACDh_')]
    dea_c = [c for c in sub.columns if c.startswith('MACDs_')]
    hist_v = latest[hist_c[0]] if hist_c else np.nan
    dif_v = latest[dif_c[0]] if dif_c else np.nan
    dea_v = latest[dea_c[0]] if dea_c else np.nan
    rvol = latest.get('rvol',np.nan); chg = latest.get('chg',np.nan)
    lookback = min(90, len(sub)); rc = sub['close'].iloc[-lookback:]
    ph, pl = rc.max(), rc.min()
    pct = (close-pl)/(ph-pl)*100 if ph>pl else 50
    ath = sub['close'].max(); ath_r = close/ath if ath>0 else 0
    dist_ma20 = (close/ma20-1)*100 if not pd.isna(ma20) else np.nan
    bb_u = [c for c in sub.columns if c.startswith('BBU_')]
    bb_upper = latest[bb_u[0]] if bb_u else np.nan
    state = 'N/A'
    try: state = build_market_analysis(sub)['state_label']
    except: pass
    reminders = _reminders(latest, sub, rsi_buy_threshold=35)
    pers = _personalized_warnings(latest, sub)

    is_buy = date in buys
    action = 'BUY' if is_buy else 'SELL'
    bp, bs, ba = buys[date] if is_buy else sells[date]

    print(f'\n{"="*60}')
    print(f'{date}  {action} {bs}sh @ {bp:.2f} = {ba} yuan')
    print(f'Close:{close:.2f} MA20:{ma20:.2f}(dist:{dist_ma20:+.1f}%) RSI:{rsi:.0f} 90d%ile:{pct:.0f}% ATHr:{ath_r:.3f}')
    print(f'MACD DIF:{dif_v:+.3f} DEA:{dea_v:+.3f} HIST:{hist_v:+.4f} RVOL:{rvol:.2f}')
    print(f'State: {state}  Reminders:{len(reminders)}  Personalized:{len(pers)}')
    for r in reminders: print(f'  R: {r}')
    for w in pers: print(f'  P: {w}')

    # Aftermath for buys
    if is_buy:
        fdf = df[df.index > end_dt]
        if 'close' in fdf.columns and not fdf.empty:
            fc = fdf['close']
            lo = fc.min(); lo_d = fc.idxmin(); lo_r = (lo/bp-1)*100
            print(f'  Aftermath: Low={lo_d.strftime("%Y-%m-%d")} {lo:.2f} ({lo_r:+.1f}%)')
            for days in [30,60,90]:
                tgt = end_dt + pd.Timedelta(days=days)
                cx = fc[fc.index <= tgt]
                if not cx.empty: fp=cx.iloc[-1]; ret=(fp/bp-1)*100; print(f'    {days}d: {fp:.2f} ({ret:+.1f}%)')
