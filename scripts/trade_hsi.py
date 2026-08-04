"""恒生ETF交易分析"""
import sys; sys.path.insert(0, '.')
import pandas as pd
import numpy as np

trades = pd.read_csv('journal/HSI/trades.csv', parse_dates=['date'])
trades = trades.sort_values('date').reset_index(drop=True)

position = 0; total_cost = 0; realized_pnl = 0
sell_records = []

for i, row in trades.iterrows():
    if row['action'] == 'buy':
        position += row['shares']
        total_cost += row['shares'] * row['price']
    else:
        avg_cost = total_cost / position if position > 0 else 0
        pnl = row['shares'] * (row['price'] - avg_cost)
        realized_pnl += pnl
        sell_records.append({
            'date': row['date'], 'shares': row['shares'],
            'sell_price': row['price'], 'avg_cost': avg_cost,
            'pnl': pnl, 'pnl_pct': (row['price']/avg_cost-1)*100
        })
        cost_ratio = row['shares'] / position
        total_cost -= total_cost * cost_ratio
        position -= row['shares']

print(f'当前持仓: {position} 份')
print(f'当前成本: {total_cost/position:.4f}' if position > 0 else '无持仓')
print(f'已实现盈亏: {realized_pnl:+.0f} 元')
print()

print('=== 卖出盈亏明细 ===')
print(f'{"日期":<12} {"卖出价":>8} {"成本":>8} {"数量":>7} {"盈亏":>10} {"盈亏%":>8}')
for t in sell_records:
    tag = ' *** 大亏!' if t['pnl'] < -500 else ''
    print(f'{t["date"].strftime("%Y-%m-%d"):<12} {t["sell_price"]:>8.3f} {t["avg_cost"]:>8.4f} {t["shares"]:>7} {t["pnl"]:>+10.0f} {t["pnl_pct"]:>+7.1f}%{tag}')

win = sum(1 for t in sell_records if t['pnl'] > 0)
loss = sum(1 for t in sell_records if t['pnl'] <= 0)
total_win = sum(t['pnl'] for t in sell_records if t['pnl'] > 0)
total_loss = sum(t['pnl'] for t in sell_records if t['pnl'] <= 0)
print(f'\n盈利 {win}笔 +{total_win:.0f}元  |  亏损 {loss}笔 {total_loss:.0f}元  |  合计 {realized_pnl:+.0f}元')

# 买入分析
print()
print('=== 买入价格分位 ===')
buys = trades[trades['action']=='buy']
bp = buys['price'].values
p25, p50, p75 = np.percentile(bp, [25,50,75])
print(f'最低: {bp.min():.3f}  最高: {bp.max():.3f}  25%: {p25:.3f}  50%: {p50:.3f}  75%: {p75:.3f}')

for _, r in buys.iterrows():
    pct = (r['price'] - bp.min()) / (bp.max() - bp.min()) * 100
    flag = ' *** 高位!' if r['price'] >= p75 else ''
    print(f'  {r["date"].strftime("%Y-%m-%d")}  {r["price"]:.3f} x {r["shares"]:>5}份  '
          f'金额 {r["shares"]*r["price"]:>8.0f}  分位 {pct:.0f}%{flag}')

# 3月23日异常交易
print()
print('=== 2026-03-23 异常操作 ===')
mar23 = trades[trades['date']=='2026-03-23']
for _, r in mar23.iterrows():
    print(f'  {r["action"]} {r["shares"]}份 @ {r["price"]:.3f}  → 金额 {r["shares"]*r["price"]:.0f}')
