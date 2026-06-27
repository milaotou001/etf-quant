# 当前状态

- 最后更新：2026-06-27
- 当前目标：决策辅助面板已可用，继续迭代优化
- 当前执行者：Claude

## 已完成

- `data.py` — akshare 数据获取 + 本地 CSV 缓存（超过 1 天自动刷新）
- `dashboard.py` — 三层面板：大势一行总结 + 纪律提醒 + 关键数字留白
- `chart.py` — mplfinance K 线图（布林带 + MA + 成交量 + RSI，不标注买卖箭头）
- `main.py` — CLI 主入口，支持 --days/--no-plot/--force-refresh/--entry-price/--entry-date
- 终端端到端测试通过

## 使用方式

```powershell
.venv\Scripts\python.exe main.py                  # 默认 90 天窗口
.venv\Scripts\python.exe main.py --days 180       # 半年窗口
.venv\Scripts\python.exe main.py --no-plot        # 只看面板不画图
.venv\Scripts\python.exe main.py --force-refresh  # 强制刷新数据
.venv\Scripts\python.exe main.py --entry-price 1.385 --entry-date 2026-06-20  # 持仓模式
```

## 下一步

- 用户实际使用反馈
- 面板信息密度可根据实际看盘体验调整

## 本轮禁止

- 不输出自动买卖信号
- 不引入 ML/DL
- 不实现自动化下单
- 不批量删除文件
