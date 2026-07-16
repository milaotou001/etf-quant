import os
from pathlib import Path
import sys
import tempfile
import unittest

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from policy.evidence import INITIAL_EVIDENCE
from policy.reviews import load_policy_reviews


def _policy_app(review_path: str) -> AppTest:
    script = (
        "from policy.page import render_policy_strategy\n"
        f"render_policy_strategy({review_path!r})"
    )
    return AppTest.from_string(script).run(timeout=10)


class PolicyPageTests(unittest.TestCase):
    def test_page_renders_three_simple_sections_without_tabs_or_candidate_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = os.path.join(directory, "policy_reviews.json")
            app = _policy_app(review_path)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.title[0].value, "战略方向")
        self.assertIn("年度战略白名单尚未发布", app.info[0].value)
        visible_text = " ".join(
            element.value
            for collection in (app.markdown, app.caption, app.subheader)
            for element in collection
        )
        self.assertIn("年度方向", visible_text)
        self.assertIn("ETF匹配", visible_text)
        self.assertIn("政策证据审核", visible_text)
        self.assertIn("地方覆盖：已查10/10个重点地区｜8地发现落地｜覆盖充分", visible_text)
        self.assertIn("2地本轮未见强证据，0地未检索", visible_text)
        self.assertIn("落地覆盖7个省级辖区", visible_text)
        self.assertIn("查看地方覆盖明细", [item.label for item in app.expander])
        self.assertIn("粤芯四期列入重大项目建设", visible_text)
        self.assertIn("晶合四期加速落地", visible_text)
        self.assertIn("地方扩产与项目证据已形成多地交叉验证", visible_text)
        self.assertNotIn("地方资金和项目证据仍待补齐", visible_text)
        self.assertNotIn("地方没有落地", visible_text)
        self.assertNotIn("产业候选档案", visible_text)
        self.assertEqual(len(app.tabs), 0)
        self.assertEqual(
            len(
                [
                    button
                    for button in app.button
                    if button.label == "确认方向、地方证据与ETF"
                ]
            ),
            3,
        )

    def test_clicking_confirm_persists_user_review(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = os.path.join(directory, "policy_reviews.json")
            app = _policy_app(review_path)
            confirm = next(
                button for button in app.button if button.label == "确认这条证据"
            )

            confirm.click().run(timeout=10)
            state = load_policy_reviews(review_path)

        first_id = INITIAL_EVIDENCE[0]["id"]
        self.assertEqual(state["reviews"][first_id]["decision"], "confirmed")

    def test_main_app_lists_strategy_as_sixth_page_and_routes_before_market_data(self):
        source = Path(PROJECT_ROOT, "app.py").read_text(encoding="utf-8")
        navigation = (
            '["状态与图表", "复盘日志", "策略回测", "策略规则", '
            '"半年买入计划", "战略方向"]'
        )

        self.assertIn(navigation, source)
        self.assertIn('if page == "战略方向":', source)
        strategy_route = source.index('if page == "战略方向":')
        market_load = source.index("df = load_prepared_data", strategy_route)
        self.assertLess(strategy_route, market_load)


if __name__ == "__main__":
    unittest.main()
