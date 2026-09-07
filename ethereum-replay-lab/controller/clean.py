#!/usr/bin/env python3
"""`make clean` — remove ONLY this project's containers, networks, volumes.

We rely on the project prefix (`erl_`) so that no other project is
touched. If RUN_ID is set, we only clean that run; otherwise we clean
every `erl_*` container / network / volume present.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ERL_ROOT", "/data/DeAtkVer/ethereum-replay-lab"))
sys.path.insert(0, str(ROOT / "controller"))
from prefix import PREFIX


def sh(cmd, timeout=120):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, check=False)
        return out.returncode, out.stdout, out.stderr
    except Exception as exc:
        return 1, "", str(exc)


def main() -> int:
    rid = os.environ.get("RUN_ID", "").strip()
    profile = os.environ.get("ACTIVE_PROFILE", "").strip()
    include_volumes = os.environ.get("CLEAN_INCLUDE_VOLUMES", "") == "1"

    project_filter = f"{PREFIX}{profile}" if profile else PREFIX
    rid_filter = rid or None

    # 1. stop + remove containers
    rc, out, _ = sh(["docker", "ps", "-a", "--format", "{{.Names}}"])
    targets = []
    for ln in out.splitlines():
        name = ln.strip()
        if not name.startswith(project_filter):
            continue
        if rid_filter and rid_filter not in name:
            continue
        targets.append(name)
    print(f"containers to remove ({len(targets)}): {targets}")
    for name in targets:
        sh(["docker", "rm", "-f", name], timeout=60)

    # 2. remove networks
    rc, out, _ = sh(["docker", "network", "ls", "--format", "{{.Name}}"])
    nets = []
    for ln in out.splitlines():
        name = ln.strip()
        if not name.startswith(project_filter):
            continue
        if rid_filter and rid_filter not in name:
            continue
        nets.append(name)
    print(f"networks to remove ({len(nets)}): {nets}")
    for name in nets:
        sh(["docker", "network", "rm", name], timeout=60)

    # 3. (optional) remove volumes
    if include_volumes:
        rc, out, _ = sh(["docker", "volume", "ls", "--format", "{{.Name}}"])
        vols = []
        for ln in out.splitlines():
            name = ln.strip()
            if not name.startswith(project_filter):
                continue
            if rid_filter and rid_filter not in name:
                continue
            vols.append(name)
        print(f"volumes to remove ({len(vols)}): {vols}")
        for name in vols:
            sh(["docker", "volume", "rm", name], timeout=60)

    # 4. optionally remove the runs/<rid> directory
    if rid and (ROOT / "runs" / rid).is_dir():
        if os.environ.get("CLEAN_INCLUDE_RUN_DIR", "") == "1":
            import shutil
            shutil.rmtree(ROOT / "runs" / rid, ignore_errors=True)
            print(f"removed runs/{rid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())