import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dashboard import (compute_indicators, build_market_analysis, build_rsi_cash_plan,
                       build_buy_checklist, build_campaign_observation, show, _risk_veto)
from instruments import get_instrument


def _macd_cols(df):
    dif = next(c for c in df.columns if c.startswith("MACD_"))
    dea = next(c for c in df.columns if c.startswith("MACDs_"))
    hist = next(c for c in df.columns if c.startswith("MACDh_"))
    return dif, dea, hist


def _base_df(include_amount=False):
    dates = pd.date_range("2026-01-01", periods=80, freq="D")
    close = pd.Series(np.linspace(1.0, 1.4, len(dates)), index=dates)
    data = {
        "open": close * 0.995,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.linspace(100000, 140000, len(dates)),
    }
    if include_amount:
        data["amount"] = np.linspace(10000000, 18000000, len(dates))
    return pd.DataFrame(data, index=dates)


def _analysis_df(**overrides):
    df = compute_indicators(_base_df())
    dif_col, dea_col, hist_col = _macd_cols(df)
    last = df.index[-1]
    prev = df.index[-2]
    defaults = {
        "close": 1.4210,
        "ma5": 1.4054,
        "ma10": 1.4002,
        "ma20": 1.3732,
        "ma60": 1.2500,
        "rvol": 0.78,
        "rsi": 58,
        "chg": 0.5,
        dif_col: 0.0145,
        dea_col: 0.0104,
        hist_col: 0.0041,
    }
    defaults.update(overrides)
    for col, value in defaults.items():
        df.loc[last, col] = value
    df.loc[prev, hist_col] = overrides.get("prev_hist", 0.0030)
    return df


# ═══ 旧测试（指标计算 + 市场分析） ═══

class MarketAnalysisTests(unittest.TestCase):
    def test_amount_rvol_is_preferred_when_amount_exists(self):
        df = compute_indicators(_base_df(include_amount=True))
        expected = df["amount"].iloc[-1] / df["amount"].rolling(20).mean().iloc[-1]
        self.assertTrue(df.attrs["rvol_available"])
        self.assertAlmostEqual(df["rvol"].iloc[-1], expected)

    def test_core_rvol_is_unavailable_when_verified_amount_is_missing(self):
        df = compute_indicators(_base_df(include_amount=False), get_instrument("563360"))
        self.assertFalse(df.attrs["rvol_available"])
        self.assertEqual(df.attrs["rvol_type"], "暂不可用")
        self.assertTrue(pd.isna(df["rvol"].iloc[-1]))

    def test_current_sample_is_quiet_strength(self):
        analysis = build_market_analysis(_analysis_df())
        self.assertEqual(analysis["state_label"], "缩量偏强")
        self.assertIn("量能确认不足", analysis["one_liner"])
        self.assertIn("看是否放量突破，最好 RVOL > 1.2。", analysis["next_watch"])
        self.assertIn("不需要等待 RSI 低位才观察", analysis["next_watch"][2])

    def test_rsi_cash_plan_only_outputs_below_threshold(self):
        normal_df = _analysis_df(rsi=58)
        low_df = _analysis_df(rsi=30)
        self.assertEqual(build_rsi_cash_plan(normal_df, 35), [])
        self.assertTrue(build_rsi_cash_plan(low_df, 35))

    def test_macd_red_bar_requires_hist_growth(self):
        df = _analysis_df(prev_hist=0.0050, **{"MACDh_12_26_9": 0.0041})
        macd_step = [step for step in build_market_analysis(df)["steps"] if step[0] == "MACD"][0]
        self.assertEqual(macd_step[1], "红柱为正")
        self.assertIn("没有继续增强", macd_step[2])

    def test_overheat_priority_beats_strong_breakout(self):
        analysis = build_market_analysis(_analysis_df(rvol=1.3, rsi=72))
        self.assertEqual(analysis["state_label"], "高位放量过热")


# ═══ 风险否决测试 ═══

