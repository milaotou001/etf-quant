import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from mobile_view import load_mobile_plan
from purchase_plan import default_purchase_plan, save_purchase_plan
from scripts.export_mobile_plan_secret import build_secrets_toml, export_secret_file


class MobilePlanExportTests(unittest.TestCase):
    def test_generated_toml_round_trips_the_plan(self):
        plan = default_purchase_plan()
        parsed = tomllib.loads(build_secrets_toml(plan))
        self.assertEqual(parsed["MOBILE_READ_ONLY"], "true")
        self.assertEqual(load_mobile_plan(parsed), plan)

    def test_export_refuses_a_missing_private_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "purchase_plan"):
                export_secret_file(
                    Path(directory, "missing-purchase_plan.json"),
                    Path(directory, "secrets.toml"),
                )

    def test_export_writes_only_the_secret_file(self):
        plan = default_purchase_plan()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "purchase_plan.json")
            target = Path(directory, "mobile_streamlit_secrets.toml")
            save_purchase_plan(plan, str(source))
            export_secret_file(source, target)
            self.assertEqual(
                load_mobile_plan(tomllib.loads(target.read_text(encoding="utf-8"))),
                plan,
            )


if __name__ == "__main__":
    unittest.main()
