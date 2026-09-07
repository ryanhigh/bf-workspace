"""`bunnyfinder` profile adapter.

Wraps the BunnyFinder author artefact under
`/data/DeAtkVer/Bunnyfinder/bf_workspace` (read-only) so that the
unified controller can launch known cases (none, basic, exante, ...) using
the same make-style verbs as every other profile.

Key invariants
--------------
  * The upstream artefact is **never** written to. Each run copies only the
    files the case needs (case compose + entrypoint + mysql compose) into
    `runs/<run_id>/bf_workspace/` and makes that copy read-only.
  * The copied tree uses `${BASEDIR}` in compose paths, so we set
    `BASEDIR=runs/<run_id>/bf_workspace/` when invoking `docker compose`.
  * `bf_workspace/runtest.sh` regenerates `genesis.ssz` / `genesis.json`
    on every run. We invoke `prysmctl` ourselves to keep the operation
    idempotent.

Case → version map (per bf_workspace/attack.sh dispatcher):

    v5: none, exante, sandwich, staircase, unrealized, withholding,
        selfish, staircaseii, sync, basic
    v4: staircase, unrealized, withholding, selfish

We default to v5 unless scenario is in v4-only.
"""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from common import sh, append_event, utc_iso, file_sha256
from profiles.base import BaseAdapter

BF_ROOT = Path("/data/DeAtkVer/Bunnyfinder/bf_workspace")
BF_MINIMAL = Path("/data/DeAtkVer/Bunnyfinder/bf_minimal")
ENTRYPOINT_SRC = Path("/data/DeAtkVer/Bunnyfinder/bf_workspace/entrypoint")

# Maps scenario → (version_dir, prysm_image, prysmctl_image, attacker_image)
V5 = "v5"
V4 = "v4"
V4_ONLY = {"staircase-v4", "unrealized-v4", "withholding-v4", "selfish-v4",
           "staircase", "unrealized", "withholding", "selfish"}
# Note: bf_workspace/attack.sh maps:
#   v4:  staircase, unrealized, withholding, selfish
#   v5:  everything else (none, exante, sandwich, staircase-ii, sync, mix, rl, teku, basic)
DEFAULT_VERSION_BY_SCENARIO = {
    "none":         V5, "exante": V5, "sandwich": V5, "staircase-ii": V5,
    "sync": V5, "mix": V5, "basic": V5, "staircaseii": V5,
    "rl-staircase": V5, "teku": V5,
    "staircase": V4, "unrealized": V4, "withholding": V4, "selfish": V4,
}

PRYSM_IMAGES_V5 = {
    "beacon": "tscel/bf.prysm:v5.2.0",
    "prysmctl": "tscel/prysmctl:v5.2.0",
    "attacker": "tscel/bunnyfinder:latest",
    "el": "tscel/geth:v1.13-base-v5",
}
PRYSM_IMAGES_V4 = {
    "beacon": "tscel/bf.prysm:v4.2.1",  # closest v4 we have for the modified Prysm
    "prysmctl": "tscel/prysmctl:v5.2.0",  # v4 prysmctl is not present; v5.2.0 still
                                          # speaks the same testnet generate-genesis subcmd
    "attacker": "tscel/bunnyfinder:latest",
    "el": "tscel/geth:v1.13-base-v5",
}


