# Ethereum Replay Lab

A private, repeatable experimental platform for replaying known Ethereum
attack strategies and collecting observable artefacts for downstream detection
research.

This project does **not** modify any neighbour project under `/data/DeAtkVer/`
(including `Bunnyfinder/`, `DyValid/`, `security-analysis/`, `lighthouse-static-analysis/`).
It only consumes their public, on-disk artefacts (Docker images, configs,
genesis) where useful, and never writes back into them.

## Current status (filled in by the agent as work progresses)

See `docs/PROGRESS.md` for the authoritative per-phase checklist and
`docs/STATUS.md` for the up-to-date "what was actually run" evidence map.

## Profiles

The platform supports four isolated profiles; each is an adapter on top of
the same controller:

| Profile             | Layer   | Reference client / image                | Notes                                            |
|---------------------|---------|----------------------------------------|--------------------------------------------------|
| `pos-baseline`      | EL+CL   | `ethereum/client-go` + `sigp/lighthouse` + `local/teku` | Healthy baseline, no attack                      |
| `bunnyfinder`       | EL+CL   | `tscel/bf.prysm:v5.2.0` + `tscel/geth:v1.13-base-v5` + `tscel/bunnyfinder:latest` | Reuses `/data/DeAtkVer/Bunnyfinder/bf_minimal/` artefacts |
| `eclipse`           | EL      | `ethereum/client-go` (historical)       | Keeps internal discovery on; attacker peer set   |
| `gethlighting-legacy` | EL    | `ethereum/client-go:1.10.20`           | Pre-MP-1482986 era chain semantics                |

## Layout

```
ethereum-replay-lab/
├── README.md
├── .gitignore
├── Makefile                 # doctor / build / baseline / run / repeat / collect / analyze / clean
├── docs/                    # PROGRESS.md, STATUS.md, phase reports
├── docs/lit-map.md          # literature → implementation mapping table
├── profiles/                # one subdir per profile (compose + config)
│   ├── pos-baseline/
│   ├── bunnyfinder/
│   ├── eclipse/
│   └── gethlighting-legacy/
├── controller/              # Python: orchestrator, scheduler, run/collect/analyze
├── data/                    # unified schema (events, manifest, results)
├── runs/                    # per-run_id outputs (gitignored)
└── tooling/                 # tshark helpers, metric collectors, etc.
```

## Quickstart

```bash
cd /data/DeAtkVer/ethereum-replay-lab
make doctor        # check host + Docker + required artefacts
make build          # pull / build only the images needed for the active profile
make baseline      # start a healthy profile run (no attack)
make run           # execute one experiment using the active profile + scenario
make repeat        # repeat the same experiment N times (default 3)
make collect       # normalise raw outputs into the unified schema
make analyze       # produce the per-attack result summary
make clean         # tear down ONLY this project's containers, networks, volumes
```

Each `run` produces a unique `run_id` under `runs/<run_id>/`.