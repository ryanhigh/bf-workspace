# Progress — phase tracker

This is the single source of truth for which phase is in progress, what was
verified, and what is left. Each phase lists (a) done, (b) actually-executed
verification with evidence path, (c) open questions, (d) next.

> Convention: every "verification" item below MUST be backed by a command run
> during this session whose captured output lives somewhere in this repo
> (typically `docs/STATUS.md`, `runs/<run_id>/manifest.json`, or a per-phase
> log). No claim of completion without evidence.

## Phase 0 — literature & environment reconciliation — IN PROGRESS

* **Done**
  * Created `/data/DeAtkVer/ethereum-replay-lab/` (empty before, verified).
  * Initialised in-project git (separate from `Bunnyfinder/bf_workspace/.git`).
  * Wrote `.gitignore` (secrets, run outputs, build cache excluded).
  * Wrote `docs/lit-map.md` with explicit attachment-divergence note.
  * Audited on-disk artefacts:
    * `Bunnyfinder/bf_minimal/` — present; contains `attack.sh`, `build.sh`,
      `runtest.sh`, `case/`, `config/`, `code/attacker_v5/`,
      `code/modified_prysm_5_2_0/`, `entrypoint/`.
    * `Bunnyfinder/bf_workspace/` — present; git-tracked; contains `v4/` and
      `v5/` directories, 13+ attack cases each.
    * Docker images pre-pulled: `tscel/bf.prysm` (5 versions), `tscel/bunnyfinder`
      (2 tags), `tscel/geth:v1.13-base-v5` (referenced by compose, NOT yet
      confirmed locally — see gap), `ethereum/client-go`, `sigp/lighthouse`,
      `ethpandaops/ethereum-genesis-generator:6.1.2`,
      `protolambda/eth2-val-tools`, `local/teku`.
  * Host capability audit:
    * Ubuntu 20.04 / x86_64, 32 cores, 62 GiB RAM, **98 GiB disk (only 13 GiB
      free — tight)**.
    * Docker 24.0.5 + Compose v2.29.7, buildx 0.13.1 in `~/.docker/cli-plugins/`.
    * JDK 21 (Temurin) at `/home/ubantu/jdk`.
    * Go 1.20.3 (system) — sufficient for the controller, not for the Go
      builds inside `Bunnyfinder/bf_minimal/code/attacker_v5` (those have their
      own Dockerfiles and build context).
    * `sudo -n` requires a password — we will not rely on sudo for any
      project-internal action.
    * `1ms.run`, `xuanyuan.me`, `ketches.cn` mirrors are configured in
      `/etc/docker/daemon.json`. We can pull from upstream through them.
* **Verified by**
  * `docs/STATUS.md` §0 — host facts.
  * `docs/STATUS.md` §1 — image presence + digests.
* **Open**
  * ~~Eclipse paper PDF / artefact~~ **RESOLVED** — three PDFs delivered by user on
    2026-09-07 to `docs/`:
    `000---[2026][WWW]Eclipse Attacks on Ethereum's Peer-to-Peer Network.pdf`,
    `[gethlighting]ndss2023-heo.pdf`,
    `BunnyFinder_Finding_Incentive_Flaws_for_Ethereum_Consensus.pdf`.
    Text extracted to `docs/eclipse.txt`, `docs/gethlighting.txt`,
    `docs/bunnyfinder.txt` via `pdftotext -layout`.
  * Eclipse paper target version confirmed from `eclipse.txt`: **Geth v1.14.3**
    (2024-05-09), `MaxPeers=50`, 16 outgoing / 34 incoming, discv4 table
    17×16=272 nodes, `tableIPLimit` per-bucket=16, DNS list via `all.json`.
  * Our on-disk geth is **v1.17.5** (newer; removed clique mining and changed
    discovery/static-node config semantics), so the eclipse mechanism is
    reproduced on 1.17.5 and the v1.14.3-vs-1.17.5 delta is documented as GAP.
  * Historical `ethereum/client-go:v1.10.20` / `v1.11.0` images: **[GAP]** — still
    not on disk; gethlighting-legacy stays skeletal until pulled.
