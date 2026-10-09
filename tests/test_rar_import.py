import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from database.db import get_connection, initialize_database
from database.repository import Repository
from services.excel_import import import_rar


class FakeRarMember:
    filename = "2ndn14_postrad.ri"

    def is_dir(self):
        return False


class FakeRarArchive:
    member = FakeRarMember()

    def __init__(self, _):
        pass

    def infolist(self):
        return [self.member]

    def read(self, member):
        if member is not self.member:
            raise AssertionError("unexpected archive member")
        return b"V I\n1 2\n3 4\n"


class RarImportTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        database_path = Path(temporary_directory.name) / "measurements.db"
        initialize_database(database_path)
        self.repository = Repository(get_connection(database_path))
        self.addCleanup(self.repository.connection.close)

    def test_rar_import_reads_through_rarfile_without_invoking_system_command(self):
        with patch("rarfile.RarFile", FakeRarArchive):
            summary = import_rar(io.BytesIO(b"fake archive"), self.repository)

        self.assertEqual(summary["mediciones_nuevas"], 1)
        self.assertEqual(summary["puntos_nuevos"], 2)
        self.assertEqual(summary["archivos_seleccionados"], 1)
        self.assertEqual(summary["errores"], [])
        measurements = self.repository.iv_measurements()
        self.assertEqual(measurements.iloc[0].dispositivo, "2NDN14")
        self.assertEqual(measurements.iloc[0].campana, "postrad")
        self.assertEqual(len(self.repository.points(int(measurements.iloc[0].id))), 2)


if __name__ == "__main__":
    unittest.main()
