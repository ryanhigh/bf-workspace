"""Minimal baseline detector: flags containers that exited non-zero
or that crashed/Restarted inside the per-service log dump.

This is intentionally dumb. It is the floor under which every other
detector must sit; if the baseline fires, the experiment is invalid.
"""
from __future__ import annotations
import json
from pathlib import Path


def detect(run_dir: Path, manifest: dict) -> dict:
    logs_dir = run_dir / "logs"
    if not logs_dir.is_dir():
        return {"name": "baseline", "alarm": False, "evidence": "no logs dir"}
    crashed: list[str] = []
    for p in logs_dir.iterdir():
        if not p.is_file() or not p.name.endswith(".log"):
            continue
        if not p.name.startswith(("erl_", "attacker", "beacon", "execute",
                                  "bootnode", "el1", "cl1", "vc1", "honest")):
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        # very crude heuristics; we will tune per-profile later
        for marker in ("ERRO fatal", "level=eror", "panic:",
                       "FATAL", "level=fatal", "Restarting"):
            if marker in text:
                crashed.append(f"{p.name}:{marker}")
                break
    return {
        "name": "baseline",
        "alarm": bool(crashed),
        "latency_s": None,
        "evidence": "; ".join(crashed) if crashed else "no crashes",
    }