"""Debug keyword_in_assertion filter"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from validate_text import _keyword_in_assertion

tests = [
    ("等 MACD 绿柱缩短再评估", "绿柱缩短", False),
    ("等 MACD 绿柱缩短或价格止跌", "绿柱缩短", False),
    ("不是高质量放量突破", "放量突破", False),
    ("不是高质量放量突破", "放量", False),
    ("已经死叉", "死叉", True),
    ("DIF 下穿 DEA 形成死叉", "死叉", True),
]

for text, kw, expected in tests:
    result = _keyword_in_assertion(text, kw)
    status = "OK" if result == expected else "FAIL"
    print(f"{status}: '{kw}' in '{text}' -> {result} (expected {expected})")
