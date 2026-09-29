import unittest

import numpy as np
import pandas as pd

from services.measurements import iv_measurement_noise_flags


class IvMeasurementNoiseTests(unittest.TestCase):
    def setUp(self):
        self.voltage = np.linspace(0, 1, 201)
        self.base_current = 0.0001 + 0.001 * self.voltage**2
        self.measurements = pd.DataFrame([
            {"id": measurement_id, "dispositivo_id": 1, "campana_id": 1}
            for measurement_id in (1, 2, 3)
        ])

    def test_flags_random_noise_without_flagging_smooth_curves(self):
        noise = np.random.default_rng(7).normal(0, 0.00004, len(self.voltage))
        points = {
            1: pd.DataFrame({"v": self.voltage, "i": self.base_current}),
            2: pd.DataFrame({"v": self.voltage, "i": self.base_current + 0.00001 * self.voltage}),
            3: pd.DataFrame({"v": self.voltage, "i": self.base_current + noise}),
        }

        flags = iv_measurement_noise_flags(self.measurements, points).set_index("id")

        self.assertEqual(flags.loc[1, "control_iv"], "OK")
        self.assertEqual(flags.loc[2, "control_iv"], "OK")
        self.assertEqual(flags.loc[3, "control_iv"], "REVISAR ruido")
        self.assertGreater(flags.loc[3, "noise_ratio"], flags.loc[3, "noise_threshold"])

    def test_flags_an_isolated_current_spike(self):
        spiky_current = self.base_current.copy()
        spiky_current[100] += 0.001
        points = {
            1: pd.DataFrame({"v": self.voltage, "i": self.base_current}),
            2: pd.DataFrame({"v": self.voltage, "i": self.base_current + 0.00001 * self.voltage}),
            3: pd.DataFrame({"v": self.voltage, "i": spiky_current}),
        }

        flags = iv_measurement_noise_flags(self.measurements, points).set_index("id")

        self.assertEqual(flags.loc[3, "control_iv"], "REVISAR ruido")
        self.assertEqual(flags.loc[1, "control_iv"], "OK")

    def test_short_curves_are_not_assigned_a_noise_flag(self):
        short_measurement = pd.DataFrame([{"id": 4, "dispositivo_id": 1, "campana_id": 1}])
        short_points = {4: pd.DataFrame({"v": np.arange(6), "i": np.arange(6)})}

        flags = iv_measurement_noise_flags(short_measurement, short_points)

        self.assertEqual(flags.loc[0, "control_iv"], "Sin puntaje (<9 puntos)")


if __name__ == "__main__":
    unittest.main()
