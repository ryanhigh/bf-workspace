#!/usr/bin/env python3
"""Phase 7 repeat runner — run one scenario N times, capture the key
observable each round, and write a repeat-summary.json proving the flow
is reproducible.

Usage:
  python3 controller/repeat_run.py <profile> <scenario> <rounds> [extra...]

The observable differs per profile (detected from profile name):
  eclipse*          -> victim net_peerCount (expects >= attacker count)
  gethlighting*     -> victim eth_blockNumber advancing (sync works)

Each round uses a fresh run_id (<scenario>-repeat-<i>). We drive run.py
in subprocess, then sample the observable live before teardown via a
small docker-exec probe. Because teardown happens inside run.py, we
instead parse the compose.log after the fact for the strongest evidence.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/data/DeAtkVer/ethereum-replay-lab")
sys.path.insert(0, str(ROOT / "controller"))
from common import sh  # noqa: E402


def run_one(profile: str, scenario: str, rid: str, wait: str) -> dict:
    env = {
        **os.environ,
        "ACTIVE_PROFILE": profile,
        "ACTIVE_SCENARIO": scenario,
        "RUN_ID": rid,
        "SKIP_DOCTOR": "1",
        "ECLIPSE_WAIT": wait,
    }
    t0 = time.time()
    proc = subprocess.run(
        ["python3", str(ROOT / "controller" / "run.py"),
         str(ROOT), "--profile", profile, "--scenario", scenario,
         "--run-id", rid, "--skip-doctor", "--timeout-mult", "1.0"],
        capture_output=True, text=True, env=env, timeout=900,
    )
    elapsed = time.time() - t0
    run_dir = ROOT / "runs" / rid
    manifest = None
    if (run_dir / "manifest.json").is_file():
        manifest = json.loads((run_dir / "manifest.json").read_text())
    # Extract the strongest evidence from compose.log
    evidence = _extract_evidence(run_dir, profile)
    return {
        "run_id": rid,
        "rc": proc.returncode,
        "elapsed_s": round(elapsed, 1),
        "manifest": manifest is not None,
        "evidence": evidence,
    }


def _extract_evidence(run_dir: Path, profile: str) -> dict:
    log = run_dir / "logs" / "compose.log"
    if not log.is_file():
        return {"error": "no compose.log"}
    text = log.read_text(errors="replace")
    out: dict = {}
    # eclipse: count inbound peers accepted by victim
    if "eclipse" in profile:
        import re
        out["victim_inbound_peers"] = len(re.findall(
            r"victim-1.*Adding p2p peer.*conn=inbound", text))
        out["victim_staticdial"] = len(re.findall(
            r"victim-1.*Adding p2p peer.*conn=staticdial", text))
        m = re.search(r"Looking for peers\s+peercount=(\d+)", text)
        if m:
            out["last_peercount"] = int(m.group(1))
    # gethlighting: block sync evidence
    if "gethlighting" in profile:
        import re
        out["mined_blocks"] = len(re.findall(r"mined potential block", text))
        out["victim_imported_segments"] = len(re.findall(
            r"victim-1.*Imported new chain segment", text))
        m = re.search(r"victim-1.*Imported new chain segment.*number=(\d+)", text)
        if m:
            out["victim_last_block"] = int(m.group(1))
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: repeat_run.py <profile> <scenario> <rounds> [wait_seconds]",
              file=sys.stderr)
        return 2
    profile, scenario, rounds = argv[0], argv[1], int(argv[2])
    wait = argv[3] if len(argv) > 3 else "60"

    results = []
    for i in range(1, rounds + 1):
        rid = f"{scenario}-repeat-{i}"
        print(f"\n=== round {i}/{rounds}  rid={rid} ===", flush=True)
        r = run_one(profile, scenario, rid, wait)
        results.append(r)
        print(f"  rc={r['rc']} elapsed={r['elapsed_s']}s evidence={r['evidence']}",
              flush=True)

    summary = {
        "profile": profile,
        "scenario": scenario,
        "rounds": rounds,
        "results": results,
    }
    out = ROOT / "docs" / f"repeat-{profile}-{scenario}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))