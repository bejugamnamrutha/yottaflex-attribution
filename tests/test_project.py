
import json
import tempfile
import unittest
from pathlib import Path

from src.generator import generate
from src.analytics import (
    load_frames,
    campaign_roi,
    model_summary,
    exception_report,
)


class ProjectTests(unittest.TestCase):

    def create_dataset(self, directory, campaigns=8, contacts=80,
                       touchpoints=250, opportunities=40):
        cfg = Path(directory) / "config.json"

        cfg.write_text(json.dumps({
            "starter_scale": {
                "campaigns": campaigns,
                "contacts": contacts,
                "touchpoints": touchpoints,
                "opportunities": opportunities
            },
            "scale": {
                "campaigns": campaigns,
                "contacts": contacts,
                "touchpoints": touchpoints,
                "opportunities": opportunities
            }
        }))

        data_dir = Path(directory) / "data"

        manifest, summary = generate(
            data_dir, "starter", 20261022, cfg
        )

        frames = load_frames(data_dir / "attribution.db")
        return manifest, summary, frames

    def test_starter_generation_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, summary, frames = self.create_dataset(
                d, campaigns=5, contacts=40,
                touchpoints=100, opportunities=20
            )

            self.assertEqual(manifest["counts"]["Campaign"], 5)
            self.assertEqual(manifest["counts"]["Contact"], 40)
            self.assertTrue(summary["passed"])

    def test_all_four_attribution_models_exist(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            expected = {
                "first_touch", "last_touch",
                "linear", "position_based"
            }

            actual = set(frames["AttributionResult"]["model"].unique())
            self.assertEqual(actual, expected)

    def test_attribution_credit_sums_to_one(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            sums = frames["AttributionResult"].groupby(
                ["opportunity_id", "model"]
            )["credit"].sum()

            self.assertTrue(((sums - 1).abs() < 0.00001).all())

    def test_duplicate_revenue_is_identified(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            orders = frames["Order"]
            duplicate = orders[
                orders["issue_type"] == "duplicate_revenue"
            ]

            self.assertGreater(len(duplicate), 0)

            ref = duplicate.iloc[0]["external_order_ref"]
            matching = orders[orders["external_order_ref"] == ref]

            valid = matching[
                matching["issue_type"].fillna("") == ""
            ]

            self.assertEqual(len(valid), 1)

    def test_post_conversion_touch_is_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            flagged = frames["Touchpoint"][
                frames["Touchpoint"]["issue_type"] ==
                "post_conversion_touch"
            ]

            self.assertGreater(len(flagged), 0)

            results = frames["AttributionResult"]
            opportunities = frames["Opportunity"].set_index(
                "opportunity_id"
            )

            attributed = set(results["opportunity_id"])

            for _, touch in flagged.iterrows():
                matching = opportunities[
                    opportunities["contact_id"] == touch["contact_id"]
                ]

                for opp_id, opp in matching.iterrows():
                    if opp_id in attributed:
                        self.assertGreater(
                            touch["occurred_at"], opp["closed_at"]
                        )

    def test_currency_mismatch_is_excluded_from_roi(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            roi = campaign_roi(frames, "linear")
            eur = frames["CostRecord"][
                frames["CostRecord"]["currency"] != "USD"
            ]

            self.assertGreater(len(eur), 0)

            for campaign_id in eur["campaign_id"].unique():
                expected = frames["CostRecord"][
                    (frames["CostRecord"]["campaign_id"] == campaign_id) &
                    (frames["CostRecord"]["currency"] == "USD") &
                    (frames["CostRecord"]["issue_type"].fillna("") == "")
                ]["amount"].sum()

                actual = roi.loc[
                    roi["campaign_id"] == campaign_id, "spend"
                ].iloc[0]

                if expected == 0:
                    self.assertTrue(actual != actual)
                else:
                    self.assertAlmostEqual(actual, expected)

    def test_missing_campaign_cost_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            roi = campaign_roi(frames, "linear")
            missing = roi[roi["missing_cost_flag"]]

            self.assertGreater(len(missing), 0)
            self.assertTrue(missing["spend"].isna().all())
            self.assertTrue(missing["roi"].isna().all())
            self.assertTrue(missing["roas"].isna().all())

    def test_anonymous_lead_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(
                d,
                campaigns=20,
                contacts=1000,
                touchpoints=4000,
                opportunities=200
            )

            anonymous = frames["Lead"][
                frames["Lead"]["lead_id"] == "LEAD-ANOM-000001"
            ]

            self.assertEqual(len(anonymous), 1)
            self.assertTrue(anonymous["contact_id"].isna().all())
            self.assertTrue(anonymous["session_id"].notna().all())

    def test_exception_report(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, frames = self.create_dataset(d)

            report = exception_report(frames)

            self.assertGreater(report["duplicate_revenue_rows"], 0)
            self.assertGreater(report["currency_mismatch_costs"], 0)
            self.assertGreater(
                report["campaigns_missing_cost_records"], 0
            )


if __name__ == "__main__":
    unittest.main()
