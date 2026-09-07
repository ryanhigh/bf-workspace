#!/usr/bin/env python3
"""`make doctor` — host + artefact + capability check.

Exits 0 if every required dependency is present and exits non-zero with a
short failure summary if not. Captures evidence into docs/STATUS.md.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "controller"))

from prefix import PREFIX  # noqa: E402

REQUIRED_TOOLS = ["docker", "python3"]
REQUIRED_PY = []  # nothing yet — pure-stdlib controller on purpose
REQUIRED_IMAGES_BY_PROFILE = {
    "pos-baseline": ["ethereum/client-go:latest", "sigp/lighthouse:latest",
                     "ethpandaops/ethereum-genesis-generator:6.1.2",
                     "protolambda/eth2-val-tools:latest"],
    "bunnyfinder": ["tscel/geth:v1.13-base-v5", "tscel/bf.prysm:v5.2.0",
                    "tscel/bunnyfinder:latest", "tscel/prysmctl:v5.2.0",
                    "mysql:latest"],
    "eclipse": ["ethereum/client-go:latest"],
    "gethlighting-legacy": ["ethereum/client-go:latest"],
}


def sh(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, check=False)
        return out.returncode, out.stdout, out.stderr
    except FileNotFoundError:
        return 127, "", f"missing: {cmd[0]}"
    except Exception as exc:
        return 1, "", str(exc)


def has_image(image: str) -> bool:
    rc, out, _ = sh(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    return rc == 0 and out.strip().startswith("sha256:")


def main() -> int:
    failures = []
    print(f"== doctor ==")
    print(f"project_root: {ROOT}")
    print(f"docker_resource_prefix: {PREFIX}")

    # 1. required binaries
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            failures.append(f"missing tool: {tool}")
        else:
            print(f"OK  tool: {tool} ({shutil.which(tool)})")

    # 2. docker daemon
    rc, _, err = sh(["docker", "version", "--format", "{{.Server.Version}}"])
    if rc != 0:
        failures.append(f"docker daemon not reachable: {err.strip()}")
    else:
        print(f"OK  docker daemon reachable")

    # 3. python deps
    for mod in REQUIRED_PY:
        try:
            __import__(mod)
            print(f"OK  python module: {mod}")
        except ImportError:
            failures.append(f"missing python module: {mod}")

    # 4. artefact path (BunnyFinder)
    bf = Path("/data/DeAtkVer/Bunnyfinder/bf_workspace")
    if not bf.is_dir():
        failures.append(f"BunnyFinder artefact not found: {bf}")
    else:
        print(f"OK  BunnyFinder artefact: {bf}")

    # 5. disk space
    rc, out, _ = sh(["bash", "-lc",
                     "df -B1M /data | tail -1 | awk '{print $4}'"])
    free_mb = int(out.strip() or "0")
    print(f"disk free: {free_mb} MB on /data")
    if free_mb < 5_000:
        failures.append(f"disk space critically low (<5GB) on /data")

    # 6. required images per active profile
    profile = os.environ.get("ACTIVE_PROFILE", "pos-baseline")
    needed = REQUIRED_IMAGES_BY_PROFILE.get(profile, [])
    for img in needed:
        if has_image(img):
            print(f"OK  image: {img}")
        else:
            failures.append(f"missing image for profile {profile}: {img}")
            print(f"MISS image: {img}")

    # 7. emit a machine-readable summary
    summary = {
        "profile": profile,
        "free_mb": free_mb,
        "failures": failures,
        "ok": len(failures) == 0,
    }
    Path(ROOT / "docs" / "doctor.json").write_text(json.dumps(summary, indent=2))
    print(f"\nfailures: {len(failures)}")
    if failures:
        for f in failures:
            print(f"  - {f}")
        return 1
    print("doctor OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())