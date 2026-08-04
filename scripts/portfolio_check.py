"""检查当前持仓 vs 理想配置"""
import sys; sys.path.insert(0, '.')
from trades import load_trades
from data import load_data

trades = load_trades()

# 理想比例
ideal = {
    "宽基": 0.40,   # A500 + 沪深300
    "科技": 0.10,   # 科创50
    "黄金": 0.20,   # 518880
    "现金": 0.30,
}

# 各标的当前价格
prices = {}
for sym in ["563360", "510300", "588000", "518880"]:
    try:
        df = load_data(sym)
        prices[sym] = df.iloc[-1]['close']
    except:
        prices[sym] = None

# 计算各标的持仓（FIFO）
positions = {}
for sym in ["563360", "510300", "588000", "518880"]:
    sym_trades = trades.get(sym, [])
    if not sym_trades:
        positions[sym] = {"qty": 0, "cost": 0, "value": 0}
        continue

    # FIFO 计算剩余持仓
    queue = []
    cost_total = 0
    for t in sym_trades:
        if t['type'] == 'buy':
            queue.append({"qty": t['qty'], "price": t['price']})
        else:
            remaining = t['qty']
            for buy in queue[:]:
                if remaining <= 0:
                    break
                match_qty = min(remaining, buy['qty'])
                buy['qty'] -= match_qty
                remaining -= match_qty
                if buy['qty'] <= 0:
                    queue.remove(buy)

    hold_qty = sum(b['qty'] for b in queue)
    hold_cost = sum(b['qty'] * b['price'] for b in queue)
    price = prices.get(sym)
    hold_value = hold_qty * price if price else 0

    positions[sym] = {"qty": hold_qty, "cost": hold_cost, "value": hold_value}

# 汇总
print("=== 当前持仓 ===")
total_value = 0
for sym, name, cat in [("563360", "A500", "宽基"), ("510300", "沪深300", "宽基"),
                         ("588000", "科创50", "科技"), ("518880", "黄金", "黄金")]:
    p = positions[sym]
    price = prices.get(sym, 0)
    print(f"{name}: {p['qty']:.0f}股 x {price:.4f} = {p['value']:,.0f}  成本: {p['cost']:,.0f}")
    total_value += p['value']

# 加现金
cash = 100000  # 用户说的10万
total_assets = total_value + cash
print(f"\n总资产: {total_assets:,.0f} (持仓{total_value:,.0f} + 现金{cash:,.0f})")

# 宽基 = A500 + 沪深300
kuanji_value = positions["563360"]["value"] + positions["510300"]["value"]
keji_value = positions["588000"]["value"]
gold_value = positions["518880"]["value"]

print(f"\n=== 实际 vs 理想 ===")
categories = [
    ("宽基(A500+300)", kuanji_value, 0.40),
    ("科技(科创50)", keji_value, 0.10),
    ("黄金", gold_value, 0.20),
    ("现金", cash, 0.30),
]

for name, value, target_pct in categories:
    actual_pct = value / total_assets * 100
    target_value = total_assets * target_pct
    gap = value - target_value
    bar = "█" * int(actual_pct / 2) + "░" * int((target_pct * 100 - actual_pct) / 2) if actual_pct < target_pct * 100 else "█" * int(target_pct * 100 / 2)
    status = "✓" if abs(gap / total_assets) < 0.03 else ("超配" if gap > 0 else "不足")
    print(f"{name}: 实际 {actual_pct:.1f}% ({value:,.0f}) vs 目标 {target_pct*100:.0f}% ({target_value:,.0f})  {status} {gap:+,.0f}")

# 加上定投后的黄金
gold_after_dca = gold_value + 30000  # 定投
print(f"\n--- 黄金12周定投后 ---")
gold_pct_after = gold_after_dca / (total_assets + 30000) * 100  # 现金减少30K，总资产不变
# 实际总资产不变（现金转持仓）
gold_pct2 = gold_after_dca / total_assets * 100
print(f"黄金: {gold_pct2:.1f}% ({(gold_value+30000):,.0f})")
