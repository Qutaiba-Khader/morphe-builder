# Real version formats (2026-08-01 to 2026-11-03)

Every case below is replayed by `tests/test_version_history.py` from `tests/fixtures/history.json`. Rebuild the fixture with
`tools/history_fixture.py`; answer the pairs `tools/history_replay.py` prints with ObtainX's own `compareVersionStrings`, then `tools/history_replay.py --save FILE`.

| Format | Real example | Where it comes from | How it is handled |
|---|---|---|---|
| App, plain | `1.12.1`, `2.5.1`, `2026.42.0`, `21.30.216`, `46.2.3` | Stremio's feed, APKMirror | Numeric order |
| App, label in the name | `21.44.528-BETA` | APKMirror | A final beats its own beta. ObtainX offers beta to final |
| App, label inside only | file `21.41.525`, app says `21.41.525-EXTENDED` | YouTube from APKMirror | The site shows the file's version; `verify_apk` accepts a suffix |
| Feed pre-release | `2.2.0-beta.5`, `1.10.0-rc.18` | Stremio's feed, beta entries | We do not follow them. Ordered correctly with the patch number in dots |
| Patch, final | `v2.0.0`, `v0.6.0`, `v0.8.1` | Patch repos | In the APK's versionName: `21.30.216.2.0.0`; on a pre-release channel `.9999`, above its own dev.N |
| Patch, dev | `v2.1.0-dev.6` | Morphe, TikTok | `21.44.528.2.1.0.6`; alpha, beta and rc rank above dev in that slot |
| Patch jump | `1.49.0-dev.5` to `2.1.0-dev.6` | An app stuck, then rebuilt | Still offered |
| Two bundles in one release | tag `v0.9.0-dev.7` has `patches-0.9.0-dev.6.mpp` and `patches-0.9.0-dev.7.mpp` | TikTok's dev releases | The file of the tag, else the highest, in the builder and both checks |
| Same-day rebuild | `26.11.02-subs` held 2.5.0 and 2.5.1 | Our releases | Best version offered, the other removed |
| Same number again | `youtube-…-v21.30.216-all.apk` in many tags | Daily or manual rebuilds | Same text: not offered again |
| versionCode goes down | 21.41.525 to -EXTENDED; 21.44.528-BETA to 21.44.528 | Real builds, 26.10.14 and 26.11.01 | Android refuses it. YouTube Experimental now has the maximum code; for others `verify_apk` compares with the highest ever released, and Health reports it |
| Version backwards | Not seen in the channels we follow | | Pin wins by design; otherwise Health reports it |

## What a phone compares

ObtainX compares the `versionName` the phone reports with the version the update page offers (`lib/version/app_version.dart`,
`version_comparison.dart`). Until 2026-11-03 the page offered `46.2.3-0.8.1` against a reported `46.2.3`: `missingBuildRevision`,
which ObtainX shows as "Version order unclear", on every app. Now the page offers exactly the `versionName` inside the APK, and
`src/core/apk_version.py` writes the patch version into it with dots. A plain `46.2.3` is older than `46.2.3.0.8.1` in ObtainX, so an
app installed earlier gets one clean update, and a patch-only update is ordered. Health fails if the page and the APK ever differ.

Morphe's own code must not see that number. It reads the same `versionName` (`Utils.getAppVersionName`) and alerts when it sorts above the recommended version, as text: `21.30.216.2.0.0` is above `21.30.216`, so a stable build opened with "Experimental Alert" (26.11.03-morphe, on the owner's phone). It also sends that name to YouTube as the client version. So `src/core/java/ReportStockVersion.java` makes `getAppVersionName` and `getUniversalAppVersionOverride` answer with the app's real version; `verify_apk` and Health read those answers from the dex and fail on a wrong one. A fix like this on an unchanged bundle needs a higher number or no phone gets it: `rebuild = "2.0.0:1"` in config.toml gives `21.30.216.2.0.0.1`, and the next bundle or app version drops it.
