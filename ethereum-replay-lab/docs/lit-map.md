# Phase 0 — Literature ↔ Implementation Mapping

> Status: **draft, evidence-anchored to artefacts on this host**.
> Date: 2026-09-07.

## 0. Attachment divergence — must read before the table

The original task referenced three artefacts as PDF attachments:

1. *Eclipse Attacks on Ethereum's Peer-to-Peer Network*
2. *Partitioning Ethereum without Eclipsing It* (Gethlighting)
3. *BunnyFinder: Finding Incentive Flaws for Ethereum Consensus*

In this session **no PDF was delivered with the prompt** and the host
directory tree contains no file matching those titles. What the host does
contain that is relevant to each paper:

| Paper                         | What is on disk                                                                                                          |
|-------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| Eclipse Attacks (Heilman et al., USENIX Security 2015) | None of the artefact (we did not download anything in this session).                                    |
| Gethlighting                  | None of the artefact.                                                                                                    |
| BunnyFinder (He et al., S&P 2025, DOI 10.5281/zenodo.17042549) | Author artefact already present as `Bunnyfinder/bf_workspace/` (git-tracked, multi-version) and the slim wrapper `Bunnyfinder/bf_minimal/` |

Adjacent literature we *do* have but is **not the same** as the three target
papers, so we do not treat it as primary evidence:

* `blockchain_delay_attack_verifier_research.md` — survey of *DoSVER / DoSDET*
  (Luo et al.), an unrelated execution-layer DoS model checker.
* `IMPLEMENTATION_PLAN.md` — a previous project's Lighthouse static-analysis
  plan, unrelated to this replay lab.
* `Bunnyfinder/networkabil.md` — user-authored research notes on network-layer
  actions as extensions to BunnyFinder's SSF action space.

The mapping table below therefore mixes three evidence classes, which are
labelled explicitly per row:

* **[ART]** = directly observed in an artefact present on this host
* **[DOC]** = documentation / spec / source-code comment cited from memory
* **[GAP]** = currently not pinned by an on-disk artefact and flagged as a
  verification gap

The user instruction is to keep going without the missing PDFs. We do that,
but every row that touches Eclipse / Gethlighting in particular carries a
`[GAP]` tag so downstream agents (or humans) can revisit when those PDFs /
artefacts become available.

## 1. Mapping table

| # | Strategy / paper | Protocol layer | Attacker capability / preconditions | Client version or commit | Protocol-upgrade config | Source-code patch needed? | Observation points / success criterion | Original-reproduction vs this project |
|---|------------------|----------------|------------------------------------|-------------------------|--------------------------|---------------------------|---------------------------------------|--------------------------------------|
| 1 | **BunnyFinder — basic withholding case** | CL (Beacon) proposer/attester | Owns some `attacker_v5` validators, can edit its own message timing/content; honest validators run modified Prysm | `tscel/bf.prysm:v5.2.0` (built from `Bunnyfinder/bf_minimal/code/modified_prysm_5_2_0/`), `tscel/bunnyfinder:latest` (from `Bunnyfinder/bf_minimal/code/attacker_v5/`), `tscel/geth:v1.13-base-v5` | Capella + Deneb forks at epoch 0; Electra at epoch 100000; chainId `32382`; `SECONDS_PER_SLOT=3`, `SLOTS_PER_EPOCH=32`; 256 validators; preset `interop` | Yes — `attacker_v5` is the attacker's own client (not the honest ones). Honest Prysm `v5.2.0` is "modified" per artefact but the actual modifications live in the bf workspace's `code/` subdirs and are baked into `tscel/bf.prysm:v5.2.0`; we use that image as-is and do **not** rewrite the modified Prysm source | (a) `head/reorg` events in honest beacon logs (beacon2); (b) attacker reward CSV `/root/attackerdata/reward.csv`; (c) MySQL tables populated by the attacker process; (d) container logs of `attacker`, `beacon1`, `beacon2`. Success = reorg in honest chain AND attacker out-earns honest baseline. | Original artefact boots from `bf_workspace` working tree (compose files, runtest.sh, attack-*.yml). This project reuses `bf_minimal/` artefacts in read-only mode and adds an **adapter** under `profiles/bunnyfinder/` so the same compose is launched by the unified controller, with a per-run `BASEDIR` and `run_id` to keep state isolated |
| 2 | **BunnyFinder — withholding / staircase / exante / sandwich / unrealized / selfish / sync / staircaseii** | CL | Same as #1 | Different Prysm versions per case — confirmed: `tscel/bf.prysm:v4.0.5-1`, `v4.2.1`, `v5.0.1`, `v5.1.2`, `v5.2.0` exist on host (`docker image ls`). Mapping between case name and version lives in `Bunnyfinder/bf_workspace/attack.sh` (`v4/runtest.sh` for staircase, unrealized, withholding, selfish; `v5/runtest.sh` for everything else). We adopt this mapping | Same interop preset (#1) | Same as #1, but built from the `v4/code/` or `v5/code/` trees, depending on case | Same as #1 | Same as #1. The adapter selects which image to use based on case name, using the bf_workspace version map as ground truth (read-only) |
| 3 | **Eclipse — discovery-table / persistent node DB / DNS discovery / connection slot** | EL devp2p (RLPx, discv4, discv5) | Attacker can (a) pre-poison the victim's discovery table or DNS list before the victim boots, or (b) race the victim for connections after boot. Connection slot management (`MaxPeers`, `TrustMax`, `MaxActiveDialPeers`) is part of the attack surface | `[GAP]` — paper artefact not present on host. We will use a contemporary Geth release (`ethereum/client-go`) and reproduce the **mechanism conditions** (poisoned discovery table + connection competition). We do **not** mark this as a faithful paper reproduction until the artefact is downloaded and version-locked | Per-paper: pre-Berlin discovery, `MaxPeers` defaults of the chosen commit | Not on the victim — attacks should be possible on the unmodified client. We must verify `MaxPeers`, `TrustMax`, the SQL-db discovery v4 schema, and DNS source list in the chosen commit before claiming "Eclipse reproduction" | (a) honest victim's `peers` count never reaches the configured target during attack; (b) honest node's `BlockLookup`, `header` and `body` requests only served by attacker; (c) honest node's view of `head` diverges from honest-majority | Same as #1: we launch the unmodified client in a private network with **internal** bootnode + **internal** DNS discovery, so we can poison the DNS list and pre-seed the discovery table from inside the experiment. We do **not** close down the discovery subsystem — that would be an Eclipse-bypass, not Eclipse |
| 4 | **Gethlighting — Geth v1.10.20 / v1.11.0 mitigation** | EL block-sync (downloader) | Attacker races honest peers for serving `BlockBodies` / `Receipts`; the bug is the early-return path that signals "done" before the body actually arrived | `[GAP]` — paper artefact not present on host. We will pin `ethereum/client-go:v1.10.20` (pre-fix) and `v1.11.0` (post-fix) once Docker pulls succeed, and document the **exact commit** before any reproduction claim | pre-merge, no PoS, clique/ethash dev chain | Per the paper, no patch is needed on the vulnerable version — the mechanism is in the unmodified client. We need to verify the source commit of `v1.10.20` and `v1.11.0` before any claim | (a) honest victim's `head` advances even when it has no working peers; (b) honest node announces header but never asks for body; (c) request flood from attacker succeeds; (d) honest node's `Downloader` finishes "sync" with 0 valid block bodies | We will build the **private chain** on the chosen historical Geth version, not the latest mainnet one. We will not use `netem`/`tc` delay as a *substitute* for the mechanism — only as an explicit control |

