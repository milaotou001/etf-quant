"""交割单全面分析"""
import pandas as pd
import numpy as np

path = r'C:\Users\admin\xwechat_files\wxid_4jc53psc169r12_a8d8\msg\file\2026-07\普通账户电子对账单.xlsx'
df = pd.read_excel(path, sheet_name='Sheet1', header=None)

# ── 基础信息 ──
name = df.iloc[5, 4]
acct = df.iloc[5, 1]
period = df.iloc[6, 4]
cash_balance = df.iloc[10, 1]
total_assets = df.iloc[11, 1]

print(f"账户: {name} | 客户号: {acct}")
print(f"账单周期: {period}")
print(f"当前资金余额: {cash_balance:,.2f} | 资产总值: {total_assets:,.2f}")
print()

# ── 流水明细 ──
tx_cols = ['日期','币种','股东账号','证券代码','证券名称','摘要','成交数量','成交均价','佣金','印花税','其他费','发生金额','资金余额']
tx = df.iloc[17:df.index[df.iloc[:, 0].astype(str).str.contains('股票持仓')].tolist()[0]].copy()
tx.columns = tx_cols
tx = tx[tx['日期'].notna() & (tx['日期'].astype(str).str.match(r'^\d{8}$'))].copy()

for c in ['成交数量','成交均价','佣金','印花税','其他费','发生金额','资金余额']:
    tx[c] = pd.to_numeric(tx[c], errors='coerce')

tx['日期'] = pd.to_datetime(tx['日期'], format='%Y%m%d')
tx = tx.sort_values('日期').reset_index(drop=True)

# 只保留买卖
trades = tx[tx['摘要'].isin(['证券买入','证券卖出'])].copy()
# 区分现金操作
transfers = tx[~tx['摘要'].isin(['证券买入','证券卖出','银行转存','转存管转入','转存管转出',
                                   '基金买入','基金赎回','利息归本','红利差异税',
                                   '股息入账','理财质押','理财到期兑付','理财申购'])]

print(f"总流水 {len(tx)} 笔 | 买卖 {len(trades)} 笔 | 银证转账/其他 {len(tx)-len(trades)} 笔")
print()

# ── 按标的汇总 ──
trades['成交金额'] = trades['成交数量'] * trades['成交均价']
trades['手续费'] = trades['佣金'].abs() + trades['印花税'].abs() + trades['其他费'].abs()

# 按代码和买卖方向分组
print("=" * 80)
print("【一、交易品种概览】")
print()
stocks = trades.groupby(['证券代码','证券名称']).agg(
    买入次数=('摘要', lambda x: (x == '证券买入').sum()),
    卖出次数=('摘要', lambda x: (x == '证券卖出').sum()),
    买入总金额=('成交金额', lambda x: x[trades.loc[x.index, '摘要'] == '证券买入'].sum()),
    卖出总金额=('成交金额', lambda x: x[trades.loc[x.index, '摘要'] == '证券卖出'].sum()),
    总手续费=('手续费','sum')
).sort_values('买入总金额', ascending=False)

for (code, name_str), row in stocks.iterrows():
    pnl = row['卖出总金额'] - row['买入总金额']
    tot = row['买入次数'] + row['卖出次数']
    if row['买入次数'] > 0 and row['卖出次数'] > 0:
        print(f"  {code} {name_str}: 买{int(row['买入次数'])}次 卖{int(row['卖出次数'])}次 | 买入{row['买入总金额']:,.0f} 卖出{row['卖出总金额']:,.0f} | 手续费{row['总手续费']:,.0f}")
    elif row['买入次数'] > 0:
        print(f"  {code} {name_str}: 买{int(row['买入次数'])}次 (仍持有) | 买入{row['买入总金额']:,.0f} | 手续费{row['总手续费']:,.0f}")

print()
print("=" * 80)
print("【二、买卖时机分析】")

# 对每个有完整买卖周期的标的
# 简化：用先进先出匹配
from collections import deque

def match_trades(trades_df):
    """FIFO匹配买卖，返回每笔已平仓交易的盈亏"""
    results = []
    for code in trades_df['证券代码'].unique():
        if pd.isna(code) or code == '':
            continue
        stock_trades = trades_df[trades_df['证券代码'] == code].sort_values('日期')
        name = stock_trades['证券名称'].iloc[0]
        queue = deque()
        for _, t in stock_trades.iterrows():
            if t['摘要'] == '证券买入':
                queue.append({'date': t['日期'], 'qty': t['成交数量'], 'price': t['成交均价'], 'fee': t['手续费']})
            elif t['摘要'] == '证券卖出':
                sell_qty = t['成交数量']
                sell_price = t['成交均价']
                sell_date = t['日期']
                sell_fee = t['手续费']
                while sell_qty > 0 and queue:
                    buy = queue[0]
                    match_qty = min(sell_qty, buy['qty'])
                    buy_cost = match_qty * buy['price'] + buy['fee'] * (match_qty / buy['qty'])
                    sell_proceeds = match_qty * sell_price - sell_fee * (match_qty / sell_qty)
                    pnl = sell_proceeds - buy_cost
                    pnl_pct = (sell_proceeds / buy_cost - 1) * 100
                    hold_days = (sell_date - buy['date']).days
                    results.append({
                        '代码': code, '名称': name,
                        '买入日': buy['date'], '卖出日': sell_date,
                        '买入价': buy['price'], '卖出价': sell_price,
                        '数量': match_qty, '盈亏': pnl, '盈亏%': pnl_pct,
                        '持有天数': hold_days
                    })
                    buy['qty'] -= match_qty
                    buy['fee'] *= (1 - match_qty / (match_qty + buy['qty'])) if buy['qty'] > 0 else 0
                    if buy['qty'] <= 0:
                        queue.popleft()
                    sell_qty -= match_qty
    return pd.DataFrame(results)

