import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from database.db import get_connection, initialize_database
from database.repository import Repository
from services.excel_import import import_rar, rar_device_groups, _read_rar_member


class FakeRarMember:
    filename = "2ndn14_postrad.ri"
    file_size = len(b"V I\n1 2\n3 4\n")

    def is_dir(self):
        return False


class FakeRarMember2(FakeRarMember):
    filename = "2nd14_postrad.ri"


class FakeRarMember3(FakeRarMember):
    filename = "MOSFET7_post_horno.ri"


class FakeRarArchive:
    member = FakeRarMember()
    members = [member]

    def __init__(self, _):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def infolist(self):
        return self.members


class RarImportTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        database_path = Path(temporary_directory.name) / "measurements.db"
        initialize_database(database_path)
        self.repository = Repository(get_connection(database_path))
        self.addCleanup(self.repository.connection.close)

    def test_rar_import_uses_bsdtar_to_extract_selected_member(self):
        extracted_content = b"V I\n1 2\n3 4\n"
        archive_content = b"fake archive"
        process_result = type("ProcessResult", (), {
            "returncode": 0,
            "stdout": extracted_content,
            "stderr": b"",
        })()
        uploaded_file = io.BytesIO(archive_content)
        uploaded_file.seek(5)

        def extract_member(command, **_):
            self.assertEqual(Path(command[2]).read_bytes(), archive_content)
            return process_result

        with (
            patch("rarfile.RarFile", FakeRarArchive),
            patch("services.excel_import.subprocess.run", side_effect=extract_member) as run,
            patch("services.excel_import.shutil.which", return_value="/usr/bin/bsdtar"),
        ):
            summary = import_rar(uploaded_file, self.repository)

        self.assertEqual(summary["mediciones_nuevas"], 1)
        self.assertEqual(summary["puntos_nuevos"], 2)
        self.assertEqual(summary["archivos_seleccionados"], 1)
        self.assertEqual(summary["errores"], [])
        measurements = self.repository.iv_measurements()
        self.assertEqual(measurements.iloc[0].dispositivo, "2NDN14")
        self.assertEqual(measurements.iloc[0].campana, "postrad")
        self.assertEqual(len(self.repository.points(int(measurements.iloc[0].id))), 2)
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["bsdtar", "-xOf"])
        self.assertEqual(command[-2:], ["--", FakeRarMember.filename])

    def test_rar_device_selection_matches_complete_device_not_prefix(self):
        process_result = type("ProcessResult", (), {
            "returncode": 0,
            "stdout": b"V I\n1 2\n3 4\n",
            "stderr": b"",
        })()
        with (
            patch.object(FakeRarArchive, "members", [FakeRarMember(), FakeRarMember2()]),
            patch("rarfile.RarFile", FakeRarArchive),
            patch("services.excel_import.subprocess.run", return_value=process_result) as run,
            patch("services.excel_import.shutil.which", return_value="/usr/bin/bsdtar"),
        ):
            summary = import_rar(io.BytesIO(b"fake archive"), self.repository, selected_devices={"2ND14"})

        self.assertEqual(summary["archivos_seleccionados"], 1)
        self.assertEqual(run.call_args.args[0][-2:], ["--", FakeRarMember2.filename])
        measurements = self.repository.iv_measurements()
        self.assertEqual(measurements.dispositivo.tolist(), ["2ND14"])

    def test_rar_device_groups_separate_similar_families(self):
        with (
            patch.object(FakeRarArchive, "members", [FakeRarMember(), FakeRarMember2()]),
            patch("rarfile.RarFile", FakeRarArchive),
        ):
            groups = rar_device_groups(io.BytesIO(b"fake archive"))

        self.assertEqual(groups, {"2ND": [(14, "2ND14")], "2NDN": [(14, "2NDN14")]})

    def test_rar_device_groups_include_other_device_families(self):
        with (
            patch.object(FakeRarArchive, "members", [FakeRarMember(), FakeRarMember3()]),
            patch("rarfile.RarFile", FakeRarArchive),
        ):
            groups = rar_device_groups(io.BytesIO(b"fake archive"))

        self.assertEqual(groups, {"2NDN": [(14, "2NDN14")], "MOSFET": [(7, "MOSFET7")]})

    def test_rar_import_filter_selects_device_from_other_family(self):
        process_result = type("ProcessResult", (), {
            "returncode": 0,
            "stdout": b"V I\n1 2\n3 4\n",
            "stderr": b"",
        })()
        with (
            patch.object(FakeRarArchive, "members", [FakeRarMember(), FakeRarMember3()]),
            patch("rarfile.RarFile", FakeRarArchive),
            patch("services.excel_import.subprocess.run", return_value=process_result) as run,
            patch("services.excel_import.shutil.which", return_value="/usr/bin/bsdtar"),
        ):
            summary = import_rar(
                io.BytesIO(b"fake archive"),
                self.repository,
                selected_devices={"MOSFET7"},
            )

        self.assertEqual(summary["archivos_seleccionados"], 1)
        self.assertEqual(run.call_args.args[0][-2:], ["--", FakeRarMember3.filename])
        measurements = self.repository.iv_measurements()
        self.assertEqual(measurements.dispositivo.tolist(), ["MOSFET7"])

    def test_rar_member_extraction_rejects_truncated_output(self):
        process_result = type("ProcessResult", (), {
            "returncode": 0,
            "stdout": b"partial",
            "stderr": b"",
        })()
        with patch("services.excel_import.subprocess.run", return_value=process_result):
            with self.assertRaisesRegex(ValueError, "extracción incompleta"):
                _read_rar_member(Path("archive.rar"), "2ndn14.ri", 100)

    def test_rar_member_extraction_reports_bsdtar_errors(self):
        process_result = type("ProcessResult", (), {
            "returncode": 1,
            "stdout": b"",
            "stderr": b"member is damaged",
        })()
        with patch("services.excel_import.subprocess.run", return_value=process_result):
            with self.assertRaisesRegex(ValueError, "member is damaged"):
                _read_rar_member(Path("archive.rar"), "2ndn14.ri", 100)


if __name__ == "__main__":
    unittest.main()
