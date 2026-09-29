import unittest

import numpy as np
import pandas as pd

from services.measurements import compare_measurements_to_reference


class MeasurementRepository:
    def __init__(self, curves):
        self.curves = curves

    def points(self, measurement_id):
        return self.curves[measurement_id]


class MeasurementReferenceComparisonTests(unittest.TestCase):
    def test_compares_each_curve_vt_and_current_to_selected_measurement(self):
        voltage = np.linspace(0, 1, 11)
        curves = {
            1: pd.DataFrame({"v": voltage, "i": 0.0002 + 0.0001 * voltage}),
            2: pd.DataFrame({"v": voltage, "i": 0.00022 + 0.0001 * voltage}),
            3: pd.DataFrame({"v": voltage, "i": 0.0003 - 0.0001 * voltage}),
        }
        measurements = pd.DataFrame([{"id": measurement_id, "archivo": f"M{measurement_id}"} for measurement_id in curves])

        comparison = compare_measurements_to_reference(MeasurementRepository(curves), measurements, 1).set_index("id")

        self.assertAlmostEqual(comparison.loc[1, "error_vt"], 0)
        self.assertAlmostEqual(comparison.loc[1, "error_i"], 0)
        self.assertAlmostEqual(comparison.loc[2, "error_i"], 20e-6)
        self.assertAlmostEqual(comparison.loc[2, "error_i_pct"], 10)
        self.assertAlmostEqual(comparison.loc[3, "error_vt"], 1)

    def test_requires_the_reference_to_be_in_the_active_measurement_selection(self):
        with self.assertRaises(ValueError):
            compare_measurements_to_reference(MeasurementRepository({}), pd.DataFrame(), 1)


if __name__ == "__main__":
    unittest.main()
