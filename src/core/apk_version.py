# ---------------------------------------------------------
# morphe-builder: the version an installed app reports must BE the version its update page offers.
#
# ObtainX and Obtainium compare the update page with the versionName the phone reports. A build keeps the
# stock versionName (46.2.3), and nothing on the phone says which patches it has, so a patch-only update
# could not be told from the same build: "46.2.3" against "46.2.3-0.8.1" is ObtainX's "Version order
# unclear". So each APK's versionName carries the patch version: 46.2.3.0.8.1. Dots, not "-": in
# ObtainX's version_comparison.dart a plain 46.2.3 is then simply older than 46.2.3.0.8.1, with no warning.
#
# Licensed under the GNU GPLv3, like the rest of this repository.
# ---------------------------------------------------------

from __future__ import annotations

import re
import struct
import zipfile
from pathlib import Path

RES_STRING_POOL = 0x0001
RES_XML_START_ELEMENT = 0x0102
UTF8_FLAG = 1 << 8
TYPE_STRING = 0x03
PAGE = 16384

_BUNDLE_RE = re.compile(r"(\d+(?:\.\d+)*)(?:[-._]?(dev|pre|alpha|beta|rc)[-._]?(\d*))?", re.IGNORECASE)
# One number has to keep dev.16 < alpha.1 < beta.3 < rc.1 < the final bundle: ObtainX orders numbers only.
_PRE_BASE = {"dev": 0, "pre": 1000, "alpha": 2000, "beta": 3000, "rc": 4000}
FINAL_ON_PRERELEASE = 9999


class ApkVersionError(Exception):
    pass


def revision(bundle_version: str, prerelease: bool) -> str:
    """Patch version as numbers: 0.8.1; dev: 2.1.0-dev.6 -> 2.1.0.6; a final on the pre-release channel -> 2.1.0.9999."""
    m = _BUNDLE_RE.search(bundle_version)
    if not m:
        return ""
    if m.group(2):
        return f"{m.group(1)}.{_PRE_BASE[m.group(2).lower()] + int(m.group(3) or 0)}"
    return f"{m.group(1)}.{FINAL_ON_PRERELEASE}" if prerelease else m.group(1)


def update_version(app_version: str, bundle_version: str, prerelease: bool) -> str:
    rev = revision(bundle_version, prerelease)
    return f"{app_version}.{rev}" if rev else app_version


def _encode(text: str, utf8: bool) -> bytes:
    if utf8:
        raw = text.encode()
        if len(text) > 0x7F or len(raw) > 0x7F:
            raise ApkVersionError(f"version too long: {text}")
        return bytes([len(text), len(raw)]) + raw + b"\0"
    return struct.pack("<H", len(text)) + text.encode("utf-16-le") + b"\0\0"


def set_manifest_version_name(axml: bytes, name: str) -> bytes:
    """A binary AndroidManifest.xml with <manifest android:versionName> set to name: a new string at the end of the
    pool (existing indexes stay valid, and attribute names must stay first), and the attribute pointing at it."""
    if struct.unpack_from("<H", axml, 8)[0] != RES_STRING_POOL:
        raise ApkVersionError("the manifest does not start with a string pool")
    _type, header, pool_size = struct.unpack_from("<HHI", axml, 8)
    count, styles, flags, strings_start, styles_start = struct.unpack_from("<IIIII", axml, 16)
    if styles or styles_start:
        raise ApkVersionError("a manifest string pool with styles is not expected")
    offsets_at = 8 + header
    strings_at = 8 + strings_start
    pool_end = 8 + pool_size
    utf8 = bool(flags & UTF8_FLAG)
    blob = bytes(axml[strings_at:pool_end])
    new_offset = len(blob.rstrip(b"\0")) + (1 if utf8 else 2)  # keep the last string's terminator; padding goes
    if not utf8:
        new_offset += new_offset % 2
    blob = blob[:new_offset] + _encode(name, utf8)
    blob += b"\0" * (-len(blob) % 4)
    offsets = axml[offsets_at:strings_at] + struct.pack("<I", new_offset)
    new_pool_size = header + len(offsets) + len(blob)
    pool = bytearray(axml[8:offsets_at]) + offsets + blob
    struct.pack_into("<I", pool, 4, new_pool_size)
    struct.pack_into("<I", pool, 8, count + 1)
    struct.pack_into("<I", pool, 20, strings_start + 4)
    rest = bytearray(axml[pool_end:])
    if not _point_version_name(rest, _pool_strings(bytes(pool), utf8), count):
        raise ApkVersionError("<manifest> has no android:versionName")
    out = bytearray(axml[:8]) + pool + rest
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out)


def _pool_strings(pool: bytes, utf8: bool) -> list[str]:
    count, _styles, _flags, start, _ = struct.unpack_from("<IIIII", pool, 8)
    header = struct.unpack_from("<H", pool, 2)[0]
    out: list[str] = []
    for i in range(count):
        p = start + struct.unpack_from("<I", pool, header + 4 * i)[0]
        if utf8:
            p += 2 if pool[p] & 0x80 else 1
            n = pool[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | pool[p + 1]
                p += 2
            else:
                p += 1
            out.append(pool[p : p + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", pool, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", pool, p)[0]
                p += 2
            out.append(pool[p : p + n * 2].decode("utf-16-le", "replace"))
    return out


def _point_version_name(chunks: bytearray, strings: list[str], new_index: int) -> bool:
    off = 0
    while off + 8 <= len(chunks):
        chunk_type, header, size = struct.unpack_from("<HHI", chunks, off)
        if size <= 0:
            return False
        if chunk_type == RES_XML_START_ELEMENT:
            body = off + header
            _ns, name_idx = struct.unpack_from("<iI", chunks, body)
            if strings[name_idx] != "manifest":
                return False
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", chunks, body + 8)
            for i in range(attr_count):
                a = body + attr_start + i * attr_size
                if strings[struct.unpack_from("<I", chunks, a + 4)[0]] == "versionName":
                    struct.pack_into("<i", chunks, a + 8, new_index)
                    chunks[a + 15] = TYPE_STRING
                    struct.pack_into("<I", chunks, a + 16, new_index)
                    return True
            return False
        off += size
    return False


def _is_signature(name: str) -> bool:
    return bool(re.fullmatch(r"META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC))", name, re.IGNORECASE))


def set_version_name(apk: Path, name: str) -> None:
    """Rewrite the APK with that versionName. Its signature no longer holds: sign it again after this."""
    tmp = apk.with_suffix(".versioned.apk")
    with zipfile.ZipFile(apk) as src, zipfile.ZipFile(tmp, "w") as dst:
        for info in src.infolist():
            if _is_signature(info.filename):
                continue
            data = src.read(info.filename)
            if info.filename == "AndroidManifest.xml":
                data = set_manifest_version_name(data, name)
            out = zipfile.ZipInfo(info.filename, info.date_time)
            out.compress_type = info.compress_type
            out.external_attr = info.external_attr
            if info.compress_type == zipfile.ZIP_STORED:
                # Android maps stored files directly: resources.arsc on 4 bytes, native libraries on a page.
                align = PAGE if info.filename.endswith(".so") else 4
                start = dst.fp.tell() + 30 + len(info.filename.encode())
                out.extra = b"\0" * (-start % align)
            dst.writestr(out, data)
    tmp.replace(apk)
