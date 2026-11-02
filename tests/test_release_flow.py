"""The build -> release -> update offer flow, on fixed inputs with no network.

Each test name carries the ID of its row in docs/flow-map/main.md. Run with
`python -m unittest discover -s tests` from the repository root.
"""
from __future__ import annotations

import http.client
import io
import json
import os
import struct
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
os.environ.setdefault("GITHUB_REPOSITORY", "owner/repo")
os.environ.setdefault("GITHUB_TOKEN", "test")

import apk_package  # noqa: E402
import gen_site  # noqa: E402
import prune_release  # noqa: E402
import release_check  # noqa: E402
import verify_apk  # noqa: E402

from src.core import builder, patcher, prebuilts  # noqa: E402
from src.core.config import AppEntry  # noqa: E402
from src.core.prebuilts import get_highest_ver  # noqa: E402
from src.scripts import matrix  # noqa: E402

BIG = 80_000_000
SUBS_NOTES = ("> ⚙️ » CLI: `MorpheApp/morphe-desktop-1.20.0-all.jar`\n\n"
              "> ⚙️ » Patches: `MorpheApp/patches-2.0.0.mpp`\n\n"
              "> ⚙️ » Patches: `Qutaiba-Khader/patches-0.6.0.mpp`\n")
DL = "https://github.com/owner/repo/releases/download"


def asset(name, tag="26.11.02-subs", size=BIG, **kw):
    return {"id": abs(hash(name)) % 10_000, "name": name, "size": size, "state": "uploaded", "digest": "sha256:ab",
            "download_count": 0, "browser_download_url": f"{DL}/{tag}/{name}", **kw}


def release(tag, names, published="2026-11-02T20:11:16Z", body=SUBS_NOTES, **kw):
    return {"tag_name": tag, "published_at": published, "body": body, "html_url": "u", "prerelease": False,
            "assets": [asset(n, tag) if isinstance(n, str) else n for n in names], **kw}


PHONE_OLD = "stremio-phone-clone-subs-v2.5.0-arm64-v8a.apk"
PHONE_NEW = "stremio-phone-clone-subs-v2.5.1-arm64-v8a.apk"
TV_OLD = "stremio-tv-clone-subs-v1.12.0-armeabi-v7a.apk"
TV_NEW = "stremio-tv-clone-subs-v1.12.1-armeabi-v7a.apk"


class Site(unittest.TestCase):
    """What the site chooses to offer."""

    def setUp(self):
        self.config = gen_site.app_config()
    # P-REL-01
    def test_P_REL_01_same_day_rebuild_offers_the_highest_version(self):
        apps = gen_site.collect([release("26.11.02-subs", [PHONE_OLD, PHONE_NEW, TV_OLD, TV_NEW])])
        self.assertEqual(apps["stremio-phone"]["builds"][0]["version"], "2.5.1")
        self.assertEqual(apps["stremio-tv"]["builds"][0]["version"], "1.12.1")
        self.assertEqual([b["version"] for b in apps["stremio-phone"]["builds"]], ["2.5.1"], "the replaced APK is not listed")
    # P-REL-02
    def test_P_REL_02_a_newer_release_wins_over_an_older_one(self):
        apps = gen_site.collect([
            release("26.10.28-subs", [TV_NEW], published="2026-10-28T10:00:00Z"),
            release("26.11.02-subs", [TV_OLD], published="2026-11-02T10:00:00Z"),
        ])
        self.assertEqual(apps["stremio-tv"]["builds"][0]["tag"], "26.11.02-subs")
    # P-REL-03
    def test_P_REL_03_a_pin_wins_over_a_higher_version(self):
        config = {k: {**v, "pin": "1.12.0"} if v["id"] == "stremio-tv" else v for k, v in self.config.items()}
        rel = release("26.11.02-subs", [TV_OLD, TV_NEW])
        with mock.patch.object(gen_site, "app_config", return_value=config):
            apps = gen_site.collect([rel])
        self.assertEqual(apps["stremio-tv"]["builds"][0]["version"], "1.12.0")
        self.assertEqual([a["name"] for a in gen_site.superseded(rel, config)], [TV_NEW])
    # P-REL-04
    def test_P_REL_04_update_version_uses_the_apps_own_bundle(self):
        build = gen_site.collect([release("26.11.02-subs", [TV_NEW])])["stremio-tv"]["builds"][0]
        self.assertEqual(gen_site.build_version(build), "1.12.1-0.6.0")
    # P-REL-05
    def test_P_REL_05_update_versions_keep_their_order(self):
        def version(patch, prerelease=False):
            return gen_site.build_version({"version": "21.44.528", "tag": "t", "prerelease": prerelease,
                                           "patches": [{"file": f"M/patches-{patch}.mpp", "version": patch}]})
        self.assertEqual(version("2.0.0"), "21.44.528-2.0.0")
        self.assertEqual(version("2.1.0-dev.6", True), "21.44.528-2.1.0.6")
        self.assertEqual(version("2.1.0", True), "21.44.528-2.1.0.9999")
        self.assertEqual(version("2.1.0-rc.1", True), "21.44.528-2.1.0.4001", "above dev.16, below the final")
        self.assertEqual(version("2.1.0-beta", True), "21.44.528-2.1.0.3000")
    # P-REL-06
    def test_P_REL_06_no_bundle_in_the_notes_ranks_lowest(self):
        self.assertEqual(gen_site.build_version({"version": "1.0", "tag": "26.11.02-subs", "patches": []}), "1.0-0")
    # P-REL-07
    def test_P_REL_07_an_incomplete_replacement_replaces_nothing(self):
        rel = release("t", [asset(PHONE_OLD), asset(PHONE_NEW, state="starter")])
        self.assertEqual(gen_site.superseded(rel, self.config), [])
        rel = release("t", [asset(PHONE_OLD), asset(PHONE_NEW, size=100)])
        self.assertEqual(gen_site.superseded(rel, self.config), [])
    # P-REL-08
    def test_P_REL_08_api_reads_retry_a_cut_off_answer_only(self):
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"ok": 1}'
        with mock.patch.object(gen_site.time, "sleep"), mock.patch.object(
                gen_site.urllib.request, "urlopen", side_effect=[http.client.IncompleteRead(b""), ok]):
            self.assertEqual(gen_site._get(gen_site.API + "/x"), {"ok": 1})
        missing = urllib.error.HTTPError("u", 404, "no", {}, None)
        with mock.patch.object(gen_site.urllib.request, "urlopen", side_effect=missing) as call:
            with self.assertRaises(urllib.error.HTTPError):
                gen_site._get(gen_site.API + "/x")
        self.assertEqual(call.call_count, 1, "a 404 is an answer, not a hiccup")
        with mock.patch.object(gen_site.time, "sleep"), mock.patch.object(
                gen_site.urllib.request, "urlopen", side_effect=http.client.IncompleteRead(b"")) as call:
            with self.assertRaises(http.client.HTTPException):
                gen_site._get(gen_site.API + "/x")
        self.assertEqual(call.call_count, 3)
    # P-REL-92
    def test_P_REL_92_an_apk_still_uploading_is_not_offered(self):
        rel = release("t", [asset(PHONE_OLD), asset(PHONE_NEW, state="starter")])
        self.assertEqual([b["version"] for b in gen_site.collect([rel])["stremio-phone"]["builds"]], ["2.5.0"])
    # P-REL-93
    def test_P_REL_93_architectures_are_ordered_by_version(self):
        other = "stremio-phone-clone-subs-v2.5.1-armeabi-v7a.apk"
        rel = release("t", [PHONE_OLD, other])
        self.assertEqual([b["version"] for b in gen_site.collect([rel])["stremio-phone"]["builds"]], ["2.5.1", "2.5.0"])


