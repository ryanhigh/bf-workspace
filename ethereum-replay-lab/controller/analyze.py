#!/usr/bin/env python3
"""`make analyze` — turn raw events + per-service logs into result.json.

Extracts mechanism-level evidence from the run's compose.log (peer
connections, block imports, block mining, invalid-tx rejection) and
emits the 6-layer judgement from the Phase 6 spec:

  1. experiment valid?
  2. strategy executed?
  3. mechanism observed?
  4. node-state impact?
  5. consensus/incentive impact?
  6. detector alarm? (pluggable detectors)

Everything here is a heuristic; it is explicitly NOT a detection model
and must not be read as one.
"""
from __future__ import annotations
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(os.environ.get("ERL_ROOT", "/data/DeAtkVer/ethereum-replay-lab"))


def _event_counts(events_path: Path) -> Counter:
    counts: Counter = Counter()
    if not events_path.exists():
        return counts
    with events_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            counts[ev.get("event_type", "unknown")] += 1
    return counts


def _extract_log_evidence(log_path: Path, profile: str) -> dict:
    if not log_path.is_file():
        return {}
    text = log_path.read_text(errors="replace")
    out: dict = {}
    if "eclipse" in profile:
        out["victim_inbound_peers"] = len(re.findall(
            r"victim-1.*Adding p2p peer.*conn=inbound", text))
        out["victim_staticdial_peers"] = len(re.findall(
            r"victim-1.*Adding p2p peer.*conn=staticdial", text))
    elif "gethlighting" in profile:
        out["mined_blocks"] = len(re.findall(r"mined potential block", text))
        out["victim_imported_segments"] = len(re.findall(
            r"victim-1.*Imported new chain segment", text))
        out["insufficient_funds_mentions"] = len(re.findall(
            r"insufficient funds", text, re.IGNORECASE))
    return out


def main() -> int:
    rid = os.environ.get("RUN_ID", "")
    profile = os.environ.get("ACTIVE_PROFILE", "")
    if not rid:
        print("RUN_ID required", file=sys.stderr)
        return 2
    run_dir = ROOT / "runs" / rid
    if not run_dir.is_dir():
        print(f"no such run: {run_dir}", file=sys.stderr)
        return 2

    events_path = run_dir / "events.jsonl"
    counts = _event_counts(events_path)
    manifest = {}
    if (run_dir / "manifest.json").is_file():
        manifest = json.loads((run_dir / "manifest.json").read_text())

    log_evidence = _extract_log_evidence(run_dir / "logs" / "compose.log",
                                          profile)

    # Layer 1 — experiment valid
    valid = counts.get("compose.up.done", 0) > 0 and counts.get("run.done", 0) > 0

    # Layer 2 — strategy executed (actions.done fired)
    strategy_executed = counts.get("actions.done", 0) > 0

    # Layer 3 — mechanism observed (profile-specific heuristic)
    mechanism = None
    if "eclipse" in profile:
        mechanism = log_evidence.get("victim_inbound_peers", 0) > 0
    elif "gethlighting" in profile and "tx-flood" in (manifest.get("scenario", "")):
        mechanism = log_evidence.get("insufficient_funds_mentions", 0) > 0 or \
                    counts.get("gethlighting.attacker.ready", 0) > 0
    elif "gethlighting" in profile:
        mechanism = log_evidence.get("mined_blocks", 0) > 0

    # Layer 6 — detectors
    try:
        sys.path.insert(0, str(ROOT / "controller"))
        from detectors import run_all_detectors
        detectors = run_all_detectors(run_dir, manifest)
    except Exception:
        detectors = []

    result = {
        "run_id": rid,
        "profile": profile,
        "event_counts": dict(counts),
        "log_evidence": log_evidence,
        "valid": valid,
        "strategy_executed": strategy_executed,
        "mechanism_observed": mechanism,
        "node_state_impact": None,
        "consensus_impact": None,
        "detectors": detectors,
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"analyze: {rid} valid={valid} strategy={strategy_executed} "
          f"mechanism={mechanism} evidence={log_evidence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())