closed = match_trades(trades)

if len(closed) > 0:
    # 整体统计
    win_trades = closed[closed['盈亏'] > 0]
    loss_trades = closed[closed['盈亏'] < 0]
    total_pnl = closed['盈亏'].sum()

    print(f"\n已平仓交易: {len(closed)} 笔")
    print(f"  盈利: {len(win_trades)} 笔 ({len(win_trades)/len(closed)*100:.0f}%), 总盈利 {win_trades['盈亏'].sum():,.0f}")
    print(f"  亏损: {len(loss_trades)} 笔 ({len(loss_trades)/len(closed)*100:.0f}%), 总亏损 {loss_trades['盈亏'].sum():,.0f}")
    print(f"  净盈亏: {total_pnl:,.0f}")
    print(f"  平均每笔: {closed['盈亏'].mean():,.0f} | 中位: {closed['盈亏'].median():,.0f}")
    print(f"  胜率: {len(win_trades)/len(closed)*100:.0f}%")
    print(f"  平均持有天数: {closed['持有天数'].mean():.0f} 天 | 中位: {closed['持有天数'].median():.0f} 天")

    # 盈亏比
    avg_win = win_trades['盈亏'].mean() if len(win_trades) > 0 else 0
    avg_loss = abs(loss_trades['盈亏'].mean()) if len(loss_trades) > 0 else 0
    if avg_loss > 0:
        print(f"  盈亏比: {avg_win/avg_loss:.2f} (平均赚/平均亏)")

print()
print("=" * 80)
print("【三、行为模式检查】")

# 1. 频繁交易
date_range = (trades['日期'].max() - trades['日期'].min()).days
tx_per_month = len(trades) / (date_range / 30)
print(f"\n1. 交易频率: {len(trades)}笔 / {date_range:.0f}天 = {tx_per_month:.1f}笔/月")

# 2. 单个标的反复操作
by_stock = trades.groupby('证券代码')
multi_trade_stocks = {c: len(g) for c, g in by_stock if len(g) > 10 and c and not pd.isna(c)}
if multi_trade_stocks:
    print(f"\n2. 高频操作标的 (>10次):")
    for code, cnt in sorted(multi_trade_stocks.items(), key=lambda x: -x[1]):
        name = trades[trades['证券代码'] == code]['证券名称'].iloc[0]
        print(f"     {code} {name}: {cnt}次")

# 3. 处置效应：赚钱就跑 vs 亏钱死扛
if len(closed) > 0:
    closed['盈亏%'] = pd.to_numeric(closed['盈亏%'], errors='coerce')
    small_win = closed[(closed['盈亏%'] > 0) & (closed['盈亏%'] < 5)]
    big_loss = closed[closed['盈亏%'] < -10]
    print(f"\n3. 处置效应检查:")
    print(f"   赚0-5%就跑: {len(small_win)}笔 (占盈利交易 {len(small_win)/max(1,len(win_trades))*100:.0f}%)")
    print(f"   亏超10%还扛: {len(big_loss)}笔 (占亏损交易 {len(big_loss)/max(1,len(loss_trades))*100:.0f}%)")

    # 4. 持有天数分布
    print(f"\n4. 持有天数分布:")
    for label, lo, hi in [("超短 <3天", 0, 3), ("短线 3-20天", 3, 20),
                           ("中线 20-120天", 20, 120), ("长线 >120天", 120, 99999)]:
        cnt = len(closed[(closed['持有天数'] >= lo) & (closed['持有天数'] < hi)])
        avg_pnl = closed[(closed['持有天数'] >= lo) & (closed['持有天数'] < hi)]['盈亏%'].mean()
        print(f"     {label}: {cnt}笔, 平均盈亏 {avg_pnl:+.1f}%")

print()
print("=" * 80)
print("【四、手续费分析】")
total_fee = trades['手续费'].sum()
total_volume = trades['成交金额'].sum()
print(f"\n  总手续费: {total_fee:,.0f} | 总成交额: {total_volume:,.0f}")
print(f"  手续费占比: {total_fee/total_volume*100:.3f}%")
print(f"  佣金: {trades['佣金'].abs().sum():,.0f} | 印花税: {trades['印花税'].abs().sum():,.0f} | 其他: {trades['其他费'].abs().sum():,.0f}")

print()
print("=" * 80)
print("【五、最赚钱 vs 最亏钱 TOP5】")
if len(closed) > 0:
    top_win = closed.nlargest(5, '盈亏')
    top_loss = closed.nsmallest(5, '盈亏')
    print("\n  ★ 最赚钱:")
    for _, t in top_win.iterrows():
        print(f"    {t['名称']} {t['买入日'].strftime('%Y-%m-%d')}→{t['卖出日'].strftime('%Y-%m-%d')} ({t['持有天数']}天) {t['买入价']:.2f}→{t['卖出价']:.2f} +{t['盈亏']:,.0f} ({t['盈亏%']:+.1f}%)")
    print("\n  ★ 最亏钱:")
    for _, t in top_loss.iterrows():
        print(f"    {t['名称']} {t['买入日'].strftime('%Y-%m-%d')}→{t['卖出日'].strftime('%Y-%m-%d')} ({t['持有天数']}天) {t['买入价']:.2f}→{t['卖出价']:.2f} {t['盈亏']:,.0f} ({t['盈亏%']:+.1f}%)")
