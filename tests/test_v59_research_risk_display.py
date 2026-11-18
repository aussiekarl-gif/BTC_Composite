import unittest

import numpy as np
import pandas as pd

from engines.research.v59_risk_display import (
    DISPLAY_RISK_MAX,
    display_research_risk,
    display_research_risk_series,
)


class ResearchRiskDisplayTests(unittest.TestCase):
    def test_scalar_scale_is_bounded_and_monotonic(self):
        raw = np.linspace(0.0, 1.0, 101)
        shown = [display_research_risk(value) for value in raw]
        self.assertTrue(all(0.0 <= value <= DISPLAY_RISK_MAX for value in shown))
        self.assertTrue(all(a <= b for a, b in zip(shown, shown[1:])))
        self.assertAlmostEqual(shown[0], 0.0)
        self.assertAlmostEqual(shown[-1], DISPLAY_RISK_MAX)

    def test_sqrt_mapping_spreads_low_raw_values(self):
        self.assertGreater(display_research_risk(0.01), 0.01)
        self.assertAlmostEqual(display_research_risk(0.25), 0.20)
        self.assertAlmostEqual(display_research_risk(1.0), 0.40)

    def test_series_preserves_index_and_missing_values(self):
        source = pd.Series([0.0, 0.25, np.nan, 1.0], index=list("abcd"))
        shown = display_research_risk_series(source)
        self.assertEqual(list(shown.index), list(source.index))
        self.assertAlmostEqual(shown["b"], 0.20)
        self.assertTrue(pd.isna(shown["c"]))
        self.assertAlmostEqual(shown["d"], 0.40)


if __name__ == "__main__":
    unittest.main()
