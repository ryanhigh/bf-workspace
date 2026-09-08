"""Unified Action DSL — single action pool, single executor, multi-chain.

This module replaces both `eclipse_strategy.py` (eclipse-only DSL) and the
implicit bunnyfinder actionset with a single, flat registry of Action
subclasses. Each Action declares its own `exec_kind` (local / rpc_admin /
rpc_beacon / rpc_file); the UnifiedExecutor dispatches by that tag and
otherwise treats every action identically.

Design intent: a Strategy JSON can mix actions drawn from any source —
BunnyFinder's `set_strategy`, Eclipse's `burst_dial`, plain control flow
like `sleep` / `return` — and they all execute through the same loop,
get logged in the same schema, and feed the same downstream analysis.

This file is the single source of truth for action definitions; profile
adapters (`profiles/eclipse.py`, `profiles/bunnyfinder.py`) only supply
the per-action runtime context (container names, IPs, RPC endpoints)
and never inspect the action name.
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------- Execution kinds ----------

# Every Action declares exactly one of these. The Executor only inspects
# `exec_kind` — never the action name or the strategy file — to decide
# how to run. Adding a new kind means adding one `_exec_<kind>` branch
# and one `run()` that can handle it.
EXEC_LOCAL     = "local"         # run in this process (control flow)
EXEC_RPC_ADMIN = "rpc_admin"     # docker exec + wget -> geth admin RPC
EXEC_RPC_BEACON= "rpc_beacon"    # docker exec + wget -> prysm beacon API
                                # OR write file -> attacker Go process reads it
EXEC_RPC_FILE  = "rpc_file"      # docker exec + write a file inside a container


# ---------- Action ----------

class Action(ABC):
    name: str = "action"
    category: str = "any"        # pre-attack / attack / settle / any
    exec_kind: str = EXEC_LOCAL

    @abstractmethod
    def run(self, params: dict, ctx: dict) -> dict:
        """All Actions return a JSON-serialisable dict describing the result.
        `ctx` is per-profile runtime state (container names, IPs, etc.)
        populated by the active profile adapter's `ctx_for()` method.
        """


# ---------- Registry (the "action pool") ----------

ACTION_POOL: dict[str, Action] = {}

def register(cls: type) -> type:
    """Class decorator: instantiate and add to the global pool."""
    inst = cls()
    ACTION_POOL[inst.name] = inst
    return cls

def get(name: str) -> Action:
    if name not in ACTION_POOL:
        raise KeyError(f"unknown action {name!r}; available: "
                       f"{sorted(ACTION_POOL)}")
    return ACTION_POOL[name]

def pool_snapshot() -> dict[str, str]:
    """Used by events.jsonl `profile.meta` to advertise the active action set."""
    return {k: v.exec_kind for k, v in sorted(ACTION_POOL.items())}


# ---------- Concrete actions ----------

# ---- LOCAL: pure control flow, no RPC ----

@register
class SleepAction(Action):
    name = "sleep"
    exec_kind = EXEC_LOCAL
    category = "any"
    def run(self, params, ctx):
        s = float(params.get("seconds", 1))
        time.sleep(s)
        return {"slept_s": s}


@register
class ReturnAction(Action):
    name = "return"
    exec_kind = EXEC_LOCAL
    category = "any"
    def run(self, params, ctx):
        # signals the executor to break out of the current phase loop
        return {"returned": True, "signal": "phase_return"}


@register
class AbortAction(Action):
    name = "abort"
    exec_kind = EXEC_LOCAL
    category = "any"
    def run(self, params, ctx):
        ctx["_abort"] = True
        return {"aborted": True}


# ---- RPC_ADMIN: geth admin RPC via docker exec ----

def _docker_exec(container: str, payload: dict, rpc_port: int = 8545,
                 timeout: int = 5) -> dict:
    """Run a JSON-RPC call inside a container via wget, return the
    `result` field. Raises RuntimeError on docker or JSON errors."""
    body = json.dumps(payload)
    # We pass args as a list (no shell) so JSON braces survive intact.
    proc = subprocess.run([
        "docker", "exec", container,
        "wget", "-qO-", f"--timeout={timeout}",
        "--post-data=" + body,
        "--header=Content-Type: application/json",
        f"http://127.0.0.1:{rpc_port}",
    ], capture_output=True, text=True, timeout=timeout + 5)
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker exec rc={proc.returncode} "
            f"err={proc.stderr[-200:]}")
    return json.loads(proc.stdout)


@register
class ResolveEnodeAction(Action):
    name = "resolve_enode"
    exec_kind = EXEC_RPC_ADMIN
    category = "pre-attack"
    def run(self, params, ctx):
        container = ctx["attacker_container"]
        data = _docker_exec(container, {
            "jsonrpc": "2.0", "method": "admin_nodeInfo",
            "params": [], "id": 1})
        enode = data["result"]["enode"]
        # enode comes back with 127.0.0.1 — rewrite to victim_ip so the
        # attacker doesn't try to dial itself.
        if "@" in enode:
            _, after = enode.split("://", 1)
            pub, _ = after.split("@", 1)
            enode = f"enode://{pub}@{ctx['victim_ip']}:30303"
        ctx["peer_enode"] = enode
        return {"enode": enode}


@register
class AddStaticPeerAction(Action):
    name = "add_static_peer"
    exec_kind = EXEC_RPC_ADMIN
    category = "pre-attack"
    def run(self, params, ctx):
        if "peer_enode" not in ctx:
            raise RuntimeError("add_static_peer needs resolve_enode first")
        container = ctx["attacker_container"]
        data = _docker_exec(container, {
            "jsonrpc": "2.0", "method": "admin_addPeer",
            "params": [ctx["peer_enode"]], "id": 1})
        return {"ok": bool(data.get("result")), "result": data.get("result")}


@register
class BurstDialAction(Action):
    name = "burst_dial"
    exec_kind = EXEC_RPC_ADMIN
    category = "attack"
    def run(self, params, ctx):
        if "peer_enode" not in ctx:
            raise RuntimeError("burst_dial needs resolve_enode first")
        container = ctx["attacker_container"]
        n = int(params.get("repeats", 3))
        gap = float(params.get("interval_s", 2))
        successes = 0
        for i in range(n):
            try:
                data = _docker_exec(container, {
                    "jsonrpc": "2.0", "method": "admin_addPeer",
                    "params": [ctx["peer_enode"]], "id": 1})
                if data.get("result"):
                    successes += 1
            except Exception as e:
                ctx.setdefault("_dial_errors", []).append(str(e))
            time.sleep(gap)
        return {"sent": n, "ok": successes}


@register
class SamplePeersAction(Action):
    name = "sample_peers"
    exec_kind = EXEC_RPC_ADMIN
    category = "any"
    def run(self, params, ctx):
        atk = ctx["attacker_container"]
        vic = ctx.get("victim_container", atk)
        atk_peers = _docker_exec(atk, {
            "jsonrpc": "2.0", "method": "admin_peers",
            "params": [], "id": 1})
        atk_npc = _docker_exec(atk, {
            "jsonrpc": "2.0", "method": "net_peerCount",
            "params": [], "id": 1})
        vic_npc = _docker_exec(vic, {
            "jsonrpc": "2.0", "method": "net_peerCount",
            "params": [], "id": 1})
        snap = {
            "t": time.time(),
            "attacker_peers": len(atk_peers.get("result") or []),
            "attacker_net_peerCount": int(atk_npc.get("result") or 0, 16)
                if isinstance(atk_npc.get("result"), str) else atk_npc.get("result"),
            "victim_net_peerCount": int(vic_npc.get("result") or 0, 16)
                if isinstance(vic_npc.get("result"), str) else vic_npc.get("result"),
        }
        return snap


@register
class WaitPeersAction(Action):
    name = "wait_peers"
    exec_kind = EXEC_RPC_ADMIN
    category = "any"
    def run(self, params, ctx):
        container = ctx["attacker_container"]
        mn = int(params.get("min", 1))
        timeout = float(params.get("timeout", 60))
        deadline = time.time() + timeout
        last_n = 0
        while time.time() < deadline:
            try:
                data = _docker_exec(container, {
                    "jsonrpc": "2.0", "method": "admin_peers",
                    "params": [], "id": 1})
                last_n = len(data.get("result") or [])
                if last_n >= mn:
                    return {"reached_min": mn, "peer_count": last_n}
            except Exception:
                pass
            time.sleep(2)
        return {"reached_min": None, "peer_count": last_n, "timed_out": True}


# ---- RPC_BEACON / RPC_FILE: bunnyfinder actions ----

@register
class SetStrategyAction(Action):
    """Write a BunnyFinder strategy JSON into the attacker's container.
    The Go attacker process inside the container polls /root/strategy.json
    and applies its actions per slot."""
    name = "set_strategy"
    exec_kind = EXEC_RPC_FILE
    category = "pre-attack"
    def run(self, params, ctx):
        container = ctx["attacker_container"]
        strategy = params.get("strategy", "basic")
        # For the smoke-test we just write a tiny stub JSON; the real
        # BF strategies are loaded from bf_workspace/v5/config/strategies/.
        stub = {
            "uid": f"inject-{strategy}",
            "category": strategy,
            "slots": [],
            "injected_at": time.time(),
        }
        # Use docker exec to write the file inside the container.
        # We base64-encode to avoid shell-quote issues.
        import base64
        body = base64.b64encode(json.dumps(stub).encode()).decode()
        proc = subprocess.run([
            "docker", "exec", container,
            "sh", "-c",
            f"echo {body} | base64 -d > /root/strategy.json",
        ], capture_output=True, text=True, timeout=10)
        return {
            "strategy": strategy,
            "container": container,
            "write_rc": proc.returncode,
            "stub_uid": stub["uid"],
        }


@register
class DelayToNextSlotAction(Action):
    """Sleep until the next slot boundary.

    bunnyfinder chains have a known genesis_time + seconds_per_slot;
    `ctx['genesis_time']` and `ctx['seconds_per_slot']` must be set by
    the bunnyfinder adapter."""
    name = "delay_to_next_slot"
    exec_kind = EXEC_LOCAL
    category = "any"
    def run(self, params, ctx):
        gensis = ctx.get("genesis_time")
        sps = ctx.get("seconds_per_slot", 12)
        if gensis is None:
            # No clock available — fall back to a fixed sleep.
            time.sleep(float(params.get("fallback_seconds", 12)))
            return {"slept_fallback_s": params.get("fallback_seconds", 12),
                    "fallback": True}
        now = time.time()
        elapsed = now - gensis
        slot = int(elapsed // sps)
        next_slot_boundary = gensis + (slot + 1) * sps
        time.sleep(max(0, next_slot_boundary - now))
        return {"slept_until_slot": slot + 1, "seconds_per_slot": sps}


@register
class ModifyParentRootAction(Action):
    """Inject a 'modify parent root' directive into the attacker's
    strategy file. The Go attacker reads this on its next slot tick."""
    name = "modify_parent_root"
    exec_kind = EXEC_RPC_FILE
    category = "attack"
    def run(self, params, ctx):
        container = ctx["attacker_container"]
        slot_offset = int(params.get("slot_offset", 1))
        # We append a slot directive; the Go attacker picks it up.
        directive = {
            "slot": "auto",                # attacker picks next slot
            "level": 0,
            "actions": {"BlockGetNewParentRoot":
                        f"modifyParentRoot:{slot_offset}"},
        }
        import base64
        body = base64.b64encode(json.dumps(directive).encode()).decode()
        proc = subprocess.run([
            "docker", "exec", container,
            "sh", "-c",
            f"echo {body} | base64 -d >> /root/strategy.json",
        ], capture_output=True, text=True, timeout=10)
        return {"directive_appended": True, "slot_offset": slot_offset,
                "write_rc": proc.returncode}


@register
class StoreSignedAttestAction(Action):
    """Sign an attestation but DON'T broadcast it. Mirrors BF's
    storeSignedAttest action — used to withhold attestations from the
    network. We record the would-be payload; actual signing requires the
    validator's BLS key and is performed by the Go attacker process
    inside the validator container. We trigger it by writing a
    one-shot directive."""
    name = "store_signed_attest"
    exec_kind = EXEC_RPC_FILE
    category = "attack"
    def run(self, params, ctx):
        container = ctx.get("validator_container", ctx["attacker_container"])
        directive = {
            "slot": "auto",
            "level": 0,
            "actions": {"AttestBeforeBroadCast": "store"},
        }
        import base64
        body = base64.b64encode(json.dumps(directive).encode()).decode()
        proc = subprocess.run([
            "docker", "exec", container,
            "sh", "-c",
            f"echo {body} | base64 -d >> /root/strategy.json",
        ], capture_output=True, text=True, timeout=10)
        return {"directive": "store_signed_attest", "container": container,
                "write_rc": proc.returncode}


# ---------- Strategy (JSON) ----------

@dataclass
class PhaseStep:
    t_rel_seconds: float
    phase: str
    actions: list   # list[dict] each with keys name, params

@dataclass
class Strategy:
    uid: str
    category: str
    phases: list   # list[PhaseStep]

    @classmethod
    def from_json_file(cls, path) -> "Strategy":
        return cls.from_dict(json.loads(open(path).read()))

    @classmethod
    def from_dict(cls, d: dict) -> "Strategy":
        phases = []
        for raw in d.get("phases", []):
            phases.append(PhaseStep(
                t_rel_seconds=float(raw.get("t_rel_seconds", 0)),
                phase=raw.get("phase", "ATTACK"),
                actions=raw.get("actions", []),
            ))
        return cls(uid=d.get("uid", ""),
                   category=d.get("category", ""),
                   phases=phases)


# ---------- Unified Executor (single code path for every action) ----------

class UnifiedExecutor:
    """Walks a Strategy and runs each action through the same loop,
    logging into a single events.jsonl sink. The Executor itself knows
    nothing about eclipse or bunnyfinder — every action comes with its
    own `exec_kind`, and the only branch is `_exec_local` /
    `_exec_docker_rpc` / `_exec_docker_write_file`. Profile adapters
    supply the per-action `ctx`."""

    def __init__(self, ctx_provider: Callable[[Action], dict],
                 log_sink: Callable[[str, dict], None]):
        self.ctx_provider = ctx_provider
        self.log_sink = log_sink

    def run(self, strat: Strategy) -> list[dict]:
        results: list[dict] = []
        ctx: dict = {}                   # shared runtime state
        ctx["_abort"] = False
        t0 = time.time()
        for phase in strat.phases:
            wait = (t0 + phase.t_rel_seconds) - time.time()
            if wait > 0:
                time.sleep(wait)
            self.log_sink("strategy.phase", {
                "phase": phase.phase,
                "t_rel_seconds": phase.t_rel_seconds,
                "n_actions": len(phase.actions),
            })
            for ad in phase.actions:
                if ctx.get("_abort"):
                    self.log_sink("strategy.aborted",
                                  {"after_phase": phase.phase})
                    return results
                action = get(ad["name"])
                params = ad.get("params", {})
                self.log_sink("strategy.action.start", {
                    "action": action.name,
                    "exec_kind": action.exec_kind,
                    "category": action.category,
                    "phase": phase.phase,
                })
                t_start = time.time()
                try:
                    # Merge the per-action ctx into the shared ctx so
                    # actions can hand state to each other (e.g.
                    # resolve_enode writes ctx["peer_enode"], and a
                    # later add_static_peer reads it back). We pass the
                    # SAME dict object so mutations persist.
                    act_ctx = self.ctx_provider(action)
                    ctx.update(act_ctx)
                    result = action.run(params, ctx)
                    ok = True
                    err = None
                except Exception as e:
                    result = {"exception": type(e).__name__}
                    ok = False
                    err = str(e)
                t_end = time.time()
                self.log_sink("strategy.action.done", {
                    "action": action.name,
                    "exec_kind": action.exec_kind,
                    "ok": ok,
                    "elapsed_s": round(t_end - t_start, 3),
                    **({"error": err} if err else {}),
                    **{k: v for k, v in result.items()
                       if k not in ("ok", "error")},
                })
                results.append({"action": action.name, "ok": ok,
                                "elapsed_s": round(t_end - t_start, 3),
                                "result": result})
                # signal-based short-circuit
                if result.get("signal") == "phase_return":
                    break
        return results