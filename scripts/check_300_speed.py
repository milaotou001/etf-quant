import sys, time
sys.path.insert(0, r'C:\Users\admin\Desktop\etf量化工具')
from breadth import load_breadth

t0 = time.time()
result = load_breadth('510300')
elapsed = time.time() - t0

print(f'Total: {elapsed:.1f}s')
print(f'MA21: {result.get("ma21_display")} ({result.get("stocks_with_ma21")}/{result.get("total_stocks")})')
print(f'Coverage: {result.get("coverage_ratio")}')
