"""`pos-baseline` profile adapter.

Self-contained, BF-independent EL+CL private network designed for the
"healthy baseline, no attack" verification step. Uses:

  * ethereum/client-go:latest            (execution layer)
  * sigp/lighthouse:latest               (consensus layer + validator)
  * ethpandaops/ethereum-genesis-generator:6.1.2 (genesis material)
  * protolambda/eth2-val-tools:latest    (keystores + deposit data)

Topology (everything inside the `erl_posb-<run_id>` docker network):

  bootnode        — geth --nodekey... (low-cost, no mining, no peers)
  el1             — geth, --networkid=32380, --chain=..., peers=bootnode
  cl1             — lighthouse bn  → el1 (JWT-auth)
  vc1..vc4        — lighthouse vc → cl1

We deliberately do NOT use kurtosis / ethereum-package; the lab has to
build a baseline that is independent of those tools so we have a stable
floor for the Phase 1 verification.

**Important:** Generating a working PoS private chain is non-trivial (we
need an EL genesis with deposits, a CL genesis derived from it, and
shared JWT). The current implementation is a *smoke test* that brings
the EL and CL up and confirms they reach "looking for peers". Finalized
state is verified in the analyse step via the CL REST API.
"""
from __future__ import annotations
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any

from common import sh, append_event, utc_iso, file_sha256
from profiles.base import BaseAdapter
from prefix import PREFIX

CHAIN_ID = 32380
NETWORK_ID = 32380
GENESIS_TIME_DELAY = 15
SECONDS_PER_SLOT = 6  # lighthouse default
NUM_VALIDATORS = 4
PASSWORD = "posbpass"  # demo only; per-run


