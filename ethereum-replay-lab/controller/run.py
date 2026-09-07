#!/usr/bin/env python3
"""`make run` / `make baseline` — execute one experiment.

Flow
----
1. doctor pre-checks (skip if SKIP_DOCTOR=1)
2. allocate a per-run BASEDIR (runs/<run_id>)
3. instantiate the profile adapter; call prepare() to materialise
   compose files, secrets, etc.
4. compose up (mysql first if applicable)
5. background log streaming into events.jsonl
6. call adapter.run_actions(prepared) for scenario-specific actions
7. wait `wait_seconds`
8. compose down
9. write manifest.json + result.json
10. clean teardown of project containers/network
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("ERL_ROOT", "/data/DeAtkVer/ethereum-replay-lab"))
sys.path.insert(0, str(ROOT / "controller"))

from common import (sh, append_event, utc_iso, gen_run_id, file_sha256,
                    project_paths)  # noqa: E402
from registry import load_adapter, list_profiles, profile_descriptions  # noqa: E402


def _docker_image_id(image: str) -> str:
    rc, out, _ = sh(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    return out.strip() if rc == 0 else ""


def _compose_up(adapter, prepared: dict[str, Any], services: list[str] | None) -> tuple[int, str, str]:
    cmd: list[str] = ["docker", "compose", "-p", adapter.project_name()]
    for f in prepared["compose_files"]:
        cmd += ["-f", str(f)]
    cmd += ["up", "-d"]
    if services:
        cmd += services
    env = {**os.environ, **adapter.env}
    return sh(cmd, timeout=600, env=env, cwd=str(adapter.run_dir))


def _compose_ps(adapter, prepared: dict[str, Any]) -> str:
    cmd = ["docker", "compose", "-p", adapter.project_name()]
    for f in prepared["compose_files"]:
        cmd += ["-f", str(f)]
    cmd += ["ps", "--format", "json"]
    env = {**os.environ, **adapter.env}
    rc, out, err = sh(cmd, timeout=60, env=env, cwd=str(adapter.run_dir))
    return out or err


def _compose_logs(adapter, prepared: dict[str, Any], log_path: Path,
                  stop_event: threading.Event) -> None:
    cmd = ["docker", "compose", "-p", adapter.project_name()]
    for f in prepared["compose_files"]:
        cmd += ["-f", str(f)]
    cmd += ["logs", "-f", "--no-color", "--tail", "0"]
    env = {**os.environ, **adapter.env}
    with log_path.open("wb") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                env=env, cwd=str(adapter.run_dir))
        while not stop_event.is_set():
            time.sleep(0.2)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _doctor_ok(root: Path) -> bool:
    if os.environ.get("SKIP_DOCTOR") == "1":
        return True
    rc, _, _ = sh(["python3", str(root / "controller" / "doctor.py"), str(root)],
                  timeout=120)
    return rc == 0


def _write_result(run_dir: Path, payload: dict[str, Any]) -> Path:
    p = run_dir / "result.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return p


def _collect_per_service_logs(adapter, prepared: dict[str, Any], run_dir: Path) -> list[Path]:
    """After teardown, dump per-service logs via `docker logs` (one-shot)
    so we don't lose the trailing entries that `compose logs` sometimes
    truncates when containers are killed before flush."""
    out_paths: list[Path] = []
    ps_out = _compose_ps(adapter, prepared)
    try:
        services = json.loads(ps_out) if ps_out.strip().startswith("[") else []
    except Exception:
        services = []
    for svc in services:
        name = svc.get("Name") or svc.get("Service") or svc.get("Names")
        if not name:
            continue
        if not name.startswith(adapter.project_name()):
            continue
        rc, out, err = sh(["docker", "logs", "--timestamps",
                            "--tail", "10000", name], timeout=60)
        log_path = run_dir / "logs" / f"{name}.log"
        log_path.write_text(out + err)
        out_paths.append(log_path)
    return out_paths


def _judge_layers(meta: dict[str, Any], events_path: Path,
                  elapsed: float, wait: int, error: str | None) -> dict[str, Any]:
    """Six-layer judgement per Phase 6 spec.

    1. experiment valid?
    2. strategy executed?
    3. mechanism reproduced?
    4. node-state impact?
    5. consensus/incentive impact?
    6. detector alarm? (deferred to analyse step)
    """
    valid = error is None and elapsed >= 0.5 * wait
    return {
        "valid": valid,
        "strategy_executed": None,  # filled by analyse step
        "mechanism_observed": None,
        "node_state_impact": None,
        "consensus_impact": None,
        "detector_alarm": None,
        "notes": error or "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(ROOT))
    parser.add_argument("--profile", default=os.environ.get("ACTIVE_PROFILE", "pos-baseline"))
    parser.add_argument("--scenario", default=os.environ.get("ACTIVE_SCENARIO", "normal"))
    parser.add_argument("--run-id", default=os.environ.get("RUN_ID", ""))
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument("--no-tear-down", action="store_true",
                        help="leave containers running (debug only)")
    parser.add_argument("--timeout-mult", type=float, default=1.0,
                        help="multiplier on adapter wait_seconds (debug)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sys.path.insert(0, str(root / "controller"))
    from registry import load_adapter

    run_id = args.run_id or gen_run_id()
    run_dir = project_paths(root, args.profile, args.scenario, run_id)

    print(f"== run profile={args.profile} scenario={args.scenario} "
          f"run_id={run_id} run_dir={run_dir}")

    if args.skip_doctor or os.environ.get("SKIP_DOCTOR") == "1":
        print("doctor: skipped (SKIP_DOCTOR)")
    elif not _doctor_ok(root):
        append_event(run_dir, {"event_type": "doctor.failed",
                               "note": "doctor reported missing dependencies"})
        print("doctor failed — aborting")
        return 2

    adapter = load_adapter(args.profile)(root=root, run_dir=run_dir,
                                          scenario=args.scenario, env={})

    meta = adapter.meta()
    append_event(run_dir, {"event_type": "profile.meta", "meta": meta})

    # Prepare
    t0 = time.time()
    try:
        prepared = adapter.prepare()
    except Exception as exc:
        tb = traceback.format_exc()
        append_event(run_dir, {"event_type": "prepare.failed",
                               "error": str(exc), "traceback": tb[-1000:]})
        print(f"prepare failed: {exc}")
        _write_result(run_dir, {"valid": False, "error": str(exc),
                                "phase": "prepare"})
        return 1
    append_event(run_dir, {"event_type": "prepare.done", "elapsed_s": time.time() - t0,
                           "wait_seconds": prepared["wait_seconds"],
                           "compose_files": [str(p) for p in prepared["compose_files"]]})

    # Compose up
    append_event(run_dir, {"event_type": "compose.up.starting"})
    t1 = time.time()
    rc, out, err = _compose_up(adapter, prepared, None)
    append_event(run_dir, {"event_type": "compose.up.done",
                           "returncode": rc,
                           "elapsed_s": time.time() - t1,
                           "stdout_tail": out[-400:],
                           "stderr_tail": err[-400:]})
    if rc != 0:
        # try to capture logs before exit
        try:
            _collect_per_service_logs(adapter, prepared, run_dir)
        finally:
            if not args.no_tear_down:
                adapter.tear_down(prepared)
        _write_result(run_dir, {"valid": False, "error": "compose up failed",
                                "compose_up_rc": rc,
                                "compose_up_err": err[-400:]})
        return 1

    # Background log streaming
    log_path = run_dir / "logs" / "compose.log"
    stop = threading.Event()
    thr = threading.Thread(target=_compose_logs, args=(adapter, prepared, log_path, stop),
                           daemon=True)
    thr.start()

    # Run scenario actions (may schedule attacks)
    t2 = time.time()
    try:
        actions_summary = adapter.run_actions(prepared)
        append_event(run_dir, {"event_type": "actions.done",
                               "elapsed_s": time.time() - t2,
                               "summary": actions_summary})
    except Exception as exc:
        append_event(run_dir, {"event_type": "actions.failed",
                               "error": str(exc)})
        actions_summary = {"error": str(exc)}

    # Wait
    wait = int(prepared["wait_seconds"] * args.timeout_mult)
    print(f"waiting {wait}s ...")
    append_event(run_dir, {"event_type": "wait.start", "seconds": wait})
    wait_t0 = time.time()
    time.sleep(wait)
    append_event(run_dir, {"event_type": "wait.done", "elapsed_s": time.time() - wait_t0})

    # Snapshot per-service logs
    snap_t = time.time()
    try:
        snap_paths = _collect_per_service_logs(adapter, prepared, run_dir)
    except Exception as exc:
        append_event(run_dir, {"event_type": "snap.failed", "error": str(exc)})
        snap_paths = []
    append_event(run_dir, {"event_type": "snap.done", "elapsed_s": time.time() - snap_t,
                           "snapshots": [str(p) for p in snap_paths]})

    # Stop log streaming
    stop.set()
    thr.join(timeout=10)

    # Tear down
    if not args.no_tear_down:
        td_t = time.time()
        try:
            adapter.tear_down(prepared)
        except Exception as exc:
            append_event(run_dir, {"event_type": "teardown.failed", "error": str(exc)})
        append_event(run_dir, {"event_type": "teardown.done", "elapsed_s": time.time() - td_t})

    # Manifest
    elapsed_total = time.time() - t0
    manifest = {
        "run_id": run_id,
        "profile": args.profile,
        "scenario": args.scenario,
        "meta": meta,
        "prepared": {k: v for k, v in prepared.items()
                     if k in ("source_case", "source_case_sha256", "wait_seconds")},
        "actions_summary": actions_summary,
        "elapsed_total_s": elapsed_total,
        "run_dir": str(run_dir),
        "compose_project": adapter.project_name(),
        "host": {"uname": sh(["uname", "-a"])[1].strip()},
        "compose_up_rc": rc,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    append_event(run_dir, {"event_type": "run.done", "elapsed_total_s": elapsed_total})

    # Initial result (overwritten by analyse step)
    _write_result(run_dir, _judge_layers(meta, run_dir / "events.jsonl",
                                          elapsed_total, prepared["wait_seconds"],
                                          error=None))
    print(f"== done run_id={run_id} elapsed={elapsed_total:.1f}s "
          f"manifest={run_dir/'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())