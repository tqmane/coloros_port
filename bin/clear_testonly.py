#!/usr/bin/env python3
"""Clear android:testOnly="true" in a binary AndroidManifest.xml.

Why this is needed
------------------
A16's CustCore.apk (the package that provides
com.oplus.customize.coreapp.configmanager.configprovider.AppFeatureProvider)
ships with android:testOnly="true". On a stock OnePlus 15 something else
whitelists it, but on a ported ROM PackageManager marks it DISABLED_USER
during the first scan. With the provider's package disabled, the Seedling SDK
plugin cannot resolve
    com.oplus.coreapp.appfeature.AppFeatureProviderUtils
and Fluid Cloud card pinning (ライブアラートのピン留め) stops working.

The A14 build of the same package has no testOnly flag, which is why the
problem only appears when porting A16 onto an A14 base.

This rewrites the attribute value in place: same file length, same offsets,
only the 4-byte integer holding the boolean flips from 1 to 0. Length-preserving
edits keep every other structure in the AXML valid.

Usage:  clear_testonly.py <AndroidManifest.xml>
Exit:   0 = cleared or already false, 1 = error, 2 = attribute not present
"""

import struct
import sys

RES_TEST_ONLY = 0x01010272

CHUNK_XML = 0x0003
CHUNK_STRING_POOL = 0x0001
CHUNK_RESOURCE_MAP = 0x0180
CHUNK_START_ELEMENT = 0x0102

# Attribute record layout inside a START_ELEMENT chunk:
#   ns(4) name(4) rawValue(4) typedSize(2) res0(1) dataType(1) data(4) = 20 bytes
ATTR_SIZE = 20
ATTR_NAME_OFF = 4
ATTR_RAW_OFF = 8
ATTR_DATA_OFF = 16

# ResXMLTree_attrExt.attributeStart is measured from the start of attrExt,
# which begins after ResXMLTree_node: chunk header (8) + lineNumber (4)
# + comment (4) = 16 bytes into the chunk.
ATTR_EXT_OFF = 16


def clear_test_only(path: str) -> int:
    with open(path, "rb") as fh:
        buf = bytearray(fh.read())

    if len(buf) < 8:
        print(f"error: {path} too small to be an AXML file", file=sys.stderr)
        return 1

    magic, _hsize, _fsize = struct.unpack_from("<HHI", buf, 0)
    if magic != CHUNK_XML:
        print(f"error: {path} is not a binary AndroidManifest.xml", file=sys.stderr)
        return 1

    # Pass 1: resource map gives us the attribute-name index for testOnly.
    test_only_idx = None
    off = 8
    while off + 8 <= len(buf):
        ctype, _hsize, csize = struct.unpack_from("<HHI", buf, off)
        if csize < 8 or off + csize > len(buf):
            break
        if ctype == CHUNK_RESOURCE_MAP:
            count = (csize - 8) // 4
            ids = struct.unpack_from("<%dI" % count, buf, off + 8)
            if RES_TEST_ONLY in ids:
                test_only_idx = ids.index(RES_TEST_ONLY)
            break
        off += csize

    if test_only_idx is None:
        return 2

    # Pass 2: walk elements and flip the value wherever that attribute appears.
    cleared = 0
    already = 0
    off = 8
    while off + 8 <= len(buf):
        ctype, hsize, csize = struct.unpack_from("<HHI", buf, off)
        if csize < 8 or off + csize > len(buf):
            break

        if ctype == CHUNK_START_ELEMENT:
            # ResXMLTree_node: chunk(8) lineNo(4) comment(4)
            # ResXMLTree_attrExt: ns(4) name(4) attrStart(2) attrSize(2)
            #                     attrCount(2) idIdx(2) classIdx(2) styleIdx(2)
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", buf, off + 24)
            if attr_size == 0:
                attr_size = ATTR_SIZE
            base = off + ATTR_EXT_OFF + attr_start
            for i in range(attr_count):
                rec = base + i * attr_size
                if rec + attr_size > off + csize:
                    break
                name_idx = struct.unpack_from("<I", buf, rec + ATTR_NAME_OFF)[0]
                if name_idx != test_only_idx:
                    continue
                data_at = rec + ATTR_DATA_OFF
                value = struct.unpack_from("<I", buf, data_at)[0]
                if value == 0:
                    already += 1
                    continue
                # TYPE_INT_BOOLEAN: 0 = false, 0xffffffff = true.
                struct.pack_into("<I", buf, data_at, 0)
                # rawValue is a string reference; -1 means "no raw string".
                raw_at = rec + ATTR_RAW_OFF
                if struct.unpack_from("<i", buf, raw_at)[0] != -1:
                    struct.pack_into("<i", buf, raw_at, -1)
                cleared += 1

        off += csize

    if cleared == 0:
        return 0 if already else 2

    with open(path, "wb") as fh:
        fh.write(buf)
    print(f"cleared testOnly in {path} ({cleared} occurrence(s))")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(1)
    sys.exit(clear_test_only(sys.argv[1]))
