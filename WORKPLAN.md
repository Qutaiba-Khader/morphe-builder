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

via the owner's skill and MCP discovery service. Also search for error-prevention
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
      An offline backup of the key and its password is held by the owner, outside this repo.
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

## Phase 7 — stable and pre-release side by side (2026-09-20 → 2026-09-21)

- [x] Each app has a pre-release twin (`*-Experimental`, brand `morphe-dev`) built from the patch
      source's newest dev bundle; it releases, tracks and updates separately.
- [x] Every twin has its own package, so both channels install at once:
      `app.morphe.android.youtube.dev`, `com.reddit.frontpage.morphe`. Verified by reading the
      package out of each built APK.
- [x] The YouTube twin first kept the stable package. Cause, read from the Morphe source:
      `GmsCore support` takes YouTube's package from `Clone app`'s `packageName` option
      (`setOrGetFallbackPackageName`) and only falls back to `app.morphe.android.youtube` while it
      is `Default` — and the name *had* been passed, but after the excludes, and the CLI binds a
      `-O` option to the `-e` it follows. It landed on another patch. Passing it straight after
      `-e 'Clone app'` fixed it. (An interim note claiming YouTube could not be cloned was wrong
      and is gone.)
- [x] Parity: every app and channel gets the same site card, API entries, Obtainium endpoint,
      one-tap badge and README row. The README's Apps table is now generated
      (`tools/gen_readme.py`, the `readme` job in `site.yml`), so a new app or channel appears
      there after its first build with no hand edit.
- [x] The site now also redeploys after a standalone **Build APKs** run, not only after **CI**.
- [x] Asset names are split against `config.toml` rather than guessed, because a brand can
      contain a hyphen (`morphe-dev`).

## Phase 8 — full review with /test-skills (2026-09-21)

Four independent review lanes (oracle harnesses, consumer/contract sweep, flow and taint
tracing, differential and falsification) plus a static toolchain pass (ruff, actionlint,
node --check). 2 HIGH, 6 MEDIUM and a tail of LOW findings, all verified before fixing:

- **HIGH — the "Add every app" link never worked.** Obtainium's redirect service only forwards
  `obtainium://app/` and `obtainium://add/`; the bulk `obtainium://apps/` link landed on
  "Invalid URL". The app itself handles `apps` (its `home.dart`), so the link is now our own
  page, `obtainium/_all.html`.
- **HIGH — a rebuild window published a stale or partial site.** CI re-drafts one brand's
  release while the others stay published; the old guard fired only when *zero* apps were left,
  so a Site run in that window published the previous build (once, one whose package was
  shared with stable YouTube) or dropped a whole brand. `gen_site.py` now asks the Actions API
  whether CI or Build APKs is running and, if so, publishes nothing (`skip=true`, exit 0 — no
  red run); without that permission it compares the live site's tags with the published ones.
- MEDIUM: multi-arch apps got an arm64-only Obtainium entry → per-arch `variants`, buttons and
  badges. The catalog ignored `version = "dev"` → sources are catalogued per version spec,
  resolved exactly as the builder does. 228 of 383 catalog packages listed "Version codes:"
  lines as versions → parser fixed. App ids came from `app-name`, so two tables sharing one
  merged → ids come from the table name. The package id could fall back to a hand-written
  value → it now only ever comes from the APK (or the live record of the same file). A
  hand-typed catalog count had drifted → generated.
- Documented, not changed: Obtainium does not see patch-only rebuilds (it tracks the app
  version); changing that needs version detection off and a phone test.
- **Found only by testing the fixes live — the site stopped updating on new releases.**
  `actions/deploy-pages` uses the commit SHA as the deployment id, and Pages keeps serving the
  first artifact deployed for a SHA while reporting success (actions/deploy-pages#383; a
  non-SHA build version is rejected with 404). A release brings no commit, so every scheduled
  build was "deployed" and never shown — CI #7 built YouTube 21.16.256 and the API kept
  serving 21.13.164. All four review lanes had passed that hop on its green status. The Site
  workflow now pushes `_site` to a `gh-pages` branch (a new commit whenever content changes;
  timestamp-only changes are ignored) and Pages serves that branch.
- The flow test now reads each APK's real package and compares it with the Obtainium id,
  checks ids are unique, compares app names with `config.toml`, checks each README row's version
  and download link, and opens the bulk-add page.

## Phase 9 — README redesign (2026-09-21)

- The README now opens with what a phone user needs, in order: a banner
  (`.github/readme/banner.svg`), the Download tables, three install steps (MicroG-RE for
  YouTube), and a stable-or-pre-release comparison. Everything technical follows under
  **How it works**, with the deepest parts folded.
- The Download tables are still generated (`tools/gen_readme.py`): one table per channel with
  two columns, so the Download and Add to Obtainium buttons sit side by side on a wide screen
  and wrap under each other on a phone. With four columns they shrank and the Obtainium column
  was cut off at 390 px. Packages, release tags and endpoints moved to a folded table.
- Checked by rendering the pushed README on github.com at 1280 px and 390 px, light and dark;
  the flow test also checks each app sits in its channel's table and the package table.
