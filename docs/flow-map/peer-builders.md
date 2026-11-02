# How similar builders handle versions (read 2026-11-03)

Read from the code at the commit named; none of it was run. Used to compare with `tools/gen_site.py`, `src/scripts/matrix.py`, `src/core/prebuilts.py`.

| Repo @ commit | Compares | Names | Rebuilds when | Reaches users by |
|---|---|---|---|---|
| holjab/AutoMorph @ 786b7f8 | digit tuples, labels lost (`scripts/morphe.py:123,150`) | `<pkg>_<ver>_patched.apk` | a stored version differs (`scripts/main.py:206`) | its own portal and email |
| nvbangg/builder-for-morphe @ 12d409a (our upstream) | digits before the first `-`, dev builds tie (`src/core/prebuilts.py:31`) | `<app>-<brand>-v<ver>-<arch>.apk` | upstream date is newer (`src/scripts/matrix.py:160`) | Obtainium on GitHub releases |
| krvstek/uni-apks @ 4c6175a | `is_newer_version` (`src/scripts/matrix.py:77`) | as upstream | also tracks stock per app (`matrix.py:244`) | as upstream |
| j-hc/revanced-magisk-module @ 3379efd | `sort -V` before `-` (`utils.sh:264`) | release = previous + 1 (`build.yml:44`) | bundle name in the stored notes (`utils.sh:213`) | module update JSON with a versionCode |
| FiorenMas/Revanced-And-Revanced-Extended-Non-Root @ e3ac3b9 | `sort -V` (`src/build/utils.sh:200`) | one release, versionless files | asset dates (`src/etc/ci.sh:22`) | README links |
| nxn94/AutoMorpheBuilder @ fa85517 | numeric, patch tag opaque (`check-existing-releases.js:127`) | `<app>-v<ver>-<patchTag>` | exact tag and input fingerprint (`build-fingerprint.js:34`) | Obtainium GitHub source |
| X-Abhishek-X/Morphe-Automated-Build-Scripts @ 6c28459 | leading ints (`scripts/check_updates.py:111`) | date in the release and the APK | stored state `!=` | release only |
| iamwaqargulzar/auto-morphe-apk-builds @ 5ea51a0 | numeric, labels become 0 (`tool/util.ts:73`) | `<app>-v<ver>-p<patch>` | tag exists (`tool/cli.ts:74`) | per-release `build.json` |
| nikhilbadyal/docker-py-revanced @ cc11b21 | PEP 440 (`src/manager/release_manager.py:25`) | every bundle and a digest in the APK name (`src/app.py:187`) | newer version or changed source | per-app pages and deep links, like ours |

Adopted: each APK records its own bundles (iamwaqargulzar `tool/release.ts:34`, docker-py `src/app.py:187`); pre-release labels ranked in the update version (docker-py). A rebuild that changes only build options stays invisible to phones here (j-hc's and docker-py's naming avoids it), because the update version names the app and the patches only.
