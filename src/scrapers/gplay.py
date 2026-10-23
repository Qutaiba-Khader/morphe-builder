# ---------------------------------------------------------
# morphe-builder: Google Play as a second APK source.
#
# Downloads go through goopdl (MIT, https://github.com/Villoh/goopdl), run with `uvx` at a pinned
# version, so nothing is added to the project's dependencies. It signs in with a Google account
# when GOOPDL_ACCOUNT_EMAIL + GOOPDL_AAS_TOKEN are set (required on GitHub's runners, which
# Aurora's anonymous token dispenser refuses), else anonymously through that dispenser.
#   gplay-dlurl = "https://play.google.com/store/apps/details?id=com.google.android.youtube"
#
# Google Play only serves an OLD version when asked for its exact version code. The code comes
# from the patches when they list one, else from APKMirror's release page (APKMirror records
# every variant's code in VERSION_CODE_HINTS even when its own download then fails), else Play
# is asked for the version by name, which works while that version is still being rolled out.
#
# Play delivers an app as a base APK plus split APKs (CPU, screen density, language). They are
# packed into an .apkm (base.apk + split_*.apk), the same bundle format APKMirror uses, which
# the Morphe CLI merges while patching. A universal build ("all"/"both") needs the 64-bit AND
# the 32-bit CPU split; when Play will not serve one of them, this source fails instead of
# publishing an APK that silently drops 32-bit devices.
#
# Licensed under the GNU GPLv3, like the rest of this repository.
# ---------------------------------------------------------

import os
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.core.logger import pr, wpr
from src.scrapers.base import (
    VERSION_CODE_HINTS,
    AppMetadata,
    BaseScraper,
    DownloadResult,
    ScraperError,
)

GOOPDL = ("uvx", "--quiet", "--from", "goopdl==1.2.1", "goopdl")
TIMEOUT = 900
# builder arch -> goopdl device type
_ARCHES = {"arm64-v8a": "arm64", "armeabi-v7a": "armv7", "x86_64": "x86_64", "x86": "x86"}
# goopdl device type -> the CPU split Play names after it
_ABI_SPLIT = {"arm64": "config.arm64_v8a", "armv7": "config.armeabi_v7a", "x86_64": "config.x86_64", "x86": "config.x86"}
# goopdl's "armv7" pool also holds 64-bit phones, which Play answers with the 64-bit split; these
# phones run 32-bit only (measured: YouTube 21.16.256 came with config.armeabi_v7a from the A13).
_PROFILES = {"armv7": ("Samsung A13 5G", "Samsung J5 Prime", "Realme 5 Pro"), "arm64": (None,), "x86_64": (None,), "x86": (None,)}


class GPlayError(ScraperError):
    pass


def package_from_url(url: str) -> str:
    """`gplay-dlurl` is a Play Store link (…details?id=<pkg>) or a bare package name."""
    if "://" not in url:
        pkg = url.strip()
    else:
        pkg = (parse_qs(urlparse(url).query).get("id") or [""])[0]
    if not re.fullmatch(r"[A-Za-z][\w]*(\.[A-Za-z0-9_]+)+", pkg):
        raise GPlayError(f"Not a Google Play app link or package name: '{url}'")
    return pkg


