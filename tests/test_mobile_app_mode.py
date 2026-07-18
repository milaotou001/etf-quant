import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MobileAppModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(PROJECT_ROOT, "app.py").read_text(encoding="utf-8")

    def test_navigation_comes_from_runtime_mode(self):
        self.assertIn("MOBILE_READ_ONLY = is_mobile_read_only(os.environ)", self.source)
        self.assertIn("mobile_page_options(MOBILE_READ_ONLY)", self.source)

    def test_private_controls_are_inside_local_only_branch(self):
        branch = self.source.index("if not MOBILE_READ_ONLY:")
        uploader = self.source.index("st.file_uploader", branch)
        cloud_plan = self.source.index("load_mobile_plan(os.environ)", uploader)
        self.assertLess(branch, uploader)
        self.assertLess(uploader, cloud_plan)

    def test_cloud_plan_render_is_explicitly_read_only(self):
        self.assertIn("read_only=MOBILE_READ_ONLY", self.source)
        self.assertIn("if read_only:", self.source)
        self.assertIn("手机只读快照", self.source)

    def test_cloud_branch_does_not_reconcile_or_save(self):
        route = self.source.index('if page == "半年买入计划"')
        start = self.source.index("if MOBILE_READ_ONLY:", route)
        end = self.source.index("else:", start)
        branch = self.source[start:end]
        self.assertNotIn("reconcile_purchase_plan", branch)
        self.assertNotIn("save_purchase_plan", branch)
        self.assertNotIn("load_trade_cache", branch)

    def test_cloud_main_view_prioritizes_rsi(self):
        self.assertIn("primary_metric_order(read_only)", self.source)
        self.assertIn('metric_columns["rsi"]', self.source)

    def test_mobile_css_and_read_only_plan_card_exist(self):
        self.assertIn("@media (max-width: 700px)", self.source)
        self.assertIn(".plan-cell-readonly", self.source)
        self.assertIn("color: #101828 !important", self.source)
        for card in ("status-card", "plan-intro", "progress-card", "cash-card"):
            start = self.source.index(f".{card} {{")
            end = self.source.index("}", start)
            self.assertIn("color: #101828 !important", self.source[start:end])
        self.assertIn("grid-template-columns: 1fr", self.source)

    def test_cloud_data_failure_is_explicit(self):
        self.assertIn("本次未取得行情数据", self.source)

    def test_cloud_plan_does_not_fetch_live_prices(self):
        self.assertIn(
            "for core_symbol in plan_price_symbols(MOBILE_READ_ONLY, TARGETS):",
            self.source,
        )

    def test_cloud_main_view_loads_synced_trade_points(self):
        self.assertIn("load_mobile_trades(os.environ)", self.source)
        self.assertIn("mobile_trade_cache.get(symbol)", self.source)
        self.assertIn("暂无已同步交易点", self.source)

    def test_local_mode_has_mobile_snapshot_export_entry(self):
        self.assertIn("生成手机同步包", self.source)
        self.assertIn("export_secret_file", self.source)

    def test_mobile_trade_points_follow_the_same_visibility_toggle(self):
        self.assertIn('show_trades = st.checkbox("显示个人交易记录")', self.source)
        self.assertIn("mobile_trade_cache.get(symbol) if MOBILE_READ_ONLY and show_trades", self.source)
        self.assertIn("个人交易点已关闭", self.source)


if __name__ == "__main__":
    unittest.main()
