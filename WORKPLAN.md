# Work plan — Qutaiba-Khader/morphe-builder

Fork of [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe)
(itself downstream of [krvstek/uni-apks](https://github.com/krvstek/uni-apks)), which patches
Android apps with [Morphe](https://morphe.software) patch bundles on GitHub Actions.
Nothing runs on private infrastructure — GitHub's hosted runners do the whole build.

## Standing rule — before every phase

**Before starting each phase, check the available skills and MCP servers and use whatever fits.**

    search_skills  "<keywords from the phase>"
    search_mcps    "<keywords from the phase>"
    load_skill     <top match>        # or get_mcp_info <server>

via the claude-radar MCP at `http://192.168.1.103:6580/mcp`. Also search for error-prevention
skills in the phase's domain. State which skills/MCPs will be used before proceeding. This is
not optional and not a one-off — it is repeated at the top of every phase, including reruns.

## Phases

### Phase 0 — repository
- [x] Fork into `Qutaiba-Khader/morphe-builder`, public, fork link kept so upstream `sync.yml` keeps pulling fixes.
- [x] Actions enabled, workflow token set to read/write.
- [x] Repo variable `IGNORE_SYNC_FILES` set so our own files survive an upstream sync.
- [x] Pages enabled with **GitHub Actions** as the source.

### Phase 1 — YouTube builds
- [x] `config.toml` cut to YouTube only; every other app kept in place as `enabled = false` examples.
- [x] Own signing key: BKS keystore, RSA-4096, alias `Morphe`, stored as the secrets
      `KEYSTORE_BASE64` / `KEYSTORE_PASS` / `KEYSTORE_ALIAS`. Upstream reads those env vars
      directly (`src/core/builder.py:231`, `src/core/patcher.py:161`) — no code change needed.
      Backup of the key and its password: `/root/.secrets/morphe-builder/` on the Proxmox host.
      **Losing it means every installed copy must be uninstalled before it can update again.**
- [x] One green CI run producing a signed `youtube-morphe-vXX-all.apk` in Releases.

### Phase 2 — easy to add apps and patch sources
- [x] `ADD.md` — the copy-paste recipe (an app is four lines, a patch source is one).
- [x] `config.toml` header pointing at it.
- [x] `tools/gen_catalog.py` + `.github/workflows/catalog.yml` — weekly and on demand, downloads
      each configured source's `.mpp` and runs `list-patches --with-packages --with-versions`,
      writing `data/catalog.json`: every source, the apps it can patch, the patch names, the
      compatible versions. This is what makes adding a source a lookup instead of a question.

### Phase 3 — GitHub Pages
- [x] `site/` — static, no framework, dark and light. One card per app with latest version,
      date, size, architecture and a download button; **All versions** expands the full history.
- [x] `.github/workflows/site.yml` — builds and deploys after every CI run, on a 6-hourly
      schedule, on demand, and when called by `catalog.yml`.

### Phase 4 — JSON API
- [x] The site's data files are the API, served from the same Pages origin (which sends
      `access-control-allow-origin: *`, so scripts and browsers can call it cross-origin):
      `api/index.json`, `api/latest.json`, `api/apps/<app>.json`, `api/catalog.json`.
      CDN-cached, no backend, and none of the 60-requests-per-hour limit of GitHub's own API.

### Phase 5 — verification
- [x] Flow-tracing code test from the real entry points (`main.py`, each workflow trigger)
      through to the published artefact, checking every feature is reachable and not just present.

## Verified 2026-09-20

Traced every entry point to its artefact, then confirmed each one by running it.

| Entry point | Reaches | Result |
|---|---|---|
| `ci.yml` (10:00 UTC / dispatch) | `build.yml` → `main.py` → release | `26.09.20-morphe`, `youtube-morphe-v21.13.164-all.apk`, 128.4 MB |
| `site.yml` (`workflow_run` after CI) | `gen_site.py` → `_site` → Pages | fired by itself after CI #1 and deployed |
| `site.yml` (dispatch, 6-hourly, `workflow_call`) | same | all four paths exercised |
| `catalog.yml` (weekly / dispatch) | `gen_catalog.py` → commit → calls `site.yml` | 8 sources, 359 packages, 0 failures |
| `index.html` → `app.js` | `api/*.json` on the same origin | 21/21 checks, no script errors |

Signing was verified against the artefact, not the config: the published APK reports
`CN=Morphe`, SHA-256 `7687718c8b2e…7603`, which is this repo's key and not the one bundled
upstream. The sha256 in `api/latest.json` matches the downloaded file.

Three defects the trace found, all fixed:

1. `gen_site.py` titled the app id, so the site read “Youtube”. It now takes the name from
   `config.toml`.
2. `catalog.yml` tested `git diff` on a path that is untracked on a fresh fork, so the very
   first catalog would never have been committed. It stages first, then diffs `--cached`.
3. A workflow called by `catalog.yml` checks out the commit that started the run, so the
   catalog it had just pushed was deployed one run late. `site.yml` now checks out `main`.

`tools/flow-test.mjs` re-runs the browser half of this against the live site at any time.

## Phase 6 — Reddit and Obtainium (2026-09-20)

- [x] Reddit enabled; `reddit-morphe-v2026.14.0-all.apk` published alongside YouTube.
      Enabling an app under an existing brand does not look "new" to the daily update check,
      so the first build needs **Build all apps** — now documented in the README and ADD.md.
- [x] Obtainium endpoints. Its GitHub source versions an app by the release **tag**, which here
      is a date, so it would announce an update on every release. Its HTML source runs
      `versionExtractionRegEx` over the APK link instead, which carries the real app version, so
      each app gets `obtainium/<id>.html` holding exactly one APK link, plus
      `api/obtainium.json` with a ready-made config, deep link and one-tap add URL. Settings key
      names were taken from Obtainium's own source (`lib/providers/source_provider.dart`,
      `lib/app_sources/html.dart`), not guessed, and Python's `re.escape` output is stripped of
      `\-` because Dart's RegExp rejects it in unicode mode.
- [x] `config.toml` gained an optional `package` per app — the Android package name the deep
      link needs.
- [x] Flow test extended to 35 checks, all passing against the live site, including decoding
      each deep link and running each version regex against the real filename.
- [x] README now documents the four schedules, every endpoint with an example response, and
      the Obtainium setup.

## Known characteristics

- The stock APK comes from APKMirror, which is behind Cloudflare. The build starts a bypass
  container on the runner; an occasional red run that passes on retry is normal.
- `FiorenMas/Revanced-And-Revanced-Extended-Non-Root` solves the same problem with two solvers
  (FlareSolverr on 8191 plus the same bypass container on 8000) and two extra APK sources
  (APKPure, and Google Play through an Aurora Store client). Those are the escape hatches if
  APKMirror alone proves unreliable here.
- Releases and the site are public.
