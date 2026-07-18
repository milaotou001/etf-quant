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


if __name__ == "__main__":
    unittest.main()