* **Next**
  * ~~Finish §0-§2 of `docs/STATUS.md`.~~ DONE (plus §6-§10 eclipse evidence).
  * Move to Phase 1.

## Phase 1 — isolated baseline networks

* **Plan**
  * Build `pos-baseline` profile: 1 bootnode, 1 EL, 1 CL, 4 validators, all
    inside `erl-posb-<run_id>` network, no external DNS, no public bootnodes.
  * `bunnyfinder` profile: copy `Bunnyfinder/bf_minimal/` artefacts into a
    per-run `BASEDIR`, launch `attack-none.yml` (no-attack) and `attack-basic.yml`
    (attack) under separate compose projects.
  * `eclipse` profile: clique chain on a pinned `ethereum/client-go`, internal
    bootnode, internal DNS-discovery.
  * `gethlighting-legacy` profile: pinned `ethereum/client-go:v1.10.20`,
    clique chain, attacker-peer.
* **Verified by**: presence of `runs/<run_id>/manifest.json` for at least one
  successful baseline run.
* **Open**: nothing yet.
* **Next**: Phase 2 controller scaffolding once Phase 1 has one successful run.

## Phase 2 — automated experiment loop

* **Plan**: Python controller under `controller/` exposing
  `doctor/build/baseline/run/repeat/collect/analyze/clean` (the user-listed
  verbs). Per-run `run_id` (timestamp+uuid), `BASEDIR` isolation, manifest
  capture.
* **Verified by**: at least one `make baseline` + `make run` + `make clean`
  cycle completes and produces a parseable manifest.
* **Next**: Phase 3 (BunnyFinder).

## Phase 3 — BunnyFinder known strategies

* **Plan**: integrate the `attack-none.yml`, `attack-basic.yml`, then `attack-staircase.yml`
  and `attack-exante.yml` (one per Prysm major version) as controller-driven
  scenarios. Each scenario reuses the bf_workspace compose files via an adapter.
* **Verified by**: at least one no-attack baseline and one with-attack run per
  scenario, with `runs/<run_id>/manifest.json` and `runs/<run_id>/events.jsonl`.
* **Next**: Phase 4 (Eclipse).

## Phase 4 — Eclipse

* **Plan**: a small Eclipse lab that exercises discovery-table poisoning
  (via internal DNS discovery) and connection-slot competition. Mark as
  *mechanism reproduction* rather than *paper reproduction* until the
  artefact is pinned.
* **DONE — 4 stages verified on geth v1.17.5** (all evidence in `docs/STATUS.md`
  §6-§10, live `net_peerCount` / `admin_peers` snapshots):
  * `stage-a` (1 attacker dials 1 victim): victim `net_peerCount=0x1`, peer
    `inbound=True static=False`. Run `runs/eclipse-debug-002/`.
  * `stage-b` (8 attackers): victim `net_peerCount=0x8`, all `inbound=True`.
    Run `runs/eclipse-stage-b-002/`.
  * `stage-c` (16 attackers): victim `net_peerCount=0x10`, all `inbound=True`.
    Run `runs/eclipse-stage-c-001/`.
  * `stage-d` (4 attackers, victim born with attacker StaticNodes — DB
    pre-fill): first 4 `inbound` (attacker dial), then victim re-dials its
    own StaticNodes with `conn=staticdial` after disconnect. Run
    `runs/eclipse-stage-d-002/`.
* **Real bugs found + fixed during Phase 4** (both in
  `controller/profiles/eclipse.py`):
  1. geth ≥1.17 reports its enode with loopback IP; admin_addPeer must
     rewrite the IP segment to the docker-network IP.
  2. geth ≥1.17 preloads public mainnet bootstrap nodes by default → must
     set `BootstrapNodes=[]`, `BootstrapNodesV5=[]`, `NoDiscovery=true`,
     `DiscoveryV4/V5=false` in `[Node.P2P]`.
  3. `wget --post-data="{{...}}"` emitted doubled braces, silently breaking
     JSON; fixed to single braces.
