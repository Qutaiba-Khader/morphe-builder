#!/usr/bin/env python3
"""Read the package name out of an APK's binary AndroidManifest.xml.

Patches can rename the app (Morphe's non-root YouTube installs as
`app.morphe.android.youtube`, not `com.google.android.youtube`), and Obtainium
refuses to install when the downloaded package does not match the configured
id, so the id has to come from the built APK rather than from the patch
bundle's "compatible packages".

Works on a local file, or over HTTP with range requests so only the zip
directory and the manifest entry are fetched (~100 KB, not the whole APK).
Stdlib only.
"""

from __future__ import annotations

import struct
import sys
import urllib.request
import zlib

RES_STRING_POOL = 0x0001
RES_XML_START_ELEMENT = 0x0102
UTF8_FLAG = 1 << 8


def _string_pool(data: bytes, off: int) -> list[str]:
    _type, header_size, _size = struct.unpack_from("<HHI", data, off)
    count, _style_count, flags, strings_start, _styles_start = struct.unpack_from("<IIIII", data, off + 8)
    offsets = struct.unpack_from(f"<{count}I", data, off + header_size)
    base = off + strings_start
    utf8 = bool(flags & UTF8_FLAG)
    out: list[str] = []
    for rel in offsets:
        p = base + rel
        if utf8:
            # two varint lengths (chars, bytes), then the bytes
            n = data[p]
            p += 2 if n & 0x80 else 1
            n = data[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[p + 1]
                p += 2
            else:
                p += 1
            out.append(data[p : p + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", data, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0]
                p += 2
            out.append(data[p : p + n * 2].decode("utf-16-le", "replace"))
    return out


def package_from_manifest(axml: bytes) -> str:
    """Return the `package` attribute of the <manifest> element."""
    strings: list[str] = []
    off = 8  # skip the file header
    while off + 8 <= len(axml):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", axml, off)
        if chunk_size <= 0:
            break
        if chunk_type == RES_STRING_POOL:
            strings = _string_pool(axml, off)
        elif chunk_type == RES_XML_START_ELEMENT:
            body = off + header_size
            _ns, name_idx = struct.unpack_from("<iI", axml, body)
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, body + 8)
            if strings and strings[name_idx] == "manifest":
                for i in range(attr_count):
                    a = body + attr_start + i * attr_size
                    _a_ns, a_name, a_raw = struct.unpack_from("<iii", axml, a)
                    if strings[a_name] == "package" and a_raw >= 0:
                        return strings[a_raw]
                raise LookupError("<manifest> has no package attribute")
        off += chunk_size
    raise LookupError("no <manifest> element found")


# --------------------------------------------------------------------- remote


def _fetch(url: str, start: int | None = None, end: int | None = None) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "morphe-builder")
    if start is not None:
        req.add_header("Range", f"bytes={start}-{'' if end is None else end}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def package_from_url(url: str) -> str:
    """Read the package name using HTTP range requests only."""
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as head:
        total = int(head.headers["Content-Length"])
        url = head.geturl()

    tail_len = min(total, 128 * 1024)
    tail = _fetch(url, total - tail_len)
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise LookupError("no end-of-central-directory (zip64 APK?)")
    cd_size, cd_off = struct.unpack_from("<II", tail, eocd + 12)

    cd = tail[-(total - cd_off) :] if cd_off >= total - tail_len else _fetch(url, cd_off, cd_off + cd_size - 1)

    p = 0
    while p + 46 <= len(cd) and cd[p : p + 4] == b"PK\x01\x02":
        method, = struct.unpack_from("<H", cd, p + 10)
        comp_size, = struct.unpack_from("<I", cd, p + 20)
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", cd, p + 28)
        local_off, = struct.unpack_from("<I", cd, p + 42)
        name = cd[p + 46 : p + 46 + name_len].decode("utf-8", "replace")
        if name == "AndroidManifest.xml":
            local = _fetch(url, local_off, local_off + 30 + 65536)
            ln_len, le_len = struct.unpack_from("<HH", local, 26)
            data_at = 30 + ln_len + le_len
            need = local_off + data_at + comp_size - 1
            blob = local[data_at : data_at + comp_size]
            if len(blob) < comp_size:
                blob = _fetch(url, local_off + data_at, need)
            return package_from_manifest(zlib.decompress(blob, -15) if method == 8 else blob)
        p += 46 + name_len + extra_len + comment_len
    raise LookupError("AndroidManifest.xml not in the central directory")


def package_of(target: str) -> str:
    if target.startswith(("http://", "https://")):
        return package_from_url(target)
    import zipfile

    with zipfile.ZipFile(target) as zf:
        return package_from_manifest(zf.read("AndroidManifest.xml"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: apk_package.py <apk path or url>")
    print(package_of(sys.argv[1]))
