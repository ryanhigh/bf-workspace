"""BunnyFinder-specific detector.

Mirror of the heuristic the bf_workspace/runtest.sh uses to detect a
strategy firing: scan the honest beacon (beacon2) log for the reorg
events emitted when the attacker rewrites history.

This detector deliberately ignores attacker1 logs and only flags honest
nodes, so it cannot be tricked by the attacker itself logging 'reorg'.
"""
from __future__ import annotations
import re
from pathlib import Path

RE = re.compile(r"newSlot=(\d+)|oldSlot=(\d+)|reorg", re.IGNORECASE)


def detect(run_dir: Path, manifest: dict) -> dict:
    logs_dir = run_dir / "logs"
    if not logs_dir.is_dir():
        return {"name": "bunnyfinder_reorg", "alarm": False,
                "evidence": "no logs dir"}
    hits = []
    for p in logs_dir.iterdir():
        # only honest beacon services, NOT attacker1
        if "attacker" in p.name:
            continue
        if "beacon" not in p.name and "honest" not in p.name:
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        if "reorg" in text.lower():
            for line in text.splitlines():
                if "reorg" in line.lower():
                    hits.append(line[:300])
    return {
        "name": "bunnyfinder_reorg",
        "alarm": bool(hits),
        "latency_s": None,
        "evidence": f"{len(hits)} reorg lines" if hits else "no reorg lines",
    }