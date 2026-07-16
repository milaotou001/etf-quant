import os
import sys
import tempfile
import unittest
from datetime import date


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from policy.catalog import POLICY_CANDIDATES
from policy.coverage import (
    COVERAGE_STATUS_LANDED,
    COVERAGE_STATUS_UNSEARCHED,
    build_coverage_summary,
    passes_local_execution_gate,
)
from policy.evidence import INITIAL_EVIDENCE
from policy.reviews import (
    load_policy_reviews,
    review_direction,
    resolve_evidence_status,
    review_evidence,
)
from policy.strategy import build_policy_snapshot, is_etf_review_stale


class PolicyCatalogTests(unittest.TestCase):
    def test_catalog_contains_legacy_34_plus_high_end_instruments(self):
        self.assertEqual(len(POLICY_CANDIDATES), 35)
        corrected = next(
            item for item in POLICY_CANDIDATES if item["id"] == "high-end-instruments"
        )
        self.assertEqual(corrected["origin"], "十五五原文修正")

    def test_candidate_ids_are_unique_and_evidence_only_uses_known_ids(self):
        candidate_ids = [item["id"] for item in POLICY_CANDIDATES]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
        known = set(candidate_ids)
        referenced = {
            industry
            for evidence in INITIAL_EVIDENCE
            for industry in evidence["industries"]
        }
        self.assertEqual(referenced - known, set())


class PolicyReviewTests(unittest.TestCase):
    def test_codex_verified_evidence_is_not_effective_before_user_confirmation(self):
        evidence = INITIAL_EVIDENCE[0]

        status = resolve_evidence_status(evidence, {"reviews": {}})

        self.assertEqual(status, "Codex已核验")

    def test_confirmed_evidence_becomes_effective_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "reviews.json")
            review_evidence(
                INITIAL_EVIDENCE[0]["id"],
                "confirmed",
                "2026-07-16",
                path=path,
            )
            state = load_policy_reviews(path)

        self.assertEqual(
            resolve_evidence_status(INITIAL_EVIDENCE[0], state),
            "正式生效",
        )
        self.assertEqual(
            state["reviews"][INITIAL_EVIDENCE[0]["id"]]["reviewed_on"],
            "2026-07-16",
        )

    def test_rejected_evidence_never_counts_as_effective(self):
        reviews = {
            "reviews": {
                INITIAL_EVIDENCE[0]["id"]: {
                    "decision": "rejected",
                    "reviewed_on": "2026-07-16",
                    "note": "原文定位需要修正",
                }
            }
        }

        status = resolve_evidence_status(INITIAL_EVIDENCE[0], reviews)

        self.assertEqual(status, "已驳回")

    def test_unknown_evidence_and_invalid_decision_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "reviews.json")
            with self.assertRaisesRegex(ValueError, "未知证据"):
                review_evidence("missing", "confirmed", "2026-07-16", path=path)
            with self.assertRaisesRegex(ValueError, "审核决定"):
                review_evidence(
                    INITIAL_EVIDENCE[0]["id"],
                    "pending",
                    "2026-07-16",
                    path=path,
                )

    def test_snapshot_keeps_formal_whitelist_empty(self):
        snapshot = build_policy_snapshot({"reviews": {}})

        self.assertEqual(snapshot["formal_directions"], [])
        self.assertEqual(snapshot["candidate_count"], 35)
        self.assertEqual(snapshot["codex_verified_count"], len(INITIAL_EVIDENCE))
        self.assertEqual(
            snapshot["pending_confirmation_count"],
            len(INITIAL_EVIDENCE),
        )

    def test_snapshot_has_three_to_five_draft_directions_with_one_main_and_one_backup(self):
        snapshot = build_policy_snapshot({"reviews": {}, "direction_reviews": {}})

        self.assertGreaterEqual(len(snapshot["directions"]), 3)
        self.assertLessEqual(len(snapshot["directions"]), 5)
        self.assertTrue(all(item["status"] == "草案" for item in snapshot["directions"]))
        for direction in snapshot["directions"]:
            self.assertIsNotNone(direction["main_etf"])
            self.assertLessEqual(len(direction.get("backup_etfs", [])), 1)

    def test_direction_requires_current_etf_confirmation_and_local_execution(self):
        draft = build_policy_snapshot({"reviews": {}, "direction_reviews": {}})["directions"][0]
        reviews = {"version": 1, "reviews": {}, "direction_reviews": {}}
        for evidence_id in draft["required_evidence_ids"]:
            reviews["reviews"][evidence_id] = {
                "decision": "confirmed",
                "reviewed_on": "2026-07-16",
                "note": "",
            }

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "reviews.json")
            from policy.reviews import save_policy_reviews

            save_policy_reviews(reviews, path)
            review_direction(
                draft["id"],
                draft["selection_version"],
                "confirmed",
                "2026-07-16",
                path=path,
            )
            confirmed_reviews = load_policy_reviews(path)
            confirmed = build_policy_snapshot(confirmed_reviews)

        formal_ids = {item["id"] for item in confirmed["formal_directions"]}
        self.assertNotIn(draft["id"], formal_ids)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "reviews.json")
            from policy.reviews import save_policy_reviews

            save_policy_reviews(confirmed_reviews, path)
            review_direction(
                draft["id"],
                draft["selection_version"],
                "confirmed",
                "2026-07-16",
                coverage_version=confirmed["directions"][0]["coverage"]["version"],
                path=path,
            )
            fully_confirmed_reviews = load_policy_reviews(path)
            fully_confirmed = build_policy_snapshot(fully_confirmed_reviews)

        self.assertIn(
            draft["id"],
            {item["id"] for item in fully_confirmed["formal_directions"]},
        )

        stale_version = {**confirmed["directions"][0], "selection_version": "changed"}
        from policy.strategy import resolve_direction_status

        self.assertEqual(
            resolve_direction_status(stale_version, confirmed_reviews, confirmed["evidence"]),
            "草案",
        )

        self.assertEqual(
            resolve_direction_status(
                confirmed["directions"][0],
                fully_confirmed_reviews,
                confirmed["evidence"],
                {"passes_local_execution": False},
            ),
            "草案",
        )

    def test_etf_review_is_stale_after_ninety_days(self):
        self.assertFalse(is_etf_review_stale("2026-07-16", date(2026, 10, 14)))
        self.assertTrue(is_etf_review_stale("2026-07-16", date(2026, 10, 15)))


