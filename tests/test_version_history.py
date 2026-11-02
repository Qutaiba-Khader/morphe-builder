"""Three months of real versions replayed through the code (fixture: tests/fixtures/history.json).

Every version here really existed: our releases and the APKs in them, Stremio's feed as archived, and the
Morphe, CLI, TikTok and Stremio patch releases. The ObtainX answers come from ObtainX's own compareVersionStrings.
"older" means the first version is older than the second, so the phone is offered the update.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO as _StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]
os.environ.setdefault("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")

import gen_site  # noqa: E402
import history_replay  # noqa: E402
import release_check  # noqa: E402
import verify_apk  # noqa: E402

from test_release_flow import coded_manifest  # noqa: E402

from src.core import prebuilts  # noqa: E402
from src.core.prebuilts import get_highest_ver  # noqa: E402
from src.scrapers.stremio import StremioScraper  # noqa: E402
from src.scripts import matrix  # noqa: E402

HISTORY = history_replay.load()
OURS = HISTORY["ours"]
APK_RE = re.compile(r"^(?P<stem>.+)-v(?P<version>.+)-(?P<arch>all|arm64-v8a|armeabi-v7a)\.apk$")
CERT = "7687718c8b2e96088ba64cfa833db63c9bb76ecf5c7dda62e65e05e37fb77603"
# Real builds below the highest versionCode ever released, which Android refuses on a phone holding that one:
# YouTube Experimental after 21.41.525 and after 21.44.528-BETA. verify_apk rejects these now.
REAL_CODE_DROPS = {"26.10.14-morphe-dev", "26.10.15-morphe-dev", "26.11.01-morphe-dev"}


def order(version):
    """An oracle written apart from the code: numbers, then a final beats its own label."""
    numbers = tuple(int(n) for n in re.match(r"\d+(?:\.\d+)*", version).group(0).split("."))
    return (numbers, 0 if re.search(r"[a-zA-Z]", version) else 1)


class Upstream(unittest.TestCase):
    """The versions the upstream projects really published."""

    # P-HIS-01
    def test_P_HIS_01_the_highest_tag_is_always_the_newest_real_one(self):
        for key, seq in HISTORY["upstream"].items():
            tags = []
            for release in seq:
                tags.append(release["tag"])
                self.assertEqual(get_highest_ver(tags), release["tag"], f"{key} at {release['published']}")

    # P-HIS-02
    def test_P_HIS_02_every_real_file_name_gives_its_version(self):
        checked, lag = 0, []
        for key in ("morphe-patches", "subs-patches", "tiktok-patches", "morphe-cli"):
            for release in HISTORY["upstream"][key]:
                for file in release["files"]:
                    match = gen_site._FILE_VERSION_RE.search(file)
                    self.assertIsNotNone(match, file)
                    if match.group(1) != release["tag"].lstrip("v"):
                        lag.append(release["tag"])
                    checked += 1
        self.assertGreater(checked, 300)
        # real: TikTok's dev releases also carry the bundle of the dev before; every release still has the file of its tag
        self.assertEqual(sorted(set(lag)), [f"v0.9.0-dev.{n}" for n in range(1, 8)])
        for release in HISTORY["upstream"]["tiktok-patches"]:
            assets = [{"name": f} for f in release["files"]]
            want = release["tag"].lstrip("v")
            self.assertEqual(matrix._bundle_of({"tag_name": release["tag"], "assets": assets}), want)
            self.assertEqual(release_check._file_version({"tag_name": release["tag"], "assets": assets}), want)
            self.assertEqual(prebuilts._get_target_asset(assets, "mpp", "s", release["tag"])["name"], f"patches-{want}.mpp")

    # P-HIS-03
    def test_P_HIS_03_every_real_bundle_moves_the_update_version_up(self):
        for key in ("morphe-patches", "subs-patches", "tiktok-patches"):
            texts = []
            for release in HISTORY["upstream"][key]:
                version = release["tag"].lstrip("v")
                # a dev channel takes every release of its source; finals count as the channel's top
                build = {"version": "1.0", "tag": "t", "prerelease": True, "patches": [{"file": f"o/patches-{version}.mpp", "version": version}]}
                texts.append(tuple(int(n) for n in re.findall(r"\d+", gen_site.build_version(build))))
            self.assertEqual(texts, sorted(texts), key)
            self.assertEqual(len(texts), len(set(texts)), key)

    # P-HIS-04
    def test_P_HIS_04_the_formats_seen_are_the_formats_known(self):
        formats = {re.sub(r"\d+", "N", r["tag"]) for seq in HISTORY["upstream"].values() for r in seq}
        self.assertEqual(formats, {"vN.N.N", "vN.N.N-dev.N"}, "a new upstream format: add its cases here and in docs/flow-map/version-formats.md")
        apps = {re.sub(r"\d+", "N", APK_RE.match(a["name"])["version"]) for r in OURS for a in r["assets"] if APK_RE.match(a["name"])}
        self.assertEqual(apps, {"N.N.N", "N.N.N-BETA"}, "a new app version format")


class Offers(unittest.TestCase):
    """What a phone would have been offered after each real release."""

    # P-HIS-05
    def test_P_HIS_05_after_every_real_release_the_right_build_is_offered(self):
        for count in range(1, len(OURS) + 1):
            so_far = OURS[:count]
            apps = gen_site.collect(so_far)
            for app_id, app in apps.items():
                build = app["builds"][0]
                # by hand: the newest release holding this app, and the best version in it
                config = gen_site.app_config()
                holding = [r for r in so_far if any((p := gen_site.split_asset(a["name"], config)) and (config.get(p[0]) or {"id": ""})["id"] == app_id for a in r["assets"])]
                if not holding:  # an app name from before the rename
                    continue
                newest = max(holding, key=lambda r: r["published_at"])
                names = [gen_site.split_asset(a["name"], config) for a in newest["assets"]]
                versions = [p[1] for p in names if p and (config.get(p[0]) or {"id": ""})["id"] == app_id]
                self.assertEqual(build["tag"], newest["tag_name"], f"{app_id} after {so_far[-1]['tag_name']}")
                self.assertEqual(build["version"], max(versions, key=order), f"{app_id} after {so_far[-1]['tag_name']}")

    # P-HIS-06
    def test_P_HIS_06_every_real_change_reaches_a_phone_through_obtainx(self):
        missing, wrong = [], []
        for installed, offered, app_id in history_replay.transitions(OURS):
            answer = HISTORY["obtainx"].get(f"{installed}|{offered}")
            if answer is None:
                missing.append((installed, offered))
            elif answer != "older":
                wrong.append((app_id, installed, offered, answer))
        self.assertEqual(missing, [], "a new version text: re-run tools/history_replay.py through ObtainX")
        self.assertEqual(wrong, [])
        self.assertGreater(len(history_replay.transitions(OURS)), 90)

    # P-HIS-07
    def test_P_HIS_07_rebuilds_with_nothing_new_are_not_offered(self):
        self.assertEqual(HISTORY["obtainx"]["21.30.216-2.0.0|21.30.216-2.0.0"], "same")
        self.assertEqual(prebuilts.get_highest_ver(["v2.1.0-dev.20", "v2.1.0"]), "v2.1.0")
        apps = gen_site.collect(OURS)
        for app_id in apps:
            rows = history_replay.offers(OURS)[app_id]
            texts = [r["text"] for r in rows]
            self.assertEqual(len(texts), len(set(texts)), f"{app_id}: a text came back after moving on")

    # P-HIS-08
    def test_P_HIS_08_the_formats_that_broke_or_could_break_stay_right_in_obtainx(self):
        for installed, offered in history_replay.EXTRA_PAIRS:
            self.assertEqual(HISTORY["obtainx"][f"{installed}|{offered}"], "older", f"{installed} -> {offered}")

    # P-HIS-09
    def test_P_HIS_09_where_things_stand_now(self):
        latest = {k: (a["builds"][0]["version"], gen_site.build_version(a["builds"][0])) for k, a in gen_site.collect(OURS).items()}
        self.assertEqual(latest["stremio-phone"][0], "2.5.1")
        self.assertEqual(latest["stremio-tv"], ("1.12.1", "1.12.1-0.6.0"))
        self.assertEqual(latest["stremio-tv-replace"], ("1.12.1", "1.12.1-0.6.0"))
        self.assertEqual(latest["reddit-experimental"][1], "2026.42.0-2.1.0.6")
        code = HISTORY["apks"]["26.11.02-morphe-dev/youtube-experimental-morphe-dev-v21.44.528-all.apk"]["versionCode"]
        self.assertEqual(code, "2147483647", "above every real YouTube build, so a phone holding any of them can update")


class Apks(unittest.TestCase):
    """The real files behind those offers: 117 APKs read with their real manifests."""

    def named(self):
        for release in OURS:
            for asset in release["assets"]:
                facts = HISTORY["apks"][f"{release['tag_name']}/{asset['name']}"]
                match = APK_RE.match(asset["name"])
                if match:
                    yield release, asset, facts, match

    # P-HIS-10
    def test_P_HIS_10_the_number_shown_is_the_number_inside(self):
        labels = set()
        for _release, asset, facts, match in self.named():
            self.assertTrue(verify_apk.version_matches(facts["versionName"], match["version"]), asset["name"])
            if facts["versionName"] != match["version"]:
                labels.add(facts["versionName"])
        self.assertEqual(labels, {"21.41.525-EXTENDED"}, "real builds whose app shows a store label: the check must not reject them")

    # P-HIS-11
    def test_P_HIS_11_every_real_apk_has_one_key_and_a_stable_package(self):
        config = gen_site.app_config()
        packages = {}
        for _release, asset, facts, match in self.named():
            self.assertEqual(facts["signer"], CERT, asset["name"])
            app_id = (config.get(gen_site.split_asset(asset["name"], config)[0]) or {"id": match["stem"]})["id"]
            packages.setdefault(app_id, set()).add(facts["package"])
        for app_id, found in packages.items():
            self.assertEqual(len(found), 1, f"{app_id}: {found}")

    # P-HIS-12
    def test_P_HIS_12_the_real_cpu_is_the_named_cpu(self):
        for _release, asset, facts, match in self.named():
            if match["arch"] != "all":
                self.assertIn(match["arch"], facts["abis"], asset["name"])

    # P-HIS-13
    def test_P_HIS_13_builds_below_the_highest_version_code_are_the_known_ones_and_are_refused(self):
        seen, drops = {}, set()
        for release, _asset, facts, match in self.named():
            code = int(facts["versionCode"])
            last = seen.get(match["stem"])
            if last and code < last[1]:
                drops.add(release["tag_name"])
                # the real file, through the real check, with what was really shipped before it
                with tempfile.TemporaryDirectory() as folder:
                    apk = Path(folder) / "x.apk"
                    with zipfile.ZipFile(apk, "w") as zf:
                        zf.writestr("AndroidManifest.xml", coded_manifest(facts["package"], facts["versionName"], code))
                    with mock.patch.object(verify_apk, "shipped_code", return_value=last[1]):
                        self.assertIn("Android would refuse", verify_apk.lower_code(apk, match["stem"], "o/r", "t", set()))
            seen[match["stem"]] = (release["tag_name"], max(code, last[1]) if last else code)
        self.assertEqual(drops, REAL_CODE_DROPS)

    # P-HIS-14
    def test_P_HIS_14_every_real_asset_name_finds_its_app(self):
        config = gen_site.app_config()
        for release in OURS:
            for asset in release["assets"]:
                parts = gen_site.split_asset(asset["name"], config)
                if asset["name"].startswith("reddit-login"):
                    self.assertIsNone(parts, "the helper APK is not an update of anything")
                else:
                    self.assertIsNotNone(parts, asset["name"])


class ThePages(unittest.TestCase):
    """The real final state through the whole generator: latest.json, obtainium.json and every update page."""

    # P-HIS-20
    def test_P_HIS_20_every_real_app_gets_the_right_files(self):
        facts = HISTORY["apks"]

        def fact(url, key):
            return facts["/".join(url.rsplit("/", 2)[1:])][key]

        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "_site"
            with mock.patch.object(gen_site, "OUT_DIR", out), mock.patch.object(gen_site, "build_state", return_value=("idle", "")), \
                    mock.patch.object(gen_site, "fetch_releases", return_value=OURS), mock.patch.object(gen_site, "fetch_live", return_value={}), \
                    mock.patch.object(gen_site, "package_of", side_effect=lambda url: fact(url, "package")), \
                    mock.patch.object(gen_site, "signer_of", side_effect=lambda url: fact(url, "signer")), \
                    mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": CERT}), redirect_stdout(_StringIO()):
                self.assertEqual(gen_site.main(), 0)
            latest = json.loads((out / "api/latest.json").read_text(encoding="utf-8"))["apps"]
            entries = {e["app"]: e for e in json.loads((out / "api/obtainium.json").read_text(encoding="utf-8"))["apps"]}
            self.assertEqual(set(entries), set(latest))
            for app_id, entry in entries.items():
                page = (out / entry["page"]).read_text(encoding="utf-8")
                self.assertEqual(re.findall(r'href="([^"]+\.apk)"', page), [entry["apk"]], app_id)
                self.assertIn(f'content="{entry["build_version"]}"', page, app_id)
                self.assertTrue(entry["build_version"].startswith(latest[app_id]["version"] + "-"), app_id)
                self.assertEqual(entry["package"], fact(entry["apk"], "package"), app_id)
                self.assertTrue(verify_apk.version_matches(fact(entry["apk"], "versionName"), latest[app_id]["version"]), app_id)
                self.assertIn(f"-v{latest[app_id]['version']}-", entry["apk"], app_id)
            self.assertEqual(entries["stremio-phone"]["build_version"], "2.5.1-0.6.0")
            self.assertEqual(entries["stremio-tv"]["build_version"], "1.12.1-0.6.0")

    # P-HIS-21
    def test_P_HIS_21_what_is_not_an_update_is_known(self):
        for installed, offered in history_replay.NOT_UPDATES:
            self.assertNotEqual(HISTORY["obtainx"][f"{installed}|{offered}"], "older", f"{installed} -> {offered}")
        self.assertEqual(HISTORY["obtainx"]["21.44.528-2.1.0.6|21.44.528-BETA-2.1.0.7"], "newer")

    # P-HIS-22
    def test_P_HIS_22_the_real_notes_with_each_apks_bundles_are_read(self):
        recent = {r["tag_name"]: r for r in OURS if "<!-- patches:" in r["body"]}
        self.assertLessEqual({"26.11.02-subs", "26.11.02-morphe-dev"}, set(recent))
        apps = gen_site.collect([recent["26.11.02-subs"]])
        replacement = apps["stremio-tv-replace"]["builds"][0]["patches"]
        self.assertEqual([p["file"] for p in replacement], ["Qutaiba-Khader/patches-0.6.0.mpp"], "this APK has no Morphe bundle, unlike the clones")
        clone = apps["stremio-tv"]["builds"][0]["patches"]
        self.assertEqual([p["version"] for p in clone], ["0.6.0", "2.0.0"], "its own bundle first")


class SameDay(unittest.TestCase):
    """The real same-day rebuild that started this: 26.11.02-subs held both versions."""

    NAMES = ["stremio-phone-clone-subs-v2.5.0-arm64-v8a.apk", "stremio-phone-clone-subs-v2.5.1-arm64-v8a.apk",
             "stremio-tv-clone-subs-v1.12.0-armeabi-v7a.apk", "stremio-tv-clone-subs-v1.12.1-armeabi-v7a.apk",
             "stremio-tv-replacement-subs-v1.12.0-armeabi-v7a.apk", "stremio-tv-replacement-subs-v1.12.1-armeabi-v7a.apk"]

    def release(self):
        body = "> ⚙️ » Patches: `MorpheApp/patches-2.0.0.mpp`\n> ⚙️ » Patches: `Qutaiba-Khader/patches-0.6.0.mpp`\n"
        return {"tag_name": "26.11.02-subs", "published_at": "2026-11-02T20:11:16Z", "prerelease": False, "html_url": "", "body": body,
                "assets": [{"name": n, "size": 73_000_000, "state": "uploaded", "browser_download_url": f"https://x/{n}", "id": i} for i, n in enumerate(self.NAMES)]}

    # P-HIS-15
    def test_P_HIS_15_the_real_case_offers_the_new_versions_and_removes_the_old(self):
        rel = self.release()
        apps = gen_site.collect([rel])
        self.assertEqual(gen_site.build_version(apps["stremio-phone"]["builds"][0]), "2.5.1-0.6.0")
        self.assertEqual(gen_site.build_version(apps["stremio-tv"]["builds"][0]), "1.12.1-0.6.0")
        self.assertEqual(gen_site.build_version(apps["stremio-tv-replace"]["builds"][0]), "1.12.1-0.6.0")
        doomed = sorted(a["name"] for a in gen_site.superseded(rel, gen_site.app_config()))
        self.assertEqual(doomed, sorted(self.NAMES[0::2]))

    # P-HIS-16
    def test_P_HIS_16_a_beta_and_its_final_in_one_release(self):
        names = ["youtube-experimental-morphe-dev-v21.44.528-BETA-all.apk", "youtube-experimental-morphe-dev-v21.44.528-all.apk"]
        rel = {"tag_name": "t-morphe-dev", "published_at": "2026-11-01T00:00:00Z", "prerelease": True, "html_url": "", "body": "",
               "assets": [{"name": n, "size": 90_000_000, "state": "uploaded", "browser_download_url": f"https://x/{n}"} for n in names]}
        self.assertEqual(gen_site.collect([rel])["youtube-experimental"]["builds"][0]["version"], "21.44.528")


class Feed(unittest.TestCase):
    """Stremio's download feed as really published, from web.archive.org snapshots."""

    def snapshots(self):
        self.assertGreater(len(HISTORY["feed"]), 15)
        return HISTORY["feed"]

    def scraper(self, snapshot):
        entries = [{"id": k, "kind": "android", "value": v} for k, v in snapshot.items() if k != "ts"]
        net = mock.MagicMock()
        net.get.return_value = json.dumps({"entries": entries})
        return StremioScraper(net)

    # P-HIS-17
    def test_P_HIS_17_every_archived_version_is_read_as_published(self):
        for snapshot in self.snapshots():
            scraper = self.scraper(snapshot)
            for entry_id in ("android", "android_tv", "android_beta", "android_tv_beta"):
                if entry_id in snapshot:
                    meta = scraper.fetch_metadata(f"https://api.strem.io/downloads/config#{entry_id}")
                    self.assertEqual(meta.versions, [snapshot[entry_id]["versionName"]], snapshot["ts"])

    # P-HIS-18
    def test_P_HIS_18_the_versions_only_go_up_in_the_channels_we_follow(self):
        for entry_id in ("android", "android_tv"):
            seen = [s[entry_id]["versionName"] for s in self.snapshots() if entry_id in s]
            distinct = list(dict.fromkeys(seen))
            drops = [(a, b) for a, b in zip(distinct, distinct[1:]) if order(b) < order(a)]
            self.assertEqual(drops, [], f"{entry_id}: a real rollback, see docs/flow-map/version-formats.md")

    # P-HIS-19
    def test_P_HIS_19_a_new_feed_version_starts_a_build_and_a_built_one_does_not(self):
        app = mock.MagicMock(dl_urls={"stremio": "https://api.strem.io/downloads/config#android_tv"}, app_name="Stremio TV Clone", brand="subs", table="Stremio-TV")
        latest_tv = self.snapshots()[-1]["android_tv"]["versionName"]
        for version, carried in (("1.12.1", True), ("1.12.2", False), (latest_tv, latest_tv in ("1.11.3", "1.12.0", "1.12.1"))):
            net = mock.MagicMock(gh_headers={})
            value = {"versionName": version, "tag": f"v{version}", "versionCode": {"arm": "1"}}
            feed = json.dumps({"entries": [{"id": "android_tv", "kind": "android", "value": value}]})
            net.get.side_effect = lambda url, headers=None, feed=feed: feed if "strem.io" in url else json.dumps(OURS)
            with mock.patch.object(matrix, "epr"):
                self.assertEqual(matrix._stremio_needs_build("x/y", "subs", [app], net), not carried, version)


if __name__ == "__main__":
    unittest.main()
