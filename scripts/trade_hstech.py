"""恒生科技ETF交易分析"""
import sys; sys.path.insert(0, '.')
import pandas as pd
import numpy as np

trades = pd.read_csv('journal/HSTECH/trades.csv', parse_dates=['date'])
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

# 阶段分析
print()
print('=== 阶段分析 ===')

print()
print('【阶段1: 2025年5-11月 低买高卖期】')
early = trades[trades['date'] <= '2025-11-30']
for _, r in early.iterrows():
    amt = r['shares'] * r['price']
    print(f'  {r["date"].strftime("%Y-%m-%d")}  {r["action"]:<4} {r["price"]:.3f} x {r["shares"]:>5}份  {amt:>8.0f}元')
early_pnl = sum(t['pnl'] for t in sell_records if t['date'] <= pd.Timestamp('2025-11-30'))
print(f'  阶段已实现盈亏: {early_pnl:+.0f}元')

print()
print('【阶段2: 2026年1-2月 密集高位加仓】')
mid = trades[(trades['date'] >= '2026-01-01') & (trades['date'] <= '2026-02-28')]
for _, r in mid.iterrows():
    amt = r['shares'] * r['price']
    flag = ' *** 高位!' if r['action']=='buy' and r['price'] >= p75 else ''
    print(f'  {r["date"].strftime("%Y-%m-%d")}  {r["action"]:<4} {r["price"]:.3f} x {r["shares"]:>5}份  {amt:>8.0f}元{flag}')
mid_buys = mid[mid['action']=='buy']
print(f'  加仓小计: {mid_buys["shares"].sum()}份  {(mid_buys["shares"]*mid_buys["price"]).sum():.0f}元')
print(f'  加仓均价: {(mid_buys["shares"]*mid_buys["price"]).sum()/mid_buys["shares"].sum():.3f} (75分位={p75:.3f})')

print()
print('【阶段3: 2026年2-3月 恐慌清仓】')
late = trades[(trades['date'] >= '2026-02-27') & (trades['action']=='sell')]
for _, r in late.iterrows():
    print(f'  {r["date"].strftime("%Y-%m-%d")}  卖出 {r["price"]:.3f} x {r["shares"]}份 ← 割肉')
late_pnl = sum(t['pnl'] for t in sell_records if t['date'] >= pd.Timestamp('2026-02-27'))
print(f'  清仓小计: {late["shares"].sum()}份  亏损: {late_pnl:+.0f}元')
