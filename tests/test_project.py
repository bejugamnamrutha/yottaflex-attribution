import json, tempfile, unittest
from pathlib import Path
from src.generator import generate, validate
from src.analytics import load_frames, campaign_roi, model_summary

class ProjectTests(unittest.TestCase):
    def test_starter_generation_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/"config.json"
            cfg.write_text(json.dumps({"starter_scale":{"campaigns":5,"contacts":40,"touchpoints":100,"opportunities":20},"scale":{"campaigns":5,"contacts":40,"touchpoints":100,"opportunities":20}}))
            manifest,summary=generate(Path(d)/"data","starter",20261022,cfg)
            self.assertEqual(manifest["counts"]["Campaign"],5)
            self.assertEqual(manifest["counts"]["Contact"],40)
            self.assertTrue(summary["passed"])
    def test_credit_sums_and_roi(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/"config.json"
            cfg.write_text(json.dumps({"starter_scale":{"campaigns":8,"contacts":80,"touchpoints":250,"opportunities":40},"scale":{"campaigns":8,"contacts":80,"touchpoints":250,"opportunities":40}}))
            generate(Path(d)/"data","starter",20261022,cfg)
            frames=load_frames(Path(d)/"data"/"attribution.db")
            sums=frames["AttributionResult"].groupby(["opportunity_id","model"]).credit.sum()
            self.assertTrue(((sums-1).abs()<0.00001).all())
            self.assertIn("roi",campaign_roi(frames,"linear").columns)
            self.assertGreater(len(model_summary(frames)),0)

if __name__=="__main__": unittest.main()
