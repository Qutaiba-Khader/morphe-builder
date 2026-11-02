#!/usr/bin/env python3
"""Generate the Pages site and its JSON API from this repo's own GitHub releases.

Reads  : GitHub Releases + Actions runs API, the live site, site/static/*,
         data/catalog.json (optional), config.toml
Writes : _site/ - the static files (flat), api/*.json, api/apps/<id>.json,
         obtainium/<id>.html (+ <id>-<arch>.html, all.html), .nojekyll

Release assets are named  <app>-<brand>-v<version>-<arch>.apk  under a  YY.MM.DD-<source>
tag, which is all the structure the site needs.

Stdlib only, so the workflow needs no dependency install.
"""

from __future__ import annotations

import html
import http.client
import json
import os
import re
import shutil
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apk_package import manifest_attrs, manifest_from_url, package_of, signer_of  # noqa: E402
from gen_catalog import _upstream_ver_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "site" / "static"
CATALOG_FILE = ROOT / "data" / "catalog.json"
OUT_DIR = ROOT / "_site"

ARCHES = ("all", "arm64-v8a", "armeabi-v7a", "x86_64", "x86")  # src/core/config.py VALID_ARCHES
# <stem>-v<version>-<arch>.apk, where the stem is "<app name>-<brand>" with both
# lowercased and spaces hyphenated (src/core/builder.py). The brand itself can
# contain a hyphen ("morphe-dev"), so the stem is split against config.toml
# rather than guessed.
ASSET_RE = re.compile(
    r"^(?P<stem>.+)-v(?P<version>.+)-(?P<arch>" + "|".join(ARCHES) + r")\.apk$",
    re.IGNORECASE,
)

API = "https://api.github.com"
MIN_APK_BYTES = 1_000_000


def _get(url: str) -> Any:
    api = urllib.parse.urlparse(url).hostname == "api.github.com"
    if api:
        # The API answers with `Cache-Control: max-age=60, s-maxage=60`: a run
        # started right after a build can get the release list from BEFORE it
        # and publish nothing new (seen 2026-09-21, 12 s after a publish). A
        # unique query string and no-cache make every read a fresh one.
        url += ("&" if "?" in url else "?") + f"_={time.time_ns()}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "morphe-builder-site")
    req.add_header("Cache-Control", "no-cache")
    # The job token goes to the GitHub API only - never to the Pages site, which a
    # custom domain could put on a third-party host.
    if api and (token := os.getenv("GITHUB_TOKEN")):
        req.add_header("Authorization", f"Bearer {token}")
    # A cut-off answer or a 5xx is the API's hiccup, not an answer: read it again.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (http.client.HTTPException, json.JSONDecodeError, urllib.error.URLError) as exc:
            is_answer = isinstance(exc, urllib.error.HTTPError) and exc.code < 500
            if is_answer or attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


# Workflows that turn a release back into a DRAFT while they rebuild it
# (upstream build.yml "Prepare version and draft release"). While one runs, the
# releases this script can see are a partial, older picture.
BUILD_WORKFLOWS = frozenset({"CI", "Build APKs"})
ACTIVE_STATUSES = ("in_progress", "queued", "waiting", "pending", "requested")


def build_state(repo: str) -> tuple[str, str]:
    """-> ("busy", detail) | ("idle", "") | ("unknown", why). Needs `actions: read`."""
    try:
        for status in ACTIVE_STATUSES:
            data = _get(f"{API}/repos/{repo}/actions/runs?status={status}&per_page=50")
            for run in data.get("workflow_runs", []):
                if run.get("name") in BUILD_WORKFLOWS:
                    return "busy", f"{run['name']} #{run.get('run_number')} is {status}"
        return "idle", ""
    except Exception as exc:  # noqa: BLE001 - no permission / API down: decide from tags instead
        return "unknown", str(exc)


def set_output(key: str, value: str) -> None:
    if path := os.getenv("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")


def fetch_live(site_url: str) -> dict[str, Any]:
    try:
        return _get(site_url + "api/latest.json")
    except Exception:  # noqa: BLE001 - no live site yet = first run
        return {}


def all_releases(repo: str, page_size: int = 30, max_pages: int = 20) -> list[dict[str, Any]]:
    """Every release, drafts included. Small pages: a page of 100 with all its assets is about 380 KB and
    GitHub cut that answer off three reads in a row (2026-11-02), which skipped the whole site."""
    out: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        # A failure raises, on any page: a partial list could drop an app from the site.
        batch = _get(f"{API}/repos/{repo}/releases?per_page={page_size}&page={page}")
        out.extend(batch)
        if len(batch) < page_size:
            break
    return out


