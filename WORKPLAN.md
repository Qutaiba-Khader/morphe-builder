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

## Phase 10 — website redesign (2026-09-21)

- The website follows the README: a hero in the banner's colours (with its three app tiles and
  an **Add every app to Obtainium** button), then **Download** with a Stable and a Pre-release
  list (green / violet, each app a row with Download and Add to Obtainium buttons and an
  All versions drawer that also shows the package), then **Install** in three steps,
  **Stable or pre-release?**, and **Catalog and API** as two tabs at the bottom.
- Type: Bricolage Grotesque for headings and app names, the system font for body text (Roboto
  on Android). Buttons are at least 48 px tall; the green is `#15803d` so white text passes
  AA; light and dark themes; reduced motion respected.
- The Obtainium endpoint pages and the add-every-app page share the hero look (inline CSS, no
  external files). Each endpoint still holds exactly one APK link.
- Checked with the flow test (`SITE_DIR=site/static` runs the local page against the live API)
  and screenshots at 1280 px and 390 px, light and dark. The screenshots caught a literal
  "null" on every card (DOM `append(null)`); the flow test's first check for it could not
  see it, because the text node is glued to its neighbours ("All versionsnull"), so it now
  walks the text nodes and was proven to fail on the buggy code.

## Phase 11 — install problems reported from the phone (2026-09-22)

- *"The app source is 'qutaiba-khader.github.io' but the release package comes from
  'github.com'"* is Obtainium's APK-origin check (`apps_provider_install.dart`: it compares the
  root host of the app page with the APK's and asks once per install unless *Don't show again*
  is ticked). Expected here: the page is on Pages, the APK in GitHub releases. Documented in the
  README, on the website and on the add-every-app page. Cancel aborts the install.
- *"Conflict"* is Android's `STATUS_FAILURE_CONFLICT` (a downgrade reports *Invalid* instead):
  a different signing key on the same package, or a clashing provider or permission. All eight
  published APKs verify with this repository's key (`apksigner`) and the stable and pre-release
  builds share no package, provider authority or permission, so the copy already on the phone
  came from elsewhere (Morphe Manager or another builder). Documented; the fix is one uninstall.
- The same check found one broken artifact: the 26.09.20-morphe-dev YouTube Experimental was
  built before the Clone-app fix and declared `app.morphe.android.youtube`, so it replaced stable
  YouTube. Removed from that release (notes say why). The flow test now checks every APK link
  on the site, API, Obtainium configs, README and every Releases asset: it downloads, has the
  listed size, carries its version and the package of the app it is listed under. It failed on
  that asset before the removal and passes after.

## Phase 12 — compared with GROWNUPS/Morphe-Patcher-Web (2026-09-30)

That project is a self-hosted web patcher (you bring the APK, it patches on your server). This
one builds and publishes on GitHub. Case by case:

| Their case | Here |
|---|---|
| Newest CLI and patch bundle pulled automatically | same: CLI and bundle resolved to `latest` / `dev` on every build (CLI 1.17.0, patches 1.45.0-dev.20 on 2026-09-29) |
| Recommended / compatible / experimental version grading | the builder always takes the newest version the patches support (`list-versions`, `-x` for the pre-release channel), so every build is the "optimal target" |
| `--striplibs` per architecture | upstream passes `--striplibs arm64-v8a,armeabi-v7a` for `all` builds and the single arch otherwise |
| Split APKs | APKMirror `.apkm` bundles: the base APK is extracted (`_extract_base_apk`) |
| Stock APK authenticity | stronger here: the stock APK's signature is checked against `sig.txt` before patching |
| Persistent keystore, fingerprint shown | same key every build; **added**: the certificate SHA-256 is read from every APK, published (API `signing_cert_sha256`, README, website) and enforced — the Site run fails and publishes nothing if a build carries another key (repo variable `SIGNING_CERT_SHA256`). A key change is exactly what makes phones report "Conflict". |
| Shows which patch bundle version is active | **added**: each build records the patch bundle(s) and CLI from its release notes (`patches`, `cli` in the API), shown on the cards, in the version history and in the README |
| `--continue-on-error` | deliberately not used: a patch that fails fails the build instead of shipping an APK silently missing it |
| Webhook notifications (Discord/ntfy/Gotify) | upstream sends Telegram when `TELEGRAM_*` secrets are set; GitHub release watching and Obtainium cover the rest |
| Branding on/off, custom app name | `patcher-args` per app (the pre-release twins use it) |
| Web upload, URL import, hot folder, job queue, live log stream, custom `.mpp` upload | not applicable: builds run on GitHub Actions, logs are the Actions logs, custom bundles are a line in `config.toml` |
| LAN-only security notice | nothing here accepts input; the site is static |

## Phase 13 — Obtainium sees patch-only rebuilds (2026-10-05)

- Reported: new patch releases, no update in Obtainium. Cause: Obtainium tracked the APP version
  from the file name, and most rebuilds keep it (YouTube 21.16.256 from patches 1.44.0 to 1.45.0;
  YouTube Experimental 21.39.522 from 1.45.0-dev.17 to 1.46.0-dev.2).
