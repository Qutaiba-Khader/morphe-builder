#!/usr/bin/env python3
"""Read the package name (and the signing certificate) out of an APK.

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


def manifest_attrs(axml: bytes) -> dict[str, str]:
    """The attributes of the <manifest> element (package, versionName, versionCode, ...)."""
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
                attrs: dict[str, str] = {}
                for i in range(attr_count):
                    a = body + attr_start + i * attr_size
                    _a_ns, a_name, a_raw = struct.unpack_from("<iii", axml, a)
                    if a_raw >= 0:
                        attrs[strings[a_name]] = strings[a_raw]
                    elif attr_size >= 20 and axml[a + 15] in (0x10, 0x11):  # a typed integer: versionCode
                        attrs[strings[a_name]] = str(struct.unpack_from("<I", axml, a + 16)[0])
                return attrs
        off += chunk_size
    raise LookupError("no <manifest> element found")


def package_from_manifest(axml: bytes) -> str:
    """Return the `package` attribute of the <manifest> element."""
    attrs = manifest_attrs(axml)
    if "package" not in attrs:
        raise LookupError("<manifest> has no package attribute")
    return attrs["package"]


# --------------------------------------------------------------------- Morphe's code

MORPHE_UTILS = "Lapp/morphe/extension/shared/Utils;"


def _uleb(data: bytes, p: int) -> tuple[int, int]:
    out = shift = 0
    while True:
        byte = data[p]
        p += 1
        out |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return out, p


def morphe_versions(dex: bytes) -> dict[str, str | None] | None:
    """What Morphe's Utils answers, if this dex holds that class: {method: the version}. None for a method that does not simply
    return a constant, as getAppVersionName does before our build step: it then reads the versionName with the patch number."""
    if MORPHE_UTILS.encode() not in dex:
        return None
    _strings_n, strings, _types_n, types, _protos_n, _protos, _fields_n, _fields, _methods_n, methods, class_count, classes = struct.unpack_from("<12I", dex, 0x38)

    def text(index: int) -> str:
        _, p = _uleb(dex, struct.unpack_from("<I", dex, strings + 4 * index)[0])
        return dex[p : dex.index(0, p)].decode("utf-8", "replace")

    wanted = {"getAppVersionName": None, "getRecommendedAppVersion": None}
    for i in range(class_count):
        type_idx, data = struct.unpack_from("<I", dex, classes + 32 * i)[0], struct.unpack_from("<I", dex, classes + 32 * i + 24)[0]
        if text(struct.unpack_from("<I", dex, types + 4 * type_idx)[0]) != MORPHE_UTILS or not data:
            continue
        p = data
        sizes = []
        for _ in range(4):
            n, p = _uleb(dex, p)
            sizes.append(n)
        for _ in range(sizes[0] + sizes[1]):
            _, p = _uleb(dex, p)
            _, p = _uleb(dex, p)
        for count in sizes[2:]:
            index = 0
            for k in range(count):
                step, p = _uleb(dex, p)
                index = step if k == 0 else index + step
                _, p = _uleb(dex, p)
                code, p = _uleb(dex, p)
                name = text(struct.unpack_from("<I", dex, methods + 8 * index + 4)[0])
                if name in wanted and code:
                    start = code + 16
                    if dex[start] == 0x1A and dex[start + 4] == 0x11 and dex[start + 1] == dex[start + 5]:  # const-string, return-object
                        wanted[name] = text(struct.unpack_from("<H", dex, start + 2)[0])
        return wanted
    return None


def morphe_problem(versions: dict[str, str | None], version_name: str | None, experimental: bool) -> str:
    """Why Morphe's code in this build is wrong, as it decides: ExperimentalAppNoticePatch alerts when reported > recommended."""
    reported, recommended = versions.get("getAppVersionName"), versions.get("getRecommendedAppVersion")
    if not reported:
        return "Morphe's code reads the versionName with the patch number: a stable build opens with its Experimental Alert"
    if version_name and version_name != reported and not version_name.startswith(f"{reported}."):
        return f"Morphe's code says version {reported}, the app is {version_name}"
    if not experimental and recommended and reported > recommended:
        return f"a stable build on {reported}, above Morphe's recommended {recommended}: it opens with its Experimental Alert"
    return ""


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
    return package_from_manifest(manifest_from_url(url))


def manifest_from_url(url: str) -> bytes:
    """Read AndroidManifest.xml using HTTP range requests only."""
    return _read_remote(url)[0]


def names_from_url(url: str) -> list[str]:
    """The names of the files in the APK, using HTTP range requests only."""
    return _read_remote(url)[1]


def morphe_versions_from_url(url: str) -> dict[str, str | None] | None:
    """morphe_versions of an APK over HTTP. The extension's dex files come last, so few are fetched."""
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as head:
        total = int(head.headers["Content-Length"])
        url = head.geturl()
    tail = _fetch(url, max(0, total - 128 * 1024))
    eocd = tail.rfind(b"PK\x05\x06")
    cd_size, cd_off = struct.unpack_from("<II", tail, eocd + 12)
    cd = _fetch(url, cd_off, cd_off + cd_size - 1)
    dexes: list[tuple[int, str, int, int, int]] = []
    p = 0
    while p + 46 <= len(cd) and cd[p : p + 4] == b"PK\x01\x02":
        method, = struct.unpack_from("<H", cd, p + 10)
        size, = struct.unpack_from("<I", cd, p + 20)
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", cd, p + 28)
        at, = struct.unpack_from("<I", cd, p + 42)
        name = cd[p + 46 : p + 46 + name_len].decode("utf-8", "replace")
        if name.startswith("classes") and name.endswith(".dex"):
            dexes.append((int(name[7:-4] or 1), name, method, size, at))
        p += 46 + name_len + extra_len + comment_len
    for _n, _name, method, size, at in sorted(dexes, reverse=True):
        head_bytes = _fetch(url, at, at + 29)
        name_len, extra_len = struct.unpack_from("<HH", head_bytes, 26)
        start = at + 30 + name_len + extra_len
        blob = _fetch(url, start, start + size - 1)
        found = morphe_versions(zlib.decompress(blob, -15) if method == 8 else blob)
        if found:
            return found
    return None


