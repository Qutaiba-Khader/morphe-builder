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
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gen_site  # noqa: E402
from apk_package import manifest_attrs, manifest_from_url, signer_of  # noqa: E402
from gen_catalog import _upstream_ver_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEED = "https://api.strem.io/downloads/config"
UPSTREAM = "nvbangg:builder-for-morphe:main"

# How long a condition may last before it counts: some are normal for a while. A new upstream
# version waits for the next check (GitHub runs them hours late), a release for Pages to deploy.
GRACE = {
    "feed-behind": timedelta(hours=14),
    "patches-behind": timedelta(hours=14),
    "offered-stale": timedelta(hours=1),
    "sync-behind": timedelta(days=7),
    "check-error": timedelta(hours=12),
}
CI_MAX_AGE = timedelta(hours=30)


def enabled_apps() -> list[dict[str, Any]]:
    """Every enabled table of config.toml, as this check needs it."""
    data = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    default_brand = str(data.get("brand", "Morphe"))
    apps = []
    for table, body in data.items():
        if not isinstance(body, dict) or body.get("enabled") is not True:
            continue
        patches = body.get("patches") or {}
        source, spec = next(iter(patches.items()), ("", {}))
        apps.append({
            "id": gen_site.slug(table),
            "brand": str(body.get("brand", default_brand)),
            "source": re.sub(r"^(github|gitlab):", "", source),
            "patch_version": spec.get("version", "latest") if isinstance(spec, dict) else "latest",
            "feed": str(body.get("stremio-dlurl", "")),
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
        page = data["pages"].get(app_id) or ""
        links = re.findall(r'href="([^"]+\.apk)"', page)
        meta = re.search(gen_site.BUILD_VERSION_REGEX, page)
        if links != [entry["apk"]]:
            found[f"page-link:{app_id}"] = f"{app_id}: its update page links {links}, not {entry['apk']}"
        if not meta or meta.group(1) != entry["build_version"]:
            found[f"page-version:{app_id}"] = f"{app_id}: its update page says {meta.group(1) if meta else 'nothing'}, not {entry['build_version']}"
        if not have.get("patches"):
            found[f"no-bundle:{app_id}"] = f"{app_id}: its release notes name no patch bundle, so a patch update would not be noticed"
        if not entry["build_version"].startswith(have.get("version", "") + "-"):
            found[f"page-version:{app_id}"] = f"{app_id}: update version {entry['build_version']} does not start with {have.get('version')}"
        found.update(_check_apk(app_id, entry, have, data))
    return found


def _check_apk(app_id: str, entry: dict[str, Any], have: dict[str, Any], data: dict[str, Any]) -> dict[str, str]:
    apk = data["apks"].get(entry["apk"]) or {"error": "not read"}
    if apk.get("error"):
        return {f"apk-unreachable:{app_id}": f"{app_id}: its APK cannot be read: {apk['error']}"}
    found: dict[str, str] = {}
    if apk.get("package") != entry.get("package"):
        found[f"apk-package:{app_id}"] = f"{app_id}: the APK is {apk.get('package')}, the update entry says {entry.get('package')}"
    if apk.get("version") not in (None, have.get("version")):
        found[f"apk-version:{app_id}"] = f"{app_id}: the APK says version {apk.get('version')}, the site says {have.get('version')}"
    if data.get("signer") and apk.get("signer") != data["signer"]:
        found[f"apk-signer:{app_id}"] = f"{app_id}: the APK is signed with {apk.get('signer')}: phones cannot update to it"
    return found


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
        bundle = data["bundles"].get(app["source"])
        if bundle:
            org = app["source"].split("/", 1)[0].lower()
            mine = [p.get("version") for p in have.get("patches") or [] if p.get("file", "").lower().startswith(org + "/")]
            if mine and bundle not in mine:
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
    site = data.get("site_run")
    if site and site.get("conclusion") == "failure":
        found["site-failed"] = "the Site workflow failed: phones keep being offered the last published versions"
    tests = data.get("tests_run")
    if tests and tests.get("conclusion") == "failure":
        found["tests-failed"] = "the release flow tests failed on the newest code"
    ci = data.get("ci")
    if not ci:
        found["ci-stale"] = "the CI workflow has no runs"
    else:
        age = now - _parse_time(ci["created_at"])
        if age > CI_MAX_AGE:
            found["ci-stale"] = f"the daily check last ran {int(age.total_seconds() // 3600)} h ago: GitHub may have stopped the schedule"
        for job in data.get("ci_failed_jobs") or []:
            found[f"ci-failed:{job}"] = f"the build failed: {job}"
    if data.get("sync_behind"):
        found["sync-behind"] = f"{data['sync_behind']} upstream commits are not merged: the sync may be stuck"
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
        return {"package": attrs.get("package"), "version": attrs.get("versionName"), "signer": signer_of(url)}
    except Exception as exc:  # noqa: BLE001 - any failure to read it is the finding
        return {"error": str(exc)[:200]}


def _text(url: str) -> str:
    req = urllib.request.Request(f"{url}?_={int(datetime.now().timestamp())}", headers={"User-Agent": "morphe-builder-health"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def feed_versions(apps: list[dict[str, Any]]) -> dict[str, str]:
    wanted = [a for a in apps if a["feed"] and "@" not in a["feed"]]
    if not wanted:
        return {}
    entries = {e.get("id"): e.get("value") for e in json.loads(_text(FEED)).get("entries", [])}
    return {a["id"]: str((entries.get(a["feed"].partition("#")[2]) or {}).get("versionName") or "") for a in wanted}


def patch_bundles(apps: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for source, version in {(a["source"], a["patch_version"]) for a in apps if a["source"]}:
        if version == "dev":
            tags = [r["tag_name"] for r in gen_site._get(f"{gen_site.API}/repos/{source}/releases?per_page=100")]
            out[source] = max(tags, key=_upstream_ver_key).lstrip("v")
        else:
            out[source] = str(gen_site._get(f"{gen_site.API}/repos/{source}/releases/latest")["tag_name"]).lstrip("v")
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

    raw = read("releases", lambda: [r for page in (1, 2, 3, 4) for r in gen_site._get(f"{gen_site.API}/repos/{repo}/releases?per_page=100&page={page}")], [])
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
        "ci": ci,
        "site_run": (site_runs.get("workflow_runs") or [None])[0],
        "tests_run": (tests_runs.get("workflow_runs") or [None])[0],
        "ci_failed_jobs": failed,
        "sync_behind": compare.get("ahead_by") or 0,
        "signer": os.getenv("SIGNING_CERT_SHA256", "").replace(":", "").strip().lower(),
        "flow_failures": flow_failures(os.getenv("FLOW_TEST_LOG", "")),
    }, errors


def flow_failures(path: str) -> list[str]:
    if not path or not Path(path).exists():
        return []
    return [line[6:].split("  — ")[0].strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.startswith("FAIL  ")]


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
    problems = {**errors, **check_offers(apps, data), **check_upstream(apps, data), **check_runs(data, now)}
    if "check-error:releases" in errors:
        problems = {k: v for k, v in problems.items() if k.startswith("check-error")}  # no releases read: nothing else can be judged
    new_state = update_state(state, problems, now)
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
