#!/usr/bin/env python3
"""Does the update a phone is offered match what should be offered? Asks the live site.

Runs after every Site run and every six hours (.github/workflows/health.yml). Each check is
made from outside, the way a phone or a visitor sees things: the published pages, the real
APK files, Stremio's feed and the patch repositories. Anything wrong turns the run red. The
state and the last report live on the `health` branch, where a watcher outside GitHub reads
them and pushes the alert, and sees it when this check itself stops running.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gen_site  # noqa: E402
from apk_package import manifest_attrs, manifest_from_url, names_from_url, signer_of  # noqa: E402
from gen_catalog import _upstream_ver_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEED = "https://api.strem.io/downloads/config"
UPSTREAM = "nvbangg:builder-for-morphe:main"
UPSTREAM_REPO = "nvbangg/builder-for-morphe"

# How long a condition may last before it counts: some are normal for a while. A new upstream
# version waits for the next check (GitHub runs them hours late), a release for Pages to deploy.
GRACE = {
    "feed-behind": timedelta(hours=14),
    "patches-behind": timedelta(hours=14),
    "offered-stale": timedelta(hours=1),
    "apk-unreachable": timedelta(hours=2),
    "wanted-behind": timedelta(days=3),
    "sync-behind": timedelta(days=7),
    "check-error": timedelta(hours=12),
}
CI_MAX_AGE = timedelta(hours=30)
# Not "cancelled": a run another run replaced in its queue is normal.
BAD_CONCLUSIONS = ("failure", "startup_failure", "timed_out", "action_required")


def owner_of(repo: str) -> str:
    return repo.split("/", 1)[0]


def enabled_apps() -> list[dict[str, Any]]:
    """Every enabled table of config.toml, as this check needs it."""
    data = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    default_brand = str(data.get("brand", "Morphe"))
    apps = []
    for table, body in data.items():
        if not isinstance(body, dict) or body.get("enabled", True) is not True:
            continue
        patches = body.get("patches") or {}
        source, spec = next(iter(patches.items()), ("", {}))
        apps.append({
            "id": gen_site.slug(table),
            "brand": str(body.get("brand", default_brand)),
            "source": re.sub(r"^(github|gitlab):", "", source),
            "patch_version": spec.get("version", "latest") if isinstance(spec, dict) else "latest",
            "feed": str(body.get("stremio-dlurl", "")),
            "pin": (m.group(1) if (m := re.search(r"@v?([^:]+):\d+$", str(body.get("stremio-dlurl", "")))) else ""),
            "keywords": bool(body.get("changelog-keywords")),
        })
    return apps


# ------------------------------------------------------------------- pure checks


def check_offers(apps: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, str]:
    """What is offered against the releases, the pages and the real files."""
    found: dict[str, str] = {}
    expected = gen_site.collect(data["releases"])
    latest = data["latest"].get("apps") or {}
    entries = {e["app"]: e for e in data["obtainium"].get("apps") or []}
    for app in apps:
        app_id = app["id"]
        want = (expected.get(app_id) or {}).get("builds") or []
        if not want:
            found[f"no-release:{app_id}"] = f"{app_id}: no release holds a build of it"
            continue
        have = latest.get(app_id)
        entry = entries.get(app_id)
        if not have or not entry:
            found[f"not-offered:{app_id}"] = f"{app_id}: the site offers no update entry for it"
            continue
        if (have.get("version"), have.get("tag")) != (want[0]["version"], want[0]["tag"]):
            found[f"offered-stale:{app_id}"] = (f"{app_id}: the site offers {have.get('version')} ({have.get('tag')}), "
                                                f"the releases say {want[0]['version']} ({want[0]['tag']})")
        if app.get("pin") and have.get("version") != app["pin"]:
            found[f"pin-not-offered:{app_id}"] = f"{app_id}: config.toml pins {app['pin']}, the site offers {have.get('version')}"
        page = data["pages"].get(app_id) or ""
        links = re.findall(r'href="([^"]+\.apk)"', page)
        meta = re.search(gen_site.BUILD_VERSION_REGEX, page)
        if links != [entry["apk"]]:
            found[f"page-link:{app_id}"] = f"{app_id}: its update page links {links}, not {entry['apk']}"
        if not meta or meta.group(1) != entry["build_version"]:
            found[f"page-version:{app_id}"] = f"{app_id}: its update page says {meta.group(1) if meta else 'nothing'}, not {entry['build_version']}"
        if not have.get("patches"):
            found[f"no-bundle:{app_id}"] = f"{app_id}: its release notes name no patch bundle, so a patch update would not be noticed"
        if not entry["build_version"].startswith(have.get("version", "")):
            found[f"page-version:{app_id}"] = f"{app_id}: update version {entry['build_version']} does not start with {have.get('version')}"
        found.update(_check_apk(app_id, entry, have, data))
        notes = next((str(r.get("body") or "") for r in data["releases"] if r.get("tag_name") == have.get("tag")), "")
        for line in notes.splitlines():
            wanted = re.search(r"\(wanted ([^)]+)\)", line)
            if wanted and any(f"/{f.get('name')})" in line for f in have.get("files") or [{"name": "\0"}]):
                found[f"wanted-behind:{app_id}"] = f"{app_id}: built on {have.get('version')} because {wanted.group(1)} cannot be downloaded yet"
    return found


def _check_apk(app_id: str, entry: dict[str, Any], have: dict[str, Any], data: dict[str, Any]) -> dict[str, str]:
    apk = data["apks"].get(entry["apk"]) or {"error": "not read"}
    if apk.get("error"):
        return {f"apk-unreachable:{app_id}": f"{app_id}: its APK cannot be read: {apk['error']}"}
    found: dict[str, str] = {}
    if apk.get("package") != entry.get("package"):
        found[f"apk-package:{app_id}"] = f"{app_id}: the APK is {apk.get('package')}, the update entry says {entry.get('package')}"
    if apk.get("version") is not None and apk["version"] != entry.get("build_version"):
        found[f"apk-version:{app_id}"] = (f"{app_id}: the update page offers {entry.get('build_version')}, the APK says {apk['version']}: "
                                          "ObtainX compares those two once it is installed")
    arch, abis = entry.get("arch"), apk.get("abis")
    if abis is not None and arch not in (None, "all") and arch not in abis:
        found[f"apk-cpu:{app_id}"] = f"{app_id}: built for {arch}, but its libraries are for {sorted(abis) or 'nothing'}"
    if data.get("signer") and apk.get("signer") != data["signer"]:
        found[f"apk-signer:{app_id}"] = f"{app_id}: the APK is signed with {apk.get('signer')}: phones cannot update to it"
    return found


def offer_rank(version: str, text: str) -> tuple[Any, ...]:
    """The order ObtainX gives update versions: the app version with its label, then the patch revision.
    Real: 21.44.528-2.1.0.6 to 21.44.528-BETA-2.1.0.7 has higher numbers and is still no update."""
    revision = text[len(version) + 1:] if text.startswith((f"{version}-", f"{version}.")) else ("" if text == version else text)
    return (_upstream_ver_key(version), tuple(int(n) for n in re.findall(r"\d+", revision)))


def check_direction(apps: list[dict[str, Any]], data: dict[str, Any], previous: dict[str, Any]) -> dict[str, str]:
    """An offer phones cannot take. Android refuses a lower versionCode than the one installed, and a phone can
    hold ANY build ever released, so the highest ever shipped is the bar. ObtainX shows a lower update version as
    "up to date". A changed package makes a different app. A pin is deliberate."""
    found: dict[str, str] = {}
    pinned = {a["id"] for a in apps if a.get("pin")}
    for entry in data["obtainium"].get("apps") or []:
        app_id, old = entry["app"], previous.get(entry["app"]) or {}
        if app_id in pinned:
            continue
        apk = data["apks"].get(entry["apk"]) or {}
        code, highest = apk.get("code"), ((data.get("shipped_codes") or {}).get("codes") or {}).get(app_id)
        if code and highest and int(code) < highest["code"]:
            found[f"offer-downgrade:{app_id}"] = (f"{app_id}: offered versionCode {code} is lower than {highest['code']} of {highest['file']}: "
                                                  "Android refuses it on a phone holding that build")
        if old.get("text") and old.get("version") and offer_rank(entry.get("version", ""), entry["build_version"]) < offer_rank(old["version"], old["text"]):
            found[f"offer-backwards:{app_id}"] = f"{app_id}: the update version went from {old['text']} to {entry['build_version']}: phones see no update"
        if old.get("package") and entry.get("package") and old["package"] != entry["package"]:
            found[f"offer-package:{app_id}"] = f"{app_id}: the package changed from {old['package']} to {entry['package']}: phones get a second app, not an update"
    return found


def shipped_codes(releases: list[dict[str, Any]]) -> dict[str, Any]:
    """{"codes": app id -> the highest versionCode of any APK ever published, "unread": files that could not be read}.
    One read per published file, not per name: a rebuild keeps its name with another code."""
    config = gen_site.app_config()
    files: list[tuple[str, str, str]] = []
    for release in releases:
        for asset in release.get("assets", []):
            parts = gen_site.split_asset(asset["name"], config)
            if parts and (entry := config.get(parts[0])):
                files.append((entry["id"], asset["name"], asset["browser_download_url"]))

    def code_of(item: tuple[str, str, str]) -> tuple[str, str, int | None]:
        app_id, name, url = item
        try:
            return app_id, name, int(manifest_attrs(manifest_from_url(url)).get("versionCode") or 0)
        except Exception:  # noqa: BLE001 - the others still set the bar; this one is reported
            return app_id, name, None

    codes: dict[str, dict[str, Any]] = {}
    unread: list[str] = []
    with ThreadPoolExecutor(8) as pool:
        for app_id, name, code in pool.map(code_of, files):
            if code is None:
                unread.append(name)
            elif code > (codes.get(app_id) or {"code": 0})["code"]:
                codes[app_id] = {"code": code, "file": name}
    return {"codes": codes, "unread": unread}


def check_upstream(apps: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, str]:
    """A new app version or a new patch release that has not reached the offer."""
    found: dict[str, str] = {}
    latest = data["latest"].get("apps") or {}
    for app in apps:
        have = latest.get(app["id"])
        if not have or app["keywords"]:
            continue
        feed_version = data["feeds"].get(app["id"])
        if feed_version == "":
            found[f"check-error:feed:{app['id']}"] = f"{app['id']}: Stremio's feed no longer lists its entry"
        elif feed_version and feed_version != have.get("version"):
            found[f"feed-behind:{app['id']}"] = f"{app['id']}: Stremio publishes {feed_version}, we offer {have.get('version')}"
        bundle = data["bundles"].get((app["source"], app["patch_version"]))
        if bundle:
            org = app["source"].split("/", 1)[0].lower()
            mine = [p.get("version") for p in have.get("patches") or [] if p.get("file", "").lower().startswith(org + "/")]
            if not mine:
                found[f"no-bundle:{app['id']}"] = f"{app['id']}: its release notes do not name its own patch bundle"
            elif bundle not in mine:
                found[f"patches-behind:{app['id']}"] = f"{app['id']}: {app['source']} is at {bundle}, we offer {mine[0]}"
    return found


def check_runs(data: dict[str, Any], now: datetime) -> dict[str, str]:
    """Stuck drafts, a daily check that stopped running, builds that failed."""
    found: dict[str, str] = {}
    for rel in data["releases_all"]:
        if rel.get("draft"):
            found[f"stuck-draft:{rel.get('tag_name')}"] = f"{rel.get('tag_name')} is a draft with no build running: its APKs cannot be downloaded"
    for item in (data["obtainium"].get("conflicts") or []):
        found[f"package-conflict:{item.get('app')}"] = f"{item.get('app')} has the same package as {item.get('shares_with')}: it gets no update entry"
    for app_id in (data["obtainium"].get("unknown_package") or []):
        found[f"package-unknown:{app_id}"] = f"{app_id}: its package could not be read: it gets no update entry"
    if unread := (data.get("shipped_codes") or {}).get("unread"):
        found["check-error:apk-codes"] = f"{len(unread)} published APKs could not be read, so the versionCode bar may be low: {unread[:3]}"
    site = data.get("site_run")
    if site and site.get("conclusion") in BAD_CONCLUSIONS:
        found["site-failed"] = f"the Site workflow ended {site['conclusion']}: phones keep being offered the last published versions"
    tests = data.get("tests_run")
    if tests and tests.get("conclusion") in BAD_CONCLUSIONS:
        found["tests-failed"] = f"the release flow tests ended {tests['conclusion']} on the newest code"
    ci = data.get("ci")
    if not ci:
        found["ci-stale"] = "the CI workflow has no runs"
    else:
        age = now - _parse_time(ci["created_at"])
        if age > CI_MAX_AGE:
            found["ci-stale"] = f"the daily check last ran {int(age.total_seconds() // 3600)} h ago: GitHub may have stopped the schedule"
        for job in data.get("ci_failed_jobs") or []:
            found[f"ci-failed:{job}"] = f"the build failed: {job}"
        if ci.get("conclusion") in BAD_CONCLUSIONS and not data.get("ci_failed_jobs"):
            found["ci-failed"] = f"the daily check ended {ci['conclusion']} with no failed job to name"
    if data.get("sync_behind"):
        found["sync-behind"] = f"{data['sync_behind']} upstream commits are not merged: the sync may be stuck"
    keep = (data.get("ignore_sync") or "").split()
    if keep:
        for path in data.get("changed_from_upstream") or []:
            if not any(path == k or path.startswith(k + "/") for k in keep):
                found[f"sync-unprotected:{path}"] = f"{path} differs from upstream and is not in IGNORE_SYNC_FILES: an upstream sync can undo it"
    for name in data.get("flow_failures") or []:
        found[f"flow-test:{name}"] = f"site flow test: {name}"
    return found


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def grace_of(key: str) -> timedelta:
    return GRACE.get(key.split(":", 1)[0], timedelta(0))


def update_state(state: dict[str, Any], problems: dict[str, str], now: datetime) -> dict[str, Any]:
    """Keep when each problem was first seen, which its grace period counts from."""
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    old = state.get("problems") or {}
    return {"problems": {key: {"first_seen": (old.get(key) or {}).get("first_seen", stamp), "text": text}
                         for key, text in sorted(problems.items())}}


def active(state: dict[str, Any], now: datetime) -> list[str]:
    return sorted(rec["text"] for key, rec in (state.get("problems") or {}).items()
                  if now - _parse_time(rec["first_seen"]) >= grace_of(key))


# ------------------------------------------------------------------- reading the world


def read_apk(url: str) -> dict[str, Any]:
    try:
        attrs = manifest_attrs(manifest_from_url(url))
        abis = {n.split("/")[1] for n in names_from_url(url) if n.startswith("lib/") and n.count("/") >= 2}
        return {"package": attrs.get("package"), "version": attrs.get("versionName"), "code": attrs.get("versionCode"),
                "signer": signer_of(url), "abis": abis}
    except Exception as exc:  # noqa: BLE001 - any failure to read it is the finding
        return {"error": str(exc)[:200]}


def _text(url: str) -> str:
    req = urllib.request.Request(f"{url}?_={int(datetime.now().timestamp())}", headers={"User-Agent": "morphe-builder-health"})
    for wait in (5, 10):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except OSError:
            time.sleep(wait)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def feed_versions(apps: list[dict[str, Any]]) -> dict[str, str]:
    wanted = [a for a in apps if a["feed"] and "@" not in a["feed"]]
    if not wanted:
        return {}
    entries = {e.get("id"): e.get("value") for e in json.loads(_text(FEED)).get("entries", [])}
    return {a["id"]: str((entries.get(a["feed"].partition("#")[2]) or {}).get("versionName") or "") for a in wanted}


def _file_version(release: dict[str, Any]) -> str:
    """The bundle version a build of this release would use. A release can hold the previous bundle too (real:
    v0.9.0-dev.7 has dev.6 and dev.7): the file of the tag, else the highest."""
    tag = str(release["tag_name"]).lstrip("v")
    versions = [m.group(1) for a in release.get("assets") or []
                if str(a.get("name", "")).endswith(".mpp") and (m := gen_site._FILE_VERSION_RE.search(a["name"]))]
    if not versions or tag in versions:
        return tag
    return max(versions, key=_upstream_ver_key)


def patch_bundles(apps: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for source, version in {(a["source"], a["patch_version"]) for a in apps if a["source"]}:
        if version == "dev":
            releases = gen_site._get(f"{gen_site.API}/repos/{source}/releases?per_page=100")
            out[source, version] = _file_version(max(releases, key=lambda r: _upstream_ver_key(r["tag_name"])))
        else:
            out[source, version] = _file_version(gen_site._get(f"{gen_site.API}/repos/{source}/releases/latest"))
    return out


def gather(repo: str, site_url: str, apps: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    """Read everything; a source that cannot be read becomes its own (slow) problem."""
    errors: dict[str, str] = {}

    def read(name: str, fn: Any, default: Any) -> Any:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            errors[f"check-error:{name}"] = f"this check could not read {name}: {str(exc)[:150]}"
            return default

    raw = read("releases", lambda: gen_site.all_releases(repo), [])
    latest = read("latest.json", lambda: json.loads(_text(site_url + "api/latest.json")), {})
    obtainium = read("obtainium.json", lambda: json.loads(_text(site_url + "api/obtainium.json")), {})
    entries = obtainium.get("apps") or []
    pages = {e["app"]: read(f"update page {e['app']}", lambda e=e: _text(e["source_url"]), "") for e in entries}
    runs = read("CI runs", lambda: gen_site._get(f"{gen_site.API}/repos/{repo}/actions/workflows/ci.yml/runs?per_page=1&exclude_pull_requests=true"), {})
    ci = (runs.get("workflow_runs") or [None])[0]
    failed: list[str] = []
    if ci and ci.get("conclusion") == "failure":
        jobs = read("CI jobs", lambda: gen_site._get(f"{gen_site.API}/repos/{repo}/actions/runs/{ci['id']}/jobs?per_page=100"), {})
        failed = [j["name"] for j in jobs.get("jobs") or [] if j.get("conclusion") == "failure"]
    site_runs = read("Site runs", lambda: gen_site._get(f"{gen_site.API}/repos/{repo}/actions/workflows/site.yml/runs?per_page=1&exclude_pull_requests=true"), {})
    tests_runs = read("Tests runs", lambda: gen_site._get(f"{gen_site.API}/repos/{repo}/actions/workflows/tests.yml/runs?per_page=1&exclude_pull_requests=true"), {})
    compare = read("upstream", lambda: gen_site._get(f"{gen_site.API}/repos/{repo}/compare/main...{UPSTREAM}"), {})
    return {
        "releases": [r for r in raw if not r.get("draft")],
        "releases_all": raw,
        "latest": latest,
        "obtainium": obtainium,
        "pages": pages,
        "apks": {e["apk"]: read_apk(e["apk"]) for e in entries if e["app"] in {a["id"] for a in apps}},
        "feeds": read("Stremio's feed", lambda: feed_versions(apps), {}),
        "bundles": read("patch releases", lambda: patch_bundles(apps), {}),
        "shipped_codes": read("the APKs ever published", lambda: shipped_codes([r for r in raw if not r.get("draft")]), {}),
        "ci": ci,
        "site_run": (site_runs.get("workflow_runs") or [None])[0],
        "tests_run": (tests_runs.get("workflow_runs") or [None])[0],
        "ci_failed_jobs": failed,
        "sync_behind": compare.get("ahead_by") or 0,
        "ignore_sync": os.getenv("IGNORE_SYNC_FILES", ""),
        "changed_from_upstream": [f["filename"] for f in read("upstream files", lambda: gen_site._get(f"{gen_site.API}/repos/{UPSTREAM_REPO}/compare/main...{owner_of(repo)}:{repo.split('/')[1]}:main"), {}).get("files") or [] if f.get("status") == "modified"],
        "signer": os.getenv("SIGNING_CERT_SHA256", "").replace(":", "").strip().lower(),
        "flow_failures": flow_failures(os.getenv("FLOW_TEST_LOG", "")),
    }, errors


def flow_failures(path: str) -> list[str] | None:
    """The names of the failed flow tests; None when it did not run on this check."""
    if not path or not Path(path).exists():
        return None
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    failed = [line[6:].split("  — ")[0].strip() for line in lines if line.startswith("FAIL  ")]
    if not any(re.fullmatch(r"\d+/\d+ passed", line.strip()) for line in lines):
        failed.append("it did not finish")
    return failed


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")
    owner, name = repo.split("/", 1)
    site_url = os.getenv("SITE_URL", f"https://{owner.lower()}.github.io/{name}/")
    state_dir = Path(os.getenv("HEALTH_DIR", "health-state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    busy, detail = gen_site.build_state(repo)
    if busy == "busy":
        (state_dir / "report.json").write_text(json.dumps({"checked_at": stamp, "skipped": detail, "problems": active(state, now)}, indent=1) + "\n", encoding="utf-8")
        print(f"skip: {detail}")
        return 0

    apps = enabled_apps()
    data, errors = gather(repo, site_url, apps)
    # A source that could not be read says nothing about the offer: it waits as its own problem.
    unread = any(k.startswith(("check-error:latest", "check-error:obtainium", "check-error:update page")) for k in errors)
    offers = {} if unread else check_offers(apps, data)
    direction = {} if unread else check_direction(apps, data, state.get("offers") or {})
    problems = {**errors, **offers, **direction, **check_upstream(apps, data), **check_runs(data, now)}
    if "check-error:releases" in errors:
        problems = {k: v for k, v in problems.items() if k.startswith("check-error")}  # no releases read: nothing else can be judged
    if data["flow_failures"] is None:  # the flow test runs once a day: its findings last until the next one
        problems.update({k: rec["text"] for k, rec in (state.get("problems") or {}).items() if k.startswith("flow-test:")})
    new_state = update_state(state, problems, now)
    # What was offered: kept through a backwards problem, so it stays flagged until the offer is back above it.
    new_state["offers"] = dict(state.get("offers") or {})
    if not unread:
        for entry in data["obtainium"].get("apps") or []:
            if not any(k in direction for k in (f"offer-backwards:{entry['app']}", f"offer-package:{entry['app']}")):
                new_state["offers"][entry["app"]] = {"text": entry["build_version"], "version": entry.get("version"), "package": entry.get("package")}
    state_file.write_text(json.dumps(new_state, indent=1) + "\n", encoding="utf-8")
    now_active = active(new_state, now)
    (state_dir / "report.json").write_text(json.dumps({
        "checked_at": stamp,
        "offered": {k: {"version": v.get("version"), "tag": v.get("tag")} for k, v in (data["latest"].get("apps") or {}).items()},
        "problems": now_active,
        "waiting": sorted(rec["text"] for rec in new_state["problems"].values() if rec["text"] not in now_active),
    }, indent=1) + "\n", encoding="utf-8")
    for line in now_active:
        print(f"::error title=Release flow::{line}")
    print(f"{len(now_active)} problems, {len(new_state['problems']) - len(now_active)} waiting")
    return 1 if now_active else 0


if __name__ == "__main__":
    sys.exit(main())