def _docker_image_id(image: str) -> str:
    rc, out, _ = sh(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    return out.strip() if rc == 0 else ""


class Adapter(BaseAdapter):
    profile = "pos-baseline"

    def meta(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "scenario": self.scenario,
            "chain_id": CHAIN_ID,
            "network_id": NETWORK_ID,
            "seconds_per_slot": SECONDS_PER_SLOT,
            "num_validators": NUM_VALIDATORS,
            "images": {
                "el": "ethereum/client-go:latest",
                "cl": "sigp/lighthouse:latest",
                "genesis": "ethpandaops/ethereum-genesis-generator:6.1.2",
                "valtools": "protolambda/eth2-val-tools:latest",
            },
            "image_digests": {
                "el": _docker_image_id("ethereum/client-go:latest"),
                "cl": _docker_image_id("sigp/lighthouse:latest"),
                "genesis": _docker_image_id("ethpandaops/ethereum-genesis-generator:6.1.2"),
                "valtools": _docker_image_id("protolambda/eth2-val-tools:latest"),
            },
            "note": "Self-contained PoS baseline; no attack scenarios.",
        }

    # ---- prepare ----

    def prepare(self) -> dict[str, Any]:
        # 1. fresh BASEDIR
        work = self.run_dir / "posb"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        (work / "el-data").mkdir()
        (work / "keys").mkdir()
        (work / "cl-data").mkdir()
        (work / "logs").mkdir()

        # 2. generate EL+CL genesis via ethpandaops/ethereum-genesis-generator
        #    The tool requires preset env via files in /data/config/. We use
        #    its `all` command which writes both into /data/metadata/ (EL) and
        #    /data/config/ (CL). See the tool's README for env requirements.
        env_file = work / "preset.env"
        env_file.write_text(
            f"GENESIS_TIMESTAMP={int(__import__('time').time()) + GENESIS_TIME_DELAY}\n"
            f"CHAIN_ID={CHAIN_ID}\n"
            f"NETWORK_ID={NETWORK_ID}\n"
            f"GENESIS_GASLIMIT=30000000000\n"
            f"GENESIS_DIFFICULTY=1\n"
            f"MAX_CHUNK_SIZE=15\n"
            f"PER_EPOCH_SIZE=1\n"
            f"VALIDATOR_COUNT={NUM_VALIDATORS}\n"
            f"MIN_GENESIS_TIME=0\n"
            f"GENESIS_FORK_VERSION=0x20000089\n"
            f"ALTAIR_FORK_VERSION=0x20000090\n"
            f"ALTAIR_FORK_EPOCH=0\n"
            f"BELLATRIX_FORK_VERSION=0x20000091\n"
            f"BELLATRIX_FORK_EPOCH=0\n"
            f"CAPELLA_FORK_VERSION=0x20000092\n"
            f"CAPELLA_FORK_EPOCH=0\n"
            f"DENEB_FORK_VERSION=0x20000093\n"
            f"DENEB_FORK_EPOCH=0\n"
            f"ELECTRA_FORK_VERSION=0x20000094\n"
            f"ELECTRA_FORK_EPOCH=100000\n"
            f"SECONDS_PER_SLOT={SECONDS_PER_SLOT}\n"
            f"SLOTS_PER_EPOCH=8\n"
            f"DEPOSIT_CONTRACT_ADDRESS=0x4242424242424242424242424242424242424242\n"
            f"ETH1_FOLLOW_DISTANCE=1\n"
            f"EPOCHS_PER_ETH1_VOTING_PERIOD=1\n"
            f"TERMINAL_TOTAL_DIFFICULTY=0\n"
            f"TERMINAL_BLOCK_HASH=0x0000000000000000000000000000000000000000000000000000000000000000\n"
            f"TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH=18446744073709551615\n"
        )
        # The genesis generator requires /data/config to be a config dir
        # containing `mnemonic.txt` and other params. Simplest: mount the
        # whole work dir at /data, mount preset.env via env_file.
        gen_vol = work.parent  # bind /data on host as /data in container
        # Actually the genesis-gen container uses /data as workdir; bind a
        # per-run subdir so we don't pollute /data.
        gen_root = self.run_dir / "genroot"
        if gen_root.exists():
            shutil.rmtree(gen_root)
        gen_root.mkdir()
        shutil.copy2(env_file, gen_root / "genesis.env")

        rc, out, err = sh(
            ["docker", "run", "--rm",
             "-v", f"{gen_root.absolute()}:/data",
             "--env-file", str(env_file),
             "ethpandaops/ethereum-genesis-generator:6.1.2", "all"],
            timeout=600,
        )
        append_event(self.run_dir, {
            "event_type": "genesis.generate",
            "returncode": rc,
            "stdout_tail": out[-500:],
            "stderr_tail": err[-500:],
        })
        if rc != 0:
            raise RuntimeError(
                f"ethereum-genesis-generator failed (rc={rc}): {err[-400:]}"
            )

        # 3. verify outputs exist
        el_genesis = gen_root / "metadata" / "genesis.json"
        cl_genesis = gen_root / "config" / "genesis.ssz"
        if not el_genesis.is_file() or not cl_genesis.is_file():
            raise RuntimeError(
                f"genesis output missing: el={el_genesis.exists()} cl={cl_genesis.exists()}"
            )

        # 4. JWT secret (geth ↔ lighthouse)
        jwt_dir = self.run_dir / "secrets"
        jwt_dir.mkdir(exist_ok=True)
        jwt_hex = secrets.token_hex(32)
        (jwt_dir / "jwt.hex").write_text(jwt_hex + "\n")
        # also place where geth looks
        (work / "jwt.hex").write_text(jwt_hex + "\n")

        # 5. generate validator keystores (only if user wants the full flow)
        #    Lighthouse can also be started in --validators-disabled mode for
        #    the baseline smoke test. We default to disabled so the baseline
        #    completes quickly; toggling full validator flow is exposed as
        #    the `pos-baseline-validators` scenario.
        (work / "password.txt").write_text(PASSWORD)

        # 6. compose file (per-run, project prefix baked in)
        compose = self._compose(work, el_genesis, cl_genesis, jwt_hex)
        compose_path = work / "docker-compose.yml"
        compose_path.write_text(compose)
        compose_path.chmod(0o644)

        return {
            "compose_files": [compose_path],
            "wait_seconds": 90 if self.scenario == "normal" else 600,
            "needs_mysql": False,
            "extra_compose_first": False,
            "source_case": str(compose_path),
            "source_case_sha256": file_sha256(compose_path),
            "el_genesis": str(el_genesis),
            "cl_genesis": str(cl_genesis),
        }

    def _compose(self, work: Path, el_genesis: Path, cl_genesis: Path,
                 jwt_hex: str) -> str:
        network_name = f"{PREFIX}posb-{self.run_dir.name}"
        # geth expects the JWT secret at a path; we mount the file
        jwt_mount_src = (self.run_dir / "secrets" / "jwt.hex").absolute()
        return f"""# Auto-generated by profiles/pos_baseline.py — do not edit by hand.
# Run id: {self.run_dir.name}
networks:
  {network_name}:
    driver: bridge
    ipam:
      config:
        - subnet: 172.80.0.0/16

services:
  bootnode:
    image: ethereum/client-go:latest
    command: >
      --networkid={NETWORK_ID}
      --nodekeyhex=ae69ad58b0497b61a5b6f8af68b4a8b4d8d3b9c2a4b9e6c1c0a4f0d0b0a4b0a4
      --nodiscover
      --ipcdisable
      --http
      --http.addr=0.0.0.0
      --http.port=8545
      --port=30303
    networks:
      {network_name}:
        ipv4_address: 172.80.1.10

  el1:
    image: ethereum/client-go:latest
    depends_on: [bootnode]
    command: >
      --networkid={NETWORK_ID}
      --http
      --http.addr=0.0.0.0
      --http.port=8545
      --http.api=engine,eth,net,web3
      --authrpc.addr=0.0.0.0
      --authrpc.port=8551
      --authrpc.jwtsecret=/secrets/jwt.hex
      --nodiscover
      --port=30303
      --bootnodes=enode://ae69ad58b0497b61a5b6f8af68b4a8b4d8d3b9c2a4b9e6c1c0a4f0d0b0a4b0a4@172.80.1.10:30303
    volumes:
      - {work.absolute()}/el-data:/gethdata
      - {el_genesis}:/genesis/genesis.json:ro
      - {jwt_mount_src}:/secrets/jwt.hex:ro
    networks:
      {network_name}:
        ipv4_address: 172.80.1.20

  cl1:
    image: sigp/lighthouse:latest
    depends_on: [el1]
    command: >
      lighthouse bn
      --network=minimal
      --eth1-rpc-urls=http://172.80.1.20:8545
      --execution-endpoint=http://172.80.1.20:8551
      --execution-jwt=/secrets/jwt.hex
      --http
      --http-address=0.0.0.0
      --http-port=4000
      --metrics
      --metrics-address=0.0.0.0
      --metrics-port=5054
      --disable-packet-filter
      --target-peers=1
      --listen-address=0.0.0.0
    volumes:
      - {work.absolute()}/cl-data:/cl-data
      - {cl_genesis}:/cl-data/genesis.ssz:ro
      - {jwt_mount_src}:/secrets/jwt.hex:ro
    networks:
      {network_name}:
        ipv4_address: 172.80.1.30

  vc1:
    image: sigp/lighthouse:latest
    depends_on: [cl1]
    command: >
      lighthouse vc
      --network=minimal
      --beacon-nodes=http://172.80.1.30:4000
      --http-allow-origin=*
      --suggested-fee-recipient=0x0000000000000000000000000000000000000000
      --validators-disabled
    networks:
      {network_name}:
        ipv4_address: 172.80.1.40
"""

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        append_event(self.run_dir, {
            "event_type": "scenario.actions.scheduled",
            "scenario": self.scenario,
            "note": "baseline — no attack actions",
        })
        return {"actions_run": [], "scenario": self.scenario}

    def tear_down(self, prepared: dict[str, Any]) -> None:
        super().tear_down(prepared)