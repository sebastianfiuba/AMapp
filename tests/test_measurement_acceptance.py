import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from database.db import get_connection, initialize_database
from database.repository import Repository


class MeasurementAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "measurements.db"
        initialize_database(self.database_path)
        self.repository = Repository(get_connection(self.database_path))
        self.device_id = self.repository.add_device("2ndn14")
        self.campaign_id = self.repository.add_campaign(self.device_id, "postcañon3")
        self.measurement_ids = []
        points = pd.DataFrame({"v": [-1.0, -2.0], "i": [1e-6, 2e-6]})
        for index in range(2):
            measurement_id, _ = self.repository.add_measurement({
                "dispositivo_id": self.device_id,
                "campana_id": self.campaign_id,
                "archivo": f"m{index}.ri",
                "fecha": "",
                "descripcion": "",
                "clase": "",
                "estado": "",
                "observaciones": "",
                "measurement_hash": f"hash-{index}",
            })
            self.repository.add_points(measurement_id, points)
            self.measurement_ids.append(measurement_id)

    def test_rejection_groups_curves_and_excludes_them_from_analysis(self):
        self.repository.save_ztc(self.campaign_id, -1.5, 1.5e-6)

        self.repository.set_measurements_acceptance(self.measurement_ids, False, "Ruido alto")

        self.assertTrue(self.repository.iv_measurements(self.campaign_id).empty)
        self.assertEqual(len(self.repository.iv_measurements(self.campaign_id, include_unaccepted=True)), 2)
        self.assertTrue(self.repository.ztc_results().empty)
        rejected = self.repository.measurements().set_index("id").loc[self.measurement_ids]
        self.assertTrue((rejected["aceptada"] == 0).all())
        self.assertEqual(set(rejected["caso_no_aceptacion"]), {"Ruido alto"})

        self.repository.update_measurement_metadata(self.measurement_ids[0], {"aceptada": True})
        first = self.repository.measurements().set_index("id").loc[self.measurement_ids[0]]
        self.assertEqual(first.caso_no_aceptacion, "")
        self.repository.set_measurements_acceptance(self.measurement_ids[1:], True)
        accepted = self.repository.measurements().set_index("id").loc[self.measurement_ids]
        self.assertTrue((accepted["aceptada"] == 1).all())
        self.assertEqual(set(accepted["caso_no_aceptacion"]), {""})

    def test_migrates_legacy_eliminada_column_to_eliminado(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = Path(directory) / "legacy.db"
            legacy = sqlite3.connect(legacy_path)
            legacy.executescript("""
                CREATE TABLE dispositivos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, tag TEXT, numero TEXT);
                INSERT INTO dispositivos VALUES (1, 'D1', 'D', '1');
                CREATE TABLE campanas (
                    id INTEGER PRIMARY KEY, dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id), numero TEXT NOT NULL
                );
                INSERT INTO campanas VALUES (1, 1, 'C1');
                CREATE TABLE mediciones (
                    id INTEGER PRIMARY KEY, dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id),
                    campana_id INTEGER NOT NULL REFERENCES campanas(id), archivo TEXT NOT NULL, fecha TEXT,
                    descripcion TEXT, clase TEXT, estado TEXT, eliminada INTEGER NOT NULL DEFAULT 0,
                    measurement_hash TEXT UNIQUE, UNIQUE(campana_id, archivo)
                );
                INSERT INTO mediciones VALUES (1, 1, 1, 'old.ri', '', '', '', '', 1, 'old-hash');
            """)
            legacy.commit()
            legacy.close()

            initialize_database(legacy_path)
            migrated = Repository(get_connection(legacy_path)).measurements().iloc[0]

            self.assertEqual(migrated.eliminado, 1)
            self.assertFalse(bool(migrated.activa))
            self.assertEqual(migrated.aceptada, 1)


if __name__ == "__main__":
    unittest.main()