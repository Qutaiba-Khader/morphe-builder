# ---------------------------------------------------------
# Copyright (C) 2026 krvstek (Original Author)
# Copyright (C) 2026 The uni-apks Contributors (Modifications)
# 
# DO NOT REMOVE OR ALTER THIS COPYRIGHT HEADER.
# This file is part of uni-apks.
# Canonical source: https://github.com/krvstek/uni-apks
#
# Licensed under the GNU GPLv3. You may modify this file,
# but you MUST keep this original copyright notice intact
# and prominently state any changes made.
# See the AUTHORS file in the root directory for details.
# ---------------------------------------------------------

import json  # noqa: I001
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from src.core.config import CONFIG_PATH, AppEntry, load_toml, parse_app_entries, parse_config
from src.core.logger import IS_GITHUB, abort, epr
from src.core.network import NetworkManager, ResourceNotFoundError
from src.core.prebuilts import get_highest_ver

RETRY_AFTER = timedelta(hours=20)


def _require_ci(script: str) -> None:
    if not IS_GITHUB:
        abort(f"'{script}' is only available in GitHub Actions")

def _fetch_latest_release(source: str, net: NetworkManager, version: str = "latest") -> tuple[str, str]:
    scheme, clean_src = source.split(":", 1)
    upstream_rel: dict[str, Any]
    if scheme == "gitlab":
        project = clean_src.replace("/", "%2F")
        upstream_rel = json.loads(net.get(f"https://gitlab.com/api/v4/projects/{project}/releases/permalink/latest"))
        changelog_text = str(upstream_rel.get("description") or "")
        upstream_date = str(upstream_rel.get("released_at") or "")
    elif version == "dev":
        # morphe-builder: the newest release by date. GitHub does not list
        # releases newest-first (v1.47.0-dev.9 came before dev.14), so the
        # first entry left the dev channel on an old build.
        releases: list[dict[str, Any]] = json.loads(net.get(f"https://api.github.com/repos/{clean_src}/releases?per_page=100", headers=net.gh_headers))
        published = [r for r in releases if r.get("published_at") and not r.get("draft")]
        upstream_rel = max(published, key=lambda r: str(r["published_at"])) if published else {}
        changelog_text = str(upstream_rel.get("body") or "")
        upstream_date = str(upstream_rel.get("published_at") or "")
    else:
        upstream_rel = json.loads(net.get(f"https://api.github.com/repos/{clean_src}/releases/latest", headers=net.gh_headers))
        changelog_text = str(upstream_rel.get("body") or "")
        upstream_date = str(upstream_rel.get("published_at") or "")
    return changelog_text, upstream_date

def _fetch_our_releases(repo: str, net: NetworkManager) -> dict[str, str]:
    our_releases_by_brand: dict[str, str] = {}
    try:
        our_releases_raw = net.get(f"https://api.github.com/repos/{repo}/releases?per_page=100", headers=net.gh_headers)
        releases: list[dict[str, Any]] = json.loads(our_releases_raw)
        for rel in releases:
            tag = str(rel.get("tag_name") or "")
            brand = tag.split("-", 1)[1] if "-" in tag else ""
            # morphe-builder: the newest of the brand; GitHub does not list releases newest-first
            if brand and str(rel.get("published_at") or "") > our_releases_by_brand.get(brand, ""):
                our_releases_by_brand[brand] = str(rel.get("published_at") or "")
    except Exception as exc:
        epr(f"Failed to fetch our releases: {exc}")
        our_releases_by_brand = {}
    return our_releases_by_brand

def _stremio_needs_build(repo: str, brand: str, apps: list[AppEntry], net: NetworkManager) -> bool:
    """morphe-builder: an app taken straight from Stremio's download feed (stremio-dlurl) is rebuilt when Stremio
    publishes a version that the brand's releases do not carry yet FOR EVERY such app (asset names are
    <app-name>-<brand>-v<version>-…, as builder.py writes them), so one app built without the other is not enough."""
    from src.scrapers.stremio import StremioScraper
    wanted: set[tuple[str, str]] = set()
    for app in apps:
        url = app.dl_urls.get("stremio")
        if url:
            stem = f"{app.app_name.lower().replace(' ', '-')}-{app.brand.lower().replace(' ', '-')}"
            try:
                wanted.update((stem, v) for v in StremioScraper(net).fetch_metadata(url).versions)
            except Exception as exc:
                epr(f"Could not read Stremio's download feed for '{app.table}': {exc}")
    if not wanted:
        return False
    try:
        releases: list[dict[str, Any]] = json.loads(net.get(f"https://api.github.com/repos/{repo}/releases?per_page=100", headers=net.gh_headers))
    except Exception as exc:
        epr(f"Failed to fetch our releases: {exc}")
        return True
    # morphe-builder: a draft does not count: a cancelled run leaves one, and nobody can download from it
    names = [str(a.get("name") or "").lower() for r in releases if not r.get("draft") and str(r.get("tag_name") or "").split("-", 1)[-1] == brand for a in r.get("assets", [])]
    missing = sorted(f"{stem} {v}" for stem, v in wanted if not any(n.startswith(f"{stem}-v{v.lower()}-") for n in names))
    if missing:
        epr(f"No release carries {', '.join(missing)}: building brand '{brand}'")
    return bool(missing)