def fetch_releases(repo: str) -> list[dict[str, Any]]:
    return [r for r in all_releases(repo) if not r.get("draft")]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def github_asset_name(name: str) -> str:
    """How GitHub stores an uploaded asset name: any character outside
    [A-Za-z0-9@+-_.] becomes '.', and runs of '.' collapse (builder.py relies on
    the same rule)."""
    return re.sub(r"\.+", ".", re.sub(r"[^a-zA-Z0-9@+\-_.]", ".", name))


def version_key(version: str) -> tuple[Any, ...]:
    """The order of an app version: 2.5.1 > 2.5.0, 1.12.1 > 1.9.9, 2.2.0 > 2.2.0-beta.5."""
    return _upstream_ver_key(version)


def app_config() -> dict[str, dict[str, str]]:
    """filename stem -> {id, name, brand, patch_org}, straight from config.toml.

    The stem is how builder.py names the output: the app name and the brand,
    lowercased with spaces hyphenated, as GitHub then stores it. Keying on it
    means a brand containing a hyphen ("morphe-dev") still splits correctly, and
    the name keeps its capitalisation ("YouTube", not "Youtube"). The id comes
    from the TABLE name, which is unique - two tables may share an app-name.
    """
    config = ROOT / "config.toml"
    if not config.exists():
        return {}
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    default_brand = str(data.get("brand", "Morphe"))
    out: dict[str, dict[str, str]] = {}
    for table, body in data.items():
        if not isinstance(body, dict):
            continue
        name = str(body.get("app-name", table.replace("-", " ")))
        brand = str(body.get("brand", default_brand))
        stem = github_asset_name(f"{name.lower().replace(' ', '-')}-{brand.lower().replace(' ', '-')}").lower()
        patches = body.get("patches") or {}
        first = next(iter(patches), "") if isinstance(patches, dict) else ""
        patch_org = re.sub(r"^(github|gitlab):", "", first).split("/", 1)[0]
        pin = re.search(r"@v?([^:]+):\d+$", str(body.get("stremio-dlurl", "")))
        out[stem] = {"id": slug(table), "name": name, "brand": brand, "patch_org": patch_org,
                     "pin": pin.group(1) if pin else ""}
    return out


def table_meta() -> dict[str, dict[str, Any]]:
    """app id -> {stock package, patch sources, enabled} from config.toml.

    The stock package is the one the APK sources name (gplay-dlurl's id, or Stremio's own),
    which is how an app is matched with the community list and its Play Store icon.
    """
    config = ROOT / "config.toml"
    if not config.exists():
        return {}
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for table, body in data.items():
        if not isinstance(body, dict):
            continue
        pkg = ""
        if isinstance(gp := body.get("gplay-dlurl"), str):
            m = re.search(r"[?&]id=([\w.]+)", gp) or re.fullmatch(r"\s*([\w.]+)\s*", gp)
            pkg = m.group(1) if m else ""
        elif body.get("stremio-dlurl"):
            pkg = "com.stremio.one"
        patches = body.get("patches") or {}
        sources = [re.sub(r"^(github|gitlab):", "", k) for k in patches] if isinstance(patches, dict) else []
        out[slug(table)] = {"stock_package": pkg, "sources": sources, "enabled": bool(body.get("enabled"))}
    return out


COMMUNITY_FILE = ROOT / "data" / "community.json"