class RiskVetoTests(unittest.TestCase):
    def test_veto_breakdown_with_volume(self):
        """放量破位应否决"""
        result = _risk_veto(close=1.35, ma20=1.3732, ma60=1.25,
                            rvol_val=1.3, rsi_val=55,
                            dif=0.01, dea=0.005,
                            hist=0.003, prev_hist=0.004, chg=-1.0)
        self.assertIsNotNone(result)
        self.assertIn("放量破位", result)

    def test_veto_weak_downtrend(self):
        """弱势下行（绿柱放大 + MA20下方）应否决"""
        result = _risk_veto(close=1.35, ma20=1.3732, ma60=1.25,
                            rvol_val=0.8, rsi_val=40,
                            dif=-0.01, dea=-0.005,
                            hist=-0.02, prev_hist=-0.01, chg=-0.5)
        self.assertIsNotNone(result)
        self.assertIn("弱势下行", result)

    def test_veto_severe_overheat(self):
        """严重过热应否决"""
        result = _risk_veto(close=1.42, ma20=1.37, ma60=1.25,
                            rvol_val=0.9, rsi_val=82,
                            dif=0.02, dea=0.01,
                            hist=0.01, prev_hist=0.008, chg=1.0)
        self.assertIsNotNone(result)
        self.assertIn("严重过热", result)

    def test_veto_high_position_overheat(self):
        """高位放量过热应否决"""
        result = _risk_veto(close=1.42, ma20=1.37, ma60=1.25,
                            rvol_val=1.4, rsi_val=73,
                            dif=0.02, dea=0.01,
                            hist=0.01, prev_hist=0.008, chg=0.8)
        self.assertIsNotNone(result)
        self.assertIn("高位放量过热", result)

    def test_veto_below_ma60_bearish(self):
        """MA60下方 + DIF<DEA 应否决"""
        # hist > prev_hist（绿柱缩短）避免先被"弱势下行"否决
        result = _risk_veto(close=1.20, ma20=1.37, ma60=1.25,
                            rvol_val=0.9, rsi_val=48,
                            dif=-0.01, dea=0.005,
                            hist=-0.005, prev_hist=-0.015, chg=-0.3)
        self.assertIsNotNone(result)
        self.assertIn("MA60下方", result)

    def test_veto_passes_clean_data(self):
        """正常数据不应触发否决"""
        result = _risk_veto(close=1.42, ma20=1.37, ma60=1.25,
                            rvol_val=0.85, rsi_val=58,
                            dif=0.015, dea=0.010,
                            hist=0.005, prev_hist=0.003, chg=0.5)
        self.assertIsNone(result)

    def test_veto_nan_data_does_not_trigger(self):
        """NaN 数据时不应误触发否决"""
        result = _risk_veto(close=1.42, ma20=1.37, ma60=np.nan,
                            rvol_val=np.nan, rsi_val=np.nan,
                            dif=np.nan, dea=np.nan,
                            hist=np.nan, prev_hist=np.nan, chg=0)
        self.assertIsNone(result)


# ═══ 买入清单重构测试 ═══

