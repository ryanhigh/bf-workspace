"""Detector package — pluggable attack-detection interfaces.

The Phase 6 spec requires:
  - a swappable detector interface
  - a minimal baseline detector
  - relevant normal baselines (restart, peer churn, transaction burst,
    resource slowdown) included as control runs

Each detector module exposes:

    def detect(run_dir, manifest) -> dict:
        # returns
        # {
        #   "name": str,
        #   "alarm": bool,
        #   "latency_s": float | None,
        #   "evidence": str
        # }

`run_all_detectors` collects every detector in this package and runs them
on the same run.
"""
from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path
from typing import Any

PKG_DIR = Path(__file__).parent
DETECTORS: list[str] = [
    "baseline",         # always-on: flags containers that crashed / restarted
    "bunnyfinder_reorg",# flags honest-beacon "reorg" log entries
    "eclipse_divergence",# flags when honest nodes report no peers while
                        # the experiment is supposed to be in steady-state
]


def run_all_detectors(run_dir, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in DETECTORS:
        try:
            mod = importlib.import_module(f"detectors.{name}")
        except Exception as exc:
            results.append({"name": name, "alarm": False, "error": str(exc)})
            continue
        try:
            res = mod.detect(run_dir, manifest)
        except Exception as exc:
            res = {"name": name, "alarm": False, "error": str(exc)}
        if not isinstance(res, dict):
            res = {"name": name, "alarm": False, "evidence": "bad return"}
        results.append(res)
    return results


def iter_detector_modules():
    for m in pkgutil.iter_modules([str(PKG_DIR)]):
        if m.name.startswith("_"):
            continue
        yield m.name