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
from apk_package import package_of  # noqa: E402

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
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


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


def fetch_releases(repo: str, max_pages: int = 4) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            batch = _get(f"{API}/repos/{repo}/releases?per_page=100&page={page}")
        except urllib.error.HTTPError as exc:
            if page == 1:
                raise  # nothing read at all: never mistake that for "no releases"
            print(f"warn: releases page {page} failed: {exc}", file=sys.stderr)
            break
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
    return [r for r in out if not r.get("draft")]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def github_asset_name(name: str) -> str:
    """How GitHub stores an uploaded asset name: any character outside
    [A-Za-z0-9@+-_.] becomes '.', and runs of '.' collapse (builder.py relies on
    the same rule)."""
    return re.sub(r"\.+", ".", re.sub(r"[^a-zA-Z0-9@+\-_.]", ".", name))


def app_config() -> dict[str, dict[str, str]]:
    """filename stem -> {id, name, brand}, straight from config.toml.

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
        out[stem] = {"id": slug(table), "name": name, "brand": brand}
    return out


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


def collect(releases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """app id -> {name, brand, builds[]}, newest build first."""
    apps: dict[str, dict[str, Any]] = {}
    config = app_config()
    brands = sorted({e["brand"].lower().replace(" ", "-") for e in config.values()}, key=len, reverse=True)
    for rel in releases:
        published = rel.get("published_at") or rel.get("created_at") or ""
        for asset in rel.get("assets", []):
            parts = split_asset(asset["name"], config)
            if parts is None:
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
            build = app["builds"].setdefault(
                key,
                {
                    "version": version,
                    "tag": rel["tag_name"],
                    "published": published,
                    "prerelease": bool(rel.get("prerelease")),
                    "release_url": rel.get("html_url", ""),
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
        builds = sorted(app["builds"].values(), key=lambda b: b["published"], reverse=True)
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
<meta name="robots" content="noindex">
<style>{style}</style></head>
<body><main>
<h1>{name}</h1>
<p>Version <b>{version}</b> ({arch}), built {published}.</p>
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
<p class="small">If nothing happens, install <a href="https://github.com/ImranR98/Obtainium/releases">Obtainium</a>
first, then come back to this page. <a href="../">Back to Morphe Builder</a></p>
<script>setTimeout(function(){{location.href=document.getElementById("go").href}},300)</script>
</main></body></html>
"""


def _escape(text: str) -> str:
    # Dart's RegExp is ECMAScript: `\-` is only legal outside unicode mode, and
    # Python escapes hyphens. Leave them alone; they are not special here.
    return re.escape(text).replace("\\-", "-")


def version_regex(filename: str, version: str, arch: str) -> str:
    """Matched against the whole APK URL, not the filename.

    Obtainium runs this over the full decoded link
    (`https://github.com/.../youtube-morphe-v21.13.164-all.apk`), so it must NOT
    be anchored with `^` - `allMatches` returning nothing is what raises
    "Could not determine release version". The app prefix still keeps it from
    matching another app's link.
    """
    # ASSET_RE guarantees the name ends with exactly this suffix.
    prefix = filename[: -len(f"-v{version}-{arch}.apk")]
    # "/" so that "music-morphe" cannot match inside "yt-music-morphe"
    return f"/{_escape(prefix)}-v(.+)-{_escape(arch)}\\.apk$"


def obtainium_entry(app: dict[str, Any], build: dict[str, Any], file: dict[str, Any],
                    site_url: str, repo: str, suffix: str = "") -> dict[str, Any]:
    page = f"obtainium/{app['id']}{suffix}.html"
    settings = {
        "versionExtractionRegEx": version_regex(file["name"], build["version"], file["arch"]),
        "matchGroupToUse": "1",
        "apkFilterRegEx": "\\.apk$",
    }
    label = app["name"] if not suffix else f"{app['name']} ({file['arch']})"
    config: dict[str, Any] = {
        "id": app.get("package") or "",
        "url": site_url + page,
        "author": repo.split("/")[0],
        "name": f"{label} ({app['brand'].title()})",
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


def _page(entry: dict[str, Any], build: dict[str, Any], file: dict[str, Any]) -> str:
    e = html.escape
    return PAGE.format(
        name=e(entry["name"]), version=e(build["version"]), arch=e(file["arch"]),
        published=e(build["published"][:10]), url=e(file["url"], quote=True), filename=e(file["name"]),
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
            "phone. The version is read from the APK filename, so Obtainium only prompts when "
            "the app version really changes."
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

    # --- latest per app ------------------------------------------------------
    latest = {
        app_id: {
            "id": app_id,
            "name": app["name"],
            "package": app["package"] or None,
            "brand": app["brand"],
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
            "endpoints": {
                "index": "api/index.json",
                "latest": "api/latest.json",
                "app": "api/apps/{app_id}.json",
                "catalog": "api/catalog.json",
                "obtainium": "api/obtainium.json",
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