def _bundle_of(release: dict[str, Any]) -> str:
    """morphe-builder: the version in the .mpp file's name, which is what the release notes name, without the leading v.
    Not always the tag's: icysymmetra's v0.9.0-dev.2 ships patches-0.9.0-dev.1.mpp."""
    for asset in release.get("assets") or []:
        if m := re.search(r"-v?(\d[\w.+-]*?)\.mpp$", str(asset.get("name") or "")):
            return m.group(1)
    return str(release.get("tag_name") or "").lstrip("v")

def _expected_bundle(source: str, version: str, net: NetworkManager) -> str:
    """morphe-builder: the patch version a build would use now (as prebuilts.py picks it)."""
    clean_src = source.split(":", 1)[1]
    if version == "dev":
        releases = json.loads(net.get(f"https://api.github.com/repos/{clean_src}/releases?per_page=100", headers=net.gh_headers))
        best = get_highest_ver([str(r["tag_name"]) for r in releases if r.get("tag_name")])
        return _bundle_of(next(r for r in releases if r.get("tag_name") == best))
    return _bundle_of(json.loads(net.get(f"https://api.github.com/repos/{clean_src}/releases/latest", headers=net.gh_headers)))

def _apps_behind(brand: str, apps: list[AppEntry], source: str, expected: str, releases: list[dict[str, Any]]) -> list[str]:
    """morphe-builder: the apps whose newest build is not on the expected patch version.

    Comparing dates alone loses an update for good: an app that failed while the others built gives the brand a
    release newer than the patches, and the next run then sees nothing to do."""
    org = source.split(":", 1)[-1].split("/", 1)[0].lower()
    behind: list[str] = []
    for app in apps:
        if app.changelog_keywords:
            continue  # rebuilt only when the patch notes name it, on purpose
        stem = f"{app.app_name.lower().replace(' ', '-')}-{app.brand.lower().replace(' ', '-')}"
        own = [r for r in releases if r.get("published_at") and any(str(a.get("name") or "").lower().startswith(f"{stem}-v") for a in r.get("assets", []))]
        if not own:
            behind.append(app.table)
            continue
        notes = str(max(own, key=lambda r: str(r["published_at"])).get("body") or "").lower()
        # The APK's own line says which bundles it has; older releases only list the release's.
        line = next((ln for ln in notes.splitlines() if f"/{stem}-v" in ln and "<!-- patches:" in ln), "")
        named = re.findall(rf"{re.escape(org)}/([^,\s]+)\.mpp", line) or re.findall(rf"`{re.escape(org)}/([^`]+)\.mpp`", notes)
        # all, not any: jobs that straddle a patch release leave two bundles in the notes
        if named and not all(n.endswith(f"-{expected.lower()}") for n in named):
            behind.append(app.table)
        elif re.search(rf"» {re.escape(app.app_name.lower())}\b.*\(wanted ", notes):
            behind.append(app.table)  # it was built on a lower version because the wanted one could not be downloaded
    return behind

def _load_entries() -> list[AppEntry]:
    data = load_toml(CONFIG_PATH)
    return parse_app_entries(data, parse_config(data))

