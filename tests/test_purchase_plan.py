import os
import sys
import tempfile
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

import purchase_plan
from purchase_plan import (
    STATUS_PENDING,
    STATUS_PLANNED,
    STATUS_RECONCILED,
    build_position_progress,
    calculate_open_quantity,
    default_purchase_plan,
    load_purchase_plan,
    mark_item_bought,
    reconcile_purchase_plan,
    save_purchase_plan,
    summarize_plan,
    undo_item_mark,
)


class PurchasePlanDefaultsTests(unittest.TestCase):
    def test_strategic_satellites_use_20_30_50_current_rounds(self):
        plan = default_purchase_plan()

        expected = {
            "561380": ([1_200.0, 1_800.0, 3_000.0], 6_000.0),
            "516150": ([1_000.0, 1_500.0, 2_500.0], 5_000.0),
            "159570": ([800.0, 1_200.0, 2_000.0], 4_000.0),
        }
        expected_note = "第1笔等初步止跌；第2笔等回踩确认；第3笔等右侧修复"
        for symbol, (amounts, reserved_amount) in expected.items():
            asset = plan["assets"][symbol]
            self.assertEqual([item["planned_amount"] for item in asset["items"]], amounts)
            self.assertEqual(asset["reserved_amount"], reserved_amount)
            self.assertEqual(asset["plan_note"], expected_note)

        self.assertEqual(
            plan["allocation_scheme"]["strategic_satellite"],
            {"first": 0.2, "second": 0.3, "third": 0.5},
        )

    def test_default_plan_has_confirmed_assets_amounts_and_initial_statuses(self):
        plan = default_purchase_plan()

        self.assertEqual(plan["base_amount"], 285_000.0)
        self.assertEqual(plan["version"], 6)
        self.assertEqual(len(plan["assets"]["563360"]["items"]), 3)
        self.assertEqual(len(plan["assets"]["510300"]["items"]), 3)
        self.assertEqual(len(plan["assets"]["518880"]["items"]), 12)
        self.assertEqual(len(plan["assets"]["588000"]["items"]), 6)
        self.assertEqual(len(plan["assets"]["561380"]["items"]), 3)
        self.assertEqual(len(plan["assets"]["516150"]["items"]), 3)
        self.assertEqual(len(plan["assets"]["159570"]["items"]), 3)
        expected_wide_amounts = [3_750.0, 3_750.0, 3_750.0]
        self.assertEqual(
            [item["planned_amount"] for item in plan["assets"]["563360"]["items"]],
            expected_wide_amounts,
        )
        self.assertEqual(
            [item["planned_amount"] for item in plan["assets"]["510300"]["items"]],
            expected_wide_amounts,
        )
        self.assertEqual(plan["assets"]["563360"]["plan_note"], "第三笔等待右侧确认")
        self.assertEqual(plan["assets"]["510300"]["plan_note"], "第三笔等待右侧确认")
        self.assertTrue(all(item["planned_amount"] == 2_552.5 for item in plan["assets"]["588000"]["items"]))

        targets = {symbol: asset["target"] for symbol, asset in plan["assets"].items()}
        self.assertEqual(
            targets,
            {
                "563360": 42_000.0,
                "510300": 42_000.0,
                "518880": 57_000.0,
                "588000": 28_500.0,
                "561380": 12_000.0,
                "516150": 10_000.0,
                "159570": 8_000.0,
            },
        )
        self.assertEqual(sum(targets.values()) + plan["cash_target"], plan["base_amount"])
        self.assertTrue(
            all(
                item["status"] == STATUS_PLANNED
                for symbol in ("561380", "516150", "159570")
                for item in plan["assets"][symbol]["items"]
            )
        )

        gold = plan["assets"]["518880"]["items"]
        self.assertEqual([item["planned_date"] for item in gold], list(pd.date_range("2026-07-10", "2026-09-25", freq="7D").strftime("%Y-%m-%d")))
        self.assertEqual(gold[0]["status"], STATUS_PENDING)
        self.assertEqual(gold[0]["confirmed_date"], "2026-07-10")
        self.assertTrue(all(item["status"] == STATUS_PLANNED for item in gold[1:]))

    def test_plan_round_trips_through_private_json(self):
        plan = default_purchase_plan()
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "purchase_plan.json")
            save_purchase_plan(plan, path)
            loaded = load_purchase_plan(path)

        self.assertEqual(loaded, plan)

    def test_version_three_migration_restores_current_third_and_removes_next_round(self):
        plan = default_purchase_plan()
        plan["version"] = 3
        plan["assets"].pop("516150", None)
        plan["assets"].pop("159570", None)
        for symbol in ("563360", "510300"):
            plan["assets"][symbol]["target"] = 57_000.0
            plan["assets"][symbol]["items"] = [
                {
                    "id": f"{symbol}-{number:02d}",
                    "number": number,
                    "planned_amount": amount,
                    "planned_date": None,
                    "status": STATUS_PENDING if number <= 2 else STATUS_PLANNED,
                    "confirmed_date": f"2026-07-{11 + number:02d}" if number <= 2 else None,
                    "confirmed_dates": [],
                    "actual": None,
                    "needs_confirmation": False,
                }
                for number, amount in enumerate(
                    [3_750.0, 3_750.0, 3_750.0, 5_625.0, 2_812.5, 2_812.5],
                    start=1,
                )
            ]

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "purchase_plan.json")
            save_purchase_plan(plan, path)
            loaded = load_purchase_plan(path)

        self.assertEqual(loaded["version"], 6)
        for symbol in ("563360", "510300"):
            items = loaded["assets"][symbol]["items"]
            self.assertEqual([item["number"] for item in items], [1, 2, 3])
            self.assertEqual(
                [item["status"] for item in items],
                [STATUS_PENDING, STATUS_PENDING, STATUS_PLANNED],
            )
            self.assertEqual(
                [item["confirmed_date"] for item in items],
                ["2026-07-12", "2026-07-13", None],
            )
            self.assertEqual(loaded["assets"][symbol]["target"], 42_000.0)
            self.assertEqual(loaded["assets"][symbol]["plan_note"], "第三笔等待右侧确认")
        self.assertEqual(loaded["assets"]["561380"]["target"], 12_000.0)
        self.assertIn("516150", loaded["assets"])
        self.assertIn("159570", loaded["assets"])

    def test_version_two_plan_adds_grid_without_changing_existing_records(self):
        plan = default_purchase_plan()
        plan["version"] = 2
        plan["assets"].pop("561380", None)
        plan["assets"]["563360"]["items"][0]["status"] = STATUS_PENDING
        plan["assets"]["563360"]["items"][0]["confirmed_date"] = "2026-07-13"

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "purchase_plan.json")
            save_purchase_plan(plan, path)
            loaded = load_purchase_plan(path)

        self.assertEqual(loaded["version"], 6)
        self.assertIn("561380", loaded["assets"])
        self.assertIn("516150", loaded["assets"])
        self.assertIn("159570", loaded["assets"])
        self.assertEqual(
            [item["planned_amount"] for item in loaded["assets"]["561380"]["items"]],
            [1_200.0, 1_800.0, 3_000.0],
        )
        self.assertEqual(loaded["assets"]["563360"]["items"][0]["status"], STATUS_PENDING)
        self.assertEqual(loaded["assets"]["563360"]["items"][0]["confirmed_date"], "2026-07-13")

    def test_version_four_plan_restores_wide_third_without_changing_started_items(self):
        plan = default_purchase_plan()
        plan["version"] = 4
        for symbol in ("563360", "510300"):
            plan["assets"][symbol].pop("plan_note", None)
            plan["assets"][symbol]["items"] = plan["assets"][symbol]["items"][:2]
            plan["assets"][symbol]["items"][0]["status"] = STATUS_PENDING
            plan["assets"][symbol]["items"][0]["confirmed_date"] = "2026-07-13"

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "purchase_plan.json")
            save_purchase_plan(plan, path)
            loaded = load_purchase_plan(path)

        self.assertEqual(loaded["version"], 6)
        for symbol in ("563360", "510300"):
            items = loaded["assets"][symbol]["items"]
            self.assertEqual([item["number"] for item in items], [1, 2, 3])
            self.assertEqual(items[0]["status"], STATUS_PENDING)
            self.assertEqual(items[0]["confirmed_date"], "2026-07-13")
            self.assertEqual(items[2]["planned_amount"], 3_750.0)
            self.assertEqual(items[2]["status"], STATUS_PLANNED)

    def test_version_five_migration_updates_only_unstarted_strategic_items(self):
        plan = default_purchase_plan()
        plan["version"] = 5
        asset = plan["assets"]["561380"]
        asset["items"] = [
            {
                **item,
                "planned_amount": old_amount,
                "status": STATUS_PENDING if item["number"] == 1 else STATUS_PLANNED,
                "confirmed_date": "2026-07-17" if item["number"] == 1 else None,
            }
            for item, old_amount in zip(asset["items"], [3_000.0, 1_500.0, 1_500.0])
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "purchase_plan.json")
            save_purchase_plan(plan, path)
            loaded = load_purchase_plan(path)

        migrated = loaded["assets"]["561380"]["items"]
        self.assertEqual(loaded["version"], 6)
        self.assertEqual(
            [item["planned_amount"] for item in migrated],
            [3_000.0, 1_800.0, 3_000.0],
        )
        self.assertEqual(migrated[0]["status"], STATUS_PENDING)
        self.assertEqual(migrated[0]["confirmed_date"], "2026-07-17")

    def test_wide_plan_items_use_direct_number_headings(self):
        self.assertTrue(hasattr(purchase_plan, "plan_item_heading"))
        self.assertEqual(
            purchase_plan.plan_item_heading("563360", {"number": 3, "planned_date": None}),
            "第3笔",
        )
        self.assertEqual(
            purchase_plan.plan_item_heading("561380", {"number": 3, "planned_date": None}),
            "第1轮 · 3",
        )
        self.assertEqual(
            purchase_plan.plan_item_heading("518880", {"number": 2, "planned_date": "2026-07-17"}),
            "第2笔 · 07-17",
        )


