import unittest

import numpy as np
import pandas as pd

from services.vt_analysis import (
    average_vt_by_device_mode,
    available_temperatures,
    delta_vt_at_currents,
    filter_by_temperature,
    parse_target_currents,
    preferred_temperature,
)


class MeasurementRepository:
    def __init__(self, curves):
        self.curves = curves

    def points(self, measurement_id):
        return self.curves[measurement_id]


class VtAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.currents = np.array([1.0, 2.0, 3.0])
        self.repository = MeasurementRepository({
            1: pd.DataFrame({"v": [2.0, 4.0, 6.0], "i": self.currents}),
            2: pd.DataFrame({"v": [2.5, 4.5, 6.5], "i": self.currents}),
        })
        self.measurements = pd.DataFrame([
            {"id": 1, "dispositivo_id": 7, "campana": "A", "archivo": "M1"},
            {"id": 2, "dispositivo_id": 7, "campana": "B", "archivo": "M2"},
        ])

    def test_calculates_delta_vt_against_selected_reference_at_multiple_currents(self):
        result, warnings = delta_vt_at_currents(self.repository, self.measurements, [1.5, 2.5], 1)

        self.assertEqual(warnings, [])
        comparison = result[result.id == 2].set_index("Corriente [A]")
        self.assertAlmostEqual(comparison.loc[1.5, "VT [V]"], 3.5)
        self.assertAlmostEqual(comparison.loc[1.5, "ΔVT [V]"], 0.5)
        self.assertAlmostEqual(comparison.loc[2.5, "ΔVT [V]"], 0.5)

    def test_averages_multiple_measurements_per_device_and_mode(self):
        measurements = pd.DataFrame([
            {"id": 1, "dispositivo": "D1", "campana": "post horno", "archivo": "M1"},
            {"id": 2, "dispositivo": "D1", "campana": "post horno", "archivo": "M2"},
            {"id": 3, "dispositivo": "D1", "campana": "post curie", "archivo": "M3"},
            {"id": 4, "dispositivo": "D2", "campana": "post horno", "archivo": "M4"},
        ])
        repository = MeasurementRepository({
            1: pd.DataFrame({"v": [2.0, 4.0, 6.0], "i": self.currents}),
            2: pd.DataFrame({"v": [4.0, 6.0, 8.0], "i": self.currents}),
            3: pd.DataFrame({"v": [3.0, 5.0, 7.0], "i": self.currents}),
            4: pd.DataFrame({"v": [1.0, 3.0, 5.0], "i": self.currents}),
        })

        summary, details, warnings = average_vt_by_device_mode(repository, measurements, 2.0)

        self.assertEqual(warnings, [])
        self.assertEqual(len(details), 4)
        grouped = summary.set_index(["Dispositivo", "Modo / campaña"])
        self.assertAlmostEqual(grouped.loc[("D1", "post horno"), "VT promedio [V]"], 5.0)
        self.assertEqual(grouped.loc[("D1", "post horno"), "Mediciones válidas"], 2)
        self.assertAlmostEqual(grouped.loc[("D1", "post curie"), "VT promedio [V]"], 5.0)
        self.assertAlmostEqual(grouped.loc[("D2", "post horno"), "VT promedio [V]"], 3.0)

    def test_global_average_does_not_extrapolate(self):
        measurements = self.measurements.assign(dispositivo="D1")
        summary, _, warnings = average_vt_by_device_mode(self.repository, measurements, 0.5)

        self.assertTrue(summary.empty)
        self.assertTrue(any("fuera del rango medido" in warning for warning in warnings))

    def test_does_not_extrapolate_outside_measured_current_range(self):
        result, warnings = delta_vt_at_currents(self.repository, self.measurements, [0.5], 1)

        self.assertTrue(result.empty)
        self.assertTrue(any("fuera del rango medido" in warning for warning in warnings))

    def test_rejects_measurements_from_multiple_devices(self):
        measurements = self.measurements.copy()
        measurements.loc[1, "dispositivo_id"] = 8

        with self.assertRaisesRegex(ValueError, "mismo dispositivo"):
            delta_vt_at_currents(self.repository, measurements, [1.5], 1)

    def test_parses_and_deduplicates_target_currents(self):
        self.assertEqual(parse_target_currents("0.1; 0,2; 0.1"), [0.1, 0.2])

    def test_rejects_invalid_target_current(self):
        with self.assertRaisesRegex(ValueError, "no válida"):
            parse_target_currents("0.1; texto")

    def test_prefers_26_then_28_degrees_when_available(self):
        measurements = pd.DataFrame([
            {"id": 1, "archivo": "M1_T28", "campana": "A"},
            {"id": 2, "archivo": "M2_T26", "campana": "B"},
            {"id": 3, "archivo": "M3_T35", "campana": "C"},
        ])

        temperatures = available_temperatures(measurements)

        self.assertEqual(temperatures, [26.0, 28.0, 35.0])
        self.assertEqual(preferred_temperature(temperatures), 26.0)
        self.assertEqual(preferred_temperature([28.0, 35.0]), 28.0)
        self.assertIsNone(preferred_temperature([35.0]))
        self.assertIsNone(preferred_temperature([]))

    def test_filters_measurements_by_temperature(self):
        measurements = pd.DataFrame([
            {"id": 1, "archivo": "M1_T26", "campana": "post horno"},
            {"id": 2, "archivo": "M2_T28", "campana": "post horno"},
            {"id": 3, "archivo": "M3", "campana": "post curie"},
        ])

        result = filter_by_temperature(measurements, 26.0)

        self.assertEqual(result.id.tolist(), [1])


if __name__ == "__main__":
    unittest.main()
