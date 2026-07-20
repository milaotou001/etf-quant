"""标的目录：集中定义正式策略能力与实验观察范围。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    name: str
    market: str
    category: str
    is_core: bool
    rsi_first_entry: int | None = None
    rsi_second_entry: int | None = None
    rsi_confirmation: int | None = None
    requires_verified_amount: bool = False
    is_focus: bool = False
    is_alternate: bool = False

    @property
    def display_tier(self) -> str:
        if self.is_core:
            return "核心"
        if self.is_focus:
            return "重点"
        if self.is_alternate:
            return "候补"
        return "观察"

    @property
    def supports_campaign(self) -> bool:
        return self.is_core and self.rsi_first_entry is not None and self.rsi_second_entry is not None

    @property
    def supports_backtest(self) -> bool:
        return self.is_core and self.rsi_second_entry is not None


CORE_SYMBOLS = ("563360", "510300", "518880")

_INSTRUMENTS = (
    # === 核心持仓（已持有） ===
    InstrumentSpec("563360", "A500 ETF", "CN", "宽基", True, 40, 35, 40, True),
    InstrumentSpec("510300", "沪深300 ETF", "CN", "宽基", True, 40, 35, 40, True),
    InstrumentSpec("518880", "黄金 ETF", "CN", "黄金", True, 35, 30, 40, True),
    # === 产业卫星（按H1证据强度排序） ===
    InstrumentSpec("159570", "港股创新药 ETF", "CN", "产业卫星", False, is_focus=True),
    InstrumentSpec("561380", "电网设备 ETF", "CN", "产业卫星", False, is_focus=True),
    InstrumentSpec("516150", "稀土 ETF", "CN", "产业卫星", False, is_focus=True),
    InstrumentSpec("560860", "工业有色 ETF", "CN", "产业卫星", False, is_focus=True),
    # === 离岸成长 ===
    InstrumentSpec("513180", "恒生科技 ETF", "HK", "离岸成长", False),
    # === 暂停 ===
    InstrumentSpec("588000", "科创50 ETF", "CN", "暂停", False, 30, 25, 40, False),
    # === 防守配置（等半年报+RSI低位） ===
    InstrumentSpec("159549", "红利低波100 ETF", "CN", "防守配置", False),
    # === 候补 ===
    InstrumentSpec("159755", "电池 ETF", "CN", "候补", False, is_alternate=True),
    # === 观察（不参与买入计划） ===
    InstrumentSpec("159920", "恒生 ETF", "HK", "观察", False),
    InstrumentSpec("HSI", "恒生指数", "HK", "观察", False),
    InstrumentSpec("DBO", "WTI 原油 ETF", "US", "观察", False),
)

_BY_SYMBOL = {spec.symbol: spec for spec in _INSTRUMENTS}


def get_instrument(symbol: str) -> InstrumentSpec:
    try:
        return _BY_SYMBOL[symbol]
    except KeyError as exc:
        raise ValueError(f"不支持的标的：{symbol}") from exc


def list_instruments(include_experimental: bool = True) -> tuple[InstrumentSpec, ...]:
    if include_experimental:
        return _INSTRUMENTS
    return tuple(spec for spec in _INSTRUMENTS if spec.is_core)
