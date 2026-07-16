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
from instruments import get_instrument, list_instruments
from etf_shares import SHARE_OBSERVATION_ENABLED, load_share_observation


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
        """,
    )

    supported_symbols = [spec.symbol for spec in list_instruments()]
    parser.add_argument("--symbol", type=str, default="563360", choices=supported_symbols,
                        help="标的代码 (默认: 563360)")
    parser.add_argument("--name", type=str, default=None,
                        help="显示名称 (默认: 自动使用代码)")
    parser.add_argument("--days", type=int, default=90,
                        help="图表展示天数 (默认: 90)")
    parser.add_argument("--no-plot", action="store_true",
                        help="跳过图表生成")
    parser.add_argument("--force-refresh", action="store_true",
                        help="强制从网络刷新数据")
    args = parser.parse_args()
    instrument = get_instrument(args.symbol)
    name = args.name or instrument.name

    # 1. 数据
    df = load_data(symbol=args.symbol, force_refresh=args.force_refresh)

    share_observation = None
    if SHARE_OBSERVATION_ENABLED:
        try:
            share_observation = load_share_observation(
                args.symbol,
                df.index,
                force_refresh=args.force_refresh,
            )
        except Exception as exc:
            print(f"ETF 份额观察暂不可用：{exc}")

    # 2. 终端面板
    show(
        df,
        symbol=args.symbol,
        name=name,
        share_observation=share_observation,
    )

    # 3. 图表
    if not args.no_plot:
        print()
        df = compute_indicators(df, instrument)
        indicators = get_indicator_row(df)
        draw(df, indicators, symbol=args.symbol, name=name, days=args.days)
        print()


if __name__ == "__main__":
    main()
