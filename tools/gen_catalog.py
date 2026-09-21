#!/usr/bin/env python3
"""Build data/catalog.json: what every patch source in config.toml can actually patch.

For each `github:owner/repo` / `gitlab:owner/repo` key found under any [App.patches] table
(enabled or not), download its newest .mpp bundle and run

    morphe-desktop list-patches --patches <file> -p -v

then turn that into: source -> package -> {versions, patches}, plus the universal patches
that apply to any app.

That is what makes adding an app a lookup instead of a guess: you can see which apps a
source covers and the exact patch names before touching config.toml.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.toml"
OUT = ROOT / "data" / "catalog.json"
WORK = ROOT / "temp" / "catalog"

CLI_REPO = "MorpheApp/morphe-desktop"


# --------------------------------------------------------------------------- http


def _req(url: str, accept: str = "application/vnd.github+json") -> Any:
    req = urllib.request.Request(url)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "morphe-builder-catalog")
    if "api.github.com" in url and (token := os.getenv("GITHUB_TOKEN")):
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == 2:  # a 404 is an answer, a 5xx is weather
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "morphe-builder-catalog")
    if "api.github.com" in url and (token := os.getenv("GITHUB_TOKEN")):
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as fh:
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
    except urllib.error.HTTPError:
        # Some release assets answer urllib's redirect with a 500 from GitHub's
        # asset CDN while curl gets 200 for the same URL (seen 2026-09-21 on
        # De-Vanced v1.4.4). curl is on every runner; use it as the fallback.
        subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", str(tmp), url], check=True, timeout=300)
    tmp.replace(dest)
    return dest


def _upstream_ver_key(ver: str) -> tuple[int, ...]:
    """Mirror of src/core/prebuilts.py `_ver_key`: numbers of the part before the
    first '-', so v1.44.0 and v1.44.0-dev.9 tie (and the first listed wins)."""
    base = ver.split("-")[0]
    return tuple(int(x) for x in re.findall(r"\d+", base)) or (0,)


def _bundle(assets: list[dict[str, Any]], name_key: str, url_key: str) -> str | None:
    for a in assets:
        if str(a.get(name_key, "")).endswith((".mpp", ".rvp")) or str(a.get(url_key, "")).endswith((".mpp", ".rvp")):
            return str(a[url_key])
    return None


def resolve_github(repo: str, version: str) -> tuple[str, str]:
    """-> (bundle url, tag), choosing the release exactly as the builder does
    (src/core/prebuilts.py `_fetch_single_asset`): "latest" = the latest
    release, "dev" = the highest version among ALL releases (stable or not),
    anything else = that tag."""
    base = f"https://api.github.com/repos/{repo}/releases"
    if version == "latest":
        rel = _req(f"{base}/latest")
    elif version == "dev":
        releases = _req(base)
        best = max((r["tag_name"] for r in releases if r.get("tag_name")), key=_upstream_ver_key)
        rel = next(r for r in releases if r.get("tag_name") == best)
    else:
        rel = _req(f"{base}/tags/{version}")
    if url := _bundle(rel.get("assets", []), "name", "browser_download_url"):
        return url, rel.get("tag_name", "")
    raise LookupError(f"no .mpp asset in {repo} {rel.get('tag_name')}")


def resolve_gitlab(project: str, version: str) -> tuple[str, str]:
    enc = urllib.parse.quote(project, safe="")
    releases = _req(f"https://gitlab.com/api/v4/projects/{enc}/releases", accept="application/json")
    if version == "dev" and releases:
        best = max((r["tag_name"] for r in releases if r.get("tag_name")), key=_upstream_ver_key)
        releases = [r for r in releases if r.get("tag_name") == best]
    elif version not in ("latest", "dev"):
        releases = [r for r in releases if r.get("tag_name") == version]
    for rel in releases:  # newest first; "latest" = the first one carrying a bundle
        if url := _bundle(rel.get("assets", {}).get("links", []), "name", "url"):
            return url, rel.get("tag_name", "")
    raise LookupError(f"no .mpp asset in gitlab {project} ({version})")


def resolve_source(key: str, version: str = "latest") -> tuple[str, str, str]:
    """('github:owner/repo', version spec) -> (download url, tag, web url)."""
    kind, _, path = key.partition(":")
    if kind == "github":
        url, tag = resolve_github(path, version)
        return url, tag, f"https://github.com/{path}"
    if kind == "gitlab":
        url, tag = resolve_gitlab(path, version)
        return url, tag, f"https://gitlab.com/{path}"
    raise LookupError(f"unknown source kind: {key}")


def get_cli() -> Path:
    rel = _req(f"https://api.github.com/repos/{CLI_REPO}/releases/latest")
    asset = next(a for a in rel["assets"] if a["name"].endswith(".jar"))
    print(f"cli: {asset['name']}")
    return download(asset["browser_download_url"], WORK / asset["name"])


# ----------------------------------------------------------------------- parsing

_NAME = re.compile(r"^(?:INFO:\s*)?Name:\s*(.+)$")


def parse_patch_list(text: str) -> list[dict[str, Any]]:
    """Parse `list-patches -p -v` output into patch records."""
    patches: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pkg: str | None = None
    in_versions = False

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if m := _NAME.match(stripped):
            if current:
                patches.append(current)
            current = {"name": m.group(1).strip(), "default": True, "packages": {}}
            pkg, in_versions = None, False
            continue
        if current is None:
            continue

        if stripped.startswith("Enabled:"):
            current["default"] = stripped.split(":", 1)[1].strip().lower() == "true"
            continue
        if stripped.startswith("Compatible packages:"):
            pkg, in_versions = None, False
            continue
        if stripped.startswith("Package name:"):
            pkg = stripped.split(":", 1)[1].strip()
            current["packages"].setdefault(pkg, [])
            in_versions = False
            continue
        if stripped.startswith("Compatible versions:"):
            in_versions = True
            continue
        if stripped.startswith("Version codes:"):
            # "<version>: ARM64_V8A=47, ..." lines follow - not versions
            in_versions = False
            continue
        if in_versions and pkg and ":" not in stripped:
            current["packages"][pkg].append(stripped)

    if current:
        patches.append(current)
    return patches


def _version_key(version: str) -> tuple[Any, ...]:
    """Sortable, never compares int with str, and 8.30.51-beta.2 < 8.30.51."""
    base, _, pre = version.partition("-")
    nums = tuple((0, int(c), "") if c.isdigit() else (1, 0, c.lower()) for c in re.split(r"[._]", base))
    return (nums, 0 if pre else 1, pre.lower())


def build_source_entry(patches: list[dict[str, Any]]) -> dict[str, Any]:
    packages: dict[str, dict[str, Any]] = {}
    universal: list[str] = []

    for p in patches:
        if not p["packages"]:
            universal.append(p["name"])
            continue
        for pkg, versions in p["packages"].items():
            entry = packages.setdefault(pkg, {"versions": [], "patches": []})
            entry["patches"].append({"name": p["name"], "default": p["default"]})
            for v in versions:
                if v not in entry["versions"]:
                    entry["versions"].append(v)

    for entry in packages.values():
        entry["versions"].sort(key=_version_key, reverse=True)
        entry["patches"].sort(key=lambda p: p["name"].lower())

    return {
        "patch_count": len(patches),
        "universal_patches": sorted(universal),
        "packages": dict(sorted(packages.items())),
    }


# -------------------------------------------------------------------------- main


def sources_from_config() -> dict[tuple[str, str], list[dict[str, Any]]]:
    """(source, version spec) -> tables using it. "dev" and a pinned tag are
    different bundles from "latest", so they are catalogued separately."""
    data = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    found: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for table, body in data.items():
        if not isinstance(body, dict):
            continue
        for key, spec in (body.get("patches") or {}).items():
            version = str(spec.get("version", "latest")) if isinstance(spec, dict) else "latest"
            found.setdefault((str(key), version), []).append(
                {"table": table, "enabled": body.get("enabled", True) is True}
            )
    return found


def catalog_key(source: str, version: str) -> str:
    return source if version == "latest" else f"{source}@{version}"


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    cli = get_cli()
    used = sources_from_config()
    print(f"{len(used)} patch sources referenced by config.toml")

    catalog: dict[str, Any] = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cli": cli.name,
        "sources": {},
    }

    failures = 0
    for (source, spec), used_by in sorted(used.items()):
        key = catalog_key(source, spec)
        print(f"\n== {key}")
        try:
            url, tag, web = resolve_source(source, spec)
            mpp = download(url, WORK / f"{source.replace(':', '_').replace('/', '_')}-{tag or spec}{Path(urllib.parse.urlparse(url).path).suffix}")
            proc = subprocess.run(
                ["java", "-jar", str(cli), "list-patches", "--patches", str(mpp), "-p", "-v", "-d=false", "-i=false"],
                capture_output=True, text=True, timeout=600, check=False,  # returncode checked below
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip()[:300] or f"exit {proc.returncode}")
            entry = build_source_entry(parse_patch_list(proc.stdout))
            entry.update({"url": web, "version": tag, "spec": spec, "used_by": used_by})
            catalog["sources"][key] = entry
            print(f"   {tag}: {entry['patch_count']} patches, {len(entry['packages'])} apps")
        except Exception as exc:  # noqa: BLE001 - one bad source must not sink the catalog
            failures += 1
            catalog["sources"][key] = {"url": source, "spec": spec, "error": str(exc)[:300], "used_by": used_by,
                                       "patch_count": 0, "packages": {}, "universal_patches": []}
            print(f"   FAILED: {exc}", file=sys.stderr)

    # package -> which sources patch it
    by_package: dict[str, list[str]] = {}
    for key, entry in catalog["sources"].items():
        for pkg in entry.get("packages", {}):
            by_package.setdefault(pkg, []).append(key)
    catalog["packages"] = dict(sorted((k, sorted(v)) for k, v in by_package.items()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(catalog['sources'])} sources, "
          f"{len(catalog['packages'])} packages, {failures} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