def _string_pool(data: bytes, off: int) -> list[str]:
    _t, header_size, _s = struct.unpack_from("<HHI", data, off)
    count, _styles, flags, strings_start, _ss = struct.unpack_from("<IIIII", data, off + 8)
    offsets = struct.unpack_from(f"<{count}I", data, off + header_size)
    base, utf8, out = off + strings_start, bool(flags & 0x100), []
    for rel in offsets:
        p = base + rel
        if utf8:
            p += 2 if data[p] & 0x80 else 1
            n = data[p]
            if n & 0x80:
                n, p = ((n & 0x7F) << 8) | data[p + 1], p + 2
            else:
                p += 1
            out.append(data[p : p + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", data, p)[0]
            p += 2
            if n & 0x8000:
                n, p = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0], p + 2
            out.append(data[p : p + n * 2].decode("utf-16-le", "replace"))
    return out


def manifest_versions(apk: Path) -> tuple[str, str]:
    """(versionName, versionCode) from a base APK's binary AndroidManifest.xml."""
    with zipfile.ZipFile(apk) as zf:
        axml = zf.read("AndroidManifest.xml")
    strings: list[str] = []
    off = 8
    while off + 8 <= len(axml):
        ctype, header_size, csize = struct.unpack_from("<HHI", axml, off)
        if csize <= 0:
            break
        if ctype == 0x0001:
            strings = _string_pool(axml, off)
        elif ctype == 0x0102:
            body = off + header_size
            _ns, name_idx = struct.unpack_from("<iI", axml, body)
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, body + 8)
            if strings and strings[name_idx] == "manifest":
                name = code = ""
                for i in range(attr_count):
                    a = body + attr_start + i * attr_size
                    _a_ns, a_name, a_raw = struct.unpack_from("<iii", axml, a)
                    _vsize, _res0, vtype, vdata = struct.unpack_from("<HBBI", axml, a + 12)
                    key = strings[a_name] if 0 <= a_name < len(strings) else ""
                    if key == "versionName":
                        name = strings[a_raw] if a_raw >= 0 else (strings[vdata] if vtype == 0x03 else str(vdata))
                    elif key == "versionCode":
                        code = str(vdata)
                return name, code
        off += csize
    raise GPlayError(f"No <manifest> in {apk.name}")


