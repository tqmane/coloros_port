#!/usr/bin/env python3
"""Merge Oplus feature XML directories without replacing port-ROM features."""

from __future__ import annotations

import argparse
import copy
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


HARDWARE_PREFIXES = (
    "android.hardware.",
    "com.oplus.hardware.",
    "oplus.hardware.",
    "oppo.hardware.",
)


def parse_xml(path: Path) -> ET.ElementTree:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser)


def feature_name(element: ET.Element) -> str | None:
    if not isinstance(element.tag, str):
        return None
    if not element.tag.endswith("feature"):
        return None
    return element.get("name")


def iter_feature_elements(root: ET.Element):
    for element in root:
        name = feature_name(element)
        if name:
            yield element, name


def is_hardware_feature(name: str) -> bool:
    return name.startswith(HARDWARE_PREFIXES)


def collect_names(directory: Path) -> set[str]:
    names: set[str] = set()
    for path in sorted(directory.glob("*.xml")):
        try:
            root = parse_xml(path).getroot()
        except ET.ParseError as exc:
            raise ValueError(f"{path}: invalid XML: {exc}") from exc
        names.update(name for _, name in iter_feature_elements(root))
    return names


def write_xml(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def merge_directories(
    base_dir: Path,
    port_dir: Path,
    *,
    hardware_from_base: bool,
) -> tuple[int, int, int]:
    if not base_dir.is_dir():
        raise ValueError(f"base directory does not exist: {base_dir}")
    if not port_dir.is_dir():
        raise ValueError(f"port directory does not exist: {port_dir}")

    base_names = collect_names(base_dir)
    port_names = collect_names(port_dir)
    added_files = 0
    added_features = 0
    removed_features = 0

    if hardware_from_base:
        for port_path in sorted(port_dir.glob("*.xml")):
            tree = parse_xml(port_path)
            root = tree.getroot()
            changed = False
            for element, name in list(iter_feature_elements(root)):
                if is_hardware_feature(name) and name not in base_names:
                    root.remove(element)
                    port_names.discard(name)
                    removed_features += 1
                    changed = True
            if changed:
                write_xml(tree, port_path)

    for base_path in sorted(base_dir.glob("*.xml")):
        port_path = port_dir / base_path.name
        if not port_path.exists():
            shutil.copy2(base_path, port_path)
            added_files += 1
            port_names.update(
                name for _, name in iter_feature_elements(parse_xml(base_path).getroot())
            )
            continue

        base_tree = parse_xml(base_path)
        port_tree = parse_xml(port_path)
        base_root = base_tree.getroot()
        port_root = port_tree.getroot()
        if base_root.tag != port_root.tag:
            print(
                f"warning: root mismatch, keeping port file: {base_path.name} "
                f"({base_root.tag!r} != {port_root.tag!r})",
                file=sys.stderr,
            )
            continue

        changed = False
        for element, name in iter_feature_elements(base_root):
            if name in port_names:
                continue
            port_root.append(copy.deepcopy(element))
            port_names.add(name)
            added_features += 1
            changed = True
        if changed:
            write_xml(port_tree, port_path)

    return added_files, added_features, removed_features


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--port-dir", type=Path, required=True)
    parser.add_argument(
        "--hardware-from-base",
        action="store_true",
        help="drop hardware feature declarations that the base device does not have",
    )
    args = parser.parse_args()

    try:
        added_files, added_features, removed_features = merge_directories(
            args.base_dir,
            args.port_dir,
            hardware_from_base=args.hardware_from_base,
        )
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        "feature XML merge: "
        f"+{added_files} files, +{added_features} features, "
        f"-{removed_features} unsupported hardware features"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
