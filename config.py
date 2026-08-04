"""集中配置文件：市场状态评分、宽度阈值、变化分级。所有阈值可在此调整。"""

# ══════════════════════════════════════════════════════════════
# 市场状态 — 评分制
# ══════════════════════════════════════════════════════════════

# 均线方向：ma_today / ma_N_days_ago - 1 的阈值
MA21_SLOPE_UP = 0.005       # > +0.5% 视为向上
MA21_SLOPE_DOWN = -0.005    # < -0.5% 视为向下
MA60_SLOPE_UP = 0.008       # > +0.8% 视为向上（10日窗口，阈值放宽）
MA60_SLOPE_DOWN = -0.008

# 评分条件权重（正向条件 +1，负向条件 -1）
SCORE_PRICE_ABOVE_MA21 = 1
SCORE_PRICE_ABOVE_MA60 = 1
SCORE_MA8_ABOVE_MA21 = 1
SCORE_MA21_ABOVE_MA60 = 1
SCORE_MA21_UP = 2           # MA21 方向权重更高
SCORE_MA60_NOT_DOWN = 1     # MA60 不走弱

SCORE_PRICE_BELOW_MA21 = -1
SCORE_PRICE_BELOW_MA60 = -1
SCORE_MA8_BELOW_MA21 = -1
SCORE_MA21_BELOW_MA60 = -1
SCORE_MA21_DOWN = -2
SCORE_MA60_DOWN = -2

# 总分 → 状态映射（区间）
STATE_SCORE_BULL = 5         # >= 5 → 多头
STATE_SCORE_BULLISH = 2      # >= 2 → 偏多震荡
STATE_SCORE_BEARISH = -2     # <= -2 → 偏空震荡
STATE_SCORE_BEAR = -5        # <= -5 → 空头
# 中间 → 震荡

# 震荡"纠缠"判定：MA8/MA21/MA60 两两差值 < 此比例视为贴近
RANGE_PROXIMITY_PCT = 0.02   # 2% 以内
# 价格近期穿越 MA21 次数（10 天内）
RANGE_CROSSING_COUNT = 3

# 状态确认：新状态需连续 N 日才确认
CONFIRM_DAYS = 3

# 迟滞：多头进入 → 退出需要更低分
HYSTERESIS_ENTER_BULL = 5
HYSTERESIS_EXIT_BULL = 2     # 进入多头需 >=5，跌到 <=2 才退出

# ══════════════════════════════════════════════════════════════
# 市场宽度 — 冷热阈值
# ══════════════════════════════════════════════════════════════

BREADTH_HOT = 0.70           # > 70% 偏热
BREADTH_COLD = 0.30          # < 30% 偏冷
# 中间 → 正常

# 宽度变化分级（5日变化，百分点）
BREADTH_CHANGE_STRONG_IMPROVE = 10    # > +10pp → 明显改善
BREADTH_CHANGE_MODERATE_IMPROVE = 3   # > +3pp  → 小幅改善
BREADTH_CHANGE_STRONG_WORSEN = -10    # < -10pp → 明显恶化
BREADTH_CHANGE_MODERATE_WORSEN = -3   # < -3pp  → 小幅恶化
# 中间 → 基本稳定

# ══════════════════════════════════════════════════════════════
# 宽度数据质量
# ══════════════════════════════════════════════════════════════

COVERAGE_MIN = 0.90          # 覆盖率低于此值需警告
