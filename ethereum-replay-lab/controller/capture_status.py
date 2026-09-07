#!/usr/bin/env python3
"""STATUS.md generator for the Ethereum Replay Lab.

Appends dated evidence sections to docs/STATUS.md. Run by `make doctor`
or `make status`.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "STATUS.md"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def safe_run(cmd: list[str], timeout: int = 30) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return (out.stdout or "") + (out.stderr or "")
    except Exception as exc:
        return f"<error: {exc}>"


def append_section(title: str, body: str) -> None:
    with STATUS.open("a") as fh:
        fh.write(f"\n## {title} — captured {now()}\n\n")
        fh.write(body)
        if not body.endswith("\n"):
            fh.write("\n")


def section_0_host() -> str:
    lines = ["```"]
    lines.append(safe_run(["uname", "-a"]).strip())
    release = safe_run(["bash", "-lc", "source /etc/os-release && echo $PRETTY_NAME"]).strip()
    lines.append(f"OS: {release}")
    nproc = safe_run(["nproc"]).strip()
    mem_total_mb = 0
    mem_avail_mb = 0
    mem = safe_run(["bash", "-lc", "awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print t, a}' /proc/meminfo"]).strip()
    if mem:
        try:
            t, a = mem.split()
            mem_total_mb = int(t) // 1024
            mem_avail_mb = int(a) // 1024
        except Exception:
            pass
    lines.append(f"nproc={nproc}  mem_total_MB={mem_total_mb}  mem_avail_MB={mem_avail_mb}")
    disk = safe_run(["bash", "-lc", "df -B1G /data | tail -1"]).strip()
    lines.append(f"disk_data: {disk}")
    lines.append(f"docker: {safe_run(['bash', '-lc', 'docker version --format {{.Server.Version}}']).strip()}")
    lines.append(f"compose: {safe_run(['bash', '-lc', 'docker compose version --short']).strip()}")
    lines.append(f"buildx: {safe_run(['bash', '-lc', 'docker buildx version']).strip()}")
    lines.append(f"java: {safe_run(['bash', '-lc', '/home/ubantu/jdk/bin/java -version 2>&1 | head -1']).strip()}")
    lines.append(f"go: {safe_run(['bash', '-lc', 'go version 2>&1']).strip()}")
    lines.append(f"python3: {safe_run(['bash', '-lc', 'python3 --version 2>&1']).strip()}")
    lines.append(f"id: {safe_run(['bash', '-lc', 'id']).strip()}")
    sudo = safe_run(["bash", "-lc", "sudo -n true 2>&1 || echo NEEDS_PASSWORD"]).strip()
    lines.append(f"sudo -n: {sudo}")
    cli_plugins = safe_run(["bash", "-lc", "ls ~/.docker/cli-plugins/ 2>&1"]).strip()
    lines.append(f"docker-cli-plugins: {cli_plugins}")
    mirrors = safe_run(["bash", "-lc", "cat /etc/docker/daemon.json 2>&1"]).strip()
    lines.append(f"/etc/docker/daemon.json:\n{mirrors}")
    lines.append("```")
    return "\n".join(lines)


def section_1_images() -> str:
    images = [
        "tscel/bf.prysm:v4.0.5-1",
        "tscel/bf.prysm:v4.2.1",
        "tscel/bf.prysm:v5.0.1",
        "tscel/bf.prysm:v5.1.2",
        "tscel/bf.prysm:v5.2.0",
        "tscel/bunnyfinder:latest",
        "tscel/bunnyfinder:capella",
        "tscel/prysmctl:v5.2.0",
        "tscel/geth:v1.13-base-v5",
        "ethereum/client-go:latest",
        "sigp/lighthouse:latest",
        "ethpandaops/dora:latest",
        "ethpandaops/ethereum-genesis-generator:6.1.2",
        "protolambda/eth2-val-tools:latest",
        "local/teku:develop-jdk21",
        "mysql:latest",
    ]
    lines = ["```"]
    for img in images:
        out = safe_run(["docker", "image", "inspect", img, "--format", "{{.Id}} ({{.Size}})"])
        if out.strip() and "<error" not in out:
            lines.append(f"OK       {img}  {out.strip()}")
        else:
            lines.append(f"MISSING  {img}")
    lines.append("```")
    return "\n".join(lines)


def section_2_artefacts() -> str:
    paths = [
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/attack.sh",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/build.sh",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/runtest.sh",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/case/attack-basic.yml",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/case/attack-none.yml",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/case/mysql.yml",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/config/config.yml",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/config/genesis.json",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/config/genesis.ssz",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/config/attacker-config.toml",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/entrypoint/execute.sh",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/entrypoint/beacon.sh",
        "/data/DeAtkVer/Bunnyfinder/bf_minimal/entrypoint/validator.sh",
    ]
    lines = ["```"]
    for p in paths:
        if os.path.exists(p):
            st = os.stat(p)
            lines.append(f"OK   {p}  ({st.st_size} B)")
        else:
            lines.append(f"MISS  {p}")
    lines.append("```")
    lines.append("")
    lines.append("### bf_workspace case listing (read-only inventory)")
    lines.append("")
    for ver in ("v4", "v5"):
        d = Path(f"/data/DeAtkVer/Bunnyfinder/bf_workspace/{ver}/case")
        if d.is_dir():
            lines.append(f"**{ver}**")
            for p in sorted(d.iterdir()):
                lines.append(f"  - {p.name}")
            lines.append("")
    return "\n".join(lines)


def section_3_other_docker() -> str:
    lines = ["```"]
    lines.append("networks (non-builtin):")
    out = safe_run(["docker", "network", "ls", "--format", "{{.Name}}\t{{.Driver}}"])
    for ln in out.splitlines():
        if not ln:
            continue
        name, driver = ln.split("\t", 1)
        if name in ("bridge", "host", "none"):
            continue
        lines.append(f"  {name}  {driver}")
    lines.append("")
    lines.append("containers (running or stopped, last 30):")
    out = safe_run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"])
    for ln in out.splitlines()[:30]:
        lines.append(f"  {ln}")
    lines.append("```")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    if not STATUS.exists():
        STATUS.write_text(
            "# STATUS — Phase 0 evidence capture\n\n"
            "> Append-only evidence log. Each section is captured during a real\n"
            "> command run in this session. Do not edit retroactively; add a new\n"
            "> dated section if re-running.\n"
        )

    if argv == ["init"]:
        return 0

    for sec in argv:
        if sec == "host":
            append_section("§0 host facts", section_0_host())
        elif sec == "images":
            append_section("§1 image presence + digests", section_1_images())
        elif sec == "artefacts":
            append_section("§2 compose artefacts + bf_workspace", section_2_artefacts())
        elif sec == "other":
            append_section("§3 other docker resources", section_3_other_docker())
        elif sec == "all":
            append_section("§0 host facts", section_0_host())
            append_section("§1 image presence + digests", section_1_images())
            append_section("§2 compose artefacts + bf_workspace", section_2_artefacts())
            append_section("§3 other docker resources", section_3_other_docker())
        else:
            print(f"unknown section: {sec}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))