import unittest
from datetime import datetime
import ml

class RiskTests(unittest.TestCase):
    def test_score_in_range(self):
        s, label = ml.predict_risk("amazon", datetime(2026, 11, 4, 10), datetime(2026, 11, 4, 16))
        self.assertTrue(3 <= s <= 95)
        self.assertIn(label, ("Low", "Medium", "High"))

    def test_risky_case_scores_higher(self):
        safe, _ = ml.predict_risk("amazon", datetime(2026, 11, 4, 10), datetime(2026, 11, 4, 16), 0)
        risky, _ = ml.predict_risk("india post", datetime(2026, 11, 8, 18), datetime(2026, 11, 8, 19), 20)
        self.assertGreater(risky, safe)

    def test_explain_returns_reasons(self):
        self.assertTrue(ml.explain("india post", datetime(2026, 11, 8, 18), datetime(2026, 11, 8, 19)))

if __name__ == "__main__":
    unittest.main()
