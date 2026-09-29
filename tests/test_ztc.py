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

    def test_combined_rejects_locally_flat_crossing_with_unstable_neighboring_segment(self):
        voltage = np.linspace(0, 1, 1001)
        knots = np.array([0, .18, .2, .22, .48, .5, .52, .76, .8, .84, .9, 1])
        slope_values = np.array([-.001, -.0002, 0, .0002, .0002, 0, -.0002, -.0002, 0, .0002, .005, .01])
        slope = np.interp(voltage, knots, slope_values)
        curves = [pd.DataFrame({"v": voltage, "i": .001 + (temperature - 40) * slope}) for temperature in (20, 40, 60)]

        result, dispersion = analyze_curves(curves, [20, 40, 60], "combinado")

        candidates = dispersion.attrs["crossing_candidates"]
        self.assertEqual(len(candidates), 3)
        self.assertNotAlmostEqual(result.vt_ztc, .8, places=1)
        self.assertGreater(candidates[2]["segment_score"], candidates[0]["segment_score"])
        self.assertIn("segment_start", candidates[2])

    def test_combined_prefers_pair_crossing_near_160_microamps_when_other_segment_is_unstable(self):
        voltage = np.linspace(-5.1, -2.15, 321)
        knots = np.array([-5.1, -3.0, -2.9653266, -2.7378426, -2.5103586, -2.15])
        currents = (
            np.array([-0.0020213, -0.00038072, -0.000361795, -0.000248816, -0.000157675, -0.000064152]),
            np.array([-0.0018113, -0.00034066, -0.000325168, -0.000233309, -0.000157675, -0.000069452]),
            np.array([-0.0018138, -0.00037864, -0.000362995, -0.000268975, -0.000188878, -0.000091064]),
        )
        curves = [pd.DataFrame({"v": voltage, "i": np.interp(voltage, knots, current)}) for current in currents]

        result, dispersion = analyze_curves(curves, [20, 28, 36], "combinado")

        candidates = dispersion.attrs["crossing_candidates"]
        self.assertGreaterEqual(len(candidates), 2)
        self.assertAlmostEqual(abs(result.i_ztc) * 1_000_000, 160, delta=20)
        self.assertIn("20-28 °C", min(candidates, key=lambda candidate: candidate["stable_score"])["cruces"])


if __name__ == "__main__":
    unittest.main()