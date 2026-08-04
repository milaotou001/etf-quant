"""黄金持仓成本 + COMEX 4600 收益测算"""
import sys; sys.path.insert(0, '.')
from trades import load_trades

trades = load_trades()
gold = trades.get('518880', [])

if not gold:
    print("无黄金交易记录")
    exit()

buy_qty = 0; sell_qty = 0; total_cost = 0
for t in gold:
    if t['type'] == 'buy':
        buy_qty += t['qty']
        total_cost += t['amount']
        print(f"买入 {t['date'].strftime('%Y-%m-%d')} {t['qty']:.0f}股 @{t['price']:.4f} = {t['amount']:.2f}")
    else:
        sell_qty += t['qty']
        print(f"卖出 {t['date'].strftime('%Y-%m-%d')} {t['qty']:.0f}股 @{t['price']:.4f}")

hold_qty = buy_qty - sell_qty
avg_cost = total_cost / buy_qty if buy_qty > 0 else 0
print(f"\n现有持仓: {hold_qty:.0f}股  总成本: {total_cost:.2f}  均价: {avg_cost:.4f}")

# COMEX 4600 对应 518880 价格估算
# 518880 净值 = COMEX金价 * 汇率 / 31.1035 * 0.98 (大约)
# COMEX 4100 → 518880 ≈ 8.544
# COMEX 4600 → 518880 ≈ 8.544 * 4600/4100 = 9.585
# 简化：518880价格 ≈ COMEX * 0.002084
comex_now = 4100
comex_target = 4600
ratio = comex_target / comex_now
gold_price_now = 8.544
gold_price_target = gold_price_now * ratio

print(f"\n=== COMEX {comex_target} 测算 ===")
print(f"COMEX {comex_now} → {comex_target} 涨幅: {(ratio-1)*100:.1f}%")
print(f"518880 现价 {gold_price_now:.2f} → 预估 {gold_price_target:.2f}")

# 现有持仓收益
existing_profit = hold_qty * (gold_price_target - avg_cost) * 100  # 每100股对应...
# Actually 518880 price is per share, hold_qty is in shares
# Actually in the trade records, qty might be in 份 (1份 = 1 share), price is per share in yuan
# Let me just calculate directly
existing_value = hold_qty * gold_price_now
existing_target_value = hold_qty * gold_price_target
existing_profit = existing_target_value - total_cost

print(f"\n现有持仓:")
print(f"  当前市值: {existing_value:,.0f}元")
print(f"  目标市值: {existing_target_value:,.0f}元")
print(f"  盈利: {existing_profit:,.0f}元 ({(gold_price_target/avg_cost-1)*100:+.1f}%)")

# 定投部分
weekly = 2500
weeks = 12
# 简化：假设平均买入价在8.54附近（当前价附近）
avg_dca_price = gold_price_now * 0.98  # 假设定投均价略低于现价
dca_qty = (weekly * weeks) / avg_dca_price
dca_profit = (weekly * weeks) * (gold_price_target / avg_dca_price - 1)
dca_cost = weekly * weeks
dca_target = dca_cost * (gold_price_target / avg_dca_price)

print(f"\n定投部分 (12周 x 2500):")
print(f"  总投入: {dca_cost:,.0f}元")
print(f"  预估均价: {avg_dca_price:.2f}")
print(f"  目标市值: {dca_target:,.0f}元")
print(f"  盈利: {dca_target - dca_cost:,.0f}元")

# 彩票单
lotto_qty = 1200
lotto_price = 7.93
lotto_cost = lotto_qty * lotto_price
lotto_target = lotto_qty * gold_price_target
lotto_profit = lotto_target - lotto_cost
print(f"\n彩票单 (1200股 @7.93):")
print(f"  投入: {lotto_cost:,.0f}元")
print(f"  目标市值: {lotto_target:,.0f}元")
print(f"  盈利: {lotto_profit:,.0f}元")

# 汇总
print(f"\n=== 合计 ===")
total_invested = total_cost + dca_cost + lotto_cost
total_target = existing_target_value + dca_target + lotto_target
total_profit = total_target - total_invested
print(f"总投入: {total_invested:,.0f}元")
print(f"总市值: {total_target:,.0f}元")
print(f"总盈利: {total_profit:,.0f}元 ({(total_target/total_invested-1)*100:+.1f}%)")
