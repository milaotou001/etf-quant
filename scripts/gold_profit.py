"""COMEX 4600 黄金收益测算"""
gold_now = 8.544
comex_now = 4100
comex_target = 4600
gold_target = gold_now * comex_target / comex_now  # 9.585

print(f"COMEX {comex_now} → {comex_target} (+12.2%)")
print(f"518880 {gold_now:.2f} → {gold_target:.2f}")
print()

# 现有持仓
hold_qty = 8500
avg_cost = 8.467
cost_total = hold_qty * avg_cost
target_value = hold_qty * gold_target
profit_existing = target_value - cost_total
print(f"=== 现有持仓 ===")
print(f"{hold_qty}股 x {avg_cost:.3f} = 成本 {cost_total:,.0f}")
print(f"目标市值: {target_value:,.0f}")
print(f"盈利: {profit_existing:,.0f}")

# 定投 (假设均价接近现价8.54)
dca_weeks = 12
dca_weekly = 2500
dca_total = dca_weeks * dca_weekly
dca_avg = gold_now  # 假设均价=现价
dca_qty = dca_total / dca_avg
dca_target_value = dca_qty * gold_target
dca_profit = dca_target_value - dca_total
print(f"\n=== 定投 ===")
print(f"{dca_weeks}周 x {dca_weekly} = {dca_total:,}")
print(f"目标市值: {dca_target_value:,.0f}")
print(f"盈利: {dca_profit:,.0f}")

# 彩票单
lotto_qty = 1200
lotto_price = 7.93
lotto_cost = lotto_qty * lotto_price
lotto_target_value = lotto_qty * gold_target
lotto_profit = lotto_target_value - lotto_cost
print(f"\n=== 彩票单 ===")
print(f"{lotto_qty}股 x {lotto_price} = {lotto_cost:,.0f}")
print(f"目标市值: {lotto_target_value:,.0f}")
print(f"盈利: {lotto_profit:,.0f}")

# 合计
total_invested = cost_total + dca_total + lotto_cost
total_target = target_value + dca_target_value + lotto_target_value
total_profit = profit_existing + dca_profit + lotto_profit
total_shares = hold_qty + dca_qty + lotto_qty
print(f"\n=== 合计 ===")
print(f"总持股: {total_shares:.0f}股")
print(f"总成本: {total_invested:,.0f}")
print(f"总市值: {total_target:,.0f}")
print(f"总盈利: {total_profit:,.0f}")
print(f"收益率: {(total_target/total_invested-1)*100:+.1f}%")
