"""黄金ETF交易记录分析"""
import sys; sys.path.insert(0, '.')
import pandas as pd
import numpy as np

trades = pd.read_csv('journal/518880/trades.csv', parse_dates=['date'])
trades = trades.sort_values('date').reset_index(drop=True)

print('=== 黄金ETF 全部交易记录 ===')
print(f'共 {len(trades)} 笔交易')
print()

# 逐笔跟踪持仓
position = 0
total_cost = 0  # 持仓总成本
realized_pnl = 0  # 已实现盈亏
all_trades_pnl = []  # 每笔卖出的盈亏

for i, row in trades.iterrows():
    if row['action'] == 'buy':
        position += row['shares']
        total_cost += row['shares'] * row['price']
    else:  # sell
        # 按平均成本计算这笔卖出的盈亏
        avg_cost = total_cost / position if position > 0 else 0
        sell_pnl = row['shares'] * (row['price'] - avg_cost)
        realized_pnl += sell_pnl
        all_trades_pnl.append({
            'date': row['date'],
            'shares': row['shares'],
            'sell_price': row['price'],
            'avg_cost': avg_cost,
            'pnl': sell_pnl,
            'pnl_pct': (row['price'] / avg_cost - 1) * 100
        })
        # 按比例减少持仓成本
        cost_ratio = row['shares'] / position
        total_cost -= total_cost * cost_ratio
        position -= row['shares']

# 当前持仓
current_price = 8.475  # 最近收盘价（7月3日）
current_avg_cost = total_cost / position if position > 0 else 0
unrealized_pnl = position * (current_price - current_avg_cost) if position > 0 else 0

print(f'当前持仓: {position} 份')
print(f'当前成本: {current_avg_cost:.4f}')
print(f'当前价格: {current_price:.4f}')
print(f'未实现盈亏: {unrealized_pnl:+.0f} 元')
print(f'已实现盈亏: {realized_pnl:+.0f} 元')
print(f'总盈亏: {realized_pnl + unrealized_pnl:+.0f} 元')
print()

# 分析卖出交易
print('=== 卖出交易盈亏明细 ===')
print(f'{"日期":<12} {"卖出价":>8} {"平均成本":>8} {"数量":>6} {"盈亏":>10} {"盈亏%":>8}')
for t in all_trades_pnl:
    print(f'{t["date"].strftime("%Y-%m-%d"):<12} {t["sell_price"]:>8.3f} {t["avg_cost"]:>8.4f} {t["shares"]:>6} {t["pnl"]:>+10.0f} {t["pnl_pct"]:>+7.1f}%')

print()

# 盈利/亏损卖出统计
win_trades = [t for t in all_trades_pnl if t['pnl'] > 0]
loss_trades = [t for t in all_trades_pnl if t['pnl'] <= 0]
print(f'盈利卖出: {len(win_trades)} 笔, 总盈利 {sum(t["pnl"] for t in win_trades):+.0f} 元')
print(f'亏损卖出: {len(loss_trades)} 笔, 总亏损 {sum(t["pnl"] for t in loss_trades):+.0f} 元')

# 关键分析：高位买入
print()
print('=== 买入价格分析 ===')
buys = trades[trades['action'] == 'buy'].copy()
buys['price_rank'] = buys['price'].rank(pct=True)
print('买入价格排名（百分位，越高越贵）:')
for i, row in buys.iterrows():
    flag = ' *** 高位买入!' if row['price_rank'] > 0.7 else ''
    print(f'  {row["date"].strftime("%Y-%m-%d"):<12} {row["price"]:>8.3f} x {row["shares"]:>5}份  '
          f'金额 {row["shares"]*row["price"]:>8.0f}  价格分位 {row["price_rank"]:.0%}{flag}')