class PurchasePlanStateTests(unittest.TestCase):
    def test_planned_item_can_be_marked_pending_and_undone(self):
        plan = default_purchase_plan()
        item_id = plan["assets"]["563360"]["items"][0]["id"]

        marked = mark_item_bought(plan, item_id, "2026-07-13")
        item = marked["assets"]["563360"]["items"][0]
        self.assertEqual(item["status"], STATUS_PENDING)
        self.assertEqual(item["confirmed_date"], "2026-07-13")

        undone = undo_item_mark(marked, item_id)
        item = undone["assets"]["563360"]["items"][0]
        self.assertEqual(item["status"], STATUS_PLANNED)
        self.assertIsNone(item["confirmed_date"])

    def test_marking_does_not_mutate_the_input_plan(self):
        plan = default_purchase_plan()
        item_id = plan["assets"]["510300"]["items"][0]["id"]

        mark_item_bought(plan, item_id, "2026-07-13")

        self.assertEqual(plan["assets"]["510300"]["items"][0]["status"], STATUS_PLANNED)


class PurchasePlanReconciliationTests(unittest.TestCase):
    def test_split_fills_are_aggregated_into_one_plan_item(self):
        plan = default_purchase_plan()
        item_id = plan["assets"]["563360"]["items"][1]["id"]
        plan = mark_item_bought(
            plan,
            item_id,
            "2026-07-15",
            split_dates=["2026-07-15", "2026-07-16"],
        )
        trades = {
            "563360": [
                {"date": pd.Timestamp("2026-07-15"), "type": "buy", "price": 1.36, "qty": 1250, "amount": 1700.0},
                {"date": pd.Timestamp("2026-07-16"), "type": "buy", "price": 1.35, "qty": 1259, "amount": 1700.0},
            ]
        }

        reconciled = reconcile_purchase_plan(plan, trades)
        item = reconciled["assets"]["563360"]["items"][1]

        self.assertEqual(item["status"], STATUS_RECONCILED)
        self.assertEqual(item["actual"]["amount"], 3400.0)
        self.assertEqual(item["actual"]["qty"], 2509)
        self.assertEqual(len(item["actual"]["fills"]), 2)
        self.assertEqual(item["actual"]["dates"], ["2026-07-15", "2026-07-16"])

    def test_unique_buy_on_confirmed_date_reconciles_the_same_cell(self):
        plan = default_purchase_plan()
        item_id = plan["assets"]["563360"]["items"][0]["id"]
        plan = mark_item_bought(plan, item_id, "2026-07-13")
        trades = {
            "563360": [
                {"date": pd.Timestamp("2026-07-13"), "type": "buy", "price": 1.25, "qty": 3000, "amount": 3750.0}
            ]
        }

        reconciled = reconcile_purchase_plan(plan, trades)
        item = reconciled["assets"]["563360"]["items"][0]

        self.assertEqual(item["status"], STATUS_RECONCILED)
        self.assertEqual(item["actual"]["date"], "2026-07-13")
        self.assertEqual(item["actual"]["qty"], 3000)
        self.assertEqual(item["actual"]["price"], 1.25)
        self.assertEqual(item["actual"]["amount"], 3750.0)

    def test_multiple_same_day_buys_are_left_for_confirmation(self):
        plan = default_purchase_plan()
        item_id = plan["assets"]["510300"]["items"][0]["id"]
        plan = mark_item_bought(plan, item_id, "2026-07-13")
        trades = {
            "510300": [
                {"date": pd.Timestamp("2026-07-13"), "type": "buy", "price": 4.70, "qty": 400, "amount": 1880.0},
                {"date": pd.Timestamp("2026-07-13"), "type": "buy", "price": 4.71, "qty": 400, "amount": 1884.0},
            ]
        }

        result = reconcile_purchase_plan(plan, trades)
        item = result["assets"]["510300"]["items"][0]

        self.assertEqual(item["status"], STATUS_PENDING)
        self.assertTrue(item["needs_confirmation"])
        self.assertIsNone(item["actual"])


