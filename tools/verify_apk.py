#!/usr/bin/env python3
"""Check a freshly built APK before it can be released.

A build can finish and still be useless: the wrong key (phones refuse the update), a
version inside that differs from the file name (the update page would lie), libraries
for another CPU (the TV is 32-bit only), or a patch that left nothing in the app. An APK
that fails is deleted so it is never uploaded, and the job goes red.
"""
from __future__ import annotations

import os
import re
import sys
import tomllib
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apk_package import manifest_attrs, signer_of  # noqa: E402

NAME_RE = re.compile(r"^(?P<stem>.+)-v(?P<version>.+)-(?P<arch>all|arm64-v8a|armeabi-v7a|x86_64|x86)\.apk$")
MIN_BYTES = 1_000_000

# What a patch source must leave in the app. A patch that applied writes its extension
# classes into the dex files; if they are absent the app would run unpatched.
MARKERS = {"Qutaiba-Khader/stremio-subs-patches": b"Lapp/subsense/stremio/SubtitleRefresh;"}


def clone_package(config_path: Path) -> dict[str, str]:
    """file name stem -> the package config.toml asks for (a Clone app's -OpackageName)."""
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    default_brand = str(data.get("brand", "Morphe"))
    out: dict[str, str] = {}
    for table, body in data.items():
        if isinstance(body, dict) and (m := re.search(r"-OpackageName=([\w.]+)", str(body.get("patcher-args", "")))):
            name = str(body.get("app-name", table.replace("-", " ")))
            brand = str(body.get("brand", default_brand))
            out[f"{name.lower().replace(' ', '-')}-{brand.lower().replace(' ', '-')}"] = m.group(1)
    return out


def patch_sources(config_path: Path) -> dict[str, list[str]]:
    """file name stem -> the patch sources of its config.toml table."""
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    default_brand = str(data.get("brand", "Morphe"))
    out: dict[str, list[str]] = {}
    for table, body in data.items():
        if not isinstance(body, dict):
            continue
        name = str(body.get("app-name", table.replace("-", " ")))
        brand = str(body.get("brand", default_brand))
        patches = body.get("patches")
        sources = [re.sub(r"^(github|gitlab):", "", k) for k in patches] if isinstance(patches, dict) else []
        out[f"{name.lower().replace(' ', '-')}-{brand.lower().replace(' ', '-')}"] = sources
    return out


def problems(apk: Path, sources_by_stem: dict[str, list[str]], want_signer: str, packages: dict[str, str] | None = None) -> list[str]:
    m = NAME_RE.match(apk.name)
    if not m:
        return [f"file name does not follow <app>-<brand>-v<version>-<arch>.apk: {apk.name}"]
    if apk.stat().st_size < MIN_BYTES:
        return [f"only {apk.stat().st_size} bytes"]
    found: list[str] = []
    try:
        with zipfile.ZipFile(apk) as zf:
            names = zf.namelist()
            attrs = manifest_attrs(zf.read("AndroidManifest.xml"))
            dex = [n for n in names if re.fullmatch(r"classes\d*\.dex", n)]
            if not dex:
                found.append("no dex files")
            markers = [MARKERS[s] for s in sources_by_stem.get(m["stem"], []) if s in MARKERS]
            for marker in markers:
                if not any(marker in zf.read(n) for n in dex):
                    found.append(f"patch marker {marker.decode()} is not in the app")
    except (zipfile.BadZipFile, KeyError, LookupError, OSError) as exc:
        return [f"not a readable APK: {exc}"]

    if not attrs.get("package"):
        found.append("the manifest names no package")
    elif (want_package := (packages or {}).get(m["stem"])) and attrs["package"] != want_package:
        found.append(f"the package is {attrs['package']}, config.toml asks for {want_package}")
    inside = attrs.get("versionName")
    if inside is not None and inside != m["version"]:
        found.append(f"the app says version {inside}, the file name says {m['version']}")
    arch = m["arch"]
    abis = {n.split("/")[1] for n in names if n.startswith("lib/") and n.count("/") >= 2}
    if arch != "all" and arch not in abis:
        found.append(f"built for {arch} but its libraries are for {sorted(abis) or 'nothing'}")
    if want_signer:
        try:
            signer = signer_of(str(apk))
        except (LookupError, OSError) as exc:
            found.append(f"cannot read the signature: {exc}")
        else:
            if signer != want_signer:
                found.append(f"signed with {signer}, not {want_signer}: phones cannot update to it")
    return found


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    sources = patch_sources(root / "config.toml")
    packages = clone_package(root / "config.toml")
    want = os.getenv("SIGNING_CERT_SHA256", "").replace(":", "").strip().lower()
    if not want and os.getenv("GITHUB_ACTIONS"):
        print("::error title=APK rejected::the repository variable SIGNING_CERT_SHA256 is not set")
        return 1
    apks = [Path(a) for a in argv]
    failed = 0
    for apk in apks:
        found = problems(apk, sources, want, packages)
        if found:
            failed += 1
            for line in found:
                print(f"::error title=APK rejected::{apk.name}: {line}")
            apk.unlink(missing_ok=True)
        else:
            print(f"ok {apk.name}")
    if failed and not any(a.exists() for a in apks):
        Path("build.md").unlink(missing_ok=True)  # nothing of this job is released, so its notes are not either
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
