#!/usr/bin/env python3
"""Classify Oplus Camera Unit SDK EXIF flag ABI without external dependencies.

Checks the three ABI points involved in com.oplus.picture.exif.flag:
  * UTakePictureKeys initializes the key as long[] ([J) or int[] ([I)
  * CameraRequestTag.mExif is long (J) or int (I)
  * BaseMode.updateCaptureRequestTag accepts long[] and, on newer SDKs,
    also contains an int[] compatibility path.

Input may be a classes.dex or a jar/apk containing classes.dex.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


class DexError(RuntimeError):
    pass


@dataclass
class MethodCode:
    cls: str
    name: str
    code_off: int


class Dex:
    def __init__(self, blob: bytes):
        if not blob.startswith(b"dex\n"):
            raise DexError("not a DEX file")
        self.b = blob
        self.u16 = lambda o: struct.unpack_from("<H", blob, o)[0]
        self.u32 = lambda o: struct.unpack_from("<I", blob, o)[0]
        self.strings = self._read_strings()
        self.types = self._read_types()
        self.fields = self._read_fields()
        self.methods = self._read_methods()
        self.method_code = self._read_method_code()

    def uleb(self, off: int):
        value = shift = 0
        while True:
            x = self.b[off]
            off += 1
            value |= (x & 0x7F) << shift
            if not (x & 0x80):
                return value, off
            shift += 7
            if shift > 35:
                raise DexError("invalid uleb128")

    def _mutf8(self, off: int) -> str:
        _, p = self.uleb(off)
        e = self.b.index(0, p)
        return self.b[p:e].decode("utf-8", "replace")

    def _read_strings(self):
        n, off = self.u32(0x38), self.u32(0x3C)
        return [self._mutf8(self.u32(off + 4 * i)) for i in range(n)]

    def _read_types(self):
        n, off = self.u32(0x40), self.u32(0x44)
        return [self.strings[self.u32(off + 4 * i)] for i in range(n)]

    def _read_fields(self):
        n, off = self.u32(0x50), self.u32(0x54)
        out = []
        for i in range(n):
            c, t, name = struct.unpack_from("<HHI", self.b, off + 8 * i)
            out.append((self.types[c], self.strings[name], self.types[t]))
        return out

    def _read_methods(self):
        n, off = self.u32(0x58), self.u32(0x5C)
        out = []
        for i in range(n):
            c, proto, name = struct.unpack_from("<HHI", self.b, off + 8 * i)
            out.append((self.types[c], self.strings[name], proto))
        return out

    def _read_method_code(self):
        n, off = self.u32(0x60), self.u32(0x64)
        codes: dict[tuple[str, str], list[MethodCode]] = {}
        for ci in range(n):
            vals = struct.unpack_from("<IIIIIIII", self.b, off + 32 * ci)
            class_idx, class_data = vals[0], vals[6]
            if not class_data:
                continue
            cls = self.types[class_idx]
            p = class_data
            sf, p = self.uleb(p)
            inf, p = self.uleb(p)
            dm, p = self.uleb(p)
            vm, p = self.uleb(p)
            field_idx = 0
            for _ in range(sf + inf):
                d, p = self.uleb(p)
                _, p = self.uleb(p)
                field_idx += d
            for count in (dm, vm):
                method_idx = 0
                for _ in range(count):
                    d, p = self.uleb(p)
                    _, p = self.uleb(p)
                    code, p = self.uleb(p)
                    method_idx += d
                    mcls, name, _ = self.methods[method_idx]
                    # mcls should equal cls, but retain the method table's value.
                    if code:
                        codes.setdefault((mcls, name), []).append(MethodCode(mcls, name, code))
        return codes

    def field_type(self, cls: str, name: str):
        found = sorted({t for c, n, t in self.fields if c == cls and n == name})
        if not found:
            return None
        return found[0] if len(found) == 1 else found

    @staticmethod
    def _widths():
        w = [1] * 256
        for x in [2, 5, 8, 0x13, 0x15, 0x16, 0x19, 0x1A, 0x1C, 0x1F, 0x20,
                  0x22, 0x23, 0x29, *range(0x2D, 0x32), *range(0x32, 0x3E),
                  *range(0x44, 0x6E), *range(0x90, 0xB0), *range(0xD0, 0xD8),
                  *range(0xD8, 0xE3)]:
            w[x] = 2
        for x in [3, 6, 9, 0x14, 0x17, 0x1B, 0x24, 0x25, 0x26, 0x2A,
                  0x2B, 0x2C, *range(0x6E, 0x73), *range(0x74, 0x79),
                  0xFA, 0xFB, 0xFC, 0xFD]:
            w[x] = 3
        w[0x18] = 5
        w[0xFE] = 2
        w[0xFF] = 2
        return w

    def instructions(self, code_off: int):
        size = self.u32(code_off + 12)
        start = code_off + 16
        cu = [self.u16(start + 2 * i) for i in range(size)]
        widths = self._widths()
        i = 0
        while i < size:
            u = cu[i]
            op = u & 0xFF
            if op == 0 and (u >> 8):
                ident = u >> 8
                if ident == 1:
                    n = cu[i + 1]
                    width = 4 + 2 * n
                elif ident == 2:
                    n = cu[i + 1]
                    width = 2 + 4 * n
                elif ident == 3:
                    elem = cu[i + 1]
                    n = cu[i + 2] | (cu[i + 3] << 16)
                    width = 4 + ((elem * n + 1) // 2)
                else:
                    width = 1
            else:
                width = widths[op]
            units = cu[i:i + width]
            yield i, op, units
            i += width

    def method_type_refs(self, cls: str, name: str):
        refs = []
        for m in self.method_code.get((cls, name), []):
            for pc, op, units in self.instructions(m.code_off):
                # const-class, check-cast, instance-of, new-instance, new-array,
                # filled-new-array[/range] all carry a type@BBBB in unit 1.
                if op in (0x1C, 0x1F, 0x20, 0x22, 0x23, 0x24, 0x25) and len(units) >= 2:
                    idx = units[1]
                    if idx < len(self.types):
                        refs.append((pc, op, self.types[idx]))
        return refs

    def base_mode_exif_block(self):
        cls = "Lcom/oplus/ocs/camera/producer/mode/BaseMode;"
        methods = self.method_code.get((cls, "updateCaptureRequestTag"), [])
        key_owner = "Lcom/oplus/ocs/camera/metadata/UTakePictureKeys;"
        key_name = "KEY_PICTURE_EXIF_FLAG"
        req_owner = "Lcom/oplus/ocs/camera/common/util/CameraRequestTag;"
        for m in methods:
            ins = list(self.instructions(m.code_off))
            start = None
            for n, (pc, op, units) in enumerate(ins):
                if op == 0x62 and len(units) >= 2:  # sget-object
                    idx = units[1]
                    if idx < len(self.fields):
                        owner, name, typ = self.fields[idx]
                        if owner == key_owner and name == key_name:
                            start = n
                            break
            if start is None:
                continue
            arrays = set()
            store = None
            store_field_type = None
            # The EXIF block is at the beginning of this method. Stop after a
            # bounded window before unrelated array types can pollute the ABI
            # classification.
            start_pc = ins[start][0]
            for pc, op, units in ins[start:start + 40]:
                if pc - start_pc > 0x50:
                    break
                if op in (0x1C, 0x1F, 0x20, 0x22, 0x23, 0x24, 0x25) and len(units) >= 2:
                    t = self.types[units[1]]
                    if t in ("[I", "[J"):
                        arrays.add(t)
                if 0x52 <= op <= 0x6D and len(units) >= 2:
                    idx = units[1]
                    if idx < len(self.fields):
                        owner, name, typ = self.fields[idx]
                        if owner == req_owner and name == "mExif":
                            store = "iput-wide" if op == 0x5A else "iput" if op == 0x59 else f"op-{op:02x}"
                            store_field_type = typ
                # JPEG GPS starts immediately after the EXIF block in the
                # known Oplus implementations.
                if op == 0x62 and len(units) >= 2:
                    idx = units[1]
                    if idx < len(self.fields):
                        owner, name, _ = self.fields[idx]
                        if owner == "Landroid/hardware/camera2/CaptureRequest;" and name == "JPEG_GPS_LOCATION":
                            break
            return {
                "array_types": sorted(arrays),
                "store_opcode": store,
                "store_field_type": store_field_type,
            }
        return {"array_types": [], "store_opcode": None, "store_field_type": None}

    def key_init_array_type(self):
        cls = "Lcom/oplus/ocs/camera/metadata/UTakePictureKeys;"
        methods = self.method_code.get((cls, "<clinit>"), [])
        key_string = "com.oplus.picture.exif.flag"
        key_idx = None
        try:
            key_idx = self.strings.index(key_string)
        except ValueError:
            return None
        for m in methods:
            ins = list(self.instructions(m.code_off))
            for n, (pc, op, units) in enumerate(ins):
                # const-string vAA, string@BBBB / const-string-jumbo
                sidx = None
                if op == 0x1A and len(units) >= 2:
                    sidx = units[1]
                elif op == 0x1B and len(units) >= 3:
                    sidx = units[1] | (units[2] << 16)
                if sidx != key_idx:
                    continue
                # PreviewKey construction immediately follows. Search a small
                # bounded window for const-class [I / [J.
                for _, op2, u2 in ins[n + 1:n + 9]:
                    if op2 == 0x1C and len(u2) >= 2:
                        t = self.types[u2[1]]
                        if t in ("[I", "[J"):
                            return t
        return None


def load_dex(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"dex\n"):
        return raw
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            try:
                return z.read("classes.dex")
            except KeyError as e:
                raise DexError(f"{path}: classes.dex not found") from e
    raise DexError(f"{path}: unsupported input (expected DEX/JAR/APK)")


def inspect(path: Path):
    dex = Dex(load_dex(path))
    req_cls = "Lcom/oplus/ocs/camera/common/util/CameraRequestTag;"
    base_cls = "Lcom/oplus/ocs/camera/producer/mode/BaseMode;"
    m_exif = dex.field_type(req_cls, "mExif")
    key_type = dex.key_init_array_type()
    exif_block = dex.base_mode_exif_block()
    base_arrays = exif_block["array_types"]

    # This pattern is the ABI-safe implementation seen in the modern donor:
    # key is long[], request tag stores long, and BaseMode handles both old
    # int[] and new long[] producers before storing with iput-wide.
    exif64_dual = (
        key_type == "[J" and m_exif == "J" and
        "[J" in base_arrays and "[I" in base_arrays and
        exif_block["store_opcode"] == "iput-wide"
    )
    legacy_int32 = (
        m_exif == "I" and key_type != "[J" and
        "[I" in base_arrays and exif_block["store_opcode"] == "iput"
    )

    if exif64_dual:
        abi = "exif64-dual"
    elif legacy_int32:
        abi = "legacy-int32"
    elif key_type == "[J" or m_exif == "J":
        abi = "exif64-partial-or-unknown"
    else:
        abi = "unknown"
    return {
        "path": str(path),
        "abi": abi,
        "key_picture_exif_flag_type": key_type,
        "camera_request_tag_mExif_type": m_exif,
        "base_mode_array_type_refs": base_arrays,
        "base_mode_exif_store_opcode": exif_block["store_opcode"],
        "exif64_dual_compatible": exif64_dual,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-exif64-dual", action="store_true",
                    help="exit non-zero unless the SDK has the modern dual ABI")
    ns = ap.parse_args()
    try:
        result = inspect(ns.input)
    except (OSError, DexError, IndexError, struct.error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if ns.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Camera Unit SDK: {result['path']}")
        print(f"ABI: {result['abi']}")
        print(f"  KEY_PICTURE_EXIF_FLAG: {result['key_picture_exif_flag_type']}")
        print(f"  CameraRequestTag.mExif: {result['camera_request_tag_mExif_type']}")
        print(f"  BaseMode EXIF array refs: {', '.join(result['base_mode_array_type_refs']) or '(none)'}")
        print(f"  BaseMode EXIF store: {result['base_mode_exif_store_opcode']}")
        print(f"  EXIF64 dual compatible: {str(result['exif64_dual_compatible']).lower()}")
    if ns.require_exif64_dual and not result["exif64_dual_compatible"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
