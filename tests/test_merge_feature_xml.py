from __future__ import annotations

import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "merge_feature_xml.py"
SPEC = importlib.util.spec_from_file_location("merge_feature_xml", SCRIPT)
assert SPEC and SPEC.loader
MERGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERGER)


def write_features(path: Path, *names: str) -> None:
    root = ET.Element("oplus-config")
    for name in names:
        ET.SubElement(root, "oplus-feature", name=name)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def read_names(path: Path) -> set[str]:
    return {
        element.get("name", "")
        for element in ET.parse(path).getroot()
        if element.get("name")
    }


class MergeFeatureXmlTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.base = root / "base"
        self.port = root / "port"
        self.base.mkdir()
        self.port.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_keeps_port_software_and_adds_base_features(self) -> None:
        write_features(
            self.base / "features.xml",
            "oplus.hardware.nfc",
            "oplus.software.display.aod_support",
        )
        write_features(
            self.port / "features.xml",
            "oplus.hardware.nfc",
            "oplus.software.systemui.pin_task",
        )

        MERGER.merge_directories(
            self.base, self.port, hardware_from_base=True
        )

        self.assertEqual(
            read_names(self.port / "features.xml"),
            {
                "oplus.hardware.nfc",
                "oplus.software.display.aod_support",
                "oplus.software.systemui.pin_task",
            },
        )

    def test_removes_port_only_hardware_features(self) -> None:
        write_features(self.base / "features.xml", "oplus.hardware.nfc")
        write_features(
            self.port / "features.xml",
            "oplus.hardware.nfc",
            "oplus.hardware.fold",
            "oplus.software.fold_ui",
        )

        MERGER.merge_directories(
            self.base, self.port, hardware_from_base=True
        )

        self.assertEqual(
            read_names(self.port / "features.xml"),
            {"oplus.hardware.nfc", "oplus.software.fold_ui"},
        )

    def test_copies_base_only_files(self) -> None:
        write_features(self.base / "base-only.xml", "oplus.hardware.sensor")

        added_files, added_features, removed_features = MERGER.merge_directories(
            self.base, self.port, hardware_from_base=True
        )

        self.assertEqual((added_files, added_features, removed_features), (1, 0, 0))
        self.assertEqual(
            read_names(self.port / "base-only.xml"), {"oplus.hardware.sensor"}
        )


if __name__ == "__main__":
    unittest.main()
