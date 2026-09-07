#!/usr/bin/env python3
"""`make collect` — normalise raw container logs into events.jsonl.

For now, this is a no-op because the runner already writes structured
events. We keep the verb so future per-container log parsers have a place
to land their output (a `events.from_logs` step that post-processes the
per-service logs/*.log dumps produced by run.py).
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ERL_ROOT", "/data/DeAtkVer/ethereum-replay-lab"))


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
    events = run_dir / "events.jsonl"
    if not events.exists():
        events.write_text("")
    # Summarise log file sizes
    log_dir = run_dir / "logs"
    summary = {"run_id": rid, "profile": profile, "logs": []}
    if log_dir.is_dir():
        for p in sorted(log_dir.iterdir()):
            summary["logs"].append({"name": p.name, "size": p.stat().st_size})
    (run_dir / "collect.json").write_text(json.dumps(summary, indent=2))
    print(f"collect: {len(summary['logs'])} log files for run_id={rid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())