class GPlayScraper(BaseScraper):
    def _run(self, *args: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
        if shutil.which(GOOPDL[0]) is None:
            raise GPlayError("uv is not installed, so goopdl cannot run")
        env = dict(os.environ)
        if home is not None:
            # goopdl keeps its token pool in ~/.config/goopdl and reuses whatever device it holds,
            # whatever --profile says: one home per device type keeps a 32-bit phone 32-bit.
            home.mkdir(parents=True, exist_ok=True)
            env.setdefault("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv"))
            env["HOME"] = str(home)
        try:
            return subprocess.run([*GOOPDL, *args], capture_output=True, text=True, timeout=TIMEOUT, check=False, env=env)
        except subprocess.TimeoutExpired:
            raise GPlayError(f"goopdl took longer than {TIMEOUT} s") from None

    @staticmethod
    def _usable() -> None:
        # Aurora's anonymous dispenser answers 403 to GitHub's runners (measured 2026-10-23 on every
        # device profile), so in CI only a Google account works: GOOPDL_ACCOUNT_EMAIL + GOOPDL_AAS_TOKEN.
        if os.getenv("GITHUB_ACTIONS") == "true" and not (os.getenv("GOOPDL_ACCOUNT_EMAIL") and os.getenv("GOOPDL_AAS_TOKEN")):
            raise GPlayError("Google Play needs the GOOPDL_ACCOUNT_EMAIL and GOOPDL_AAS_TOKEN secrets on GitHub (see ADD.md)")

    def fetch_metadata(self, url: str) -> AppMetadata:
        self._usable()
        pkg = package_from_url(url)
        res = self._run("latest", pkg, "--arch", "arm64")
        m = re.search(r"Latest:\s*(\S+)\s*\((\d+)\)", res.stdout)
        if res.returncode != 0 or not m:
            raise GPlayError(f"Google Play gave no version for '{pkg}' (goopdl exit {res.returncode})")
        VERSION_CODE_HINTS.setdefault((pkg, m.group(1)), m.group(2))
        return AppMetadata(pkg_name=pkg, versions=[m.group(1)])

    def _fetch(self, pkg: str, device: str, wanted: str, out: Path, homes: Path) -> list[Path]:
        last = f"Google Play does not serve {pkg} {wanted} to a {device} device"
        for i, profile in enumerate(_PROFILES.get(device, (None,))):
            args = ["download", pkg, "-a", device, "-v", wanted, "--splits", "--no-extras", "-o", str(out)]
            if profile:
                args += ["--profile", profile]
            res = self._run(*args, home=homes / f"{device}-{i}")
            if res.returncode == 5:
                raise GPlayError("Google Play is rate limiting downloads (HTTP 429)")
            if res.returncode != 0:
                tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or [""]
                last = last if res.returncode == 4 else f"goopdl failed for {device} (exit {res.returncode}): {tail[0]}"
                continue
            files = sorted(out.glob(f"{pkg}-*.apk"))
            if any(f.name.endswith(f"-{_ABI_SPLIT[device]}.apk") for f in files) or not any("-config." in f.name and any(f.name.endswith(f"-{s}.apk") for s in _ABI_SPLIT.values()) for f in files):
                return files
            # a CPU split for another CPU: this "32-bit" phone was not 32-bit after all
            for f in files:
                f.unlink()
            last = f"Google Play sent {device} a build for another CPU"
        raise GPlayError(last)

    def download(self, url: str, version: str, dest: Path, arch: str, dpi: str, version_code: str | None = None) -> DownloadResult:
        self._usable()
        pkg = package_from_url(url)
        version = version.lstrip("v")
        code = version_code or VERSION_CODE_HINTS.get((pkg, version))
        wanted = code or version
        devices = ["arm64", "armv7"] if arch in ("all", "both") else [_ARCHES.get(arch, "")]
        if not devices[0]:
            raise GPlayError(f"No Google Play device type for arch '{arch}'")
        pr(f"Google Play: {pkg} {version} ({'version code ' + code if code else 'by version name'}) for {', '.join(devices)}")

        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            per_device: dict[str, dict[str, Path]] = {}
            errors: list[str] = []
            for device in devices:
                try:
                    files = self._fetch(pkg, device, wanted, Path(tmp) / device, dest.parent / ".goopdl")
                except GPlayError as exc:
                    errors.append(str(exc))
                    continue
                parts: dict[str, Path] = {}
                for f in files:
                    stem = f.name[len(pkg) + 1 : -4]          # "<vc>" or "<vc>-<split>"
                    _vc, _, split = stem.partition("-")
                    parts[split or "base"] = f
                if "base" not in parts:
                    errors.append(f"no base APK for {device}")
                    continue
                per_device[device] = parts
            if not per_device:
                raise GPlayError("; ".join(errors) or "nothing downloaded")

            # the APK must be the version the patches were chosen for
            first = next(iter(per_device.values()))["base"]
            got_name, got_code = manifest_versions(first)
            if got_name != version:
                raise GPlayError(f"Google Play served {got_name} ({got_code}), not {version}")

            merged: dict[str, Path] = {}
            for device, parts in per_device.items():
                for split, f in parts.items():
                    if split == "base" and "base" in merged and manifest_versions(f) != manifest_versions(merged["base"]):
                        raise GPlayError(f"{device} build is a different APK ({manifest_versions(f)[1]}), cannot combine it")
                    merged.setdefault(split, f)

            has_native = any(s in merged for s in _ABI_SPLIT.values())
            missing = [d for d in devices if has_native and _ABI_SPLIT[d] not in merged]
            if missing:
                raise GPlayError(f"No {', '.join(missing)} CPU split from Google Play ({'; '.join(errors) or 'not offered'}), "
                                 "so it cannot make this APK")
            if errors:
                wpr(f"Google Play: {'; '.join(errors)} (not needed: the other build carries every CPU split)")

            if len(merged) == 1:
                shutil.move(merged["base"], dest)
                return DownloadResult(path=dest, is_bundle=False)
            out = dest.with_suffix(".apkm")
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as zf:
                for split, f in merged.items():
                    zf.write(f, "base.apk" if split == "base" else f"split_{split}.apk")
            pr(f"Google Play: packed {len(merged)} APKs ({', '.join(sorted(merged))}) into {out.name}")
            return DownloadResult(path=out, is_bundle=True)
