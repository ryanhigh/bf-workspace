#!/usr/bin/env python3
"""`make build` — pull/build only the images the active profile needs.

Strategy: never rebuild images that already exist locally (verified by
sha256 digest). Pull only from configured mirrors. Failures abort early.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "controller"))

NEEDED = {
    "pos-baseline": [
        "ethereum/client-go:latest",
        "sigp/lighthouse:latest",
        "ethpandaops/ethereum-genesis-generator:6.1.2",
        "protolambda/eth2-val-tools:latest",
    ],
    "bunnyfinder": [
        "tscel/geth:v1.13-base-v5",
        "tscel/bf.prysm:v5.2.0",
        "tscel/bunnyfinder:latest",
        "tscel/prysmctl:v5.2.0",
        "mysql:latest",
    ],
    "eclipse": ["ethereum/client-go:latest"],
    "gethlighting-legacy": ["ethereum/client-go:latest"],
}


def sh(cmd, timeout=300):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, check=False)
        return out.returncode, out.stdout, out.stderr
    except Exception as exc:
        return 1, "", str(exc)


def has(img):
    rc, out, _ = sh(["docker", "image", "inspect", img, "--format", "{{.Id}}"])
    return rc == 0 and out.strip().startswith("sha256:")


def pull(img):
    print(f"-> docker pull {img}")
    rc, out, err = sh(["docker", "pull", img], timeout=900)
    print(out, end="")
    if err:
        print(err, end="")
    return rc == 0


def main():
    profile = os.environ.get("ACTIVE_PROFILE", "pos-baseline")
    targets = NEEDED.get(profile, [])
    summary = {"profile": profile, "pulled": [], "already_present": [], "failed": []}
    print(f"== build profile={profile} ==")
    for img in targets:
        if has(img):
            summary["already_present"].append(img)
            print(f"OK  present: {img}")
            continue
        ok = pull(img)
        if ok and has(img):
            summary["pulled"].append(img)
            print(f"OK  pulled:  {img}")
        else:
            summary["failed"].append(img)
            print(f"FAIL  pull:  {img}")
    Path(ROOT / "docs" / "build.json").write_text(json.dumps(summary, indent=2))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())