class PurchasePlanProgressTests(unittest.TestCase):
    def test_open_quantity_uses_buys_minus_sells(self):
        entries = [
            {"type": "buy", "qty": 1000},
            {"type": "sell_profit", "qty": 200},
            {"type": "buy", "qty": 100},
            {"type": "sell_loss", "qty": 50},
        ]

        self.assertEqual(calculate_open_quantity(entries), 850)

    def test_progress_is_separate_fixed_target_and_includes_pending_estimate(self):
        plan = default_purchase_plan()
        a500_item = plan["assets"]["563360"]["items"][0]["id"]
        plan = mark_item_bought(plan, a500_item, "2026-07-13")
        trades = {
            "563360": [{"type": "buy", "qty": 1000}],
            "510300": [{"type": "buy", "qty": 2000}],
            "518880": [{"type": "buy", "qty": 20_000}],
        }
        prices = {
            "563360": 1.3,
            "510300": 4.7,
            "518880": 6.0,
            "588000": 1.0,
            "561380": 0.72,
            "516150": 1.67,
            "159570": 1.46,
        }

        progress = build_position_progress(plan, trades, prices)

        self.assertEqual(progress["563360"]["target"], 42_000.0)
        self.assertEqual(progress["563360"]["market_value"], 1300.0)
        self.assertEqual(progress["563360"]["pending_estimate"], 3750.0)
        self.assertEqual(progress["563360"]["display_value"], 5050.0)
        self.assertEqual(progress["510300"]["display_value"], 9400.0)
        self.assertTrue(progress["518880"]["is_overweight"])
        self.assertEqual(progress["518880"]["gap"], 0.0)

    def test_summary_uses_fixed_plan_amounts_not_live_market_gaps(self):
        plan = default_purchase_plan()

        summary = summarize_plan(plan)

        self.assertEqual(summary["planned_total"], 82_815.0)
        self.assertEqual(summary["confirmed_amount"], 2_500.0)
        self.assertEqual(summary["remaining_amount"], 80_315.0)


if __name__ == "__main__":
    unittest.main()