class Workflows(unittest.TestCase):
    """What no unit test runs: the steps must at least be there, in order."""

    def text(self, name):
        return (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    # P-REL-100
    def test_P_REL_100_nothing_uploads_before_the_check(self):
        build = self.text("build.yml")
        self.assertLess(build.index("name: Build APKs\n        env"), build.index("name: Verify APKs"))
        self.assertLess(build.index("name: Verify APKs"), build.index("name: Upload APKs to release"))
        self.assertIn("build/.verified", build)
        self.assertIn(verify_apk.VERIFIED_MARK, build)
    # P-REL-101
    def test_P_REL_101_a_rebuild_never_drafts_a_published_release(self):
        build = self.text("build.yml")
        self.assertNotIn("--draft --repo", build.split("gh release create")[0])
        self.assertIn("concurrency:", build)
        self.assertLess(build.index("--draft=false --title"), build.rindex('startswith("build-")) | .apiUrl'), "logs go only after the release is finalized")
    # P-REL-102
    def test_P_REL_102_a_crashed_check_cannot_look_like_nothing_new(self):
        ci = self.text("ci.yml")
        self.assertNotIn('echo "build_matrix=$(uv run', ci)
        self.assertIn("jq -e", ci)
    # P-REL-103
    def test_P_REL_103_the_site_prunes_after_publishing_and_health_keeps_its_state(self):
        site, health = self.text("site.yml"), self.text("health.yml")
        self.assertLess(site.index("name: Publish to gh-pages"), site.index("prune_release.py"))
        self.assertIn("release_check.py", health)
        self.assertIn("if: always()", health.split("name: Keep the state")[1])
        self.assertIn("git push origin health", health)


class Review(unittest.TestCase):
    """Wrong answers an independent review found."""
    # P-REL-107
    def test_P_REL_107_a_straddled_build_is_labelled_with_the_lower_bundle(self):
        # releases from before each APK recorded its own bundles
        notes = ("> ⚙️ » Patches: `MorpheApp/patches-2.1.0-dev.7.mpp`\n> ⚙️ » Patches: `MorpheApp/patches-2.1.0-dev.6.mpp`\n")
        name = "youtube-experimental-morphe-dev-v21.44.528-all.apk"
        build = gen_site.collect([release("t-morphe-dev", [name], body=notes, prerelease=True)])["youtube-experimental"]["builds"][0]
        self.assertEqual(gen_site.build_version(build), "21.44.528-2.1.0.6", "the real dev.7 rebuild must still show as newer")
    # P-REL-108
    def test_P_REL_108_a_pin_wins_over_a_newer_release_and_a_missing_pin_is_reported(self):
        config = {k: {**v, "pin": "1.12.0"} if v["id"] == "stremio-tv" else v for k, v in gen_site.app_config().items()}
        rels = [release("old-subs", [TV_OLD], published="2026-10-01T00:00:00Z"), release("new-subs", [TV_NEW], published="2026-11-01T00:00:00Z")]
        with mock.patch.object(gen_site, "app_config", return_value=config):
            self.assertEqual(gen_site.collect(rels)["stremio-tv"]["builds"][0]["version"], "1.12.0")
        pinned = [{**APPS[0], "pin": "1.11.3"}]
        self.assertIn("pin-not-offered:stremio-tv", release_check.check_offers(pinned, world()))
    # P-REL-109
    def test_P_REL_109_a_final_version_beats_its_beta(self):
        self.assertGreater(gen_site.version_key("2.2.0"), gen_site.version_key("2.2.0-beta.5"))
        self.assertGreater(gen_site.version_key("2.5.10"), gen_site.version_key("2.5.9"))
    # P-REL-110
    def test_P_REL_110_what_was_shipped_reads_past_a_hyphenated_cpu_name(self):
        app = entry(name="Stremio Phone Clone")
        rel = release("a", [PHONE_NEW])
        self.assertEqual(builder._last_shipped(app, Net({"releases": [rel]})), "2.5.1")
    # P-REL-111
    def test_P_REL_111_a_patch_only_rebuild_the_site_missed_is_stale(self):
        data = world()
        data["obtainium"]["apps"][0]["build_version"] = "1.12.1-0.5.0"
        data["pages"]["stremio-tv"] = data["pages"]["stremio-tv"].replace("1.12.1-0.6.0", "1.12.1-0.5.0")
        self.assertIn("offered-stale:stremio-tv", release_check.check_offers(APPS, data))
    # P-REL-112
    def test_P_REL_112_notes_without_its_own_bundle_are_reported(self):
        data = world()
        data["latest"]["apps"]["stremio-tv"]["patches"] = [{"file": "Other/patches-1.mpp", "version": "1"}]
        self.assertIn("no-bundle:stremio-tv", release_check.check_upstream(APPS, data))
    # P-REL-113
    def test_P_REL_113_a_tiny_asset_is_not_offered(self):
        rel = release("t", [asset(PHONE_NEW, size=100)])
        self.assertNotIn("stremio-phone", gen_site.collect([rel]))


class OwnBundles(unittest.TestCase):
    """Each APK's line of the notes says which bundles it has."""
    # P-REL-114
    def test_P_REL_114_a_straddled_build_shows_each_apks_own_bundle(self):
        yt, rd = "youtube-experimental-morphe-dev-v21.44.528-all.apk", "reddit-experimental-morphe-dev-v2026.42.0-all.apk"
        notes = (f"- 🟢 » YT: [`21.44.528`]({DL}/t/{yt}) <!-- patches: MorpheApp/patches-2.1.0-dev.6.mpp -->\n"
                 f"- 🟢 » RD: [`2026.42.0`]({DL}/t/{rd}) <!-- patches: MorpheApp/patches-2.1.0-dev.7.mpp -->\n")
        apps = gen_site.collect([release("t-morphe-dev", [yt, rd], body=notes, prerelease=True)])
        self.assertEqual(gen_site.build_version(apps["youtube-experimental"]["builds"][0]), "21.44.528-2.1.0.6")
        self.assertEqual(gen_site.build_version(apps["reddit-experimental"]["builds"][0]), "2026.42.0-2.1.0.7")
    # P-REL-115
    def test_P_REL_115_the_check_reads_the_apks_own_line(self):
        ok = f"- 🟢 » TV: [`1.12.1`]({DL}/t/{TV_NEW}) <!-- patches: Qutaiba-Khader/patches-0.7.0.mpp,MorpheApp/patches-2.0.0.mpp -->\n> ⚙️ » Patches: `Qutaiba-Khader/patches-0.6.0.mpp`"
        rel = release("t-subs", [TV_NEW], body=ok)
        source = "github:Qutaiba-Khader/stremio-subs-patches"
        self.assertEqual(matrix._apps_behind("subs", [entry()], source, "0.7.0", [rel]), [], "its own line beats the release's list")
        self.assertEqual(matrix._apps_behind("subs", [entry()], source, "0.8.0", [rel]), ["Stremio-TV"])
    # P-REL-116
    def test_P_REL_116_the_build_line_records_the_bundles(self):
        app = entry()
        cli = mock.MagicMock()
        cli.mpp_map = {("github:Qutaiba-Khader/stremio-subs-patches", "latest"): Path("t/patches-0.6.0.mpp"), ("github:MorpheApp/morphe-patches", "latest"): Path("t/patches-2.0.0.mpp")}
        self.assertEqual(builder._bundles_comment(app, cli), " <!-- patches: Qutaiba-Khader/patches-0.6.0.mpp,MorpheApp/patches-2.0.0.mpp -->")
        cli.mpp_map = {}
        self.assertEqual(builder._bundles_comment(app, cli), "")


class Downgrade(unittest.TestCase):
    """A build Android would refuse to install over the last one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def apk(self, code):
        path = Path(self.tmp.name) / TV_NEW
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("AndroidManifest.xml", coded_manifest("com.stremio.one.subs", "1.12.1", code))
        return path
    # P-REL-120
    def test_P_REL_120_a_lower_code_is_refused_and_a_pin_or_higher_code_is_not(self):
        with mock.patch.object(verify_apk, "shipped_code", return_value=100):
            self.assertIn("Android would refuse", verify_apk.lower_code(self.apk(99), "s", "o/r", "t", set()))
            self.assertEqual(verify_apk.lower_code(self.apk(100), "s", "o/r", "t", set()), "")
            self.assertEqual(verify_apk.lower_code(self.apk(99), "s", "o/r", "t", {"s"}), "", "a pin backs out on purpose")
            self.assertEqual(verify_apk.lower_code(self.apk(99), "s", "", "", set()), "", "no token: a local run")
        with mock.patch.object(verify_apk, "shipped_code", return_value=None):
            self.assertEqual(verify_apk.lower_code(self.apk(99), "s", "o/r", "t", set()), "", "unknown: Health is the backstop")
    # P-REL-121
    def test_P_REL_121_the_bar_is_the_highest_code_ever_shipped(self):
        rels = [{"tag_name": "a", "assets": [{"name": "s-v1-all.apk", "browser_download_url": "old"}, {"name": "x.apk", "browser_download_url": "no"}]},
                {"tag_name": "b", "assets": [{"name": "s-v2-all.apk", "browser_download_url": "new"}]}]
        codes = {"old": coded_manifest("p", "1", 77), "new": coded_manifest("p", "2", 55)}
        with mock.patch.object(gen_site, "fetch_releases", return_value=rels), \
                mock.patch.object(verify_apk, "manifest_from_url", side_effect=lambda url: codes[url]):
            self.assertEqual(verify_apk.shipped_code("s", "o/r"), 77, "a phone can hold the old build")
            self.assertIsNone(verify_apk.shipped_code("nothing", "o/r"))
        with mock.patch.object(gen_site, "fetch_releases", side_effect=OSError("down")), redirect_stdout(io.StringIO()):
            self.assertIsNone(verify_apk.shipped_code("s", "o/r"))
    # P-REL-122
    def test_P_REL_122_the_whole_check_deletes_a_lower_code_build(self):
        good = make_apk(self.tmp.name, TV_NEW)
        with mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "", "GITHUB_ACTIONS": "", "GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"}), \
                mock.patch.object(verify_apk, "lower_code", return_value="lower") as check, redirect_stdout(io.StringIO()):
            self.assertEqual(verify_apk.main([str(good)]), 1)
        check.assert_called_once()
        self.assertFalse(good.exists())
        self.assertEqual(verify_apk.pinned_stems(ROOT / "config.toml"), set(), "nothing is pinned today")


class Direction(unittest.TestCase):
    """An offer phones cannot take."""

    def data(self, version, text, code="100", highest=100, package="p"):
        return {"obtainium": {"apps": [{"app": "stremio-tv", "apk": "u", "version": version, "build_version": text, "package": package}]},
                "apks": {"u": {"code": code}}, "shipped_codes": {"stremio-tv": {"code": highest, "file": "f"}}}
    # P-REL-117
    def test_P_REL_117_a_lower_update_version_a_lower_code_or_a_new_package_is_reported(self):
        old = {"stremio-tv": {"text": "1.12.1-0.6.0", "version": "1.12.1", "package": "p"}}
        self.assertEqual(release_check.check_direction(APPS, self.data("1.12.1", "1.12.1-0.6.1"), old), {})
        self.assertIn("offer-backwards:stremio-tv", release_check.check_direction(APPS, self.data("1.12.0", "1.12.0-0.6.0"), old))
        self.assertIn("offer-downgrade:stremio-tv", release_check.check_direction(APPS, self.data("1.12.2", "1.12.2-0.6.0", "99"), {}), "the highest ever shipped, with no earlier state")
        self.assertIn("offer-package:stremio-tv", release_check.check_direction(APPS, self.data("1.12.1", "1.12.1-0.6.0", package="q"), old))
        self.assertEqual(release_check.check_direction([{**APPS[0], "pin": "1.12.0"}], self.data("1.12.0", "1.12.0-0.6.0", "99"), old), {}, "a pin is deliberate")
        self.assertEqual(release_check.check_direction(APPS, self.data("1.12.0", "1.12.0-0.6.0"), {}), {}, "nothing to compare with yet")
        beta_after_final = self.data("21.44.528-BETA", "21.44.528-BETA-2.1.0.7")
        was = {"stremio-tv": {"text": "21.44.528-2.1.0.6", "version": "21.44.528"}}
        self.assertIn("offer-backwards:stremio-tv", release_check.check_direction(APPS, beta_after_final, was), "real ObtainX answer: not an update")
    # P-REL-118
    def test_P_REL_118_a_backwards_offer_stays_flagged_until_it_is_back_above(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        Path(folder, "state.json").write_text(json.dumps({"offered": {"stremio-tv": {"text": "9.9.9-1", "version": "9.9.9"}}}), encoding="utf-8")
        data = world()
        data["obtainium"]["apps"][0]["version"] = "1.12.1"
        for _ in range(2):
            with mock.patch.dict(os.environ, {"HEALTH_DIR": folder}), mock.patch.object(release_check, "enabled_apps", return_value=APPS), \
                    mock.patch.object(release_check, "gather", return_value=(data, {})), mock.patch.object(gen_site, "build_state", return_value=("idle", "")), \
                    mock.patch.object(release_check, "check_runs", return_value={}), redirect_stdout(io.StringIO()):
                self.assertEqual(release_check.main(), 1)
        state = json.loads(Path(folder, "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["offered"]["stremio-tv"]["text"], "9.9.9-1")
    # P-REL-119
    def test_P_REL_119_a_changed_file_outside_the_sync_list_is_reported(self):
        self.assertIn("sync-unprotected:src/core/x.py", problems(world(ignore_sync="tools src/core/y.py", changed_from_upstream=["src/core/x.py", "tools/a.py", "src/core/y.py"])))
        self.assertEqual(problems(world(ignore_sync="tools", changed_from_upstream=["tools/a.py"])), {})
        self.assertEqual(problems(world(ignore_sync="", changed_from_upstream=["x"])), {}, "no list to compare with: the check is off, not wrong")

    # P-REL-127
    def test_P_REL_127_the_highest_code_of_each_app_is_read_from_every_file(self):
        rels = [{"assets": [{"name": TV_OLD, "browser_download_url": "a"}, {"name": TV_NEW, "browser_download_url": "b"}, {"name": PHONE_NEW, "browser_download_url": "c"}, {"name": "other.txt", "browser_download_url": "d"}]}]
        answers = {"a": coded_manifest("p", "1", 9), "b": coded_manifest("p", "2", 5)}

        def read(url):
            if url == "c":
                raise OSError("gone")
            return answers[url]

        with mock.patch.object(release_check, "manifest_from_url", side_effect=read):
            self.assertEqual(release_check.shipped_codes(rels), {"stremio-tv": {"code": 9, "file": TV_OLD}})
    # P-REL-128
    def test_P_REL_128_an_apk_with_no_line_in_notes_that_have_them_claims_no_bundle(self):
        notes = f"- 🟢 » Phone: [`2.5.1`]({DL}/t/{PHONE_NEW}) <!-- patches: Qutaiba-Khader/patches-0.7.0.mpp -->\n> ⚙️ » Patches: `Qutaiba-Khader/patches-0.7.0.mpp`"
        apps = gen_site.collect([release("t", [TV_NEW, PHONE_NEW], body=notes)])
        self.assertEqual(gen_site.build_version(apps["stremio-tv"]["builds"][0]), "1.12.1-0", "not 0.7.0: a real 0.7.0 build must still show as new")
        self.assertEqual(gen_site.build_version(apps["stremio-phone"]["builds"][0]), "2.5.1-0.7.0")
    # P-REL-129
    def test_P_REL_129_the_builder_and_both_checks_pick_the_same_file_of_a_two_file_release(self):
        cases = [(["patches-0.9.0-dev.6.mpp", "patches-0.9.0-dev.7.mpp"], "v0.9.0-dev.7", "0.9.0-dev.7"),
                 (["patches-0.9.0.mpp", "patches-0.9.1.mpp"], "v9", "0.9.1"),
                 (["patches-0.9.0-dev.7.mpp", "patches-0.9.0.mpp"], "v0.9.0", "0.9.0"),
                 (["patches-0.8.1.mpp", "patches-0.9.0-dev.1.mpp"], "v0.9.0-dev.1", "0.9.0-dev.1")]
        for names, tag, want in cases:
            assets = [{"name": n} for n in names]
            self.assertEqual(prebuilts._get_target_asset(assets, "mpp", "s", tag)["name"], f"patches-{want}.mpp")
            self.assertEqual(matrix._bundle_of({"tag_name": tag, "assets": assets}), want)
            self.assertEqual(release_check._file_version({"tag_name": tag, "assets": assets}), want)
        with self.assertRaises(prebuilts.PrebuiltsError):
            prebuilts._get_target_asset([{"name": "x.txt"}], "mpp", "s", "v1")


class Edges(unittest.TestCase):
    """Small paths of the readers."""
    # P-REL-123
    def test_P_REL_123_a_release_with_other_files_still_gives_the_bundle(self):
        rel = {"tag_name": "v3", "assets": [{"name": "readme.txt"}, {"name": "patches-2.mpp"}]}
        self.assertEqual(matrix._bundle_of(rel), "2")
        self.assertEqual(release_check._file_version(rel), "2")
    # P-REL-124
    def test_P_REL_124_a_typed_attribute_that_is_no_integer_is_skipped(self):
        data = coded_manifest("a.b", "1.2", 7, data_type=0x12)
        self.assertEqual(apk_package.manifest_attrs(data), {"package": "a.b", "versionName": "1.2"})
    # P-REL-125
    def test_P_REL_125_releases_are_read_page_by_page(self):
        pages = {1: [{"tag_name": "a"}, {"tag_name": "d", "draft": True}], 2: [{"tag_name": "b"}]}
        with mock.patch.object(gen_site, "_get", side_effect=lambda url: pages[int(url.rsplit("=", 1)[1])]):
            self.assertEqual([r["tag_name"] for r in gen_site.all_releases("o/r", page_size=2)], ["a", "d", "b"])
        full = [{"tag_name": "a"}, {"tag_name": "b"}]
        with mock.patch.object(gen_site, "all_releases", return_value=full + [{"tag_name": "d", "draft": True}]):
            self.assertEqual(gen_site.fetch_releases("o/r"), full)
        missing = urllib.error.HTTPError("u", 500, "no", {}, None)
        with mock.patch.object(gen_site, "_get", side_effect=[full, missing]), self.assertRaises(urllib.error.HTTPError):
            gen_site.all_releases("o/r", page_size=2)  # a partial list could drop an app from the site
    # P-REL-126
    def test_P_REL_126_a_pinned_table_is_recognised(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
            f.write('brand = "Morphe"\n[Stremio-TV]\napp-name = "Stremio TV Clone"\nbrand = "subs"\nstremio-dlurl = "https://x/c#android_tv@1.11.3:40000003"\n[Other]\nstremio-dlurl = "https://x/c#android"\n')
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(verify_apk.pinned_stems(Path(f.name)), {"stremio-tv-clone-subs"})


class StockCheck(unittest.TestCase):
    # P-REL-94
    def test_P_REL_94_every_enabled_app_has_a_stock_signature_to_check(self):
        known = {line.split()[-1] for line in (ROOT / "sig.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
        meta = gen_site.table_meta()
        missing = [k for k, v in meta.items() if v["enabled"] and v["stock_package"] not in known]
        self.assertEqual(missing, [], "without an entry a tampered stock APK would be patched and signed with our key")


class Prune(unittest.TestCase):
    """Removing the older APK of a same-day rebuild."""

    def run_main(self, live):
        rel = release("26.11.02-subs", [PHONE_OLD, PHONE_NEW])
        with mock.patch.object(gen_site, "fetch_releases", return_value=[rel]), \
                mock.patch.object(prune_release, "live_urls", side_effect=live), \
                mock.patch.object(prune_release, "delete_asset") as delete, \
                mock.patch.object(prune_release.time, "sleep"), redirect_stdout(io.StringIO()):
            self.assertEqual(prune_release.main([], wait_seconds=0), 0)
        return delete
    # P-REL-09
    def test_P_REL_09_removed_once_the_live_site_stopped_offering_it(self):
        self.run_main([{f"{DL}/26.11.02-subs/{PHONE_NEW}"}]).assert_called_once()
    # P-REL-10
    def test_P_REL_10_kept_while_the_live_site_still_offers_it(self):
        self.run_main([{f"{DL}/26.11.02-subs/{PHONE_OLD}"}]).assert_not_called()
    # P-REL-11
    def test_P_REL_11_waits_for_pages_to_deploy(self):
        rel = release("26.11.02-subs", [PHONE_OLD, PHONE_NEW])
        old, new = {f"{DL}/26.11.02-subs/{PHONE_OLD}"}, {f"{DL}/26.11.02-subs/{PHONE_NEW}"}
        with mock.patch.object(gen_site, "fetch_releases", return_value=[rel]), \
                mock.patch.object(prune_release, "live_urls", side_effect=[old, new]), \
                mock.patch.object(prune_release, "delete_asset") as delete, \
                mock.patch.object(prune_release.time, "sleep") as sleep, redirect_stdout(io.StringIO()):
            prune_release.main([], wait_seconds=60)
        sleep.assert_called_once()
        delete.assert_called_once()
    # P-REL-12
    def test_P_REL_12_nothing_superseded_touches_nothing(self):
        with mock.patch.object(gen_site, "fetch_releases", return_value=[release("t", [PHONE_NEW])]), \
                mock.patch.object(prune_release, "delete_asset") as delete, redirect_stdout(io.StringIO()):
            prune_release.main([])
        delete.assert_not_called()
    # P-REL-13
    def test_P_REL_13_a_rebuild_keeps_the_lines_of_apks_it_did_not_rebuild(self):
        old = (f"- 🟢 » TV: [`1.12.1`]({DL}/t/{TV_NEW}) <!-- patches: Q/patches-0.6.0.mpp -->\n"
               f"- 🟢 » Phone: [`2.5.0`]({DL}/t/{PHONE_OLD}) <!-- patches: Q/patches-0.6.0.mpp -->\n"
               "> ⚙️ » Patches: `Q/patches-0.6.0.mpp`")
        new = f"- 🟢 » Phone: [`2.5.1`]({DL}/t/{PHONE_NEW}) <!-- patches: Q/patches-0.7.0.mpp -->\n\n> ⚙️ » Patches: `Q/patches-0.7.0.mpp`\n"
        merged = prune_release.merged_notes(old, new, [TV_NEW, PHONE_NEW])
        self.assertIn(TV_NEW, merged)
        self.assertNotIn(PHONE_OLD, merged, "its APK is not in the release any more")
        self.assertIn("patches-0.6.0.mpp`", merged)
        self.assertEqual(merged.count(PHONE_NEW), 1)
        rel = release("t", [TV_NEW, PHONE_NEW], body=merged)
        apps = gen_site.collect([rel])
        self.assertEqual(gen_site.build_version(apps["stremio-tv"]["builds"][0]), "1.12.1-0.6.0", "the APK that was not rebuilt keeps its own bundle")
        self.assertEqual(prune_release.merged_notes("", new, [PHONE_NEW]), new, "a first build of the day")
    # P-REL-14
    def test_P_REL_14_the_build_job_entry_point_writes_the_merged_notes(self):
        rel = release("t", [TV_NEW], body=f"- 🟢 » TV: [`1.12.1`]({DL}/t/{TV_NEW}) <!-- patches: Q/patches-0.6.0.mpp -->")
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as notes:
            notes.write("> ⚙️ » Patches: `Q/patches-0.7.0.mpp`\n")
        self.addCleanup(os.unlink, notes.name)
        with mock.patch.object(gen_site, "_get", return_value=[rel]), redirect_stdout(io.StringIO()):
            self.assertEqual(prune_release.main(["--merge-notes", "t", notes.name]), 0)
        self.assertIn(TV_NEW, Path(notes.name).read_text(encoding="utf-8"))
        # a first build of the day has no earlier notes, and an unreadable list must not rewrite the notes blind
        with mock.patch.object(gen_site, "_get", return_value=[]), redirect_stdout(io.StringIO()):
            self.assertEqual(prune_release.main(["--merge-notes", "t", notes.name]), 0)
        with mock.patch.object(gen_site, "_get", side_effect=OSError("down")), self.assertRaises(OSError):
            prune_release.main(["--merge-notes", "t", notes.name])
    # P-REL-15
    def test_P_REL_15_delete_and_live_urls_use_the_real_endpoints(self):
        with mock.patch.object(prune_release.urllib.request, "urlopen") as call:
            prune_release.delete_asset("owner/repo", 7)
        req = call.call_args[0][0]
        self.assertEqual((req.get_method(), req.full_url), ("DELETE", gen_site.API + "/repos/owner/repo/releases/assets/7"))
        latest = {"apps": {"a": {"files": [{"url": "u1"}]}, "b": {}}}
        with mock.patch.object(gen_site, "_get", return_value=latest):
            self.assertEqual(prune_release.live_urls("https://x/"), {"u1"})


def manifest(**attrs):
    """A minimal binary AndroidManifest.xml with these string attributes on <manifest>."""
    strings = ["manifest", *[s for kv in attrs.items() for s in kv]]
    blob = b""
    offsets = []
    for text in strings:
        offsets.append(len(blob))
        raw = text.encode()
        blob += bytes([len(text), len(raw)]) + raw + b"\0"
    blob += b"\0" * (-len(blob) % 4)
    header = 28
    pool_size = header + 4 * len(strings) + len(blob)
    pool = struct.pack("<HHIIIIII", 1, header, pool_size, len(strings), 0, 1 << 8, header + 4 * len(strings), 0)
    pool += struct.pack(f"<{len(strings)}I", *offsets) + blob
    attr_bytes = b""
    for i, _ in enumerate(attrs):
        attr_bytes += struct.pack("<iiiI", -1, 1 + 2 * i, 2 + 2 * i, 0) + b"\0" * 4
    body = struct.pack("<iI", -1, 0) + struct.pack("<HHHHHH", 20, 20, len(attrs), 0, 0, 0) + attr_bytes
    element = struct.pack("<HHI", 0x0102, 16, 16 + len(body)) + b"\0" * 8 + body
    return struct.pack("<HHI", 3, 8, 8 + len(pool) + len(element)) + pool + element


def coded_manifest(package, version, code, data_type=0x10):
    """A manifest whose versionCode is a typed integer, as real ones have it."""
    strings = ["manifest", "package", package, "versionName", version, "versionCode"]
    blob, offsets = b"", []
    for text in strings:
        offsets.append(len(blob))
        raw = text.encode()
        blob += bytes([len(text), len(raw)]) + raw + b"\0"
    blob += b"\0" * (-len(blob) % 4)
    pool_size = 28 + 4 * len(strings) + len(blob)
    pool = struct.pack("<HHIIIIII", 1, 28, pool_size, len(strings), 0, 1 << 8, 28 + 4 * len(strings), 0)
    pool += struct.pack(f"<{len(strings)}I", *offsets) + blob
    attrs = struct.pack("<iiiI", -1, 1, 2, 0) + b"\0" * 4 + struct.pack("<iiiI", -1, 3, 4, 0) + b"\0" * 4
    attrs += struct.pack("<iii", -1, 5, -1) + struct.pack("<HBBI", 8, 0, data_type, code)
    body = struct.pack("<iI", -1, 0) + struct.pack("<HHHHHH", 20, 20, 3, 0, 0, 0) + attrs
    element = struct.pack("<HHI", 0x0102, 16, 16 + len(body)) + b"\0" * 8 + body
    return struct.pack("<HHI", 3, 8, 8 + len(pool) + len(element)) + pool + element


def make_apk(folder, name, version="1.12.1", package="com.stremio.one.subs", libs=("armeabi-v7a",),
             dex=b"Lapp/subsense/stremio/SubtitleRefresh;", pad=True):
    path = Path(folder) / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("AndroidManifest.xml", manifest(package=package, versionName=version))
        if dex is not None:
            zf.writestr("classes.dex", dex)
        for abi in libs:
            zf.writestr(f"lib/{abi}/libx.so", b"x")
        if pad:
            zf.writestr("padding", os.urandom(1_100_000))
    return path


class Verify(unittest.TestCase):
    """The check every APK passes before it can be released."""

    SOURCES = {"stremio-tv-clone-subs": ["Qutaiba-Khader/stremio-subs-patches"]}
    PACKAGES = {"stremio-tv-clone-subs": "com.stremio.one.subs"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def check(self, path, signer=""):
        return verify_apk.problems(path, self.SOURCES, signer, self.PACKAGES)
    # P-REL-16
    def test_P_REL_16_a_good_apk_passes(self):
        with mock.patch.object(verify_apk, "signer_of", return_value="good"):
            self.assertEqual(self.check(make_apk(self.tmp.name, TV_NEW), "good"), [])
    # P-REL-17
    def test_P_REL_17_the_version_inside_must_match_the_file_name(self):
        self.assertIn("the app says version 1.12.0", self.check(make_apk(self.tmp.name, TV_NEW, version="1.12.0"))[0])
        self.assertEqual(self.check(make_apk(self.tmp.name, TV_NEW, version="1.12.1-EXTENDED")), [], "a store's label, real on YouTube 21.41.525")
    # P-REL-18
    def test_P_REL_18_the_libraries_must_be_for_the_named_cpu(self):
        self.assertIn("libraries are for ['arm64-v8a']", self.check(make_apk(self.tmp.name, TV_NEW, libs=("arm64-v8a",)))[0])
        self.assertIn("nothing", self.check(make_apk(self.tmp.name, TV_NEW, libs=()))[0])
    # P-REL-19
    def test_P_REL_19_the_patch_must_be_in_the_app(self):
        self.assertIn("patch marker", self.check(make_apk(self.tmp.name, TV_NEW, dex=b"plain"))[0])
        self.assertIn("no dex files", self.check(make_apk(self.tmp.name, TV_NEW, dex=None))[0])
    # P-REL-20
    def test_P_REL_20_the_wrong_key_is_refused(self):
        apk = make_apk(self.tmp.name, TV_NEW)
        with mock.patch.object(verify_apk, "signer_of", return_value="other"):
            self.assertIn("phones cannot update", self.check(apk, "good")[0])
        with mock.patch.object(verify_apk, "signer_of", side_effect=LookupError("no block")):
            self.assertIn("cannot read the signature", self.check(apk, "good")[0])
    # P-REL-21
    def test_P_REL_21_the_package_must_be_the_configured_clone(self):
        self.assertIn("config.toml asks for", self.check(make_apk(self.tmp.name, TV_NEW, package="com.stremio.one"))[0])
        self.assertIn("names no package", self.check(make_apk(self.tmp.name, TV_NEW, package=""))[0])
    # P-REL-22
    def test_P_REL_22_junk_never_passes(self):
        self.assertIn("only", self.check(make_apk(self.tmp.name, TV_NEW, pad=False))[0])
        self.assertIn("does not follow", self.check(make_apk(self.tmp.name, "whatever.apk"))[0])
        bad = Path(self.tmp.name) / TV_NEW
        bad.write_bytes(os.urandom(1_100_000))
        self.assertIn("not a readable APK", self.check(bad)[0])
        truncated = Path(self.tmp.name) / TV_NEW
        with zipfile.ZipFile(truncated, "w") as zf:
            zf.writestr("AndroidManifest.xml", manifest(package="p", versionName="1")[:30])
            zf.writestr("padding", os.urandom(1_100_000))
        self.assertIn("not a readable APK", self.check(truncated)[0], "a cut-off manifest raises struct.error")
        with mock.patch.object(verify_apk, "signer_of", side_effect=struct.error("short")):
            self.assertIn("cannot read the signature", self.check(make_apk(self.tmp.name, TV_NEW), "good")[0])
    # P-REL-23
    def test_P_REL_23_a_rejected_apk_is_deleted_and_the_job_fails(self):
        good = make_apk(self.tmp.name, TV_NEW)
        bad = make_apk(self.tmp.name, "stremio-phone-clone-subs-v2.5.1-arm64-v8a.apk", libs=())
        env = {"SIGNING_CERT_SHA256": "", "GITHUB_ACTIONS": ""}
        with mock.patch.dict(os.environ, env), redirect_stdout(io.StringIO()):
            self.assertEqual(verify_apk.main([str(good), str(bad)]), 1)
        self.assertTrue(good.exists())
        self.assertFalse(bad.exists())
    # P-REL-24
    def test_P_REL_24_nothing_left_means_no_notes_for_this_job(self):
        bad = make_apk(self.tmp.name, TV_NEW, libs=())
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, cwd)
        Path("build.md").write_text("notes", encoding="utf-8")
        with mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "", "GITHUB_ACTIONS": ""}), redirect_stdout(io.StringIO()):
            verify_apk.main([str(bad)])
        self.assertFalse(Path("build.md").exists())
    # P-REL-25
    def test_P_REL_25_ci_without_the_expected_key_fails(self):
        good = make_apk(self.tmp.name, TV_NEW)
        with mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "", "GITHUB_ACTIONS": ""}), redirect_stdout(io.StringIO()):
            self.assertEqual(verify_apk.main([str(good)]), 0)
        self.assertTrue((good.parent / verify_apk.VERIFIED_MARK).exists(), "the upload step goes by this mark")
        with mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "", "GITHUB_ACTIONS": "true"}), redirect_stdout(io.StringIO()):
            self.assertEqual(verify_apk.main([str(good)]), 1)
        self.assertFalse(good.exists(), "not checked for the key means it does not go out")
    # P-REL-106
    def test_P_REL_106_no_apks_leaves_no_mark(self):
        with mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "", "GITHUB_ACTIONS": ""}), redirect_stdout(io.StringIO()):
            self.assertEqual(verify_apk.main([]), 0)
    # P-REL-26
    def test_P_REL_26_config_gives_each_clone_and_its_patches(self):
        config = ROOT / "config.toml"
        self.assertEqual(verify_apk.clone_package(config)["stremio-tv-clone-subs"], "com.stremio.one.subs")
        self.assertIn("Qutaiba-Khader/stremio-subs-patches", verify_apk.patch_sources(config)["stremio-tv-clone-subs"])
    # P-REL-27
    def test_P_REL_27_the_manifest_reader_gives_the_attributes(self):
        self.assertEqual(apk_package.manifest_attrs(coded_manifest("a.b", "1.2", 2147483647))["versionCode"], "2147483647")
        data = manifest(package="a.b", versionName="1.2")
        self.assertEqual(apk_package.manifest_attrs(data), {"package": "a.b", "versionName": "1.2"})
        self.assertEqual(apk_package.package_from_manifest(data), "a.b")
        with self.assertRaises(LookupError):
            apk_package.package_from_manifest(manifest(versionName="1.2"))
        with self.assertRaises(LookupError):
            apk_package.manifest_attrs(b"\0" * 8)


def entry(table="Stremio-TV", name="Stremio TV Clone", brand="subs", patches=None, keywords=(), version="latest", urls=None):
    patches = patches or {"github:Qutaiba-Khader/stremio-subs-patches": {"version": "latest", "include": ["Subtitle auto-refresh"], "exclude": []}}
    return AppEntry(table=table, app_name=name, brand=brand, arch="armeabi-v7a", dpi="", version=version,
                    dl_urls=urls if urls is not None else {"stremio": "https://api.strem.io/downloads/config#android_tv"},
                    patcher_args=[], patches=patches, exclusive_patches=True, cli_source="c", cli_version="latest",
                    skip_sigcheck=False, enabled=True, changelog_keywords=list(keywords))


class Net:
    """Fixed answers by URL fragment."""

    gh_headers: dict[str, str] = {}

    def __init__(self, answers):
        self.answers = answers

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def get(self, url, headers=None):
        for fragment, answer in self.answers.items():
            if fragment in url:
                if isinstance(answer, Exception):
                    raise answer
                return json.dumps(answer)
        raise AssertionError(f"unexpected request: {url}")


NEW = "2026-11-02T20:00:00Z"
TV_RELEASE = release("26.11.02-subs", [TV_NEW], published=NEW)


class Check(unittest.TestCase):
    """Whether the daily check starts a build."""
    # P-REL-98
    def test_P_REL_98_a_same_day_rebuild_already_on_the_patches_is_not_repeated(self):
        answers = self.answers(upstream_date="2026-11-03T00:00:00Z")  # newer than the release's date, same bundle
        self.assertEqual(self.run_check([entry()], answers), [])
    # P-REL-99
    def test_P_REL_99_a_cancelled_runs_draft_does_not_carry_a_version(self):
        draft = release("26.11.02-subs", [TV_NEW], published=None, draft=True)
        rel = release("26.10.28-subs", [TV_OLD], published="2026-10-28T00:00:00Z")
        self.assertTrue(matrix._stremio_needs_build("owner/repo", "subs", [entry()], Net(self.answers(ours=[draft, rel]))))

    def run_check(self, apps, answers):
        out = io.StringIO()
        with mock.patch.object(matrix, "_load_entries", return_value=apps), \
                mock.patch.object(matrix, "NetworkManager", return_value=Net(answers)), \
                mock.patch.object(matrix, "epr"), \
                mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), redirect_stdout(out):
            matrix.check_builds_needed()
        return json.loads(out.getvalue())

    def behind(self, notes, name="Stremio TV Clone", expected="0.6.0", assets=(TV_NEW,)):
        rel = release("26.11.02-subs", list(assets), body=notes)
        return matrix._apps_behind("subs", [entry(name=name)], "github:Qutaiba-Khader/stremio-subs-patches", expected, [rel])
    # P-REL-28
    def test_P_REL_28_an_app_left_on_old_patches_is_behind(self):
        self.assertEqual(self.behind(SUBS_NOTES, expected="0.7.0"), ["Stremio-TV"])
        self.assertEqual(self.behind(SUBS_NOTES), [])
    # P-REL-29
    def test_P_REL_29_two_bundles_after_a_straddled_build_count_as_behind(self):
        notes = SUBS_NOTES + "> ⚙️ » Patches: `Qutaiba-Khader/patches-0.7.0.mpp`\n"
        self.assertEqual(self.behind(notes, expected="0.7.0"), ["Stremio-TV"])
    # P-REL-30
    def test_P_REL_30_a_lower_version_build_is_retried(self):
        notes = SUBS_NOTES + "- 🟢 » Stremio TV Clone: `1.12.0` (wanted 1.12.1)\n"
        self.assertEqual(self.behind(notes), ["Stremio-TV"])
    # P-REL-31
    def test_P_REL_31_an_app_never_built_is_behind(self):
        self.assertEqual(self.behind(SUBS_NOTES, assets=(PHONE_NEW,)), ["Stremio-TV"])
    # P-REL-32
    def test_P_REL_32_a_keyword_app_is_left_to_its_keywords(self):
        rel = release("t", [TV_NEW])
        self.assertEqual(matrix._apps_behind("subs", [entry(keywords=["x"])], "github:Q/p", "9.9.9", [rel]), [])

    def answers(self, tag="v0.6.0", upstream_date="2026-10-27T10:45:55Z", ours=None, feed="1.12.1"):
        return {
            "api.strem.io": {"entries": [{"id": "android_tv", "value": {"versionName": feed, "tag": f"v{feed}", "versionCode": {"arm": "1"}}}]},
            "stremio-subs-patches/releases/latest": {"tag_name": tag, "published_at": upstream_date, "body": ""},
            "owner/repo/releases": ours if ours is not None else [TV_RELEASE],
        }
    # P-REL-33
    def test_P_REL_33_nothing_new_builds_nothing(self):
        self.assertEqual(self.run_check([entry()], self.answers()), [])
    # P-REL-34
    def test_P_REL_34_a_new_patch_release_builds(self):
        self.assertEqual(self.run_check([entry()], self.answers(tag="v0.7.0", upstream_date="2026-11-03T00:00:00Z")), ["subs"])
    # P-REL-35
    def test_P_REL_35_a_new_stremio_version_builds(self):
        self.assertEqual(self.run_check([entry()], self.answers(feed="1.12.2")), ["subs"])
    # P-REL-36
    def test_P_REL_36_a_failed_app_is_retried_at_most_once_a_day(self):
        now = datetime.now(UTC)
        recent = release("t-subs", [TV_NEW], published=(now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        old = release("t-subs", [TV_NEW], published=(now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        upstream = (now - timedelta(hours=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(self.run_check([entry()], self.answers(tag="v0.7.0", upstream_date=upstream, ours=[recent])), [])
        self.assertEqual(self.run_check([entry()], self.answers(tag="v0.7.0", upstream_date=upstream, ours=[old])), ["subs"])
    # P-REL-37
    def test_P_REL_37_a_failed_comparison_starts_nothing(self):
        answers = self.answers()
        now = datetime.now(UTC)
        answers["owner/repo/releases"] = [release("t-subs", [TV_NEW], published=(now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))]
        with mock.patch.object(matrix, "_expected_bundle", side_effect=RuntimeError("down")):
            self.assertEqual(self.run_check([entry()], answers), [])
    # P-REL-38
    def test_P_REL_38_our_newest_release_is_found_in_any_list_order(self):
        rels = [release("a-subs", [], published="2026-10-01T00:00:00Z"), release("b-subs", [], published="2026-11-01T00:00:00Z")]
        self.assertEqual(matrix._fetch_our_releases("owner/repo", Net({"releases": rels}))["subs"], "2026-11-01T00:00:00Z")
    # P-REL-39
    def test_P_REL_39_expected_bundle_is_what_a_build_would_use(self):
        net = Net({"releases/latest": {"tag_name": "v2.0.0"}, "releases?per_page": [{"tag_name": "v2.1.0-dev.9"}, {"tag_name": "v2.1.0-dev.14", "assets": [{"name": "patches-2.1.0-dev.13.mpp"}]}, {"tag_name": "v2.0.0"}]})
        self.assertEqual(matrix._expected_bundle("github:M/p", "latest", net), "2.0.0")
        self.assertEqual(matrix._expected_bundle("github:M/p", "dev", net), "2.1.0-dev.13", "the file's version, which the notes record")
    # P-REL-40
    def test_P_REL_40_prerelease_labels_keep_their_order(self):
        self.assertEqual(get_highest_ver(["v2.1.0-dev.20", "v2.1.0-rc.1"]), "v2.1.0-rc.1")
        self.assertEqual(get_highest_ver(["v2.1.0-rc.1", "v2.1.0"]), "v2.1.0")


class Patching(unittest.TestCase):
    """Applying patches and choosing the stock version."""

    def cli(self):
        return patcher.PatcherCLI(Path("cli.jar"), {}, Path("apksigner"))
    # P-REL-41
    def test_P_REL_41_a_named_patch_that_did_not_apply_fails_the_build(self):
        self.assertEqual(patcher.unapplied_patches("INFO: Applied: A\nINFO: Applied: B \n", ["A", "B", "C"]), ["C"])
        out = Path(tempfile.mkdtemp()) / "x.apk"
        out.write_bytes(b"x")
        with mock.patch.object(patcher, "_run_java", return_value="INFO: Applied: A\n"), redirect_stdout(io.StringIO()):
            with self.assertRaises(patcher.PatcherError):
                self.cli().patch(Path("s.apk"), out, [], required=["A", "Renamed"])
            self.assertFalse(out.exists())
            out.write_bytes(b"x")
            self.cli().patch(Path("s.apk"), out, [], required=["A"])
            self.assertTrue(out.exists())
    # P-REL-42
    def test_P_REL_42_older_versions_come_highest_first(self):
        listing = "Most common compatible versions:\n2026.44.0 (9)\n2026.42.0 (8)\n2026.40.0 (7)\n\n"
        cli = self.cli()
        with mock.patch.object(cli, "list_versions", return_value=listing):
            got = cli.older_supported_versions("", "p", {"s": {"version": "dev", "include": [], "exclude": []}}, "2026.44.0")
        self.assertEqual([v for v, _ in got], ["2026.42.0", "2026.40.0"])
        block = ("Name: Keep\nPackage name: p\nCompatible versions:\n3.0\n2.0\n1.0\nPackage name: z\n")
        got = cli.older_supported_versions(block, "p", {"s": {"version": "dev", "include": ["Keep"], "exclude": []}}, "3.0")
        self.assertEqual([v for v, _ in got], ["2.0", "1.0"])


class Fallback(unittest.TestCase):
    """A stock version that cannot be downloaded."""

    def build(self, version="exp", force=False, failing=("2026.44.0",), older=("2026.42.0", "2026.40.0"), shipped="2026.42.0"):
        app = entry(table="Reddit-Experimental", name="Reddit Experimental", brand="morphe-dev", version=version,
                    patches={"github:M/p": {"version": "dev", "include": [], "exclude": []}},
                    urls={"apkmirror": "u"})
        cli = mock.MagicMock()
        cli.older_supported_versions.return_value = [(v, None) for v in older]
        tried = []

        def download(_entry, ver, *_a, **_k):
            tried.append(ver)
            if ver in failing:
                raise builder.BuilderError("Stock APK not found")
            return builder.DownloadResult(path=Path(f"{ver}.apk"), is_bundle=False)

        with mock.patch.object(builder, "_make_scraper"), \
                mock.patch.object(builder, "_find_pkg_name", return_value=("p", "apkmirror", set())), \
                mock.patch.object(builder, "_resolve_version", return_value=("2026.44.0", None, force)), \
                mock.patch.object(builder, "_download_apk", side_effect=download), \
                mock.patch.object(builder, "_verify_sig"), \
                mock.patch.object(builder, "_last_shipped", return_value=shipped), \
                mock.patch.object(builder, "_apply_patch", side_effect=lambda _e, _a, ver, *_r: Path(f"x-v{ver}-all.apk")), \
                mock.patch.object(builder, "wpr"), mock.patch.object(builder, "pr"), mock.patch.object(builder, "epr"):
            line = builder._build_single(app, "all", "Reddit Experimental", None, cli, False)
        return line, tried
    # P-REL-43
    def test_P_REL_43_the_next_version_down_is_built_and_marked(self):
        line, tried = self.build()
        self.assertEqual(tried, ["2026.44.0", "2026.42.0"])
        self.assertIn("(wanted 2026.44.0)", line)
        self.assertIn("2026.42.0", line)
    # P-REL-44
    def test_P_REL_44_never_below_what_phones_already_have(self):
        line, tried = self.build(failing=("2026.44.0", "2026.42.0"))
        self.assertIsNone(line)
        self.assertEqual(tried, ["2026.44.0", "2026.42.0"], "2026.40.0 is below the shipped 2026.42.0")
    # P-REL-45
    def test_P_REL_45_a_named_version_does_not_fall_back(self):
        line, tried = self.build(force=True)
        self.assertIsNone(line)
        self.assertEqual(tried, ["2026.44.0"])
    # P-REL-46
    def test_P_REL_46_a_working_top_version_has_no_mark(self):
        line, tried = self.build(failing=())
        self.assertEqual(tried, ["2026.44.0"])
        self.assertNotIn("wanted", line)
    # P-REL-47
    def test_P_REL_47_last_shipped_reads_the_newest_build_of_this_app(self):
        app = entry(table="Reddit-Experimental", name="Reddit Experimental", brand="morphe-dev")
        rels = [release("a", ["reddit-experimental-morphe-dev-v2026.40.0-all.apk"], published="2026-10-01T00:00:00Z"),
                release("b", ["reddit-experimental-morphe-dev-v2026.42.0-all.apk", "other-v1-all.apk"], published="2026-10-25T00:00:00Z"),
                release("c", ["other-v2-all.apk"], published="2026-11-01T00:00:00Z")]
        self.assertEqual(builder._last_shipped(app, Net({"releases": rels})), "2026.42.0")
        self.assertEqual(builder._last_shipped(app, Net({"releases": []})), "")
        with mock.patch.object(builder, "epr"):
            self.assertEqual(builder._last_shipped(app, Net({"releases": RuntimeError("down")})), "")


APPS = [{"id": "stremio-tv", "brand": "subs", "source": "Qutaiba-Khader/stremio-subs-patches", "patch_version": "latest",
         "feed": "https://api.strem.io/downloads/config#android_tv", "keywords": False}]
APK_URL = f"{DL}/26.11.02-subs/{TV_NEW}"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def world(**over):
    """A healthy world: what is offered matches everything."""
    rel = release("26.11.02-subs", [TV_NEW])
    build = gen_site.collect([rel])["stremio-tv"]["builds"][0]
    data = {
        "releases": [rel],
        "releases_all": [rel],
        "latest": {"apps": {"stremio-tv": {"version": "1.12.1", "tag": "26.11.02-subs", "patches": build["patches"]}}},
        "obtainium": {"apps": [{"app": "stremio-tv", "apk": APK_URL, "build_version": "1.12.1-0.6.0", "package": "com.stremio.one.subs", "source_url": "https://x/p.html"}]},
        "pages": {"stremio-tv": f'<meta name="build-version" content="1.12.1-0.6.0"><a href="{APK_URL}">x</a>'},
        "apks": {APK_URL: {"package": "com.stremio.one.subs", "version": "1.12.1", "signer": "good"}},
        "feeds": {"stremio-tv": "1.12.1"},
        "bundles": {("Qutaiba-Khader/stremio-subs-patches", "latest"): "0.6.0"},
        "ci": {"id": 1, "created_at": "2026-11-03T10:00:00Z", "conclusion": "success"},
        "site_run": {"conclusion": "success"},
        "ci_failed_jobs": [],
        "sync_behind": 0,
        "signer": "good",
        "flow_failures": [],
    }
    data.update(over)
    return data


def problems(data):
    return {**release_check.check_offers(APPS, data), **release_check.check_upstream(APPS, data), **release_check.check_runs(data, NOW)}


class Health(unittest.TestCase):
    """The check of what a phone is offered."""
    # P-REL-48
    def test_P_REL_48_a_healthy_world_has_no_problems(self):
        self.assertEqual(problems(world()), {})
    # P-REL-49
    def test_P_REL_49_the_bug_that_started_this_is_caught(self):
        """Live: an older version offered while the releases hold a newer one."""
        data = world()
        data["latest"]["apps"]["stremio-tv"]["version"] = "1.12.0"
        self.assertIn("offered-stale:stremio-tv", problems(data))
    # P-REL-50
    def test_P_REL_50_a_missing_app_is_caught(self):
        self.assertIn("no-release:stremio-tv", problems(world(releases=[])))
        self.assertIn("not-offered:stremio-tv", problems(world(obtainium={"apps": []})))
    # P-REL-51
    def test_P_REL_51_a_wrong_update_page_is_caught(self):
        self.assertIn("page-link:stremio-tv", problems(world(pages={"stremio-tv": ""})))
        self.assertIn("page-version:stremio-tv", problems(world(pages={"stremio-tv": f'<a href="{APK_URL}">'})))
        data = world()
        data["obtainium"]["apps"][0]["build_version"] = "9.9.9-1"
        self.assertIn("page-version:stremio-tv", problems(data))
    # P-REL-52
    def test_P_REL_52_an_apk_that_is_not_what_is_promised_is_caught(self):
        good = {"package": "com.stremio.one.subs", "version": "1.12.1", "signer": "good"}
        self.assertIn("apk-unreachable:stremio-tv", problems(world(apks={APK_URL: {"error": "404"}})))
        self.assertIn("apk-unreachable:stremio-tv", problems(world(apks={})))
        self.assertIn("apk-package:stremio-tv", problems(world(apks={APK_URL: {**good, "package": "x"}})))
        self.assertIn("apk-version:stremio-tv", problems(world(apks={APK_URL: {**good, "version": "1.0"}})))
        self.assertIn("apk-signer:stremio-tv", problems(world(apks={APK_URL: {**good, "signer": "bad"}})))
        data = world(apks={APK_URL: {**good, "abis": {"arm64-v8a"}}})
        data["obtainium"]["apps"][0]["arch"] = "armeabi-v7a"
        self.assertIn("apk-cpu:stremio-tv", problems(data))
        data = world(apks={APK_URL: {**good, "abis": {"armeabi-v7a"}}})
        data["obtainium"]["apps"][0]["arch"] = "armeabi-v7a"
        self.assertEqual(problems(data), {})
    # P-REL-95
    def test_P_REL_95_a_build_below_the_wanted_version_is_reported(self):
        data = world()
        data["releases"][0]["body"] += f"\n- 🟢 » Stremio TV Clone: [`1.12.1`]({APK_URL}) (wanted 1.12.2)\n"
        data["latest"]["apps"]["stremio-tv"]["files"] = [{"name": TV_NEW}]
        self.assertIn("wanted-behind:stremio-tv", release_check.check_offers(APPS, data))
        self.assertEqual(release_check.grace_of("wanted-behind:x"), timedelta(days=3))
    # P-REL-53
    def test_P_REL_53_release_notes_with_no_bundle_are_caught(self):
        data = world()
        data["latest"]["apps"]["stremio-tv"]["patches"] = []
        self.assertIn("no-bundle:stremio-tv", problems(data))
    # P-REL-54
    def test_P_REL_54_upstream_ahead_of_the_offer_is_caught(self):
        self.assertIn("feed-behind:stremio-tv", problems(world(feeds={"stremio-tv": "1.12.2"})))
        self.assertIn("check-error:feed:stremio-tv", problems(world(feeds={"stremio-tv": ""})))
        self.assertIn("patches-behind:stremio-tv", problems(world(bundles={("Qutaiba-Khader/stremio-subs-patches", "latest"): "0.7.0"})))
        self.assertEqual(problems(world(bundles={("Qutaiba-Khader/stremio-subs-patches", "dev"): "9.9.9"})), {}, "another channel of the source")
        keyword_app = [{**APPS[0], "keywords": True}]
        self.assertEqual(release_check.check_upstream(keyword_app, world(feeds={"stremio-tv": "9"})), {})
    # P-REL-55
    def test_P_REL_55_the_runs_are_checked(self):
        rel = release("x", [], draft=True)
        self.assertIn("stuck-draft:x", problems(world(releases_all=[rel])))
        self.assertIn("ci-stale", problems(world(ci=None)))
        self.assertIn("ci-stale", problems(world(ci={"created_at": "2026-11-01T10:00:00Z"})))
        self.assertIn("ci-failed:build (x)", problems(world(ci_failed_jobs=["build (x)"])))
        self.assertIn("site-failed", problems(world(site_run={"conclusion": "failure"})))
        self.assertIn("site-failed", problems(world(site_run={"conclusion": "startup_failure"})))
        self.assertEqual(problems(world(site_run={"conclusion": "cancelled"})), {}, "replaced in its queue")
        self.assertIn("ci-failed", problems(world(ci={"id": 1, "created_at": "2026-11-03T10:00:00Z", "conclusion": "timed_out"})))
        self.assertIn("tests-failed", problems(world(tests_run={"conclusion": "failure"})))
        self.assertIn("sync-behind", problems(world(sync_behind=6)))
        self.assertIn("flow-test:readme row", problems(world(flow_failures=["readme row"])))
    # P-REL-56
    def test_P_REL_56_conflicts_and_unknown_packages_are_caught(self):
        data = world()
        data["obtainium"].update(conflicts=[{"app": "a", "shares_with": "b"}], unknown_package=["c"])
        found = problems(data)
        self.assertIn("package-conflict:a", found)
        self.assertIn("package-unknown:c", found)
    # P-REL-57
    def test_P_REL_57_a_problem_counts_only_after_its_grace(self):
        state = release_check.update_state({}, {"feed-behind:x": "behind"}, NOW)
        self.assertEqual(release_check.active(state, NOW), [])
        later = NOW + timedelta(hours=15)
        state = release_check.update_state(state, {"feed-behind:x": "behind"}, later)
        self.assertEqual(release_check.active(state, later), ["behind"], "first_seen is kept from the first run")
        self.assertEqual(release_check.update_state(state, {}, later), {"problems": {}})
        fresh = release_check.update_state({}, {"ci-stale": "old"}, NOW)
        self.assertEqual(release_check.active(fresh, NOW), ["old"], "no grace")

    def run_main(self, data=None, errors=None, state=None, env=None):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        if state:
            Path(folder, "state.json").write_text(json.dumps(state), encoding="utf-8")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"HEALTH_DIR": folder, **(env or {})}), \
                mock.patch.object(release_check, "enabled_apps", return_value=APPS), \
                mock.patch.object(release_check, "gather", return_value=(data or world(), errors or {})), \
                mock.patch.object(gen_site, "build_state", return_value=("idle", "")), \
                mock.patch.object(release_check, "check_runs", return_value={}), \
                redirect_stdout(out):
            code = release_check.main()
        report = json.loads(Path(folder, "report.json").read_text(encoding="utf-8")) if Path(folder, "report.json").exists() else {}
        return code, report
    # P-REL-61
    def test_P_REL_61_healthy_run_is_green_and_quiet(self):
        code, report = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["offered"]["stremio-tv"]["version"], "1.12.1")
    # P-REL-62
    def test_P_REL_62_a_problem_turns_the_run_red_and_alerts(self):
        data = world()
        data["pages"] = {}
        code, report = self.run_main(data)
        self.assertEqual(code, 1)
        self.assertTrue(report["problems"])
    # P-REL-63
    def test_P_REL_63_a_problem_in_its_grace_waits_green(self):
        code, report = self.run_main(world(feeds={"stremio-tv": "1.12.2"}))
        self.assertEqual(code, 0)
        self.assertTrue(report["waiting"])
    # P-REL-64
    def test_P_REL_64_unreadable_releases_judge_nothing_else(self):
        code, report = self.run_main(world(releases=[]), {"check-error:releases": "cannot read"})
        self.assertEqual(code, 0)
        self.assertEqual(report["waiting"], ["cannot read"])
    # P-REL-96
    def test_P_REL_96_an_unread_page_does_not_claim_the_offer_is_wrong(self):
        code, report = self.run_main(world(pages={}, latest={}, obtainium={"apps": []}), {"check-error:latest.json": "down"})
        self.assertEqual((code, report["problems"]), (0, []))
        self.assertEqual(report["waiting"], ["down"])
    # P-REL-97
    def test_P_REL_97_flow_test_findings_last_until_its_next_run(self):
        state = {"problems": {"flow-test:row": {"first_seen": "2026-11-01T00:00:00Z", "text": "site flow test: row"}}}
        code, report = self.run_main(world(flow_failures=None), state=state)
        self.assertEqual(code, 1)
        self.assertEqual(report["problems"], ["site flow test: row"])
    # P-REL-65
    def test_P_REL_65_a_running_build_skips_the_check(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        with mock.patch.dict(os.environ, {"HEALTH_DIR": folder}), \
                mock.patch.object(gen_site, "build_state", return_value=("busy", "CI #1")), redirect_stdout(io.StringIO()):
            self.assertEqual(release_check.main(), 0)
        self.assertEqual(json.loads(Path(folder, "report.json").read_text(encoding="utf-8"))["skipped"], "CI #1")
    # P-REL-67
    def test_P_REL_67_gather_reads_every_source(self):
        latest = {"apps": {}}
        obtainium = {"apps": [{"app": "stremio-tv", "apk": APK_URL, "source_url": "https://x/p.html"}]}

        def text(url):
            if "latest.json" in url:
                return json.dumps(latest)
            if "obtainium.json" in url:
                return json.dumps(obtainium)
            return "<page>"

        def api(url):
            if "/actions/workflows/ci.yml" in url:
                return {"workflow_runs": [{"id": 5, "conclusion": "failure", "created_at": "2026-11-03T00:00:00Z"}]}
            if "/actions/runs/5/jobs" in url:
                return {"jobs": [{"name": "bad", "conclusion": "failure"}, {"name": "ok", "conclusion": "success"}]}
            if "/actions/workflows/site.yml" in url or "/actions/workflows/tests.yml" in url:
                return {"workflow_runs": []}
            if "/compare/" in url:
                return {"ahead_by": 2}
            if "&page=1" in url:
                return [release("26.11.02-subs", [TV_NEW]), release("d", [], draft=True)]
            return []

        with mock.patch.object(release_check, "_text", side_effect=text), mock.patch.object(gen_site, "_get", side_effect=api), \
                mock.patch.object(release_check, "read_apk", return_value={"package": "p"}), \
                mock.patch.object(release_check, "feed_versions", return_value={"stremio-tv": "1"}), \
                mock.patch.object(release_check, "patch_bundles", return_value={"s": "1"}):
            data, errors = release_check.gather("owner/repo", "https://x/", APPS)
        self.assertEqual(errors, {})
        self.assertEqual(data["ci_failed_jobs"], ["bad"])
        self.assertEqual(data["sync_behind"], 2)
        self.assertEqual(len(data["releases"]), 1)
        self.assertEqual(len(data["releases_all"]), 2)
        self.assertEqual(data["pages"]["stremio-tv"], "<page>")
        self.assertEqual(list(data["apks"]), [APK_URL])
    # P-REL-68
    def test_P_REL_68_a_source_that_cannot_be_read_is_its_own_problem(self):
        with mock.patch.object(release_check, "_text", side_effect=OSError("down")), mock.patch.object(gen_site, "_get", side_effect=OSError("down")), \
                mock.patch.object(release_check, "feed_versions", return_value={}), mock.patch.object(release_check, "patch_bundles", return_value={}):
            data, errors = release_check.gather("owner/repo", "https://x/", APPS)
        self.assertIn("check-error:releases", errors)
        self.assertIn("check-error:latest.json", errors)
        self.assertEqual(data["releases"], [])
    # P-REL-69
    def test_P_REL_69_feed_and_bundles_are_read_as_a_build_would(self):
        feed = {"entries": [{"id": "android_tv", "value": {"versionName": "1.12.1"}}]}
        with mock.patch.object(release_check, "_text", return_value=json.dumps(feed)):
            self.assertEqual(release_check.feed_versions(APPS), {"stremio-tv": "1.12.1"})
            self.assertEqual(release_check.feed_versions([{**APPS[0], "feed": "u#gone"}]), {"stremio-tv": ""})
        self.assertEqual(release_check.feed_versions([{**APPS[0], "feed": "u#android_tv@1.0:5"}]), {}, "a pin is not compared")
        dev = [{**APPS[0], "source": "M/p", "patch_version": "dev"}]
        with mock.patch.object(gen_site, "_get", return_value=[{"tag_name": "v2.1.0-dev.9"}, {"tag_name": "v2.1.0-dev.14"}]):
            self.assertEqual(release_check.patch_bundles(dev), {("M/p", "dev"): "2.1.0-dev.14"})
        with mock.patch.object(gen_site, "_get", return_value={"tag_name": "v0.6.0"}):
            self.assertEqual(release_check.patch_bundles(APPS), {(APPS[0]["source"], "latest"): "0.6.0"})
    # P-REL-70
    def test_P_REL_70_flow_test_failures_are_read_from_its_log(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as log:
            log.write("PASS  a\nFAIL  readme row  — detail\n")
        self.addCleanup(os.unlink, log.name)
        self.assertEqual(release_check.flow_failures(log.name), ["readme row", "it did not finish"])
        Path(log.name).write_text("PASS  a\nFAIL  readme row  — detail\n\n1/2 passed\n", encoding="utf-8")
        self.assertEqual(release_check.flow_failures(log.name), ["readme row"])
        self.assertIsNone(release_check.flow_failures(""))
        self.assertIsNone(release_check.flow_failures("/no/such/file"))
    # P-REL-71
    def test_P_REL_71_read_apk_turns_any_failure_into_a_finding(self):
        with mock.patch.object(release_check, "manifest_from_url", return_value=manifest(package="p", versionName="1")), \
                mock.patch.object(release_check, "names_from_url", return_value=["lib/x86/a.so", "classes.dex"]), \
                mock.patch.object(release_check, "signer_of", return_value="s"):
            self.assertEqual(release_check.read_apk("u"), {"package": "p", "version": "1", "code": None, "signer": "s", "abis": {"x86"}})
        with mock.patch.object(release_check, "manifest_from_url", side_effect=urllib.error.URLError("404")):
            self.assertIn("404", release_check.read_apk("u")["error"])
    # P-REL-72
    def test_P_REL_72_config_gives_the_enabled_apps(self):
        apps = {a["id"]: a for a in release_check.enabled_apps()}
        self.assertEqual(apps["stremio-tv"]["source"], "Qutaiba-Khader/stremio-subs-patches")
        self.assertIn("#android_tv", apps["stremio-tv"]["feed"])
        self.assertEqual(apps["youtube-experimental"]["patch_version"], "dev")
        self.assertNotIn("stremio", json.dumps(apps["youtube"]["feed"]))


class WholeFlow(unittest.TestCase):
    """Releases -> the generated site -> the check, with only the network faked."""

    def generate(self, releases):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        out = folder / "_site"
        with mock.patch.object(gen_site, "OUT_DIR", out), \
                mock.patch.object(gen_site, "build_state", return_value=("idle", "")), \
                mock.patch.object(gen_site, "fetch_releases", return_value=releases), \
                mock.patch.object(gen_site, "fetch_live", return_value={}), \
                mock.patch.object(gen_site, "package_of", return_value="com.stremio.one.subs"), \
                mock.patch.object(gen_site, "signer_of", return_value="good"), \
                mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "good"}), redirect_stdout(io.StringIO()):
            self.assertEqual(gen_site.main(), 0)
        return out

    def world_from(self, out, releases):
        latest = json.loads((out / "api/latest.json").read_text(encoding="utf-8"))
        obtainium = json.loads((out / "api/obtainium.json").read_text(encoding="utf-8"))
        pages = {e["app"]: (out / e["page"]).read_text(encoding="utf-8") for e in obtainium["apps"]}
        return world(releases=releases, releases_all=releases, latest=latest, obtainium=obtainium, pages=pages,
                     apks={e["apk"]: {"package": "com.stremio.one.subs", "version": e["version"], "signer": "good"} for e in obtainium["apps"]})
    # P-REL-73
    def test_P_REL_73_same_day_rebuild_end_to_end(self):
        releases = [release("26.11.02-subs", [TV_OLD, TV_NEW])]
        out = self.generate(releases)
        data = self.world_from(out, releases)
        page = data["pages"]["stremio-tv"]
        self.assertIn('content="1.12.1-0.6.0"', page)
        self.assertIn(TV_NEW, page)
        self.assertNotIn(TV_OLD, page)
        self.assertEqual(release_check.check_offers(APPS, data), {})
    # P-REL-74
    def test_P_REL_74_a_wrong_key_publishes_nothing(self):
        out = Path(tempfile.mkdtemp()) / "_site"
        with mock.patch.object(gen_site, "OUT_DIR", out), \
                mock.patch.object(gen_site, "build_state", return_value=("idle", "")), \
                mock.patch.object(gen_site, "fetch_releases", return_value=[release("26.11.02-subs", [TV_NEW])]), \
                mock.patch.object(gen_site, "fetch_live", return_value={}), \
                mock.patch.object(gen_site, "package_of", return_value="p"), \
                mock.patch.object(gen_site, "signer_of", return_value="other"), \
                mock.patch.dict(os.environ, {"SIGNING_CERT_SHA256": "good"}), redirect_stdout(io.StringIO()):
            self.assertEqual(gen_site.main(), 1)
        self.assertFalse(out.exists())
    # P-REL-75
    def test_P_REL_75_a_running_build_publishes_nothing(self):
        out = Path(tempfile.mkdtemp()) / "_site"
        with mock.patch.object(gen_site, "OUT_DIR", out), \
                mock.patch.object(gen_site, "build_state", return_value=("busy", "CI #1")), redirect_stdout(io.StringIO()):
            self.assertEqual(gen_site.main(), 0)
        self.assertFalse(out.exists())


def signed_apk_bytes(cert=b"certificate", scheme=apk_package.SCHEME_IDS[1], manifest_name="AndroidManifest.xml"):
    """A small APK with a real APK Signing Block around one certificate."""
    def lp(data):
        return struct.pack("<I", len(data)) + data
    signed_data = lp(b"") + lp(lp(cert))
    value = lp(lp(lp(signed_data)))
    pair = struct.pack("<QI", 4 + len(value), scheme) + value
    size = len(pair) + 8 + 16
    block = struct.pack("<Q", size) + pair + struct.pack("<Q", size) + apk_package.SIG_BLOCK_MAGIC
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(manifest_name, manifest(package="a.b", versionName="1.2"))
    data = raw.getvalue()
    eocd = data.rfind(b"PK\x05\x06")
    cd_off = struct.unpack_from("<I", data, eocd + 16)[0]
    patched = bytearray(data[:cd_off] + block + data[cd_off:])
    struct.pack_into("<I", patched, eocd + len(block) + 16, cd_off + len(block))
    return bytes(patched)


class FakeUrl:
    """urlopen for one in-memory file, answering HEAD and range requests."""

    def __init__(self, data):
        self.data = data

    def __call__(self, req, timeout=0):
        data = self.data
        answer = mock.MagicMock()
        answer.headers = {"Content-Length": str(len(data))}
        answer.geturl.return_value = req.full_url
        rng = req.get_header("Range")
        if rng:
            start, _, end = rng.removeprefix("bytes=").partition("-")
            answer.read.return_value = data[int(start): int(end) + 1 if end else None]
        else:
            answer.read.return_value = data
        answer.__enter__.return_value = answer
        return answer


class ApkReader(unittest.TestCase):
    """Reading a published APK without downloading it."""
    # P-REL-104
    def test_P_REL_104_file_names_are_read_over_http(self):
        with mock.patch.object(apk_package.urllib.request, "urlopen", FakeUrl(signed_apk_bytes())):
            self.assertEqual(apk_package.names_from_url("https://x/a.apk"), ["AndroidManifest.xml"])
    # P-REL-105
    def test_P_REL_105_live_pages_are_read_with_retries(self):
        answer = mock.MagicMock()
        answer.__enter__.return_value.read.return_value = b"page"
        with mock.patch.object(release_check.urllib.request, "urlopen", side_effect=[OSError("reset"), answer]), mock.patch.object(release_check.time, "sleep"):
            self.assertEqual(release_check._text("https://x/p"), "page")
        with mock.patch.object(release_check.urllib.request, "urlopen", side_effect=[OSError("reset"), OSError("reset"), answer]), mock.patch.object(release_check.time, "sleep"):
            self.assertEqual(release_check._text("https://x/p"), "page")
        with mock.patch.object(release_check.urllib.request, "urlopen", side_effect=OSError("reset")) as call, mock.patch.object(release_check.time, "sleep"):
            with self.assertRaises(OSError):
                release_check._text("https://x/p")
        self.assertEqual(call.call_count, 3)
    # P-REL-76
    def test_P_REL_76_package_and_signer_over_http(self):
        with mock.patch.object(apk_package.urllib.request, "urlopen", FakeUrl(signed_apk_bytes())):
            self.assertEqual(apk_package.package_of("https://x/a.apk"), "a.b")
            self.assertEqual(apk_package.signer_of("https://x/a.apk"), __import__("hashlib").sha256(b"certificate").hexdigest())
    # P-REL-77
    def test_P_REL_77_a_local_file_reads_the_same(self):
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            f.write(signed_apk_bytes())
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(apk_package.package_of(f.name), "a.b")
        self.assertEqual(apk_package.signer_of(f.name), __import__("hashlib").sha256(b"certificate").hexdigest())
    # P-REL-78
    def test_P_REL_78_an_unsigned_or_broken_file_is_refused(self):
        with mock.patch.object(apk_package.urllib.request, "urlopen", FakeUrl(b"junk" * 40)):
            with self.assertRaisesRegex(LookupError, "end-of-central"):
                apk_package.package_of("https://x/a.apk")
            with self.assertRaisesRegex(LookupError, "end-of-central"):
                apk_package.signer_of("https://x/a.apk")
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as zf:
            zf.writestr("other.txt", "x")
        with mock.patch.object(apk_package.urllib.request, "urlopen", FakeUrl(raw.getvalue())):
            with self.assertRaisesRegex(LookupError, "not in the central"):
                apk_package.package_of("https://x/a.apk")
            with self.assertRaisesRegex(LookupError, "not signed"):
                apk_package.signer_of("https://x/a.apk")
        with mock.patch.object(apk_package.urllib.request, "urlopen", FakeUrl(signed_apk_bytes(scheme=0x1234))):
            with self.assertRaisesRegex(LookupError, "no v2/v3"):
                apk_package.signer_of("https://x/a.apk")
    # P-REL-79
    def test_P_REL_79_utf16_string_pools_read_too(self):
        text = "x"
        raw = struct.pack("<H", len(text)) + text.encode("utf-16-le") + b"\0\0"
        pool = struct.pack("<HHIIIIII", 1, 28, 28 + 4 + len(raw), 1, 0, 0, 32, 0) + struct.pack("<I", 0) + raw
        self.assertEqual(apk_package._string_pool(pool, 0), [text])
    # P-REL-80
    def test_P_REL_80_the_command_line_prints_the_answer(self):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["x", "--signer", "a.apk"]), mock.patch.object(apk_package, "signer_of", return_value="SIG"), redirect_stdout(out):
            apk_package.cli()
        self.assertEqual(out.getvalue().strip(), "SIG")
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["x", "a.apk"]), mock.patch.object(apk_package, "package_of", return_value="PKG"), redirect_stdout(out):
            apk_package.cli()
        self.assertEqual(out.getvalue().strip(), "PKG")
        with mock.patch.object(sys, "argv", ["x"]), self.assertRaises(SystemExit):
            apk_package.cli()


class BuildList(unittest.TestCase):
    """The list of apps a build runs, and the check's failure paths."""

    def matrix_of(self, source, apps, env=None, answers=None):
        out = io.StringIO()
        with mock.patch.object(matrix, "_load_entries", return_value=apps), \
                mock.patch.object(matrix, "NetworkManager", return_value=Net(answers or {})), \
                mock.patch.dict(os.environ, env or {}), redirect_stdout(out):
            matrix.get_matrix(source)
        return json.loads(out.getvalue())
    # P-REL-81
    def test_P_REL_81_each_app_of_the_brand_is_listed(self):
        got = self.matrix_of("subs", [entry(), entry(table="Other", brand="morphe")])
        self.assertEqual(got, {"include": [{"id": "Stremio-TV"}], "prerelease": False})
    # P-REL-82
    def test_P_REL_82_a_dev_brand_is_a_prerelease(self):
        dev = entry(patches={"github:M/p": {"version": "dev", "include": [], "exclude": []}})
        self.assertTrue(self.matrix_of("subs", [dev])["prerelease"])
    # P-REL-83
    def test_P_REL_83_an_unknown_source_stops_the_build(self):
        with mock.patch.object(matrix, "abort", side_effect=SystemExit(1)), self.assertRaises(SystemExit):
            self.matrix_of("nothing", [entry()])
    # P-REL-84
    def test_P_REL_84_keywords_filter_only_with_the_filter_on(self):
        keyed = entry(keywords=["photos"])
        answers = {"owner/repo/releases": [release("x-subs", [], published=NEW)], "releases/latest": {"body": "telegram only", "published_at": NEW}}
        got = None
        with mock.patch.object(matrix, "abort", side_effect=SystemExit(1)), self.assertRaises(SystemExit):
            got = self.matrix_of("subs", [keyed], {"FILTER_CHANGELOG": "true", "GITHUB_REPOSITORY": "owner/repo"}, answers)
        self.assertIsNone(got)
        self.assertEqual(len(self.matrix_of("subs", [keyed])["include"]), 1)
        both = entry(table="B")
        both = AppEntry(**{**{f: getattr(both, f) for f in both.__dataclass_fields__}, "arch": "both"})
        self.assertEqual(len(self.matrix_of("subs", [both])["include"]), 2)

    def check(self, apps, answers, force=False):
        out = io.StringIO()
        with mock.patch.object(matrix, "_load_entries", return_value=apps), \
                mock.patch.object(matrix, "NetworkManager", return_value=Net(answers)), mock.patch.object(matrix, "epr"), \
                mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), redirect_stdout(out):
            matrix.check_builds_needed(force_all=force)
        return json.loads(out.getvalue())
    # P-REL-85
    def test_P_REL_85_force_builds_every_brand_and_no_apps_builds_none(self):
        self.assertEqual(self.check([entry()], {}, force=True), ["subs"])
        self.assertEqual(self.check([], {}), [])
    # P-REL-86
    def test_P_REL_86_an_unreadable_upstream_builds_rather_than_misses(self):
        answers = {"releases/latest": RuntimeError("down"), "owner/repo/releases": []}
        self.assertEqual(self.check([entry(urls={})], answers), ["subs"])
    # P-REL-87
    def test_P_REL_87_a_removed_patch_repo_skips_that_brand(self):
        answers = {"releases/latest": matrix.ResourceNotFoundError("gone"), "owner/repo/releases": []}
        self.assertEqual(self.check([entry(urls={})], answers), [])
    # P-REL-88
    def test_P_REL_88_a_brand_with_no_release_yet_builds(self):
        answers = {"releases/latest": {"tag_name": "v1", "published_at": NEW}, "owner/repo/releases": []}
        self.assertEqual(self.check([entry(urls={})], answers), ["subs"])
    # P-REL-89
    def test_P_REL_89_feed_failures(self):
        net = Net({"api.strem.io": RuntimeError("down"), "owner/repo/releases": RuntimeError("down")})
        with mock.patch.object(matrix, "epr"):
            self.assertFalse(matrix._stremio_needs_build("owner/repo", "subs", [entry()], net), "an unreadable feed builds nothing; Health reports it")
            self.assertEqual(matrix._fetch_our_releases("owner/repo", net), {})
        net = Net({"api.strem.io": {"entries": [{"id": "android_tv", "value": {"versionName": "1", "tag": "v1", "versionCode": {"arm": "1"}}}]}, "owner/repo/releases": RuntimeError("down")})
        with mock.patch.object(matrix, "epr"):
            self.assertTrue(matrix._stremio_needs_build("owner/repo", "subs", [entry()], net), "our releases unreadable: build rather than miss")
    # P-REL-90
    def test_P_REL_90_the_newest_dev_release_is_found_by_date(self):
        net = Net({"releases?per_page": [{"published_at": "2026-10-01T00:00:00Z", "body": "old"}, {"published_at": "2026-11-01T00:00:00Z", "body": "new"}, {"draft": True, "published_at": "2026-12-01T00:00:00Z", "body": "draft"}]})
        self.assertEqual(matrix._fetch_latest_release("github:M/p", net, version="dev"), ("new", "2026-11-01T00:00:00Z"))
        gitlab = Net({"gitlab.com": {"description": "d", "released_at": "2026-01-01T00:00:00Z"}})
        self.assertEqual(matrix._fetch_latest_release("gitlab:a/b", gitlab), ("d", "2026-01-01T00:00:00Z"))
    # P-REL-91
    def test_P_REL_91_the_command_line_runs_the_right_check(self):
        with mock.patch.object(matrix, "_require_ci"), mock.patch.object(matrix, "check_builds_needed") as check, mock.patch.object(matrix, "get_matrix") as get:
            with mock.patch.object(sys, "argv", ["m", "get-matrix"]):
                matrix.main()
            check.assert_called_once_with()
            with mock.patch.object(sys, "argv", ["m", "get-matrix-force"]):
                matrix.main()
            check.assert_called_with(force_all=True)
            with mock.patch.object(sys, "argv", ["m", "get-matrix", "subs"]):
                matrix.main()
            get.assert_called_once_with("subs")
            with mock.patch.object(sys, "argv", ["m"]), mock.patch.object(matrix, "abort", side_effect=SystemExit(1)), self.assertRaises(SystemExit):
                matrix.main()


if __name__ == "__main__":
    unittest.main()
