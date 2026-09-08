"""Unified profile adapter — single Adapter that runs any Strategy JSON.

Unlike the eclipse / bunnyfinder specific adapters, this one:
  - does NOT define its own docker compose
  - takes a pre-existing run dir + strategy JSON
  - drives the executor against whatever ctx_provider the caller supplies

The point of this adapter is to make the action pool + executor the
*only* code path for any future attack. Profile-specific setup moves
to a thin wrapper (`unified_eclipse.py`, `unified_bunnyfinder.py`) that
knows how to bring up the right containers but then defers execution
to this adapter.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from common import append_event
from profiles.base import BaseAdapter
from profiles.unified_action import (Strategy, UnifiedExecutor,
                                       pool_snapshot, get as get_action)


class Adapter(BaseAdapter):
    profile = "unified"

    SUPPORTED_SCENARIOS = ("custom",)

    def meta(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "scenario": self.scenario,
            "action_pool": pool_snapshot(),
            "supported_scenarios": list(self.SUPPORTED_SCENARIOS),
        }

    def prepare(self) -> dict[str, Any]:
        # No compose to write here. The wrapper (eclipse / bunnyfinder)
        # already prepared the run dir. We only sanity-check that a
        # strategy file path was provided via env.
        strat_path = _env("UNIFIED_STRATEGY_JSON")
        if not strat_path:
            raise RuntimeError(
                "UNIFIED_STRATEGY_JSON must be set for unified profile")
        if not Path(strat_path).exists():
            raise RuntimeError(f"strategy not found: {strat_path}")
        return {
            "compose_files": [],
            "wait_seconds": int(_env("ECLIPSE_WAIT", "60")),
            "needs_mysql": False,
            "extra_compose_first": False,
            "source_case": strat_path,
            "source_case_sha256": _sha256(strat_path),
            "strategy": strat_path,
        }

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        strat_path = prepared["strategy"]
        strat = Strategy.from_json_file(Path(strat_path))
        append_event(self.run_dir, {
            "event_type": "unified.actions.scheduled",
            "strategy": strat.uid,
            "category": strat.category,
            "n_phases": len(strat.phases),
            "action_pool": pool_snapshot(),
        })
        # The ctx_provider is supplied by the wrapper via env hook;
        # see controller/run.py for the bridge.
        provider = _ctx_provider_factory()
        executor = UnifiedExecutor(
            ctx_provider=provider,
            log_sink=lambda kind, payload: (
                append_event(self.run_dir,
                            {"event_type": kind, **payload}), None
            )[1],
        )
        results = executor.run(strat)
        append_event(self.run_dir, {
            "event_type": "actions.done",
            "strategy": strat.uid,
            "n_actions": len(results),
            "n_ok": sum(1 for r in results if r["ok"]),
        })
        return {
            "strategy": strat.uid,
            "mode": "unified",
            "actions_run": [r["action"] for r in results],
            "results": results,
        }


def _env(name: str, default: str = "") -> str:
    import os
    return os.environ.get(name, default)


def _sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- ctx_provider factory (set by wrapper via env) ----
#
# The wrapper script writes a small Python file that builds the ctx dict
# from its containers, then sets UNIFIED_CTX_FACTORY=/path/to/factory.py.
# We exec that file and call its build_ctx(action) to get the per-action
# runtime context.

def _ctx_provider_factory():
    factory_path = _env("UNIFIED_CTX_FACTORY", "")
    if not factory_path or not Path(factory_path).exists():
        # No factory means no per-action ctx — actions that need docker
        # containers will fail, but control-flow actions still work.
        def _empty(action):
            return {}
        return _empty
    # Load the factory module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_unified_ctx_factory", factory_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_ctx