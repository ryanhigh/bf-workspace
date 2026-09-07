#!/usr/bin/env python3
"""Common helpers used by every profile adapter and by run.py."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DEFAULT = Path("/data/DeAtkVer/ethereum-replay-lab")


def utc_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def gen_run_id(prefix: str = "") -> str:
    """Generate a unique run_id. Format: <prefix><unix_secs>-<8 hex bytes>.

    The 8 hex bytes come from /dev/urandom and make collisions practically
    impossible across calls even within the same second.
    """
    secs = int(dt.datetime.now().timestamp())
    rand = secrets.token_hex(4)
    if prefix and not prefix.endswith("-"):
        prefix = prefix + "-"
    return f"{prefix}{secs}-{rand}"


def sh(cmd: list[str], timeout: int = 60, env: dict[str, str] | None = None,
      cwd: str | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            check=False, env=env, cwd=cwd,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", f"missing: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as exc:
        return 1, "", str(exc)


def project_paths(root: Path, profile: str, scenario: str, run_id: str):
    """Return (run_dir, compose_dir, compose_file)."""
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    run_dir = runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_manifest(run_dir: Path, payload: dict[str, Any]) -> Path:
    p = run_dir / "manifest.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return p


def append_event(run_dir: Path, event: dict[str, Any]) -> Path:
    p = run_dir / "events.jsonl"
    event = {"ts_utc": utc_iso(), **event}
    with p.open("a") as fh:
        fh.write(json.dumps(event) + "\n")
    return p


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def file_copy_readonly(src: Path, dst: Path) -> None:
    """Copy a file or directory, marking the result read-only.

    We do this so that a buggy profile cannot silently mutate upstream
    artefacts under /data/DeAtkVer/Bunnyfinder/.
    """
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # chmod -R a-w
    subprocess.run(["chmod", "-R", "a-w", str(dst)], check=False)