class BuyChecklistTests(unittest.TestCase):
    def test_checklist_returns_none_when_no_scenario(self):
        """无场景匹配时应返回 None"""
        df = _analysis_df()
        result = build_buy_checklist(df, 35)
        self.assertIsNone(result)

    def test_risk_veto_blocks_checklist(self):
        """风险否决触发时 buy checklist 应返回 None"""
        dif_col, dea_col, hist_col = _macd_cols(_analysis_df())
        df = _analysis_df(
            close=1.35, ma20=1.3732, rvol=1.3, chg=-1.5, rsi=50,
            **{hist_col: -0.01})
        result = build_buy_checklist(df, 35)
        self.assertIsNone(result)

    def test_rsi_low_recovery_triggered_by_past_low(self):
        """过去10日内RSI曾低于阈值时触发RSI低位修复"""
        df = compute_indicators(_base_df())
        # 倒数第5天 RSI 设低，当前 RSI 回升（用 .loc 避免 Copy-on-Write）
        target_idx = df.index[-6]
        df.loc[target_idx, "rsi"] = 30  # 低于阈值35
        df.loc[df.index[-1], "rsi"] = 42  # 当前已回升
        result = build_buy_checklist(df, 35)
        self.assertIsNotNone(result)
        self.assertEqual(result["scenario"], "RSI低位修复买入")
        self.assertEqual(result["total"], 4)
        # 曾入低位应始终通过
        self.assertTrue(result["conditions"][0]["ok"])

    def test_rsi_low_recovery_not_triggered_without_past_low(self):
        """历史RSI从未低于阈值时不触发"""
        df = compute_indicators(_base_df())
        # 全部 RSI 都正常（线性上涨的数据 RSI 在 50-70 之间）
        result = build_buy_checklist(df, 35)
        # 不应触发 RSI低位修复（除非回踩或突破场景匹配）
        if result is not None:
            self.assertNotEqual(result["scenario"], "RSI低位修复买入")

    def test_pullback_no_longer_requires_down_day(self):
        """健康回踩不再要求当日收跌"""
        df = compute_indicators(_base_df())
        last = df.index[-1]
        prev = df.index[-2]
        dif_col, dea_col, hist_col = _macd_cols(df)
        # 构造：价格从近期高点回落但当日微涨，靠近MA5，缩量
        recent_high_idx = -6
        df.loc[df.index[recent_high_idx], "close"] = 1.44
        df["close"] = df["close"].astype(float)
        df.loc[last, "close"] = 1.4070
        df.loc[last, "ma5"] = 1.4054
        df.loc[last, "ma10"] = 1.4002
        df.loc[last, "ma20"] = 1.3732
        df.loc[last, "ma60"] = 1.25
        df.loc[last, "rvol"] = 0.78
        df.loc[last, "rsi"] = 55
        df.loc[last, "chg"] = 0.1  # 当日收涨！
        df.loc[last, dif_col] = 0.0145
        df.loc[last, dea_col] = 0.0104
        df.loc[last, hist_col] = 0.0041
        df.loc[prev, hist_col] = 0.0030
        result = build_buy_checklist(df, 35)
        self.assertIsNotNone(result)
        self.assertEqual(result["scenario"], "健康回踩买入")
        self.assertEqual(result["total"], 4)

    def test_pullback_has_4_conditions(self):
        """健康回踩从5条减为4条（移除'回踩确认'）"""
        df = compute_indicators(_base_df())
        last = df.index[-1]
        prev = df.index[-2]
        dif_col, dea_col, hist_col = _macd_cols(df)
        recent_high_idx = -6
        df.loc[df.index[recent_high_idx], "close"] = 1.44
        df["close"] = df["close"].astype(float)
        df.loc[last, "close"] = 1.4050
        df.loc[last, "ma5"] = 1.4054
        df.loc[last, "ma10"] = 1.4002
        df.loc[last, "ma20"] = 1.3732
        df.loc[last, "ma60"] = 1.25
        df.loc[last, "rvol"] = 0.78
        df.loc[last, "rsi"] = 55
        df.loc[last, "chg"] = -0.3
        df.loc[last, dif_col] = 0.0145
        df.loc[last, dea_col] = 0.0104
        df.loc[last, hist_col] = 0.0041
        df.loc[prev, hist_col] = 0.0030
        result = build_buy_checklist(df, 35)
        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 4)
        labels = [c["label"] for c in result["conditions"]]
        self.assertNotIn("回踩确认", labels)

    def test_breakout_has_6_conditions(self):
        """放量突破从5条增为6条（新增'不远离均线'）"""
        df = compute_indicators(_base_df())
        last = df.index[-1]
        prev = df.index[-2]
        dif_col, dea_col, hist_col = _macd_cols(df)
        # 构造放量突破：多头排列 + RVOL 1.3 + MACD偏多 + 突破前高 + RSI 60 + 偏离2%
        df.loc[last, "close"] = 1.40
        df.loc[last, "ma5"] = 1.38
        df.loc[last, "ma10"] = 1.36
        df.loc[last, "ma20"] = 1.3732
        df.loc[last, "ma60"] = 1.25
        df.loc[last, "rvol"] = 1.3
        df.loc[last, "rsi"] = 60
        df.loc[last, "chg"] = 1.2
        df.loc[last, dif_col] = 0.02
        df.loc[last, dea_col] = 0.01
        df.loc[last, hist_col] = 0.01
        df.loc[prev, hist_col] = 0.008
        # 20日前高设在1.39
        high_idx = df.index[-21]
        df.loc[high_idx, "close"] = 1.39
        result = build_buy_checklist(df, 35)
        self.assertIsNotNone(result)
        self.assertEqual(result["scenario"], "放量突破买入")
        self.assertEqual(result["total"], 6)
        labels = [c["label"] for c in result["conditions"]]
        self.assertIn("不远离均线", labels)

    def test_breakout_not_far_from_ma20_fails_when_too_far(self):
        """偏离MA20超过5%时'不远离均线'应为❌"""
        df = compute_indicators(_base_df())
        last = df.index[-1]
        prev = df.index[-2]
        dif_col, dea_col, hist_col = _macd_cols(df)
        # 偏离 8% > 5%
        df.loc[last, "close"] = 1.49
        df.loc[last, "ma5"] = 1.44
        df.loc[last, "ma10"] = 1.42
        df.loc[last, "ma20"] = 1.3732
        df.loc[last, "ma60"] = 1.25
        df.loc[last, "rvol"] = 1.3
        df.loc[last, "rsi"] = 65
        df.loc[last, "chg"] = 2.0
        df.loc[last, dif_col] = 0.03
        df.loc[last, dea_col] = 0.02
        df.loc[last, hist_col] = 0.01
        df.loc[prev, hist_col] = 0.008
        high_idx = df.index[-21]
        df.loc[high_idx, "close"] = 1.39
        result = build_buy_checklist(df, 35)
        self.assertIsNotNone(result)
        far_cond = [c for c in result["conditions"] if c["label"] == "不远离均线"][0]
        self.assertFalse(far_cond["ok"])

    def test_priority_pullback_before_rsi_low(self):
        """新优先级：同时满足回踩和RSI低位修复时，回踩优先"""
        df = compute_indicators(_base_df())
        last = df.index[-1]
        prev = df.index[-2]
        dif_col, dea_col, hist_col = _macd_cols(df)
        recent_high_idx = -6
        df.loc[df.index[recent_high_idx], "close"] = 1.44
        df["close"] = df["close"].astype(float)
        # 构造同时满足回踩和RSI低位修复的条件
        df.loc[last, "close"] = 1.4050
        df.loc[last, "ma5"] = 1.4054
        df.loc[last, "ma10"] = 1.4002
        df.loc[last, "ma20"] = 1.3732
        df.loc[last, "ma60"] = 1.25
        df.loc[last, "rvol"] = 0.78
        df.loc[last, "rsi"] = 55
        df.loc[last, "chg"] = -0.3
        df.loc[last, dif_col] = 0.0145
        df.loc[last, dea_col] = 0.0104
        df.loc[last, hist_col] = 0.0041
        df.loc[prev, hist_col] = 0.0030
        # 把历史RSI设低（满足RSI低位修复触发条件）
        rsi_low_idx = df.index[-6]
        df.loc[rsi_low_idx, "rsi"] = 30
        result = build_buy_checklist(df, 35)
        self.assertIsNotNone(result)
        # 回踩优先
        self.assertEqual(result["scenario"], "健康回踩买入")


class CampaignObservationTests(unittest.TestCase):
    def test_right_side_confirmation_requires_rsi_recovery_and_macd_improvement(self):
        df = _analysis_df(rsi=41, prev_hist=-0.006, **{"MACDh_12_26_9": -0.003})
        df.loc[df.index[-5], "rsi"] = 34

        card = build_campaign_observation(df, get_instrument("563360"))

        self.assertEqual(card["phase"], "右侧确认观察")
        self.assertTrue(card["right_confirmation"])
        self.assertNotIn("买入", card["summary"])
        self.assertNotIn("加仓", card["summary"])

    def test_experimental_symbol_has_no_campaign_observation(self):
        self.assertIsNone(build_campaign_observation(_analysis_df(), get_instrument("HSI")))

    def test_cli_uses_campaign_observation_instead_of_buy_checklist(self):
        df = _analysis_df(rsi=41, prev_hist=-0.006, **{"MACDh_12_26_9": -0.003})
        df.loc[df.index[-5], "rsi"] = 34
        output = StringIO()

        with redirect_stdout(output):
            show(df, symbol="563360")

        self.assertIn("战役观察", output.getvalue())
        self.assertNotIn("买入条件检查", output.getvalue())


if __name__ == "__main__":
    unittest.main()
