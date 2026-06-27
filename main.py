"""ETF 量化辅助工具 — 主入口

晚上复盘 → 定计划 → 挂条件单
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

sys.stdout.reconfigure(encoding='utf-8')

from data import load_data
from dashboard import show, compute_indicators, get_indicator_row
from chart import draw


def main():
    parser = argparse.ArgumentParser(
        description="ETF 决策辅助面板",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  .venv\\Scripts\\python.exe main.py                       # 默认 563360 A500 ETF
  .venv\\Scripts\\python.exe main.py --symbol 510300       # 沪深300 ETF
  .venv\\Scripts\\python.exe main.py --symbol 510300 --name "沪深300 ETF"
  .venv\\Scripts\\python.exe main.py --days 180            # 半年窗口
  .venv\\Scripts\\python.exe main.py --no-plot             # 只看面板不画图
  .venv\\Scripts\\python.exe main.py --force-refresh       # 强制刷新数据
  .venv\\Scripts\\python.exe main.py --entry-price 1.385 --entry-date 2026-06-20
        """,
    )

    parser.add_argument("--symbol", type=str, default="563360",
                        help="ETF代码 (默认: 563360)")
    parser.add_argument("--name", type=str, default=None,
                        help="显示名称 (默认: 自动使用代码)")
    parser.add_argument("--days", type=int, default=90,
                        help="图表展示天数 (默认: 90)")
    parser.add_argument("--no-plot", action="store_true",
                        help="跳过图表生成")
    parser.add_argument("--force-refresh", action="store_true",
                        help="强制从网络刷新数据")
    parser.add_argument("--entry-price", type=float, default=None,
                        help="持仓买入价")
    parser.add_argument("--entry-date", type=str, default=None,
                        help="持仓买入日期 (YYYY-MM-DD)")

    args = parser.parse_args()
    name = args.name or args.symbol

    # 1. 数据
    df = load_data(symbol=args.symbol, force_refresh=args.force_refresh)

    # 2. 终端面板
    show(df, symbol=args.symbol, name=name,
         entry_price=args.entry_price, entry_date=args.entry_date)

    # 3. 图表
    if not args.no_plot:
        print()
        df = compute_indicators(df)
        indicators = get_indicator_row(df)
        draw(df, indicators, symbol=args.symbol, name=name, days=args.days)
        print()


if __name__ == "__main__":
    main()
