"""Unified-DSL wrapper for the Eclipse attack.

Subclasses the original `eclipse.Adapter` so that container topology,
compose files, entrypoint scripts and the compose project name are all
*identical* to the original eclipse profile (no naming drift). The only
difference is `run_actions()`: instead of the old eclipse-specific DSL
loop, it loads a unified Strategy JSON and drives it through the single
`UnifiedExecutor` in `profiles/unified_action.py`.

This is the proof-point that the unified action pool can run an Eclipse
attack with the same executor code path as a BunnyFinder attack.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

from common import append_event
from profiles.eclipse import Adapter as EclipseAdapter
from profiles.unified_action import (Strategy, UnifiedExecutor, ACTION_POOL)


class Adapter(EclipseAdapter):
    # Do NOT override `profile` — we deliberately inherit "eclipse" so
    # that project_name() / container names / compose network all match
    # the original eclipse adapter exactly.
    profile = "eclipse"

    def meta(self) -> dict[str, Any]:
        m = super().meta()
        m["executor"] = "unified"
        m["action_pool_size"] = len(ACTION_POOL)
        return m

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        strat_path = os.environ.get(
            "ECLIPSE_UNIFIED_STRATEGY",
            str(Path(__file__).parent.parent.parent
                 / "profiles" / "unified" / "strategies"
                 / f"{self.scenario}.json"),
        )
        if not Path(strat_path).exists():
            raise FileNotFoundError(
                f"unified strategy not found: {strat_path}. "
                f"Set ECLIPSE_UNIFIED_STRATEGY=/path/to/strategy.json")

        n_atk = prepared.get("n_attackers", 0)
        pname = self.project_name()          # e.g. erl_eclipse-<run_id>
        victim_container = f"{pname}-victim-1"
        attacker_containers = [f"{pname}-attacker{i}-1" for i in range(n_atk)]

        strat = Strategy.from_json_file(Path(strat_path))

        # ctx provider: route rpc_admin actions to attacker containers
        # round-robin, and hand each action the victim IP + container.
        state = {"i": 0}

        def build_ctx(action):
            if action.exec_kind == "rpc_admin":
                i = state["i"] % max(1, n_atk)
                state["i"] += 1
                return {
                    "attacker_container": attacker_containers[i],
                    "victim_container":    victim_container,
                    "victim_ip":           "172.80.1.20",
                }
            return {}

        append_event(self.run_dir, {
            "event_type": "unified.actions.scheduled",
            "wrapper": "unified-eclipse",
            "strategy": strat.uid,
            "scenario": self.scenario,
            "n_attackers": n_atk,
            "action_pool_size": len(ACTION_POOL),
            "containers": {"victim": victim_container,
                            "attackers": attacker_containers},
        })

        executor = UnifiedExecutor(
            ctx_provider=build_ctx,
            log_sink=lambda kind, payload: (
                append_event(self.run_dir,
                             {"event_type": kind,
                              "wrapper": "unified-eclipse", **payload}), None
            )[1],
        )
        results = executor.run(strat)

        append_event(self.run_dir, {
            "event_type": "actions.done",
            "wrapper": "unified-eclipse",
            "strategy": strat.uid,
            "n_actions": len(results),
            "n_ok": sum(1 for r in results if r["ok"]),
        })
        return {
            "strategy": strat.uid,
            "mode": "unified",
            "scenario": self.scenario,
            "n_attackers": n_atk,
            "actions_run": [r["action"] for r in results],
        }