def write_community(api_dir: Path, now: str, meta: dict[str, dict[str, Any]], apps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """api/community/index.json + api/community/apps/<package>.json from data/community.json.

    Every app the Morphe community can patch (gathered by nvbangg/awesome-morphe), marked with
    the apps this builder already builds from it. Returns {package: icon} for the build cards.
    """
    if not COMMUNITY_FILE.exists():
        return {}
    data = json.loads(COMMUNITY_FILE.read_text(encoding="utf-8"))
    bundles = data.get("bundles") or {}
    built: dict[str, list[str]] = {}
    used: dict[str, set[str]] = {}
    for app_id, m in meta.items():
        if m["enabled"] and m["stock_package"] and app_id in apps:
            built.setdefault(m["stock_package"], []).append(app_id)
            used.setdefault(m["stock_package"], set()).update(m["sources"])
    index = []
    for pkg, app in (data.get("apps") or {}).items():
        sources = []
        for s in app.get("sources") or []:
            b = bundles.get(s["repo"], {})
            sources.append({"repo": s["repo"], **b, "used_here": s["repo"] in used.get(pkg, set()),
                            "app_patches": len(s.get("patches") or []), "patch_list": s.get("patches") or [],
                            "versions": s.get("versions") or [], "experimental": s.get("experimental") or []})
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", pkg)
        (api_dir / "community" / "apps").mkdir(parents=True, exist_ok=True)
        (api_dir / "community" / "apps" / f"{safe}.json").write_text(json.dumps(
            {"package": pkg, "name": app.get("name"), "icon": app.get("icon"), "category": app.get("category"),
             "built_here": built.get(pkg, []), "sources": sources}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        index.append({"package": pkg, "file": f"api/community/apps/{safe}.json", "name": app.get("name"),
                      "icon": app.get("icon"), "category": app.get("category"), "sources": len(sources),
                      "top": [bundles.get(s["repo"], {}).get("author", s["repo"]) for s in sources[:3]],
                      "built_here": built.get(pkg, [])})
    write_json(api_dir / "community" / "index.json", {
        "generated": now, "data_generated": data.get("generated"), "source": data.get("source"),
        "patch_sources": len(bundles), "apps": index})
    print(f"  wrote _site/api/community/apps/*.json ({len(index)} apps)")
    return {pkg: app.get("icon") for pkg, app in (data.get("apps") or {}).items() if app.get("icon")}


def split_asset(name: str, config: dict[str, dict[str, str]]) -> tuple[str, str, str] | None:
    """asset file name -> (stem, version, arch), or None if it is not an APK.

    Known stems are tried first, longest first, so a version that itself
    contains "-v" cannot move the split; the regex is only the fallback.
    """
    lower = name.lower()
    for stem in sorted(config, key=len, reverse=True):
        if lower.startswith(stem + "-v"):
            rest = name[len(stem) + 2:]
            for arch in ARCHES:
                if rest.lower().endswith(f"-{arch}.apk"):
                    return stem, rest[: -len(arch) - 5], arch
    if m := ASSET_RE.match(name):
        return m["stem"].lower(), m["version"], m["arch"]
    return None


# The builder writes the patch bundle(s) and the CLI it used into each release's
# notes: "> ⚙️ » Patches: `MorpheApp/patches-1.45.0-dev.20.mpp`" and "CLI: `...jar`".
_NOTE_RE = {
    "patches": re.compile(r"Patches:\s*`([^`]+\.mpp)`"),
    "cli": re.compile(r"CLI:\s*`([^`]+\.jar)`"),
}
_FILE_VERSION_RE = re.compile(r"-v?(\d[\w.+-]*?)(?:-all)?\.(?:mpp|jar)$")


def build_tools(body: str) -> dict[str, Any]:
    """Release notes -> {"patches": [{file, version}, ...], "cli": {file, version} | None}."""
    found: dict[str, list[dict[str, str]]] = {}
    for key, rx in _NOTE_RE.items():
        found[key] = []
        for file in dict.fromkeys(rx.findall(body or "")):
            m = _FILE_VERSION_RE.search(file)
            found[key].append({"file": file, "version": m.group(1) if m else ""})
    return {"patches": found["patches"], "cli": (found["cli"] or [None])[0]}


_OWN_BUNDLES_RE = re.compile(r"<!-- patches: ([^>]*?) -->")


def asset_tools(body: str, asset_name: str, release_tools: dict[str, Any]) -> dict[str, Any]:
    """The tools of one APK: the bundles its own line of the notes records, else the release's."""
    for line in (body or "").splitlines():
        if f"/{asset_name})" in line and (m := _OWN_BUNDLES_RE.search(line)):
            own = []
            for file in m.group(1).split(","):
                v = _FILE_VERSION_RE.search(file)
                own.append({"file": file, "version": v.group(1) if v else ""})
            return {**release_tools, "patches": own}
    # Notes that record each APK's bundles but not this APK's: unknown, so no version can be claimed for it.
    return {**release_tools, "patches": []} if _OWN_BUNDLES_RE.search(body or "") else release_tools


def _main_patches_first(tools: dict[str, Any], org: str) -> dict[str, Any]:
    """Put the app's own patch bundle first: the release notes list every bundle of the
    release, and the first is shown as the main one. The app's
    main bundle is the first patch source of its config.toml table: for Stremio that is
    Qutaiba-Khader's, and Morphe's bundle only lends it "Clone app"."""
    patches = tools.get("patches") or []
    if org:
        # Lowest first: jobs that straddle a patch release leave two of them in the notes, and an
        # update version too low only offers the app once more. Too high would hide the real update.
        mine = sorted((p for p in patches if p["file"].lower().startswith(org.lower() + "/")),
                      key=lambda p: _upstream_ver_key(p["version"]))
        patches = mine + [p for p in patches if p not in mine]
    return {**tools, "patches": patches}


def superseded(release: dict[str, Any], config: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """The assets of one release that a better version of the same app and arch replaces.

    A same-day rebuild adds to that day's release and a new version has a new file name, so
    the older APK stays beside it. The site does not list it, and prune_release.py removes it.
    The replacement must be fully uploaded before anything counts as replaced.
    """
    groups: dict[tuple[str, str], list[tuple[tuple[bool, tuple[int, ...]], dict[str, Any]]]] = {}
    for asset in release.get("assets", []):
        parts = split_asset(asset["name"], config)
        if parts:
            stem, version, arch = parts
            # a pinned version wins over a higher one: a pin is how a broken version is backed out
            pinned = version == (config.get(stem) or {}).get("pin")
            groups.setdefault((stem, arch), []).append(((pinned, version_key(version)), asset))
    out: list[dict[str, Any]] = []
    for items in groups.values():
        items.sort(key=lambda i: i[0], reverse=True)
        best_key, best = items[0]
        if best.get("state", "uploaded") != "uploaded" or best.get("size", 0) < MIN_APK_BYTES:
            continue
        out.extend(asset for key, asset in items[1:] if key != best_key)
    return out


def collect(releases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """app id -> {name, brand, builds[]}, newest build first.

    A same-day rebuild adds to that day's release, so one release can hold two
    versions of an app: within a release the highest version comes first, unless
    config.toml pins the app to one (a pin is how a broken new version is backed out),
    which also wins over any newer release.
    """
    apps: dict[str, dict[str, Any]] = {}
    config = app_config()
    brands = sorted({e["brand"].lower().replace(" ", "-") for e in config.values()}, key=len, reverse=True)
    for rel in releases:
        published = rel.get("published_at") or rel.get("created_at") or ""
        replaced = {a["name"] for a in superseded(rel, config)}
        for asset in rel.get("assets", []):
            parts = split_asset(asset["name"], config)
            # an asset still uploading has no working link yet, whatever its version
            if (parts is None or asset["name"] in replaced or asset.get("state", "uploaded") != "uploaded"
                    or asset.get("size", 0) < MIN_APK_BYTES):
                continue
            stem, version, arch = parts
            entry = config.get(stem)
            if entry is None:
                # An app no longer in config.toml but still in an old release.
                # Split off a brand the config still knows (longest first, so
                # "morphe-dev" wins over "morphe"), else the last hyphen.
                brand = next((b for b in brands if stem.endswith("-" + b)), "")
                app_part = stem[: -len(brand) - 1] if brand else stem.rpartition("-")[0]
                brand = brand or stem.rpartition("-")[2]
                entry = {
                    "id": slug(app_part or stem),
                    "name": (app_part or stem).replace("-", " ").title(),
                    "brand": brand,
                }

            app_id = entry["id"]
            app = apps.setdefault(
                app_id,
                {
                    "id": app_id,
                    "name": entry["name"],
                    "package": "",
                    "brand": entry["brand"],
                    "builds": {},
                },
            )
            key = (version, rel["tag_name"])
            app.setdefault("pin", entry.get("pin", ""))
            build = app["builds"].setdefault(
                key,
                {
                    "version": version,
                    "tag": rel["tag_name"],
                    "published": published,
                    "prerelease": bool(rel.get("prerelease")),
                    "release_url": rel.get("html_url", ""),
                    **_main_patches_first(asset_tools(rel.get("body") or "", asset["name"], build_tools(rel.get("body") or "")), entry.get("patch_org", "")),
                    "files": [],
                },
            )
            build["files"].append(
                {
                    "arch": arch,
                    "size": asset.get("size", 0),
                    "sha256": (asset.get("digest") or "").removeprefix("sha256:"),
                    "downloads": asset.get("download_count", 0),
                    "url": asset["browser_download_url"],
                    "name": asset["name"],
                }
            )

    result: dict[str, dict[str, Any]] = {}
    for app_id, app in apps.items():
        builds = sorted(app["builds"].values(), key=lambda b: (b["version"] == app["pin"], b["published"], version_key(b["version"])), reverse=True)
        for b in builds:
            b["files"].sort(key=lambda f: ARCHES.index(f["arch"].lower()) if f["arch"].lower() in ARCHES else 99)

        # The same app version is re-published under every release tag it survives.
        # Keep the newest build of each version and count the repeats.
        unique: dict[str, dict[str, Any]] = {}
        for b in builds:
            if (first := unique.get(b["version"])) is None:
                unique[b["version"]] = {**b, "files": list(b["files"]), "rebuilds": 1}
            else:
                first["rebuilds"] += 1
                # a partial multi-arch rebuild must not hide the arch it lost
                have = {f["arch"] for f in first["files"]}
                first["files"] += [f for f in b["files"] if f["arch"] not in have]
        for b in unique.values():
            b["files"].sort(key=lambda f: ARCHES.index(f["arch"].lower()) if f["arch"].lower() in ARCHES else 99)

        result[app_id] = {
            "id": app_id,
            "name": app["name"],
            "package": app["package"],
            "brand": app["brand"],
            "builds": list(unique.values()),
        }
    return result


# ----------------------------------------------------------------- obtainium
#
# Obtainium's GitHub source takes its version from the release TAG, which here
# is a date (26.09.20-morphe) - so every release would look like an update even
# when the APK is unchanged. Its HTML source instead runs
# `versionExtractionRegEx` over the APK link, which carries the real app
# version. So each app gets a tiny HTML page holding exactly one .apk link
# (the HTML source takes the LAST matching link on the page) and a config that
# extracts the version from that link's filename.

OBTAINIUM_REDIRECT = "https://apps.obtainium.imranr.dev/redirect?r="

# Shared look for the two small Obtainium pages: the site's hero colours, no
# external files, so an endpoint never depends on anything but itself.
PAGE_STYLE = """
:root{color-scheme:dark}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px 16px;
font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#eef0ff;
background:radial-gradient(60% 70% at 85% 10%,rgba(139,92,246,.45),transparent 70%),
linear-gradient(135deg,#0b1020,#1e1b4b 55%,#3b0764)}
main{width:min(34rem,100%)}
h1{margin:0 0 6px;font-size:clamp(1.7rem,6vw,2.3rem);line-height:1.1;letter-spacing:-.02em}
p{margin:0 0 14px;color:#c9cdee}
b{color:#fff}
a{color:#c7d2fe}
.btn{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:52px;
margin:22px 0;padding:12px 18px;border-radius:14px;background:#2563eb;color:#fff;
font-weight:600;text-decoration:none;word-break:break-all}
.btn.stable{background:#15803d}
.btn:focus-visible{outline:3px solid #93c5fd;outline-offset:2px}
.small{font-size:.9rem;color:#a8aede}
"""

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} {version}</title>
<meta name="app-version" content="{version}">
<meta name="build-version" content="{build_version}">
<meta name="robots" content="noindex">
<style>{style}</style></head>
<body><main>
<h1>{name}</h1>
<p>Version <b>{version}</b> ({arch}), built {published} with patches {patches}.</p>
<p><a class="btn stable" href="{url}">{filename}</a></p>
<p class="small">This is the page Obtainium checks for updates. It holds one APK link only,
so Obtainium always picks this build. To install the app yourself, use the
<a href="../">Morphe Builder website</a>.</p>
</main></body></html>
"""


# The public redirect service only forwards obtainium://app/ and obtainium://add/
# (its redirect.astro rejects anything else as "Invalid URL"), but the app
# itself handles obtainium://apps/ (lib/pages/home.dart interpretLink). So the
# add-every-app link is our own page, which hands the deep link straight to the
# phone and explains what to do when Obtainium is not installed.
BULK_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Add every app to Obtainium</title>
<style>{style}</style>
</head><body><main>
<h1>Add every app to Obtainium</h1>
<p>{count} apps: {names}.</p>
<p><a class="btn" id="go" href="{deep}">Open in Obtainium</a></p>
<p>Obtainium shows the list and asks you to confirm. Nothing is added until you do.</p>
<p class="small">When you install, Obtainium may ask whether an APK from github.com is fine for a
source on github.io. It is: the APKs are this repository's GitHub releases. Tap <b>Continue</b>.</p>
<p class="small">If nothing happens, install <a href="https://github.com/ImranR98/Obtainium/releases">Obtainium</a>
first, then come back to this page. <a href="../">Back to Morphe Builder</a></p>
<script>setTimeout(function(){{location.href=document.getElementById("go").href}},300)</script>
</main></body></html>
"""


def build_version(build: dict[str, Any]) -> str:
    """The version Obtainium/ObtainX tracks: exactly the versionName inside the APK, because that is what the phone
    reports once it is installed (resolve_versions). ObtainX compares the two: anything else is "Version order
    unclear" and an update offered for what is already there. Builds carry the patch version in it as well:
    46.2.3.0.8.1 (src/core/apk_version.py), so a patch-only rebuild is a real, ordered update.
    """
    return build.get("update_version") or build["version"]


# Read from the endpoint page itself (versionExtractWholePage): Obtainium gets
# the raw HTML with newlines turned into a literal "\n" (html.dart).
BUILD_VERSION_REGEX = 'name="build-version" content="([^"]+)"'


def obtainium_entry(app: dict[str, Any], build: dict[str, Any], file: dict[str, Any],
                    site_url: str, repo: str, suffix: str = "") -> dict[str, Any]:
    page = f"obtainium/{app['id']}{suffix}.html"
    settings = {
        "versionExtractionRegEx": BUILD_VERSION_REGEX,
        "matchGroupToUse": "1",
        "versionExtractWholePage": True,
        # compare with the phone: the page's version is the APK's own versionName,
        # so an older app shows as an update and the current one shows as current.
        "versionDetection": True,
        "apkFilterRegEx": "\\.apk$",
    }
    label = app["name"] if not suffix else f"{app['name']} ({file['arch']})"
    name, author = f"{label} ({app['brand'].title()})", repo.split("/")[0]
    # Obtainium's HTML source names every app "App" and replaces the author with
    # the page's host on every update check (html.dart AppNames(uri.host,
    # 'app'); source_provider.dart getApp). The per-app "override name/author"
    # settings win over both (App.finalName / finalAuthor).
    settings["appName"] = name
    settings["appAuthor"] = author
    config: dict[str, Any] = {
        "id": app.get("package") or "",
        "url": site_url + page,
        "author": author,
        "name": name,
        "additionalSettings": json.dumps(settings, separators=(",", ":")),
    }
    if not config["id"]:
        config.pop("id")
    encoded = urllib.parse.quote(json.dumps(config, separators=(",", ":")), safe="")
    deep = f"obtainium://app/{encoded}"
    return {
        "app": app["id"],
        "name": label,
        "arch": file["arch"],
        "version": build["version"],
        "build_version": build_version(build),
        "package": app.get("package") or None,
        "source_url": site_url + page,
        "apk": file["url"],
        "config": config,
        "deep_link": deep,
        "add_url": OBTAINIUM_REDIRECT + urllib.parse.quote(deep, safe=""),
        "page": page,
    }


def resolve_packages(apps: dict[str, dict[str, Any]], live: dict[str, Any]) -> None:
    """Set each app's package to the one its built APK actually declares.

    Patches rename apps - Morphe's non-root YouTube installs as
    `app.morphe.android.youtube`, not `com.google.android.youtube` - and
    Obtainium refuses to install when the downloaded package does not match the
    configured id ("Downloaded package ID does not match existing app ID").

    So the id only ever comes from the artefact: read it (3 attempts), or else
    reuse what the live site recorded for the SAME file (matched by sha256, else
    URL). Nothing else is trusted - a hand-written value is not tied to the build
    it would describe, and a wrong id is worse than none. An app whose package
    stays unknown simply gets no Obtainium entry this run.
    """
    live_apps = live.get("apps") or {}
    for app in apps.values():
        app["package"] = ""
        if not app["builds"]:
            continue
        file = app["builds"][0]["files"][0]
        error: Exception | None = None
        for attempt in range(3):
            try:
                app["package"] = package_of(file["url"])
                break
            except Exception as exc:  # noqa: BLE001 - network hiccup, retried below
                error = exc
                time.sleep(2 * (attempt + 1))
        if app["package"]:
            continue

        prev = live_apps.get(app["id"]) or {}
        prev_file = (prev.get("files") or [{}])[0]
        same = (file.get("sha256") and file["sha256"] == prev_file.get("sha256")) or \
               (not file.get("sha256") and file["url"] == prev_file.get("url"))
        if same and prev.get("package"):
            app["package"] = prev["package"]
            print(f"  warn: could not read {app['id']} package ({error}); "
                  f"reusing the live value for the same file: {app['package']}", file=sys.stderr)
        else:
            print(f"  warn: could not read {app['id']} package ({error}); "
                  "leaving it unknown - no Obtainium entry this run", file=sys.stderr)


def resolve_versions(apps: dict[str, dict[str, Any]], live: dict[str, Any]) -> None:
    """Set each current build's update_version: the versionName its APK really has.

    Read from the APK (3 attempts), else what the live site recorded for the same file. If neither, the file name's
    version, which is the same unless the store added a label.
    """
    live_apps = live.get("apps") or {}
    for app in apps.values():
        if not app["builds"]:
            continue
        build, file = app["builds"][0], app["builds"][0]["files"][0]
        error: Exception | None = None
        for attempt in range(3):
            try:
                if name := manifest_attrs(manifest_from_url(file["url"])).get("versionName"):
                    build["update_version"] = name
                    break
            except Exception as exc:  # noqa: BLE001 - network hiccup, retried below
                error = exc
                time.sleep(2 * (attempt + 1))
        if build.get("update_version"):
            continue
        prev = live_apps.get(app["id"]) or {}
        prev_file = (prev.get("files") or [{}])[0]
        if file.get("sha256") and file["sha256"] == prev_file.get("sha256") and prev.get("update_version"):
            build["update_version"] = prev["update_version"]
        print(f"  warn: could not read {app['id']} version ({error})", file=sys.stderr)


def resolve_signers(apps: dict[str, dict[str, Any]], live: dict[str, Any]) -> None:
    """Set each app's `signer`: SHA-256 of the certificate its current APK is signed with.

    Read from the APK's signing block over range requests (3 attempts), else the
    live record of the same file (sha256), else left empty.
    """
    live_apps = live.get("apps") or {}
    for app in apps.values():
        app["signer"] = ""
        error: Exception | None = None
        if not app["builds"]:
            continue
        file = app["builds"][0]["files"][0]
        for attempt in range(3):
            try:
                app["signer"] = signer_of(file["url"])
                break
            except Exception as exc:  # noqa: BLE001 - network hiccup, retried below
                error = exc
                time.sleep(2 * (attempt + 1))
        if app["signer"]:
            continue
        prev = live_apps.get(app["id"]) or {}
        prev_file = (prev.get("files") or [{}])[0]
        if file.get("sha256") and file["sha256"] == prev_file.get("sha256") and prev.get("signer"):
            app["signer"] = prev["signer"]
        print(f"  warn: could not read {app['id']} signer ({error})", file=sys.stderr)


def expected_signer(apps: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    """(the certificate every build must carry, apps whose current APK does not).

    Android refuses to update an app across signing keys ("Conflict" / "App not
    installed"), so one build signed with another key - the keystore secrets
    missing, say, and the builder falling back to a default key - breaks every
    installed copy of that app. The expected certificate is the repository
    variable SIGNING_CERT_SHA256 when set, otherwise the one most builds share.
    """
    want = os.getenv("SIGNING_CERT_SHA256", "").replace(":", "").strip().lower()
    seen = [a["signer"] for a in apps.values() if a.get("signer")]
    if not want and seen:
        want = max(set(seen), key=seen.count)
    wrong = sorted(a["id"] for a in apps.values() if a.get("signer") and a["signer"] != want)
    return want, wrong


def _page(entry: dict[str, Any], build: dict[str, Any], file: dict[str, Any]) -> str:
    e = html.escape
    return PAGE.format(
        name=e(entry["name"]), version=e(build["version"]), arch=e(file["arch"]),
        published=e(build["published"][:10]), url=e(file["url"], quote=True), filename=e(file["name"]),
        build_version=e(build_version(build), quote=True),
        patches=e(" + ".join(p["version"] for p in build.get("patches") or [] if p.get("version")) or "unknown"),
        style=PAGE_STYLE,
    )


def write_obtainium(apps: dict[str, dict[str, Any]], site_url: str, repo: str, now: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    unknown: list[str] = []
    seen_packages: dict[str, dict[str, Any]] = {}

    for app in sorted(apps.values(), key=lambda a: a["name"]):
        if not app["builds"]:
            continue
        build = app["builds"][0]
        files = build["files"]

        # Pages first: every app and every architecture gets one, whatever else
        # happens below, so a URL someone already added keeps working.
        pages: list[tuple[dict[str, Any], dict[str, Any]]] = []
        suffixes = [(files[0], "")] + ([(f, f"-{f['arch']}") for f in files] if len(files) > 1 else [])
        for file, suffix in suffixes:
            entry = obtainium_entry(app, build, file, site_url, repo, suffix)
            (OUT_DIR / entry["page"]).parent.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / entry["page"]).write_text(_page(entry, build, file), encoding="utf-8")
            pages.append((entry, file))
            print(f"  wrote _site/{entry['page']}")

        # Obtainium keys apps by package, and refuses an install whose package
        # differs from the id - so no id, no entry; and two apps on one package
        # (a pre-release twin built without Clone app, say) get one entry.
        pkg = app.get("package")
        if not pkg:
            unknown.append(app["id"])
            continue
        if pkg in seen_packages:
            owner = seen_packages[pkg]
            conflicts.append({"app": app["id"], "name": app["name"], "package": pkg,
                              "shares_with": owner["id"], "shares_with_name": owner["name"]})
            continue
        seen_packages[pkg] = app

        main = pages[0][0]
        if len(pages) > 1:
            # One installable per phone: the main entry is the first arch
            # (arm64-v8a), and each arch is offered on its own.
            main["variants"] = [
                {"arch": f["arch"], "source_url": e["source_url"], "apk": e["apk"],
                 "config": e["config"], "deep_link": e["deep_link"], "add_url": e["add_url"]}
                for e, f in pages[1:]
                if f["arch"] != main["arch"]  # the main entry already is that arch
            ]
        entries.append(main)

    bulk = [e["config"] for e in entries]
    deep_all = "obtainium://apps/" + urllib.parse.quote(json.dumps(bulk, separators=(",", ":")), safe="")
    names = ", ".join(html.escape(e["name"]) for e in entries) or "none yet"
    (OUT_DIR / "obtainium").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "obtainium" / "_all.html").write_text(
        BULK_PAGE.format(count=len(entries), names=names, deep=html.escape(deep_all, quote=True), style=PAGE_STYLE),
        encoding="utf-8",
    )
    print("  wrote _site/obtainium/_all.html")

    payload = {
        "generated": now,
        "repo": repo,
        "how": (
            "Add the source_url as an Obtainium app of type 'HTML', or open add_url on the "
            "phone. The version on the page is the versionName inside the APK, which is what the "
            "phone reports, so Obtainium and ObtainX compare like with like."
        ),
        "add_all_url": site_url + "obtainium/_all.html",
        "add_all_deep_link": deep_all,
        "apps": entries,
        "conflicts": conflicts,
        "unknown_package": unknown,
    }
    write_json(OUT_DIR / "api" / "obtainium.json", payload)
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(OUT_DIR.parent)}")


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")
    owner, name = repo.split("/", 1)
    site_url = os.getenv("SITE_URL", f"https://{owner.lower()}.github.io/{name}/")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def skip(reason: str) -> int:
        # Not a failure: the previous deployment stays up, and the build that is
        # running triggers this workflow again when it finishes.
        print(f"skip: {reason}")
        set_output("skip", "true")
        return 0

    # A rebuild re-drafts ONE brand's release while the others stay published,
    # so the releases visible now are a mix of new and old: the site would fall
    # back to an older build (one that may even share another app's package) or
    # drop apps entirely. Publishing is refused for the whole window.
    state, detail = build_state(repo)
    if state == "busy":
        return skip(f"{detail}; its completion will publish")

    try:
        releases = fetch_releases(repo)
    except Exception as exc:  # noqa: BLE001
        return skip(f"could not read the releases ({exc})")
    apps = collect(releases)
    print(f"{len(releases)} releases -> {len(apps)} apps (builds: {state} {detail})".rstrip())

    live = fetch_live(site_url)
    published = {r["tag_name"] for r in releases}
    live_tags = {a.get("tag") for a in (live.get("apps") or {}).values()} - {None}
    missing = sorted(live_tags - published)
    if not apps and live.get("apps"):
        # An empty result while the site shows apps is never published by itself.
        return skip("no apps visible but the live site has some")
    if state == "unknown" and missing:
        # Cannot see the builds, but a tag the live site serves has vanished from
        # the published releases - the signature of a release in draft.
        return skip(f"live site serves {missing}, which are not published now")

    resolve_packages(apps, live)
    resolve_signers(apps, live)
    resolve_versions(apps, live)
    signer, wrong = expected_signer(apps)
    if wrong:
        # Fail before writing anything: the live site and the Obtainium pages keep
        # pointing at the last good build, and the red run is the alarm.
        for app_id in wrong:
            print(f"::error::{app_id} is signed with {apps[app_id]['signer']}, not {signer}. "
                  "Phones with the app installed cannot update to it. Check the KEYSTORE_* secrets "
                  "and rebuild; the site is left as it is.")
        return 1

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    api_dir = OUT_DIR / "api"

    # --- per-app history -----------------------------------------------------
    for app_id, app in apps.items():
        write_json(
            api_dir / "apps" / f"{app_id}.json",
            {"generated": now, "repo": repo, **app},
        )

    # --- community list (data/community.json, refreshed daily by Catalog) ----
    meta = table_meta()
    icons = write_community(api_dir, now, meta, apps)

    # --- latest per app ------------------------------------------------------
    latest = {
        app_id: {
            "id": app_id,
            "name": app["name"],
            "package": app["package"] or None,
            "brand": app["brand"],
            "signer": app["signer"] or None,
            "source_package": meta.get(app_id, {}).get("stock_package") or None,
            "icon": icons.get(meta.get(app_id, {}).get("stock_package", "")) or None,
            "patch_sources": meta.get(app_id, {}).get("sources") or [],
            **{k: v for k, v in app["builds"][0].items()},
        }
        for app_id, app in apps.items()
        if app["builds"]
    }
    write_json(api_dir / "latest.json", {"generated": now, "repo": repo, "apps": latest})

    # --- catalog (generated separately by tools/gen_catalog.py) --------------
    catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8")) if CATALOG_FILE.exists() else {
        "generated": None,
        "sources": {},
        "note": "run the Catalog workflow to populate this",
    }
    write_json(api_dir / "catalog.json", catalog)

    # --- obtainium ----------------------------------------------------------
    obtainium = write_obtainium(apps, site_url, repo, now)

    # --- index ---------------------------------------------------------------
    write_json(
        api_dir / "index.json",
        {
            "generated": now,
            "repo": repo,
            "site": site_url,
            "releases": f"https://github.com/{repo}/releases",
            "signing_cert_sha256": signer or None,
            "endpoints": {
                "index": "api/index.json",
                "latest": "api/latest.json",
                "app": "api/apps/{app_id}.json",
                "catalog": "api/catalog.json",
                "obtainium": "api/obtainium.json",
                "community": "api/community/index.json",
            },
            "obtainium": {
                "add_all_url": obtainium["add_all_url"],
                "source_url": "obtainium/{app_id}.html",
            },
            "apps": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "package": a["package"] or None,
                    "brand": a["brand"],
                    "signer": a.get("signer") or None,
                    "latest_version": a["builds"][0]["version"] if a["builds"] else None,
                    "updated": a["builds"][0]["published"] if a["builds"] else None,
                    "versions": len(a["builds"]),
                    "api": f"api/apps/{a['id']}.json",
                }
                for a in sorted(apps.values(), key=lambda x: x["name"])
            ],
        },
    )

    # --- static files --------------------------------------------------------
    for src in sorted(STATIC_DIR.iterdir()) if STATIC_DIR.is_dir() else []:
        if src.is_file():
            shutil.copy2(src, OUT_DIR / src.name)
            print(f"  copied {src.name}")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