class PolicyCoverageTests(unittest.TestCase):
    def test_unreadable_reports_remain_unsearched_instead_of_not_found(self):
        records = [
            {"region": "武汉", "status": COVERAGE_STATUS_LANDED},
            {"region": "北京", "status": COVERAGE_STATUS_UNSEARCHED},
            {"region": "上海", "status": COVERAGE_STATUS_UNSEARCHED},
        ]

        summary = build_coverage_summary(records, required_checked_ratio=0.8)

        self.assertEqual(summary["checked_count"], 1)
        self.assertEqual(summary["unsearched_count"], 2)
        self.assertEqual(summary["not_found_count"], 0)
        self.assertFalse(summary["coverage_sufficient"])

    def test_local_execution_gate_requires_coverage_and_two_regions_or_national_support(self):
        insufficient = {
            "coverage_sufficient": False,
            "landed_count": 2,
            "national_support_confirmed": True,
        }
        two_regions = {
            "coverage_sufficient": True,
            "landed_count": 2,
            "national_support_confirmed": False,
        }
        one_region_with_national = {
            "coverage_sufficient": True,
            "landed_count": 1,
            "national_support_confirmed": True,
        }

        self.assertFalse(passes_local_execution_gate(insufficient))
        self.assertTrue(passes_local_execution_gate(two_regions))
        self.assertTrue(passes_local_execution_gate(one_region_with_national))

    def test_two_cities_in_the_same_province_only_count_as_one_jurisdiction(self):
        records = [
            {"region": "广州市", "province": "广东省", "status": COVERAGE_STATUS_LANDED},
            {"region": "深圳市", "province": "广东省", "status": COVERAGE_STATUS_LANDED},
        ]

        summary = build_coverage_summary(records, required_checked_ratio=1)

        self.assertEqual(summary["landed_count"], 2)
        self.assertEqual(summary["landed_jurisdiction_count"], 1)
        self.assertFalse(summary["passes_local_execution"])

    def test_current_official_source_coverage_passes_local_execution_gate(self):
        snapshot = build_policy_snapshot({"reviews": {}, "direction_reviews": {}})

        self.assertTrue(all(item["status"] == "草案" for item in snapshot["directions"]))
        coverage_by_id = {
            item["id"]: item["coverage"] for item in snapshot["directions"]
        }
        self.assertTrue(
            all(item["checked_count"] == 10 for item in coverage_by_id.values())
        )
        self.assertEqual(coverage_by_id["integrated-circuits"]["landed_count"], 8)
        self.assertEqual(coverage_by_id["artificial-intelligence"]["landed_count"], 10)
        self.assertEqual(coverage_by_id["biopharma"]["landed_count"], 8)
        self.assertTrue(
            all(
                item["landed_jurisdiction_count"] == 7
                for item in coverage_by_id.values()
            )
        )
        self.assertTrue(
            all(item["passes_local_execution"] for item in coverage_by_id.values())
        )


if __name__ == "__main__":
    unittest.main()
