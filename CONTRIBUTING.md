# Contributing to bf-workspace

This repo holds the Bunnyfinder attack research workspace: modified consensus
clients (prysm / teku), attack tooling, RL components, and per-version
experiment harnesses (v4 / v5). Everything goes through Git so results are
reproducible and reviewable.

## Branch model

```
main       <- only stable baselines; force-push is BLOCKED by a ruleset
develop    <- day-to-day integration branch (default branch on GitHub)
feature/*  <- your working branch; cut from develop, PR back into develop
```

- **Never push directly to `main`.** It is protected by a repository ruleset
  (`protect-main`) that rejects force-pushes and branch deletion. The only way
  to change `main` is via a PR from `develop` or by a fast-forward push after
  a `git merge --no-ff develop`.
- **Always branch from `develop`**, not from `main`.
- One logical change per branch. If you are running two unrelated experiments
  at once, use two `feature/*` branches.

## Day-to-day workflow

```bash
cd /data/DeAtkVer/Bunnyfinder/bf_workspace
git checkout develop
git pull                                   # sync with origin/develop

git checkout -b feature/<short-name>       # e.g. feature/eclipse-on-attestor
# ... edit code, run experiments, record results ...
git add <specific files>                   # NOT `git add -A` for big changes
git commit -m "<type>: <short summary>"
git push -u origin feature/<short-name>

# then open a PR on GitHub: feature/<short-name> -> develop
# get a self-review or a peer review, merge
```

When `develop` has accumulated a coherent batch of changes (a reproducible
attack set, a paper-ready experiment, a release cut):

```bash
git checkout main
git merge --no-ff develop                  # produces a merge commit
git push
```

## Commit message convention

Prefix the subject with one of these types. Keep the subject under ~72 chars.
Body / footer are optional; add them when the "why" is non-obvious.

| Type       | When to use                                                |
|------------|------------------------------------------------------------|
| `attack:`  | New attack case or modification to attack logic            |
| `exp:`     | Experiment runs, results, plots, captured logs             |
| `fix:`     | Bug fix in code, config, or scripts                        |
| `refactor:`| Code restructuring with no behavior change                 |
| `perf:`    | Performance improvement (build time, attack time, etc.)    |
| `docs:`    | Documentation, notes, READMEs                              |
| `test:`    | Adding or fixing tests                                     |
| `chore:`   | Tooling, .gitignore, CI, repo plumbing, dependency bumps   |
| `revert:`  | Reverts a prior commit                                     |

Examples:

```
attack: add MsgDrop 25% policy for proposer case
fix: teku jwt secret path mismatch on v5 restart
exp: reproduce withholding on 5-node localnet, log attached
docs: import networkabil research notes
chore: ignore .gradle/ and build/ recursively under code/
```

## What NOT to commit

The following are already covered by `.gitignore`, but if you generate new
artifacts in a different shape, add a rule rather than committing them:

- `results/` — runtime node data (beaconchain, blobs, geth, keystore, db).
  Excluded by `results/` rule.
- `code/*/build/`, `code/*/.gradle/` — JVM build outputs.
- `experiment/withholding/*.tar.gz` and any other data dumps.
- `*.log`, `*.tar.gz`, `*.zip` — generated artifacts.
- `.env.local`, `.env.ndss` — local env overrides. Use them, do not commit
  them. The `.gitignore` explicitly re-allows them so they can live alongside
  the repo, but they are NOT tracked.

## Pushing and the remote

This machine uses HTTPS for `origin` with a personal access token (PAT). The
PAT is NOT stored in `.git/config`; it is supplied per-push via a transient
credential helper. If your push fails with auth errors, refresh the PAT at
https://github.com/settings/tokens and re-push.

`main` cannot be force-pushed or deleted — GitHub will reject the push with
`GH013: Repository rule violations`. If you ever need to "undo" something on
`main`, prefer a revert commit on `develop` followed by merging `develop` into
`main`, or use a revert PR directly.

## Reproducing an experiment

1. Check out the commit (or tag) the experiment was recorded against:
   ```bash
   git log --oneline | grep <case>
   git checkout <sha>
   ```
2. Use the `v4/` or `v5/` harness as it stood at that commit:
   ```bash
   cd v5
   ./runtest.sh <case-name>
   ```
3. Results land in `results/<case>/` (gitignored) and are yours to keep
   locally; do not push them back.

## Questions

Open an issue on the `develop` branch (or just ask in chat). For attack
methodology questions, see `docs/networkabil.md`.
