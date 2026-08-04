"""洛阳钼业交易分析"""
import sys; sys.path.insert(0, '.')
import pandas as pd
import numpy as np

trades = pd.read_csv('journal/603993/trades.csv', parse_dates=['date'])
trades = trades.sort_values('date').reset_index(drop=True)

print('=== 洛阳钼业 全部交易 ===')
print(f'共 {len(trades)} 笔')
print()

# 逐笔跟踪
position = 0
total_cost = 0
realized_pnl = 0
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

# 卖出分析
print('=== 卖出盈亏 ===')
print(f'{"日期":<12} {"卖出价":>8} {"成本":>8} {"数量":>6} {"盈亏":>10} {"盈亏%":>8}')
for t in sell_records:
    print(f'{t["date"].strftime("%Y-%m-%d"):<12} {t["sell_price"]:>8.2f} {t["avg_cost"]:>8.2f} {t["shares"]:>6} {t["pnl"]:>+10.0f} {t["pnl_pct"]:>+7.1f}%')

win = sum(1 for t in sell_records if t['pnl'] > 0)
loss = sum(1 for t in sell_records if t['pnl'] <= 0)
print(f'\n盈利卖出: {win}笔  亏损卖出: {loss}笔')
print(f'总已实现: {realized_pnl:+.0f} 元')

# 关键：按阶段分析
print()
print('=== 买入阶段分析 ===')
buys = trades[trades['action'] == 'buy'].copy()
buy_prices = buys['price'].values
p25, p50, p75 = np.percentile(buy_prices, [25, 50, 75])
print(f'买入价格范围: {buy_prices.min():.2f} ~ {buy_prices.max():.2f}')
print(f'25分位: {p25:.2f}  50分位: {p50:.2f}  75分位: {p75:.2f}')
print()

# 三个时期
print('【阶段1: 2025年9-11月 低价建仓期】')
early = buys[buys['date'] <= '2025-11-30']
for _, r in early.iterrows():
    amt = r['shares'] * r['price']
    print(f'  {r["date"].strftime("%m-%d")}  {r["price"]:>6.2f} x {r["shares"]:>4}份  {amt:>8.0f}元')
print(f'  小计: {early["shares"].sum()}份  {(early["shares"]*early["price"]).sum():.0f}元')

print()
print('【阶段2: 2026年1月 高位密集加仓】')
mid = buys[(buys['date'] >= '2026-01-01') & (buys['date'] <= '2026-01-31')]
for _, r in mid.iterrows():
    amt = r['shares'] * r['price']
    flag = ' *** 最贵!' if r['price'] >= p75 else ''
    print(f'  {r["date"].strftime("%m-%d")}  {r["price"]:>6.2f} x {r["shares"]:>4}份  {amt:>8.0f}元{flag}')
print(f'  小计: {mid["shares"].sum()}份  {(mid["shares"]*mid["price"]).sum():.0f}元')
print(f'  均价: {(mid["shares"]*mid["price"]).sum()/mid["shares"].sum():.2f} (75分位={p75:.2f})')

print()
print('【阶段3: 2026年3月 下跌中加仓 → 恐慌清仓】')
late_buy = buys[(buys['date'] >= '2026-03-01') & (buys['date'] <= '2026-03-31')]
for _, r in late_buy.iterrows():
    print(f'  {r["date"].strftime("%m-%d")}  买入 {r["price"]:.2f} x {r["shares"]}份')
print(f'  {late_buy["shares"].sum()}份  {(late_buy["shares"]*late_buy["price"]).sum():.0f}元')
late_sell = trades[(trades['action']=='sell') & (trades['date']>='2026-03-01') & (trades['date']<='2026-03-31')]
for _, r in late_sell.iterrows():
    print(f'  {r["date"].strftime("%m-%d")}  卖出 {r["price"]:.2f} x {r["shares"]}份 ← 割肉')
print(f'  卖出小计: {late_sell["shares"].sum()}份')
