"""Eclipse-specific detector: a coarse "honest victim has 0 peers"
heuristic for now. The real detector will check whether the honest node's
peer count never reaches its configured `maxpeers` while the attacker is
active.

We rely on per-service log lines like `peers=…` or `Peer count:` which
Geth writes. This is intentionally minimal — the real detector belongs
to Phase 6 follow-up work and must live entirely in this file.
"""
from __future__ import annotations
import re
from pathlib import Path

PEERS_RE = re.compile(r"Peer count[:=]\s*(\d+)", re.IGNORECASE)


def detect(run_dir: Path, manifest: dict) -> dict:
    logs_dir = run_dir / "logs"
    if not logs_dir.is_dir():
        return {"name": "eclipse_divergence", "alarm": False,
                "evidence": "no logs dir"}
    zero_peers_seen = False
    sample_lines = []
    for p in logs_dir.iterdir():
        if "attacker" in p.name:
            continue
        if not (p.name.startswith(("erl_", "honest", "el1", "bootnode"))
                or "victim" in p.name):
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        for m in PEERS_RE.finditer(text):
            if int(m.group(1)) == 0:
                zero_peers_seen = True
                sample_lines.append(f"{p.name}:0 peers")
                break
    return {
        "name": "eclipse_divergence",
        "alarm": zero_peers_seen,
        "latency_s": None,
        "evidence": "; ".join(sample_lines[:5]) if sample_lines
                    else "no zero-peer samples",
    }