* **GAP (not yet reproduced)**: the paper's Step ③ (DNS crawler
  infiltration via `all.json`) and the full discv4-table DB pre-fill are
  not implemented; our stage-d uses static-node pre-fill as a mechanism
  stand-in. Also the paper targets geth v1.14.3; we run v1.17.5.
* **Next**: Phase 5 (Gethlighting).

## Phase 5 — Gethlighting

* **Plan**: pinned `ethereum/client-go:v1.10.20` (vulnerable) and `v1.11.0`
  (control) clique chain with one honest victim and one attacker peer set.
  Run on a CPU-pinned container.
* **DONE — mechanism verified on v1.10.20** (evidence `docs/STATUS.md` §11-§13):
  * Pulled `ethereum/client-go:v1.10.20` (commit 8f2416a89a3def6ec2c749d5afafbf2c9a18e3c8)
    and `v1.11.0` (sha256 recorded in §11).
  * `normal`: clique miner produces blocks (`mined potential block` /
    `Successfully sealed new block`), victim syncs (`eth_blockNumber` 0x15,
    `net_peerCount` 0x1). Run `runs/gethl-normal-002/`.
  * `tx-flood`: attacker unlocks a zero-balance account and ships semantically-
    invalid transfers (1 ETH from 0-balance) via `personal_signTransaction`
    + victim `eth_sendRawTransaction`. Loop fires (`flood: sent 50/100 txs`),
    victim keeps syncing and rejects the txs (`txpool {pending:0}`), confirming
    geth [EC3] graceful handling. Run `runs/gethl-txflood-001/`.
  * Real bugs fixed: v1.10.20 doesn't dial `--bootnodes` under `--nodiscover`
    (needs `static-nodes.json`); static-nodes.json shell escaping.
* **GAP (honest)**: paper-scale impact NOT reproduced — paper uses 96,000
  invalid txs × 25-35 peers to see 100s-1000s block-insertion delay; our run
  was 600 txs (3 attackers × 200) and showed no measurable delay. The
  *mechanism* is confirmed; the *impact at scale* is not. v1.11.0 control run
  not yet executed (image pulled but unused).
* **Next**: Phase 6 (data + detector interface).

## Phase 6 — unified data + detector interface

* **Plan**: per-run `events.jsonl` with `run_id`, `profile`, `node_id`,
  `event_ts`, `event_type`, optional `peer_id/slot/block_root/exec_phase`;
  per-run `manifest.json`; per-run `result.json` with the 6-layer judgement
  (valid / executed / mechanism / node / consensus / detector).
* **DONE**: `controller/analyze.py` now extracts mechanism evidence from
  compose.log (inbound/staticdial peer counts, mined blocks, imported
  segments) and emits the 6-layer result. Verified on `gethl-normal-002`:
  `valid=True strategy=True mechanism=True` + 3 detectors all alarm=false.
  Pluggable detectors live in `controller/detectors/`.
* **Next**: Phase 7.

## Phase 7 — repeat runs + delivery

* **Plan**: 3 independent runs for each completed scenario; verify no
  state leak, full restoration, full result diffability.
* **DONE** (evidence `docs/STATUS.md §14-§15`):
  * `eclipse stage-a` × 3 — all rc=0, `victim_inbound_peers=2` every round.
    Summary `docs/repeat-eclipse-stage-a.json`.
  * `gethlighting-legacy normal` × 3 — all rc=0, `mined_blocks` 34/33/33,
    `victim_imported_segments` 24/23/24. Summary
    `docs/repeat-gethlighting-legacy-normal.json`.
  * Each round: fresh run_id, fresh docker network, fresh signer keystore,
    no state leak observed (deterministic enode cache + per-run BASEDIR).
* **Delivery docs finalised**: `docs/DELIVERY.md` (5-bucket status
  classification), `docs/PROGRESS.md` (this file), `docs/STATUS.md`
  (append-only evidence §0-§15), `docs/lit-map.md`, `README.md`, `Makefile`.
* **Next**: end of project — this is the delivery checkpoint.