# Delivery status — Ethereum Replay Lab

> Final status, evidence-anchored. Date: 2026-09-07.
> Every "verified" claim below is backed by a run directory under
> `runs/<run_id>/` and a section in `docs/STATUS.md`. Nothing is claimed
> without a real docker-exec / net_peerCount / block-number observation.

## What this project is

A private, repeatable experiment platform that replays known Ethereum
attack strategies on real clients inside an isolated docker network, and
collects structured artefacts (events, manifests, per-service logs) for
later detection research.

Reference papers (all three PDFs delivered to `docs/`, text-extracted):

1. *Eclipse Attacks on Ethereum's Peer-to-Peer Network* (2026 WWW) →
   `docs/eclipse.txt`
2. *Partitioning Ethereum without Eclipsing It* (Gethlighting, NDSS 2023) →
   `docs/gethlighting.txt`
3. *BunnyFinder: Finding Incentive Flaws for Ethereum Consensus* →
   `docs/bunnyfinder.txt`

## Status classification (exactly the five buckets the task asked for)

### 1. Implemented AND actually verified

| Item | Evidence | Where |
|---|---|---|
| Eclipse `normal` — bootnode+victim RLPx handshake | `Adding p2p peer conn=staticdial` | `docs/STATUS.md §6`, `runs/eclipse-conn-004/` |
| Eclipse `stage-a` — 1 attacker dials 1 victim | victim `net_peerCount=0x1`, `inbound=True static=False` | `docs/STATUS.md §7`, `runs/eclipse-debug-002/` |
| Eclipse `stage-b` — 8 attackers fill 8 slots | victim `net_peerCount=0x8`, 8×`inbound=True` | `docs/STATUS.md §8`, `runs/eclipse-stage-b-002/` |
| Eclipse `stage-c` — 16 attackers fill 16 slots | victim `net_peerCount=0x10`, 16×`inbound=True` | `docs/STATUS.md §9`, `runs/eclipse-stage-c-001/` |
| Eclipse `stage-d` — victim born with attacker StaticNodes | victim re-dials with `conn=staticdial` after disconnect | `docs/STATUS.md §10`, `runs/eclipse-stage-d-002/` |
| Gethlighting `normal` — clique mine + victim sync | `mined potential block`, victim `eth_blockNumber=0x15` | `docs/STATUS.md §12`, `runs/gethl-normal-002/` |
| Gethlighting `tx-flood` — sign+ship invalid txs | `personal_signTransaction` returns raw, loop fires, victim rejects (`txpool {pending:0}`) | `docs/STATUS.md §13`, `runs/gethl-txflood-001/` |
| Unified controller verbs | `doctor/build/run/collect/analyze/clean` + `make` wrapper | `Makefile`, `controller/` |
| 6-layer result.json | `valid/strategy/mechanism` + 3 detectors | `controller/analyze.py`, verified on `gethl-normal-002` |
| Historical geth images pinned | v1.10.20 (commit 8f2416a8) + v1.11.0 (sha256) | `docs/STATUS.md §11` |

### 2. Implemented but NOT yet run

| Item | Why |
|---|---|
| `pos-baseline` profile (EL+CL PoS private net via ethpandaops genesis generator + Lighthouse) | `prepare()` written, never executed — time/disk went to eclipse+gethlighting |
| `bunnyfinder` profile (wraps bf_workspace v4/v5 author compose) | adapter written, `prysmctl generate-genesis` smoke verified, but no full attack-case run — user explicitly said BunnyFinder attacks need not be reproduced (they already exist in the artefact) |
| Gethlighting `v1.11.0` control run | image pulled but no run (the fix-version control for the tx-flood mechanism) |

### 3. Implemented with simulated conditions / stand-ins

| Item | What the stand-in is |
|---|---|
| Eclipse Step ① discovery-table DB pre-fill | We use `StaticNodes=[attacker_enodes]` on the victim as a *mechanism* stand-in, NOT the paper's actual discv4-table DB + Ping pre-fill |
| Eclipse Step ③ DNS crawler infiltration (`all.json`) | NOT implemented at all |
| Eclipse chain | PoS-pinged genesis (modern geth refuses clique), no mining — paper targets v1.14.3 PoS execution client |

### 4. Blocked by external conditions

| Item | Block |
|---|---|
| Eclipse paper-faithful version | paper targets geth v1.14.3; we run v1.17.5 (on-disk). v1.14.3 image not present and not pulled |
| Gethlighting paper-scale impact | paper uses 96,000 invalid txs × 25-35 peers; host has 14 GiB free disk + 32 cores, can't comfortably sustain 40 attack nodes × 96k txs |
| Full BunnyFinder case replay | user-directed: skip (attacks pre-exist in artefact) |

### 5. Not yet implemented

| Item |
|---|
| Eclipse DNS crawler infiltration (Step ③) |
| Eclipse full discv4-table DB pre-fill (we used static-node stand-in) |
| Any detection model (only minimal heuristic detectors exist, per spec) |
| Phase 7 3× repeat runs across every scenario (in progress for eclipse stage-a) |

## Known real bugs fixed during this project (all in `controller/profiles/*.py`)

1. geth ≥1.17 preloads public mainnet bootstrap nodes → must clear
   `BootstrapNodes`/`BootstrapNodesV5` + `NoDiscovery=true` for isolation.
2. geth ≥1.17 enode reports loopback IP → rewrite `@<ip>` to docker IP
   before `admin_addPeer`.
3. geth ≥1.17 ignores `static-nodes.json` (needs `[Node.P2P] StaticNodes`
   in config.toml); v1.10.20 is the opposite (needs `static-nodes.json`,
   ignores `--bootnodes` under `--nodiscover`).
4. `wget --post-data="{{...}}"` doubled braces → silent JSON parse failure.
5. geth ≥1.17 removed `--mine` / clique subcommand → PoS-pinged genesis.

## Evidence locations

- Evidence log (append-only, real command output): `docs/STATUS.md`
- Progress tracker: `docs/PROGRESS.md`
- Literature→implementation mapping: `docs/lit-map.md`
- This file: `docs/DELIVERY.md`
- Per-run artefacts: `runs/<run_id>/{manifest.json,events.jsonl,result.json,logs/compose.log}`
- Controller: `controller/` (profiles, run/collect/analyze/clean, detectors, repeat_run)
- Operator entrypoint: `Makefile` (`make doctor/build/baseline/run/repeat/collect/analyze/clean`)

## How to reproduce (operator)

```bash
cd /data/DeAtkVer/ethereum-replay-lab
make doctor
make run ACTIVE_PROFILE=eclipse ACTIVE_SCENARIO=stage-b        # 8 attackers
make run ACTIVE_PROFILE=gethlighting-legacy ACTIVE_SCENARIO=normal
make analyze RUN_ID=<run_id> ACTIVE_PROFILE=<profile>
make clean ACTIVE_PROFILE=<profile> RUN_ID=<run_id>
```