class Adapter(BaseAdapter):
    profile = "bunnyfinder"

    def meta(self) -> dict[str, Any]:
        v = self._version_dir()
        images = PRYSM_IMAGES_V5 if v == V5 else PRYSM_IMAGES_V4
        return {
            "profile": self.profile,
            "scenario": self.scenario,
            "version_dir": v,
            "images": images,
            "source_artefact": str(BF_ROOT),
            "compose_files": str(BF_ROOT / v / "case" / f"attack-{self.scenario}.yml"),
            "note": "Wraps the bf_workspace author compose files (read-only).",
        }

    def _version_dir(self) -> str:
        return DEFAULT_VERSION_BY_SCENARIO.get(self.scenario, V5)

    def prepare(self) -> dict[str, Any]:
        v = self._version_dir()
        bf_case = BF_ROOT / v / "case" / f"attack-{self.scenario}.yml"
        if not bf_case.is_file():
            raise FileNotFoundError(
                f"no compose for scenario={self.scenario} in {bf_case}"
            )

        # Per-run working copy of the bf_workspace subtree we need.
        # We copy ONLY:
        #   - entrypoint/  (executor/beacon/validator scripts, read-only)
        #   - v5/config/  (or v4/config/)  (genesis + accounts + prysm config)
        #   - the case compose file (attack-<scenario>.yml + mysql.yml)
        # We do NOT copy the entire bf_workspace — it has GBs of past logs.
        work = self.run_dir / "bf_workspace"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        src_work = BF_ROOT / v
        (work / v).mkdir(parents=True)

        # Copy case file
        (work / v / "case").mkdir(parents=True)
        shutil.copy2(bf_case, work / v / "case" / bf_case.name)
        shutil.copy2(src_work / "case" / "mysql.yml", work / v / "case" / "mysql.yml")

        # Copy config dir
        if (src_work / "config").is_dir():
            shutil.copytree(src_work / "config", work / v / "config")

        # Copy entrypoint dir (referenced by compose via ${BASEDIR}./entrypoint)
        if ENTRYPOINT_SRC.is_dir():
            shutil.copytree(ENTRYPOINT_SRC, work / "entrypoint")

        # Make the entire per-run tree read-only so the experiment cannot
        # accidentally mutate shared artefact files
        subprocess.run(["chmod", "-R", "a-w", str(work)], check=False)

        # Regenerate genesis.ssz + genesis.json via prysmctl. The bf_workspace
        # runtest.sh does this; we do it ourselves so we control the order
        # and the BASEDIR.
        cfg_dir = work / v / "config"
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{cfg_dir.absolute()}:/root/config",
            "--entrypoint", "/usr/bin/prysmctl",
            PRYSM_IMAGES_V5 if v == V5 else PRYSM_IMAGES_V4,
            "testnet", "generate-genesis",
            "--fork=deneb",
            "--num-validators=256",
            "--genesis-time-delay=15",
            "--output-ssz=/root/config/genesis.ssz",
            "--chain-config-file=/root/config/config.yml",
            "--geth-genesis-json-in=/root/config/genesis.json",
            "--geth-genesis-json-out=/root/config/genesis.json",
        ]
        rc, out, err = sh(cmd, timeout=300)
        append_event(self.run_dir, {
            "event_type": "prysmctl.generate-genesis",
            "returncode": rc,
            "stdout_tail": out[-500:],
            "stderr_tail": err[-500:],
        })
        if rc != 0:
            raise RuntimeError(
                f"prysmctl generate-genesis failed (rc={rc}): {err[-300:]}"
            )

        # Compose files relative to run_dir
        case_compose = work / v / "case" / f"attack-{self.scenario}.yml"
        mysql_compose = work / v / "case" / "mysql.yml"

        env_extra = {"BASEDIR": str(work) + "/"}
        self.env.update(env_extra)

        # duration: bunnyfinder author uses 1800 for basic, 3600 otherwise
        duration = 1800 if self.scenario in ("basic",) else 3600
        if self.scenario == "none":
            duration = 360  # short smoke for the no-attack baseline

        return {
            "compose_files": [mysql_compose, case_compose],
            "wait_seconds": duration,
            "needs_mysql": True,
            "extra_compose_first": True,  # bring mysql up before testnet
            "source_case": str(bf_case),
            "source_case_sha256": file_sha256(bf_case),
        }

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        # bunnyfinder author composes already start attacker1 with --strategy
        # derived from the case file. No controller-driven injection needed
        # for the basic cases. This hook is here for future extensions
        # (e.g. ext-* cases where we may want to swap the strategy JSON
        # mid-run).
        append_event(self.run_dir, {
            "event_type": "scenario.actions.scheduled",
            "scenario": self.scenario,
            "note": "attack scenario wired via attack-<scenario>.yml; no controller injection",
        })
        return {"actions_run": ["author-composed"], "scenario": self.scenario}

    def tear_down(self, prepared: dict[str, Any]) -> None:
        # Tear down case compose first (which also removes the per-project
        # containers and the private network), then mysql separately.
        case_compose = prepared["compose_files"][-1]
        mysql_compose = prepared["compose_files"][0]
        # Case project uses self.project_name()
        case_cmd = ["docker", "compose", "-p", self.project_name(),
                    "-f", str(case_compose), "down", "--remove-orphans",
                    "--timeout", "30"]
        env = {**os.environ, **self.env}
        sh(case_cmd, timeout=600, env=env, cwd=str(self.run_dir))
        # MySQL uses its own default project (no -p flag) — it's a singleton
        # compose in bf_workspace
        mysql_cmd = ["docker", "compose", "-f", str(mysql_compose),
                     "down", "--remove-orphans", "--timeout", "30"]
        sh(mysql_cmd, timeout=600, env=env, cwd=str(self.run_dir))