def _read_remote(url: str) -> tuple[bytes, list[str]]:
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

    names: list[str] = []
    found = None
    p = 0
    while p + 46 <= len(cd) and cd[p : p + 4] == b"PK\x01\x02":
        method, = struct.unpack_from("<H", cd, p + 10)
        comp_size, = struct.unpack_from("<I", cd, p + 20)
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", cd, p + 28)
        local_off, = struct.unpack_from("<I", cd, p + 42)
        name = cd[p + 46 : p + 46 + name_len].decode("utf-8", "replace")
        names.append(name)
        if name == "AndroidManifest.xml":
            local = _fetch(url, local_off, local_off + 30 + 65536)
            ln_len, le_len = struct.unpack_from("<HH", local, 26)
            data_at = 30 + ln_len + le_len
            need = local_off + data_at + comp_size - 1
            blob = local[data_at : data_at + comp_size]
            if len(blob) < comp_size:
                blob = _fetch(url, local_off + data_at, need)
            found = zlib.decompress(blob, -15) if method == 8 else blob
        p += 46 + name_len + extra_len + comment_len
    if found is None:
        raise LookupError("AndroidManifest.xml not in the central directory")
    return found, names


# ------------------------------------------------------------ signing block

SIG_BLOCK_MAGIC = b"APK Sig Block 42"
# APK Signature Scheme v3.1, v3 and v2 blocks, newest first; every one of them
# starts signer -> signed data -> digests, certificates
SCHEME_IDS = (0x1B93AD61, 0xF05368C0, 0x7109871A)


def _lp(buf: bytes, off: int) -> tuple[bytes, int]:
    """uint32 length-prefixed slice -> (slice, offset after it)."""
    n, = struct.unpack_from("<I", buf, off)
    return buf[off + 4 : off + 4 + n], off + 4 + n


def signer_from_block(block: bytes) -> str:
    """SHA-256 of the first signer's certificate, from an APK Signing Block."""
    import hashlib

    pairs: dict[int, bytes] = {}
    off, end = 8, len(block) - 24  # skip the leading size; stop before size + magic
    while off + 12 <= end:
        n, = struct.unpack_from("<Q", block, off)
        pid, = struct.unpack_from("<I", block, off + 8)
        pairs[pid] = block[off + 12 : off + 8 + n]
        off += 8 + n
    for scheme in SCHEME_IDS:
        if scheme in pairs:
            signers, _ = _lp(pairs[scheme], 0)
            signer, _ = _lp(signers, 0)
            signed_data, _ = _lp(signer, 0)
            _digests, p = _lp(signed_data, 0)
            certs, _ = _lp(signed_data, p)
            cert, _ = _lp(certs, 0)
            return hashlib.sha256(cert).hexdigest()
    raise LookupError("no v2/v3 signature in the APK Signing Block (v1-only APK?)")


def _signing_block(read, total: int) -> bytes:
    """read(start, length) -> bytes; returns the whole APK Signing Block."""
    tail_len = min(total, 66 * 1024)
    tail = read(total - tail_len, tail_len)
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise LookupError("no end-of-central-directory (zip64 APK?)")
    cd_off, = struct.unpack_from("<I", tail, eocd + 16)
    footer = read(cd_off - 24, 24)
    if footer[8:] != SIG_BLOCK_MAGIC:
        raise LookupError("APK is not signed with scheme v2 or later")
    size, = struct.unpack_from("<Q", footer, 0)
    return read(cd_off - size - 8, size + 8)


def signer_of(target: str) -> str:
    """SHA-256 of the signing certificate, lowercase hex (as apksigner prints it)."""
    if target.startswith(("http://", "https://")):
        with urllib.request.urlopen(urllib.request.Request(target, method="HEAD"), timeout=60) as head:
            total = int(head.headers["Content-Length"])
            url = head.geturl()
        return signer_from_block(_signing_block(lambda s, n: _fetch(url, s, s + n - 1), total))
    import os

    with open(target, "rb") as fh:
        def read(start: int, n: int) -> bytes:
            fh.seek(start)
            return fh.read(n)

        return signer_from_block(_signing_block(read, os.path.getsize(target)))


def package_of(target: str) -> str:
    if target.startswith(("http://", "https://")):
        return package_from_url(target)
    import zipfile

    with zipfile.ZipFile(target) as zf:
        return package_from_manifest(zf.read("AndroidManifest.xml"))


def cli() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--signer":
        print(signer_of(args[1]))
    elif len(args) == 1:
        print(package_of(args[0]))
    else:
        raise SystemExit("usage: apk_package.py [--signer] <apk path or url>")


if __name__ == "__main__":
    cli()