- Fix: every endpoint page carries `<meta name="build-version" content="21.16.256+p1.45.0">` (app
  version + patch bundle). The Obtainium config reads it with `versionExtractWholePage`, and
  `versionDetection` is off, because the phone reports only `21.16.256` for every rebuild and
  reconciling with it would hide the update again. Obtainium treats `+…` on the remote side as a
  distinct build (`installedMatchesRemote`); the flow test ports that function, agrees with all
  24 of Obtainium's own test cases, and checks for every app that a patch-only rebuild counts as
  an update while the same build does not.
- Apps already added keep their old settings on the phone: remove and re-add them once.
- Also seen: CI #20 (2026-10-04) Reddit Experimental failed — APKMirror had only DPI-limited
  bundles of 2026.40.0 (120-480 dpi) at build time; the builder accepts `nodpi`/`anydpi`/`*-640dpi`.
  A 120-640 dpi bundle was posted afterwards.

## Phase 14 — dev channel stuck on an old dev bundle (2026-10-10)

- Found in the check: the dev builds used patches 1.47.0-dev.9 while dev.10–dev.14 were already
  out. Two causes, both in the builder code that comes from upstream:
  - `src/core/prebuilts.py` `_ver_key` compared only the part before the first `-`, so every
    `1.47.0-dev.N` tied and `max()` returned whichever GitHub listed first (dev.9; GitHub does not
    list releases newest-first).
  - `src/scripts/matrix.py` decided "is there something new" from the FIRST release in that list
    (`per_page=1`), i.e. dev.9's date, so after one dev.9 build it would never build again until
    a release sorted above it.
- Fix: `_ver_key` orders `(numbers, final-or-pre, pre-release number)` — dev.14 > dev.9 and the
  final 1.47.0 > 1.47.0-dev.N, app versions unchanged; the dev update check takes the newest
  release by `published_at` over 100 releases; the dev list reads 100 releases.
  `tools/gen_catalog.py` mirrors the same key. Proof: the builder's own check run locally said
  `[]` before and `["morphe-dev"]` after; the key picks v1.47.0-dev.14 from the real list.
- Both files are now in the repository variable `IGNORE_SYNC_FILES`, so the daily upstream sync
  keeps our version (sync.yml restores ignored files after every merge). Upstream (nvbangg
  `builder-for-morphe`) still has the old code; any later upstream change to these two files is
  not taken automatically — compare by hand when upstream touches them.

## Phase 15 — "no update appeared in Obtainium" (2026-10-10)

- Replayed Obtainium's OWN code (Flutter 3.47.7 test on CT 200, Obtainium af286fa: the
  `obtainium://app/` import → `appFromStoredJson`, `extractVersion`, `reconcileTrackedVersion`,
  `isAppUpdateable`) on the real README links and the real endpoint pages, yesterday vs today:
  - links from 2026-10-05 on (version detection off, version read from the page): all four
    apps show the update (`21.40.161+p1.47.0-dev.9` → `+p1.47.0-dev.14`, also when the app was
    installed outside Obtainium), and no badge once the newest build is installed.
  - links from before 2026-10-05 (version from the APK file name, detection on): yesterday and
    today both read `21.40.161` → never an update for a patch-only rebuild.
- So an app added before 2026-10-05 must be re-imported once: tapping its button again replaces
  the stored settings (`import` → `saveApps` by package id, installed app kept). README and the
  website now say how to tell (the version shown has `+p…` or not) and what to tap.
- Not done: renaming release assets so even old settings would read the patch version — it
  would break existing download links and every name parser for a one-time phone action.

## Phase 16 — Obtainium showed "App" by "qutaiba-khader.github.io" (2026-10-10)

- Cause, in Obtainium's own code: its HTML source names every app "App" and gives the page's host
  as author (`html.dart` `AppNames(uri.host, tr('app'))`); `source_provider.dart getApp` keeps a
  name only if the app already has one and REPLACES the author on every update check. Replayed
  in Flutter on the real links (import + a real update check against the live pages): before,
  the author became "qutaiba-khader.github.io" after the first check on all four apps, and an
  app added through the add screen became "App"; after, all four keep their name and author.
- Fix: each link's settings carry Obtainium's per-app overrides `appName` and `appAuthor`
  (App.finalName/finalAuthor win over the source). Version text unchanged
  (`21.40.161+p1.47.0-dev.14`).
- Apps already added keep their stored settings: tap the button again and Import once (or set
  the name under the app's settings by hand).

## Phase 17 — "still no update after adding _all.html" (2026-10-10)

Replayed with Obtainium v1.6.17's own code (import → refresh → badge, real live pages):
- import records the installed version Android reports (versionDetection off does not copy the
  latest into "installed"); after the refresh an installed older build is OFFERED the update
  (YouTube dev 21.40.161 or 21.39.522, Reddit dev 2026.40.0, YouTube 21.16.256, Reddit 2026.24.0).
- an app that is not installed shows Install, never Update — the owner's Reddit Experimental
  entry was "Not installed".
- YouTube stable with a NEWER installed versionName (e.g. 21.38.123 from the mis-packaged
  2026-09-20 dev build) gets no update: Obtainium hides downgrades.
- `_all.html` pasted into Add App → NoReleasesError (harmless); a per-app page pasted there →
  an "App" entry with a hash version (works, but no name/settings). README + site say so.
