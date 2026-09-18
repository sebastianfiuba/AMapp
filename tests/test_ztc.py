import unittest

import numpy as np
import pandas as pd

from services.ztc import analyze_curves


class ZtcAnalysisTests(unittest.TestCase):
    def test_combined_crossing_returns_current_at_temperature_invariant_voltage(self):
        curves = []
        for temperature in (20, 40, 60):
            voltage = np.linspace(0, 1, 101)
            current = 0.0003 + (voltage - 0.6) * 0.0002 + (temperature - 40) * (voltage - 0.6) * 1e-7
            curves.append(pd.DataFrame({"v": voltage, "i": current}))

        result, dispersion = analyze_curves(curves, [20, 40, 60], "combinado")

        self.assertAlmostEqual(result.vt_ztc, 0.6, places=2)
        self.assertAlmostEqual(result.i_ztc, 0.0003, places=5)
        self.assertTrue(dispersion.attrs["crossing_candidates"])
        self.assertIn("slope_stability", dispersion.attrs["crossing_candidates"][0])


if __name__ == "__main__":
    unittest.main()