def get_matrix(source: str) -> None:
    source_lower = source.lower()
    filter_changelog = os.getenv("FILTER_CHANGELOG", "false").lower() == "true"
    patches_source = ""
    has_changelog_keywords = False
    is_prerelease = False
    staged: list[AppEntry] = []
    for entry in _load_entries():
        if not entry.enabled or entry.brand.lower() != source_lower:
            continue
        if not patches_source:
            patches_source = next(iter(entry.patches), "")
        if any(spec["version"] == "dev" for spec in entry.patches.values()):
            is_prerelease = True
        if entry.changelog_keywords:
            has_changelog_keywords = True
        staged.append(entry)

    changelog_text = ""
    if filter_changelog and has_changelog_keywords and patches_source:
        with NetworkManager() as net:
            repo = os.getenv("GITHUB_REPOSITORY")
            if repo:
                our_releases_by_brand = _fetch_our_releases(repo, net)
                if our_releases_by_brand.get(source_lower, ""):
                    try:
                        changelog_text, _ = _fetch_latest_release(patches_source, net)
                    except Exception as exc:
                        epr(f"Failed to fetch changelog for '{patches_source}': {exc}")

    changelog_lower = changelog_text.lower()
    include: list[dict[str, str]] = []
    for entry in staged:
        if filter_changelog and entry.changelog_keywords and changelog_text and not any(kw in changelog_lower for kw in entry.changelog_keywords):
            continue
        if entry.arch == "both":
            include.extend([{"id": entry.table, "arch": "arm64-v8a"}, {"id": entry.table, "arch": "armeabi-v7a"}])
        else:
            include.append({"id": entry.table})

    if not include:
        abort(f"No apps found for patch source '{source}'")
    print(json.dumps({"include": include, "prerelease": is_prerelease}, ensure_ascii=False))

def check_builds_needed(force_all: bool = False) -> None:
    seen: dict[str, str] = {}
    dev_brands: set[str] = set()
    entries = _load_entries()
    for entry in entries:
        if not entry.enabled:
            continue
        brand = entry.brand.lower()
        if brand not in seen:
            seen[brand] = next(iter(entry.patches), "")
        if any(spec["version"] == "dev" for spec in entry.patches.values()):
            dev_brands.add(brand)

    if not seen:
        print(json.dumps([]))
        return

    if force_all:
        print(json.dumps(list(seen.keys())))
        return

    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        abort("GITHUB_REPOSITORY environment variable is not set")

    entries_by_brand: dict[str, list[AppEntry]] = {}
    for entry in entries:
        if entry.enabled:
            entries_by_brand.setdefault(entry.brand.lower(), []).append(entry)

    with NetworkManager() as net:
        our_releases_by_brand = _fetch_our_releases(repo, net)

        brands_to_build: list[str] = []
        for brand, patches_source in seen.items():
            our_date = our_releases_by_brand.get(brand, "")
            try:
                changelog_text, upstream_date = _fetch_latest_release(patches_source, net, version="dev" if brand in dev_brands else "latest")
            except ResourceNotFoundError:
                epr(f"No upstream release found for '{patches_source}', skipping brand '{brand}'")
                continue
            except Exception as exc:
                epr(f"Failed to fetch upstream release for '{patches_source}': {exc}")
                brands_to_build.append(brand)
                continue

            if not our_date:
                brands_to_build.append(brand)
                continue
            behind: list[str] | None = None
            spec = next(iter(entries_by_brand[brand][0].patches.values()))
            try:
                expected = _expected_bundle(patches_source, spec["version"], net)
                raw = json.loads(net.get(f"https://api.github.com/repos/{repo}/releases?per_page=100", headers=net.gh_headers))
                behind = _apps_behind(brand, entries_by_brand[brand], patches_source, expected, raw) if expected[:1].isdigit() else None
            except Exception as exc:
                epr(f"Could not compare '{brand}' with its patches: {exc}")
            if upstream_date and datetime.fromisoformat(upstream_date) > datetime.fromisoformat(our_date):
                changelog_lower = changelog_text.lower()
                has_apps = False
                for app in entries_by_brand.get(brand, []):
                    if not app.changelog_keywords or any(kw in changelog_lower for kw in app.changelog_keywords):
                        has_apps = True
                        break
                # A same-day rebuild keeps the release's date, so a date alone would rebuild it at every check.
                keyed = any(app.changelog_keywords for app in entries_by_brand.get(brand, []))
                if has_apps and (behind is None or behind or keyed):
                    brands_to_build.append(brand)
                    continue
            # A retry at most once a day, so one app that cannot build does not rebuild its brand every run.
            if behind and datetime.now(UTC) - datetime.fromisoformat(our_date) > RETRY_AFTER:
                epr(f"Not on the wanted patches or version: {', '.join(behind)}: building brand '{brand}'")
                brands_to_build.append(brand)
        for brand, apps in entries_by_brand.items():
            if brand not in brands_to_build and any("stremio" in a.dl_urls for a in apps) and _stremio_needs_build(repo, brand, apps, net):
                brands_to_build.append(brand)
    print(json.dumps(brands_to_build))

def main() -> None:
    _require_ci("matrix.py")
    match sys.argv[1:]:
        case ["get-matrix"]:
            check_builds_needed()
        case ["get-matrix-force"]:
            check_builds_needed(force_all=True)
        case ["get-matrix", source]:
            get_matrix(source)
        case _:
            abort("Usage: matrix.py get-matrix [source] | get-matrix-force")

if __name__ == "__main__":
    main()