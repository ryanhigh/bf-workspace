"""BaseAdapter — small scaffold shared by every profile.

A profile's adapter must subclass BaseAdapter and implement the abstract
hooks. The base class wires up:
  * per-run BASEDIR creation
  * docker compose up / down with a stable project name
  * background log streaming into events.jsonl via `docker compose logs -f`
  * per-service health probes (best effort)
"""
from __future__ import annotations
import abc
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from common import sh, append_event, utc_iso, project_paths


class BaseAdapter(abc.ABC):
    profile: str = "abstract"

    def __init__(self, root: Path, run_dir: Path, scenario: str, env: dict[str, str]):
        self.root = root
        self.run_dir = run_dir
        self.scenario = scenario
        self.env = dict(env)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # every per-run working directory the profile needs lives under run_dir
        (self.run_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "compose").mkdir(parents=True, exist_ok=True)

    # ---- concrete helpers ----

    def project_name(self) -> str:
        """Compose project name. Includes the project prefix so we can clean
        it without touching other projects."""
        from prefix import PREFIX
        # we use the run_id tail (after the unix timestamp dash) for compactness
        # but keep uniqueness
        return f"{PREFIX}{self.profile}-{self.run_dir.name}"

    def compose_cmd(self, compose_files: list[Path], *args: str,
                    capture: bool = False) -> tuple[int, str, str]:
        cmd: list[str] = ["docker", "compose", "-p", self.project_name()]
        for f in compose_files:
            cmd += ["-f", str(f)]
        cmd += list(args)
        env = {**os.environ, **self.env}
        return sh(cmd, timeout=1800, env=env, cwd=str(self.run_dir))

    def stream_logs(self, compose_files: list[Path], log_path: Path,
                    stop_event: threading.Event) -> None:
        """Stream compose logs into log_path while stop_event is set.
        Runs in a background thread."""
        cmd = ["docker", "compose", "-p", self.project_name()]
        for f in compose_files:
            cmd += ["-f", str(f)]
        cmd += ["logs", "-f", "--no-color", "--tail", "0"]
        env = {**os.environ, **self.env}
        with log_path.open("wb") as fh:
            proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                    env=env, cwd=str(self.run_dir))
            while not stop_event.is_set():
                time.sleep(0.2)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # ---- abstract hooks ----

    @abc.abstractmethod
    def prepare(self) -> dict[str, Any]:
        """Materialise compose files, secrets, etc. under self.run_dir.

        Returns a dict that the runner will use to drive up/wait/down.
        Required keys:
          compose_files: list[Path]
          wait_seconds: int
          pre_up: optional callable or None
        """
        raise NotImplementedError

    @abc.abstractmethod
    def meta(self) -> dict[str, Any]:
        """Return metadata: image digests, source paths, version locks."""
        raise NotImplementedError

    def run_actions(self, prepared: dict[str, Any]) -> dict[str, Any]:
        """Schedule attack / scenario actions AFTER services come up.
        Default: no-op (baseline runs only)."""
        return {"actions_run": [], "note": "no actions scheduled"}

    def tear_down(self, prepared: dict[str, Any]) -> None:
        cmd = ["docker", "compose", "-p", self.project_name()]
        for f in prepared["compose_files"]:
            cmd += ["-f", str(f)]
        cmd += ["down", "--remove-orphans", "--timeout", "30"]
        env = {**os.environ, **self.env}
        sh(cmd, timeout=600, env=env, cwd=str(self.run_dir))