## 2. Per-profile pinning (what we lock down before any "reproduction" claim)

For every profile we fix the following as actual files / images / commits on
this host and write the digest into `docs/PROGRESS.md` once captured:

* `pos-baseline`
  * EL image: `ethereum/client-go:latest` (digest TBD at run time)
  * CL image: `sigp/lighthouse:latest` (digest TBD)
  * genesis: locally generated via `ethpandaops/ethereum-genesis-generator:6.1.2`
  * validators: generated via `protolambda/eth2-val-tools`
  * commit/digest captured into `docs/STATUS.md` per run
* `bunnyfinder`
  * EL image: `tscel/geth:v1.13-base-v5` (digest TBD)
  * Honest CL image: `tscel/bf.prysm:v5.2.0` (digest TBD)
  * Attacker image: `tscel/bunnyfinder:latest` (digest TBD)
  * Reuses `Bunnyfinder/bf_minimal/config/{genesis.json,genesis.ssz,config.yml}` **read-only**.
  * Compose file: `Bunnyfinder/bf_minimal/case/attack-basic.yml` **read-only**,
    copied into the per-run `BASEDIR` so each run can mutate without touching the
    artefact.
* `eclipse`
  * EL image: pinned `ethereum/client-go` (digest TBD)
  * genesis: clique, fixed chainId
  * bootnode: a local `geth --nodekey...` bootnode inside the project network
  * DNS-discovery: a small in-project DNS server that publishes an attacker-controlled
    tree root signed by a project-local key
* `gethlighting-legacy`
  * EL image: pinned `ethereum/client-go:v1.10.20` (digest TBD) and `v1.11.0` for control
  * genesis: clique, fixed chainId
  * no CL

## 3. Differences from the original reproductions

* `bunnyfinder` profile: original `bf_workspace/runtest.sh` keeps state under
  `Bunnyfinder/bf_workspace/data/...`. We **mirror** it under
  `runs/<run_id>/bf_data/` instead of `data/`. The artefact is left untouched.
* `eclipse` profile: we **cannot** pin the historical Eclipse commit until the
  paper artefact is fetched. Until then we only claim "modern-Geth discovery
  table + DNS-list poisoning under controlled topology", not "Eclipse 2015
  reproduction".
* `gethlighting-legacy` profile: same caveat — we pin the *client image* but
  we do not yet have the paper's exact chain config / peer count tables.

## 4. Verification commands (run on demand, evidence stored in `docs/STATUS.md`)

```bash
# BunnyFinder artefact presence
ls -la /data/DeAtkVer/Bunnyfinder/bf_minimal/{attack.sh,build.sh,runtest.sh,case,config}
docker image inspect tscel/bf.prysm:v5.2.0 --format '{{.Id}}'
docker image inspect tscel/bunnyfinder:latest   --format '{{.Id}}'
docker image inspect tscel/geth:v1.13-base-v5   --format '{{.Id}}'

# Modern baseline presence
docker image inspect ethereum/client-go  --format '{{.Id}}'
docker image inspect sigp/lighthouse     --format '{{.Id}}'
docker image inspect ethpandaops/ethereum-genesis-generator:6.1.2 --format '{{.Id}}'
docker image inspect protolambda/eth2-val-tools --format '{{.Id}}'

# Eclipse / Gethlighting artefact presence — currently expected MISSING
ls /data/DeAtkVer/ethereum-replay-lab/artifacts/eclipse-paper 2>/dev/null && echo OK || echo MISSING
ls /data/DeAtkVer/ethereum-replay-lab/artifacts/gethlighting-paper 2>/dev/null && echo OK || echo MISSING
```