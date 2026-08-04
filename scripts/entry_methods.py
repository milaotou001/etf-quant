"""沪深300：RSI到40后，时间分批 vs RSI分批"""
import sys; sys.path.insert(0, '.')
import numpy as np
from data import load_data
from dashboard import compute_indicators

df = compute_indicators(load_data('510300'))
c = df['close']
r = df['rsi']

# 方法1：RSI到40后，每隔2天买1笔（共3笔）
# 方法2：RSI到40买1笔，RSI继续跌到35买第2笔，反弹到40买第3笔
# 方法3：RSI到40一次性全买（对照）

time_results = []
rsi_results = []
allin_results = []

for i in range(20, len(df) - 65):
    if r.iloc[i] < 40 and r.iloc[i-1] >= 40:  # 刚碰到40
        # 时间法：T+0, T+2, T+4 各1/3
        p_t0 = c.iloc[i]
        p_t2 = c.iloc[i+2] if i+2 < len(df) else c.iloc[i]
        p_t4 = c.iloc[i+4] if i+4 < len(df) else c.iloc[i]
        avg_time = (p_t0 + p_t2 + p_t4) / 3
        ret60_time = (c.iloc[i+60] / avg_time - 1) * 100 if i+60 < len(df) else np.nan

        # RSI法：40买1笔，35买2笔，反弹40买3笔
        # 找之后RSI最低点和反弹
        found_35 = False; found_rebound = False
        p_40 = p_t0; p_35 = p_t0; p_rebound = p_t0
        for j in range(i+1, min(i+30, len(df))):
            if not found_35 and r.iloc[j] < 35:
                p_35 = c.iloc[j]
                found_35 = True
            if found_35 and not found_rebound and r.iloc[j] >= 40:
                p_rebound = c.iloc[j]
                found_rebound = True
                break
            if r.iloc[j] >= 45:  # 反弹但没到35
                break
        if not found_35:
            p_35 = p_40  # 没到35，重复在40买
            p_rebound = p_40
        if not found_rebound:
            p_rebound = p_40  # 没反弹回40

        avg_rsi = (p_40 + p_35 + p_rebound) / 3
        ret60_rsi = (c.iloc[i+60] / avg_rsi - 1) * 100 if i+60 < len(df) else np.nan

        # 一次性
        ret60_allin = (c.iloc[i+60] / p_t0 - 1) * 100 if i+60 < len(df) else np.nan

        if not np.isnan(ret60_time):
            time_results.append(ret60_time)
            rsi_results.append(ret60_rsi)
            allin_results.append(ret60_allin)

print("=== 沪深300 RSI<40 买入方法对比 ===")
for name, data in [("每隔2天买1笔(共3笔)", time_results),
                   ("RSI 40/35/40三笔制", rsi_results),
                   ("一次性全买", allin_results)]:
    wins = sum(1 for r_ in data if r_ > 0)
    print(f"{name}: 平均{np.mean(data):+.1f}%  胜率{wins}/{len(data)}({wins/len(data)*100:.0f}%)  最差{min(data):+.1f}%")

# 稳定性
time_std = np.std(time_results)
rsi_std = np.std(rsi_results)
print(f"\n波动: 时间法 std={time_std:.1f}%  RSI法 std={rsi_std:.1f}%")
