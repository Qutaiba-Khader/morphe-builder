"""morphe-builder (owner, 2026-11-18): nothing the build uploads may hold a secret.

Usage in a workflow step that has the secrets in its env:
  python3 tools/leak_guard.py mask              # tells GitHub to mask every encoded form of each secret
  python3 tools/leak_guard.py check FILE|DIR... # a file holding a secret (in any form) is deleted; exit 1

It never prints a secret: only the file's name and which secret (by its variable name) was found.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.scrapers.gplay import _SECRET_KEYS, secret_forms  # noqa: E402

KEYS = (*_SECRET_KEYS, "KEYSTORE_PASS", "KEYSTORE_BASE64")
BINARY = {".apk", ".apkm", ".apks", ".xapk", ".zip"}


def secrets() -> dict[str, str]:
    return {k: os.environ[k].strip() for k in KEYS if os.environ.get(k, "").strip()}


def mask() -> int:
    # With "debug logging" on a re-run, GitHub echoes workflow commands, so ::add-mask:: would print the encoded forms:
    # refuse, and the build step (which runs this first) stops before goopdl or anything else sees a secret.
    if os.environ.get("RUNNER_DEBUG") == "1" and secrets():
        print("::error title=Debug logging is on::the Google Play secrets are not used in a debug run; re-run without debug logging")
        return 1
    for value in secrets().values():
        for form in secret_forms(value):
            print(f"::add-mask::{form}")
    return 0


def files_of(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.is_file())
        elif p.is_file():
            out.append(p)
    return out


def check(paths: list[str]) -> int:
    found = 0
    forms = {k: [f.encode() for f in secret_forms(v)] for k, v in secrets().items()}
    for f in files_of(paths):
        data = f.read_bytes()
        # inside an APK only the Google account's secrets are looked for: a short password could match binary data
        # by chance and delete a good APK; release notes and logs are checked for every secret
        keys = _SECRET_KEYS if f.suffix.lower() in BINARY else tuple(forms)
        hits = sorted(k for k in keys if k in forms and any(x in data for x in forms[k]))
        if hits:
            found += 1
            f.unlink()
            print(f"::error title=Secret in an upload::{f} held {', '.join(hits)}: deleted, it is not uploaded")
    if found:
        return 1
    print(f"leak guard: {len(files_of(paths))} files checked, no secret in any of them")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["mask"]:
        return mask()
    if argv[:1] == ["check"]:
        return check(argv[1:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
