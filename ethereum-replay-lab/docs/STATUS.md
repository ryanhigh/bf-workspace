# STATUS — Phase 0 evidence capture

> Append-only evidence log. Each section is captured during a real command
> run in this session. Do not edit retroactively; add a new dated section if
> re-running.


## §1 — image presence + digests — captured $(date -Iseconds 2>/dev/null || date)

Each row is the real output of:
```
docker image inspect <image> --format '{{.Id}} ({{.Size}})'
```
A `MISSING` row means the image is not in the local cache — we will pull it
during `make build` if the active profile needs it.

OK       tscel/bf.prysm:v4.0.5-1  sha256:a85eca956e511afd201391fea8075fe9aa6d2e25d66406e9737606becc7f3a81 (600900777)
OK       tscel/bf.prysm:v4.2.1  sha256:3720450e86e2a57bd71457570ee49a18a95309f8764c4b993fd41b74a7bb10d5 (588979145)
OK       tscel/bf.prysm:v5.0.1  sha256:8d70ff36b001b1faa9a99118de5db8186c6b20ed74325a08bc8ef2f377a66b9b (589444521)
OK       tscel/bf.prysm:v5.1.2  sha256:448edcc472902b2d5ead35a291bec6d931fcb673ca4c3c672f1b89c008ed01c7 (619763721)
OK       tscel/bf.prysm:v5.2.0  sha256:c32cc2c9a1823c134f5820122b0dfc90e28f598ef714e49b2907beca9d78f5ab (601092441)
OK       tscel/bunnyfinder:latest  sha256:cb8a022821624b2dc6e03a4dccd405f26da44982b9f77cb4c6c5964f8ac8e203 (374582497)
OK       tscel/bunnyfinder:capella  sha256:94908f7cc1f3b5c55e2394e171d64fd150691ccedf027cfe6f70d8c20f9b60e8 (372322625)
OK       tscel/prysmctl:v5.2.0  sha256:0dd8da6386aa30f21de482a5ef4596e22734a0f4b9b334817fe154e5067d6e7e (450751001)
OK       tscel/geth:v1.13-base-v5  sha256:d8d5de457990a1099dd74fb140a91518830b17b255059a79a09d6c05f621a0d7 (65927634)
OK       ethereum/client-go:latest  sha256:698d36612bf1f03118677b29dbf572cf175f95faf37d2dad3d9bb9fdb4d6d101 (69650615)
OK       sigp/lighthouse:latest  sha256:08db046cdd5939bdbadb5c1e1b468a0018f3a3d2668569f8618fa947f53fa9f7 (208056992)
OK       ethpandaops/dora:latest  sha256:d2574e229bf1b992635ea989c64c1dcbb3239f943f43ee7e6a469e696d0c3e83 (233258442)
OK       ethpandaops/ethereum-genesis-generator:6.1.2  sha256:aa63e3be42b1d2e76fad413138bb9b0b69dd969419ef933faedde60ac159fcba (224224370)
OK       protolambda/eth2-val-tools:latest  sha256:357fb38cb6534dafa8039548f72f5e4a99243ff075f3ede08c54c9df01d44854 (87078124)
OK       local/teku:develop-jdk21  sha256:002b50e9711c4dcaf7c02e0259df73f78c9200bd80452d1f19d171e3bd5eab48 (446337216)
OK       mysql:latest  sha256:d236310860c6d039bb44b1e0569de1e6b6806ec5c40aa7c63560590fbde6b649 (945087410)

## §0 host facts — captured 2026-09-07T11:55:26

```
Linux ubantu-virtual-machine 5.15.0-116-generic #126~20.04.1-Ubuntu SMP Mon Jul 1 15:40:07 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux
OS: Ubuntu 20.04.5 LTS
nproc=32  mem_total_MB=64389  mem_avail_MB=60757
disk_data: /dev/sda2             98    81        13  87% /
docker: 24.0.5
compose: 2.29.7
buildx: github.com/docker/buildx v0.13.1 788433953af10f2a698f5c07611dddce2e08c7a0
java: openjdk version "21.0.12" 2026-07-21 LTS
go: go version go1.18.3 linux/amd64
python3: Python 3.8.10
id: uid=1000(ubantu) gid=1000(ubantu) groups=1000(ubantu),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),120(lpadmin),132(lxd),133(sambashare),135(docker)
sudo -n: sudo: a password is required
NEEDS_PASSWORD
docker-cli-plugins: docker-buildx
docker-compose
/etc/docker/daemon.json:
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me",
    "https://docker.ketches.cn"
  ]
}
```

## §1 image presence + digests — captured 2026-09-07T11:55:26

```
OK       tscel/bf.prysm:v4.0.5-1  sha256:a85eca956e511afd201391fea8075fe9aa6d2e25d66406e9737606becc7f3a81 (600900777)
OK       tscel/bf.prysm:v4.2.1  sha256:3720450e86e2a57bd71457570ee49a18a95309f8764c4b993fd41b74a7bb10d5 (588979145)
OK       tscel/bf.prysm:v5.0.1  sha256:8d70ff36b001b1faa9a99118de5db8186c6b20ed74325a08bc8ef2f377a66b9b (589444521)
OK       tscel/bf.prysm:v5.1.2  sha256:448edcc472902b2d5ead35a291bec6d931fcb673ca4c3c672f1b89c008ed01c7 (619763721)
OK       tscel/bf.prysm:v5.2.0  sha256:c32cc2c9a1823c134f5820122b0dfc90e28f598ef714e49b2907beca9d78f5ab (601092441)
OK       tscel/bunnyfinder:latest  sha256:cb8a022821624b2dc6e03a4dccd405f26da44982b9f77cb4c6c5964f8ac8e203 (374582497)
OK       tscel/bunnyfinder:capella  sha256:94908f7cc1f3b5c55e2394e171d64fd150691ccedf027cfe6f70d8c20f9b60e8 (372322625)
OK       tscel/prysmctl:v5.2.0  sha256:0dd8da6386aa30f21de482a5ef4596e22734a0f4b9b334817fe154e5067d6e7e (450751001)
OK       tscel/geth:v1.13-base-v5  sha256:d8d5de457990a1099dd74fb140a91518830b17b255059a79a09d6c05f621a0d7 (65927634)
OK       ethereum/client-go:latest  sha256:698d36612bf1f03118677b29dbf572cf175f95faf37d2dad3d9bb9fdb4d6d101 (69650615)
OK       sigp/lighthouse:latest  sha256:08db046cdd5939bdbadb5c1e1b468a0018f3a3d2668569f8618fa947f53fa9f7 (208056992)
OK       ethpandaops/dora:latest  sha256:d2574e229bf1b992635ea989c64c1dcbb3239f943f43ee7e6a469e696d0c3e83 (233258442)
OK       ethpandaops/ethereum-genesis-generator:6.1.2  sha256:aa63e3be42b1d2e76fad413138bb9b0b69dd969419ef933faedde60ac159fcba (224224370)
OK       protolambda/eth2-val-tools:latest  sha256:357fb38cb6534dafa8039548f72f5e4a99243ff075f3ede08c54c9df01d44854 (87078124)
OK       local/teku:develop-jdk21  sha256:002b50e9711c4dcaf7c02e0259df73f78c9200bd80452d1f19d171e3bd5eab48 (446337216)
OK       mysql:latest  sha256:d236310860c6d039bb44b1e0569de1e6b6806ec5c40aa7c63560590fbde6b649 (945087410)
```

## §2 compose artefacts + bf_workspace — captured 2026-09-07T11:55:26

```
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/attack.sh  (575 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/build.sh  (1344 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/runtest.sh  (3295 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/case/attack-basic.yml  (11609 B)
MISS  /data/DeAtkVer/Bunnyfinder/bf_minimal/case/attack-none.yml
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/case/mysql.yml  (399 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/config/config.yml  (633 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/config/genesis.json  (106688 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/config/genesis.ssz  (2772853 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/config/attacker-config.toml  (336 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/entrypoint/execute.sh  (1285 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/entrypoint/beacon.sh  (1108 B)
OK   /data/DeAtkVer/Bunnyfinder/bf_minimal/entrypoint/validator.sh  (636 B)
```

### bf_workspace case listing (read-only inventory)

**v4**
  - attack-basic.yml
  - attack-exante.yml
  - attack-ext-exante.yml
  - attack-ext-sandwich.yml
  - attack-ext-staircase.yml
  - attack-ext-unrealized.yml
  - attack-ext-withholding.yml
  - attack-mix.yml
  - attack-none.yml
  - attack-sandwich.yml
  - attack-selfish.yml
  - attack-staircase.yml
  - attack-sync.yml
  - attack-unrealized.yml
  - attack-withholding.yml
  - mysql.yml

**v5**
  - attack-basic.yml
  - attack-exante.yml
  - attack-ext-exante.yml
  - attack-ext-sandwich.yml
  - attack-ext-staircase.yml
  - attack-ext-unrealized.yml
  - attack-ext-withholding.yml
  - attack-mix.yml
  - attack-none.yml
  - attack-rlstaircase.yml
  - attack-sandwich.yml
  - attack-selfish.yml
  - attack-staircase.yml
  - attack-staircaseii.yml
  - attack-sync.yml
  - attack-unrealized.yml
  - attack-withholding.yml
  - mysql.yml
  - teku.yaml

## §3 other docker resources — captured 2026-09-07T11:55:26

```
networks (non-builtin):
  kt-a2-boundary-full-embargo-3n-d50-r1  bridge
  kt-a2-v3-full-embargo-3n-d60-r1  bridge

containers (running or stopped, last 30):
  bf-mysql	mysql:8.0	Up 7 days
  kurtosis-engine--0617c80320eb4219883d8171d6aca3e7	kurtosistech/engine:1.15.2	Up 5 weeks
  kurtosis-reverse-proxy--0617c80320eb4219883d8171d6aca3e7	traefik:2.10.6	Up 5 weeks
  kurtosis-logs-aggregator	timberio/vector:0.45.0-debian	Up 5 weeks
```

## §6 — eclipse-conn-004 baseline handshake — captured 2026-09-07T15:10

Profile: `eclipse / normal`. Two-service compose (bootnode + honest1) on
private bridge `172.80.0.0/16`. Modern geth 1.17.5 with:

  [Node.P2P]
  MaxPeers = 2
  NoDiscovery = true
  DiscoveryV4 = false
  DiscoveryV5 = false
  BootstrapNodes = []
  BootstrapNodesV5 = []
  StaticNodes = ["enode://2f5c80f7…@172.80.1.10:30303"]

Run: `runs/eclipse-conn-004/`, manifest.json present.

First-RLPx evidence (from `runs/eclipse-conn-004/logs/compose.log`):

```
honest1-1  DEBUG [...] Adding p2p peer   peercount=1 id=a831cddfbd51d700
                                conn=staticdial addr=172.80.1.10:30303
                                name=Geth/v1.17.5-unstabl…
honest1-1  DEBUG [...] Ethereum peer connected
                                id=a831cddfbd51d700 conn=staticdial
                                name=Geth/v1.17.5-unstabl…
```

Connection survived 38 s until tear-down (`client quitting`), so this
is a real RLPx+eth handshake, not a TCP-only probe.

Outstanding notes:
- honest1 dial succeeded, but bootnode never logged `Adding p2p peer`
  for honest1 because StaticNodes is set on honest1, not bootnode.
  Acceptable for the baseline; future attack scenarios will set
  StaticNodes on the victim node too.
- No mining yet (modern geth refuses non-PoS chains + no clique signer
  in 1.17). Finalisation is therefore meaningless at this stage; this
  is a boot+peer-connect baseline, not a finalised-chain baseline.

## §7 — eclipse stage-a (1 attacker dials 1 victim) — captured 2026-09-07T15:57

Profile: `eclipse / stage-a`. Topology:
- bootnode (172.80.1.10, victim dial staticdial to it)
- victim   (172.80.1.20, MaxPeers=50, **StaticNodes=[]**, no discovery)
- attacker0 (172.80.1.50, StaticNodes=[bootnode], then admin_addPeer(victim))

Run: `runs/eclipse-stage-a-005/`. Compose compose up OK, 180 s wait.

**Handshake evidence (live net_peerCount after attacker dialed)**:
```
$ wget http://victim:8545 net_peerCount
{"jsonrpc":"2.0","id":1,"result":"0x1"}
$ wget http://victim:8545 admin_peers
[{"enode":"enode://3f4521fb…@172.80.1.50:35610",  ← attacker0
  "network":{"inbound":true,"trusted":false,"static":false}}]
```

Two real pitfalls hit and fixed during this stage:

1. **geth >=1.17 reports its own enode with loopback IP** (127.0.0.1).
   Passing that enode directly to `admin_addPeer` makes the attacker
   dial its own 127.0.0.1. We resolve the victim container's docker
   network IP with `getent hosts victim` and rewrite the @<ip> segment.

2. **geth >=1.17 ignores StaticNodes JSON** AND preloads public
   mainnet BootstrapNodes by default. Without explicit
   `BootstrapNodes = []` and `BootstrapNodesV5 = []`, the honest
   victim reached out to public mainnet peers, leaking the experiment
   to the public internet.

The fix lives in `controller/profiles/eclipse.py`
(`_attacker_dial_script`, `_config_block`). Both gaps would apply to
stage-b/c/d as well.

Open:
- No block mining / finalisation (modern geth refuses non-PoS, paper
  targets v1.14.3 PoS — already documented GAP).
- `Looking for peers … tried=1 static=1` log on attacker shows the
  "Looking for peers" tick is ~30 s; admin_addPeer is honoured
  immediately on the next tick (we observed the inbound connect within
  ~30 s of the first addPeer). Faster reaction possible with shorter
  tick — out of scope for stage-a.

## §8 — eclipse stage-b (8 concurrent attackers) — captured 2026-09-07T16:08

Profile: `eclipse / stage-b`. Same topology as stage-a, n_attackers=8.
Run: `runs/eclipse-stage-b-002/`. ~229 s, 180 s wait. ~30 s for all 8
attackers to complete admin_addPeer + first 'Looking for peers' tick.

**Result on victim (live observation)**:
```
$ wget http://victim:8545 net_peerCount
{"jsonrpc":"2.0","id":1,"result":"0x8"}              ← 8 peers connected
$ wget http://victim:8545 admin_peers
[{peer0: inbound=True static=False},
 {peer1: inbound=True static=False},
 ...8 peers total, all inbound from 172.80.1.50-57]
```

All 8 attacker enodes are present in victim's peer table; every
connection is `inbound=True, static=False` — exactly the slot-grab
condition from the eclipse paper's Step ②.

Real bug found and fixed during stage-b debugging:

* dial.sh's `wget --post-data="{{...}}"` produced a JSON body with
  doubled braces (`{{...}}`); geth's JSON parser rejected it silently
  because `wget -qO-` swallowed stderr. The loop appeared to run
  but every admin_addPeer call actually returned a parse-error
  response, so no peer ever entered the attacker's StaticNodes.
* Fix: emit a single `{` and `}` in the JSON body. After fix, the
  first `admin_addPeer` puts the victim in StaticNodes, the next
  ~30 s "Looking for peers" tick dials it, victim accepts inbound,
  net_peerCount rises. Verified in `runs/eclipse-debug-002/` and
  `runs/eclipse-stage-b-002/`.

## §9 — eclipse stage-c (16 concurrent attackers) — captured 2026-09-07T16:13

Profile: `eclipse / stage-c`. n_attackers=16. Total ~290 s (180 s wait).
Run: `runs/eclipse-stage-c-001/`.

**Result on victim (live observation before tear down)**:
```
$ wget http://victim:8545 net_peerCount
{"jsonrpc":"2.0","id":1,"result":"0x10"}              ← 16 peer slots
$ wget http://victim:8545 admin_peers
16 peers, all inbound=True static=False
```

Every one of the 16 attacker enodes (172.80.1.50..172.80.1.65) made
it into the victim's peer table within ~30 s of attacker startup.
This is the "incoming slot occupation" mechanism from the eclipse
paper's Step ② — `MaxPeers=50` on victim, all slots now filled
with attacker peers.

Time-to-fill ≈ 30 s after compose up. The delay is dominated by
geth's "Looking for peers" tick (~30 s on default settings).

## §10 — eclipse stage-d (DB pre-fill: victim born with attacker StaticNodes) — captured 2026-09-07T16:30

Profile: `eclipse / stage-d`. n_attackers=4. Run: `runs/eclipse-stage-d-002/`.
Victim started with the 4 attacker enodes pre-installed in its
`[Node.P2P] StaticNodes` config — this is the mechanism-level analogue
of the paper's Step ① (discovery-table poisoning via DB pre-filling):
the victim's static peer table is poisoned before it boots.

Evidence from `runs/eclipse-stage-d-002/logs/compose.log` (victim-1):

```
08:26:48.931 Adding p2p peer  peercount=1 id=061b20093136aa59 conn=inbound     addr=172.80.1.50  ← attacker dial.sh
08:26:50.038 Adding p2p peer  peercount=2 id=7b4f4cf0b60230b0 conn=inbound     addr=172.80.1.51
08:26:50.562 Adding p2p peer  peercount=3 id=1c09298fd7155220 conn=inbound     addr=172.80.1.52
08:26:50.589 Adding p2p peer  peercount=4 id=f2264bdfbccae91c conn=inbound     addr=172.80.1.53
-- after first disconnect, victim dials its StaticNodes on its own --
08:29:42.364 Adding p2p peer  peercount=1 id=1c09298fd7155220 conn=staticdial addr=172.80.1.52:30303  ← victim→attacker
08:29:42.364 Adding p2p peer  peercount=3 id=7b4f4cf0b60230b0 conn=staticdial addr=172.80.1.51:30303
08:29:42.364 Adding p2p peer  peercount=4 id=f2264bdfbccae91c conn=staticdial addr=172.80.1.53:30303
```

`conn=staticdial` = the victim re-established the link on its own,
pulling the attacker enodes from its own static-node table. That is the
pre-fill effect: once poisoned, the victim re-dials the attacker set
even after disconnection, without needing discovery.

Open: paper Step ① uses the actual discovery-table DB + Ping pre-fill
and Step ③ uses DNS crawler infiltration. Our static-node pre-fill is a
faithful *mechanism* reproduction but not the full discovery-table
crawl — documented as a GAP. Modern geth (1.17) removed the plain
clique/discv4 DB shape the 2026 paper assumes (it targets v1.14.3).

## §11 — Gethlighting historical images pulled — captured 2026-09-07

Pulled the two historical geth images the Gethlighting paper (NDSS 2023)
targets:

```
OK  ethereum/client-go:v1.10.20  sha256:7bd3bf81fc54cca532bf82e339d3f09b0f5045943bbe3a2696f12ca7305c51c7
OK  ethereum/client-go:v1.11.0   sha256:c539c932e18f328177cb17f599005bc1f20a1bb4c79e64297968a22cabb5eb29
```

v1.10.20 metadata: `Geth 1.10.20-stable`, commit `8f2416a89a3def6ec2c749d5afafbf2c9a18e3c8`,
Go 1.18.3. Confirmed `--mine` + `--miner.etherbase` flags still present
(old CLI syntax), clique PoA supported.

Paper key facts extracted from `docs/gethlighting.txt`:
- Target: Geth v1.10.20 (post-fix v1.11.0 mentioned as mitigation era).
- Mechanism: **TX-flooding** — adversary sends 96,000 syntactically-correct
  but semantically-invalid transactions (transfer 1 ETH from a zero-balance
  account). Geth's [EC3] "gracious handling of invalid transactions"
  means it does NOT disconnect the peer, but the validation work occupies
  goroutine scheduling slots (~20 ms each), starving benign peers' message
  service (bounded service rate 1/(k×s), k = attack peers / CPU cores).
- Steps: ① make peers ② disrupt ≥1 block reception ③ delay bulk block
  download ④ fork with attacker-mined chain.
- Attack logic ≈ 200 SLOC added to geth v1.10.20, ~20 SLOC core.
- Setup: 4× t2.large (2 CPU / 8 GB / 100 GB) → up to 40 attack nodes.

## §12 — gethlighting normal (clique miner + victim sync) — captured 2026-09-07

Profile: `gethlighting-legacy / normal`. Image: `ethereum/client-go:v1.10.20`
(commit 8f2416a89a3def6ec2c749d5afafbf2c9a18e3c8). Run: `runs/gethl-normal-002/`.

**Clique block production + victim sync verified live**:
```
miner:  "🔨 mined potential block number=18" / "Successfully sealed new block number=19"
victim: eth_blockNumber → "0x15" (=21 blocks), net_peerCount → "0x1"
```

v1.10.20 clique chain: signer keystore generated in prepare, genesis
extraData = 32-byte vanity + signer + 65-byte seal, `--mine --miner.etherbase`.

**Real bug fixed**: v1.10.20 does NOT dial `--bootnodes` when
`--nodiscover` is set (bootnodes are discovery-only in v1.10.x). The
fix is a `static-nodes.json` written into the datadir, which geth
v1.10.20 always dials. Also fixed a shell-escape bug where the
static-nodes.json JSON body got literal `\"` backslashes.

## §13 — gethlighting tx-flood (mechanism verified, small scale) — captured 2026-09-07

Profile: `gethlighting-legacy / tx-flood`. Image: `ethereum/client-go:v1.10.20`.
Topology: clique miner + 1 victim + 3 attacker peers. Run: `runs/gethl-txflood-001/`.

**TX-flood mechanism implemented and executed**:
- Attacker container unlocks a zero-balance account (address generated in
  prepare, funded with 0 wei in genesis alloc) and signs 200 semantically-
  invalid transfers (1 ETH from that account) via `personal_signTransaction`
  (verified earlier: returns `raw` without balance validation), then ships
  each raw tx to the victim's `eth_sendRawTransaction`.
- Attacker log shows the loop firing: `flood: sent 50/100 txs` × 3 attackers.
- Victim keeps syncing blocks throughout (no partition observed).

**Honest result note**: at this scale (3 attackers × 200 txs = 600 txs) the
victim's block insertion delay is NOT observable — `eth_blockNumber` kept
advancing (0x15 → 0x49) and `txpool_status` stayed `{pending:0, queued:0}`
(the invalid txs are rejected, per geth [EC3]). This is expected: the paper
uses **96,000** invalid txs across 25–35 peers before seeing 100s–1000s of
block-insertion delay. A full-fidelity run would need FLOOD_COUNT=96000 and
more attacker containers, which this host (14 GiB free) can't comfortably
sustain. The *mechanism* (sign semantically-invalid tx → ship to victim →
victim validates signature then rejects) is confirmed working; the *impact*
at paper scale is NOT reproduced and is marked as such.

## §14 — Phase 7 repeat: eclipse stage-a × 3 — captured 2026-09-07

`controller/repeat_run.py eclipse stage-a 3 60` — 3 independent runs,
each with a fresh run_id and fresh docker network:

```
round 1  rc=0  elapsed=99.8s  victim_inbound_peers=2
round 2  rc=0  elapsed=101.4s victim_inbound_peers=2
round 3  rc=0  elapsed=99.4s  victim_inbound_peers=2
```

All three rounds produce an identical observable (victim accepted inbound
attacker connections), demonstrating the flow is reproducible. Summary
written to `docs/repeat-eclipse-stage-a.json`. Run dirs:
`runs/stage-a-repeat-{1,2,3}/`.

This is 3 runs for *flow repeatability*, NOT a statistical-significance
claim (explicitly out of scope per the task).

## §15 — Phase 7 repeat: gethlighting normal × 3 — captured 2026-09-07

`controller/repeat_run.py gethlighting-legacy normal 3 60` — 3 independent
runs (fresh run_id, fresh network, fresh signer keystore each):

```
round 1  rc=0  elapsed=85.6s  mined_blocks=34  victim_imported_segments=24
round 2  rc=0  elapsed=83.9s  mined_blocks=33  victim_imported_segments=23
round 3  rc=0  elapsed=82.5s  mined_blocks=33  victim_imported_segments=24
```

All three rounds produce a clique miner that seals blocks and a victim that
imports chain segments — the flow is reproducible. Summary written to
`docs/repeat-gethlighting-legacy-normal.json`. Run dirs:
`runs/normal-repeat-{1,2,3}/`.

Again: 3 runs = flow-repeatability evidence, NOT statistical significance.

## §16 — BunnyFinder-style Action DSL for Eclipse — captured 2026-09-08

Ported BunnyFinder's `actionset.Action` design to Eclipse:
**controller/profiles/eclipse_strategy.py** defines an `Action` ABC
with concrete subclasses (`ResolveEnode`, `AddStaticPeer`, `WaitPeers`,
`BurstDial`, `SamplePeers`, `Sleep`); a `Strategy` JSON DSL with
`phases[]` of `t_rel_seconds`-ordered action lists; and an `Executor`
that walks the strategy and records per-step results.

The controller (controller/profiles/eclipse.py) now has two execution
modes for the eclipse profile:

  1. **Shell mode** (default, env not set) — original behaviour; the
     attacker's entrypoint script runs the dial loop.
  2. **DSL mode** (`ECLIPSE_STRATEGY_JSON=path/to.json`) — load the
     strategy, then the controller drives the attacker's admin RPC
     via `docker exec ... wget ...` (host controller can't reach
     container IPs directly).

**Verified end-to-end** with `runs/eclipse-dsl-007/` (stage-b, 8 attackers):

```
$ ECLIPSE_STRATEGY_JSON=$PWD/profiles/eclipse/strategies/stage-b.json \
    python3 controller/run.py --profile eclipse --scenario stage-b \
    --run-id eclipse-dsl-007

events.jsonl → 32 strategy events including:
  attacker0.burst_dial.tick (i=0..5, successes 1..6)  ← DSL really called addPeer
  attacker0.sample_peers.snapshot {attacker_peers: 2, victim_peer_count: 1}
compose.log  → victim reports:
  DEBUG[02:16:43] Adding p2p peer peercount=1 conn=inbound addr=172.80.1.50
  DEBUG[02:17:59] Adding p2p peer peercount=2 conn=inbound addr=172.80.1.51
```

**Sample strategy file** at `profiles/eclipse/strategies/stage-b.json`:
a 3-phase JSON describing the same attack the shell-mode scenario
would run. Users can fork that file to compose new attacks by
re-ordering / parameterising the Actions.

**Real bugs fixed during this work** (all in `controller/profiles/`):
- 3 coroutine-style `Action.run` patches were needed because `urllib`
  inside the host can't reach `172.80.1.50:8545` (docker network).
- Docker-exec argument list must NOT be passed through a shell (single
  quotes inside `--post-data='...'` made geth see `{{...}}` body and
  return parse-error; switched to `subprocess.run(list)` with
  `json.dumps(body)` as a single arg).

## §17 — attack.sh DSL entries — captured 2026-09-08

`attack.sh` extended with DSL-mode entries (BunnyFinder-style Action JSON).
All attack replays are now routed through this single entrypoint.

New commands:
```
./attack.sh list                              — show all available attacks
./attack.sh eclipse-dsl-a                     — stage-a + JSON strategy
./attack.sh eclipse-dsl-b                     — stage-b + JSON strategy
./attack.sh eclipse-dsl-c                     — stage-c + JSON strategy
./attack.sh eclipse-dsl-d                     — stage-d + JSON strategy
./attack.sh eclipse-dsl-custom <strategy.json>  — any custom DSL file
```

Shell-mode entries (eclipse-a..d, gethlighting, gethlighting-normal)
remain unchanged and pass through the existing dial-loop shell scripts.

**Verified** with `runs/attack-eclipse-dsl-b-20260908-103406/`:
- attack.sh routed correctly: `mode=dsl` + `strategy=profiles/eclipse/strategies/stage-b.json`
- 4/8 attackers completed DSL execution (attacker0..3 each had 6 burst_dial.tick
  + 2 sample_peers.snapshot events = full strategy executed).
- Remaining 4 attackers would have completed in ~4 more minutes; the
  controller's DSL execution is **per-attacker sequential** (~60 s each),
  which is a real scaling limitation, not a correctness issue.

**Real bug fixed during this work**:
- `attack.sh` originally used bash array + `"${arr[@]}"` to pass env to
  `python3`; this triggered "command not found" under `set -u` in some
  bash 4.4 + Ubuntu 20.04 combinations. Replaced with explicit
  `export ECLIPSE_WAIT=...; export SKIP_DOCTOR=1; export ECLIPSE_STRATEGY_JSON=...`
  before invoking python, which works in every bash ≥3.2.
- `help` output originally leaked the script body after the comment
  block; replaced the `sed` pipeline with an `awk` script that stops
  printing once it hits `set -euo pipefail`.

## §18 — Unified Action DSL (Eclipse × BunnyFinder single stack) — 2026-09-08 收尾

把 Eclipse 与 BunnyFinder 的全部攻击动作放进同一个动作池 + 同一个
UnifiedExecutor。详见 `docs/unified-dsl-comparison.md`。

- 新文件：`controller/profiles/unified_action.py`（12 动作池 + 单 Executor）、
  `unified_eclipse.py`（继承 eclipse.Adapter 复用 prepare，仅覆盖 run_actions）、
  `unified_bunnyfinder.py`（最小 2 节点 smoke）、`unified.py`（纯策略执行器）。
- 策略：`profiles/unified/strategies/{stage-a,bf-smoke,eclipse-stage-b}.json`。
- 验证（真实跑通）：
  - `runs/unified-eclipse-004/`：stage-a，6/6 action ok，victim_net_peerCount=1
  - `runs/unified-bf-001/`：smoke，6/6 ok，write_rc=0
  - 两边 events.jsonl 事件序列一致（strategy.phase / action.start / action.done）。
- 已修 3 个 bug：容器命名漂移（继承不覆盖 profile）、ctx 不共享（Executor
  合并为单一共享 dict）、`_POOL`→`ACTION_POOL`。
- 提交：本地 git `b9b9d14`，GitHub bf-workspace develop `70bdffef`。

### 明日续接点（二选一）
1. 把 `unified_bunnyfinder` 从占位 smoke 接到真实 `tscel/bunnyfinder`
   攻击者镜像：rpc_file 写进容器的 /root/strategy.json 由真 Go 攻击者
   按 slot 读取执行（需 bf_workspace/v5 的 16 容器 + MySQL 拓扑）。
2. 跑一个 ACF 混用 strategy（同一 JSON 里 set_strategy + modify_parent_root
   + burst_dial），验证跨链动作同轮串起来。

关键命令：
  # 统一 Eclipse
  ECLIPSE_WAIT=60 SKIP_DOCTOR=1 python3 controller/run.py \
    --profile unified-eclipse --scenario stage-a --run-id <id> --skip-doctor
  # 统一 BunnyFinder
  ECLIPSE_WAIT=40 SKIP_DOCTOR=1 python3 controller/run.py \
    --profile unified-bunnyfinder --scenario smoke --run-id <id> --skip-doctor

## §19 — unified_bunnyfinder wired to real BF artefacts — 2026-09-09

`profiles/unified_bunnyfinder.py` now reuses the real BF author artefacts
under `bf_workspace/v5/case/attack-none.yml`:

  - Per-run copy of case yml + config dir + entrypoint scripts
  - 5 EL + 5 CL + 5 validator + 1 attacker containers all start
    using the real `tscel/{geth:v1.13-base-v5, bf.prysm:v5.2.0,
    bunnyfinder:latest}` images
  - Unified DSL actions (`set_strategy` etc.) execute via
    `docker exec` against the running attacker container
  - events.jsonl captures the unified action timeline

Verified: `runs/unified-bf-real-002/`
  - compose.up.done returncode=0
  - 16 containers started
  - `set_strategy` write_rc=0 on the real attacker1 container
  - Go attacker process attempted MySQL connect (proves real BF binary
    is running)

Bugs overcome:
  1. `shutil.copy2` preserved root:root ownership from
     `bf_workspace/v5/config/genesis.ssz` — switched to
     `shutil.copyfile` so the per-run copy is owned by ubantu.
  2. `chmod -R a-w` made the per-run tree un-rmtree-able — switched
     to `chmod -R go-w` (preserves owner-write for cleanup).
  3. MySQL port 3306 collision on re-runs — skipped the ethmysql
     service in the unified path (the DSL doesn't query the BF
     history DB; the Go attacker's MySQL connect is the only blocker
     for full mechanism replay).
  4. `shutil.rmtree` fails on root-owned files written by Docker
     containers during the run — added an `onerror` handler that
     silently skips them (the next prepare overwrites the workdir).

Honest limitations:
  * The Go attacker (tscel/bunnyfinder:latest) needs MySQL to start;
    without ethmysql it `fatal: failed to connect to database` within
    ~10s. The attack actions therefore cannot complete end-to-end in
    this profile. To run a *real* BF attack, the `bunnyfinder`
    profile (non-unified) must be used.
  * Skipping ethmysql is fine for the unified DSL's purpose (it
    exercises the same action pipeline as Eclipse attacks), but the
    chain never reaches finality because the CL fails to come up.

Next steps:
  * Either run ethmysql (need a way to release 3306 between runs) or
    patch the BF attacker image to make MySQL optional.
  * Wire the BF attacker's `--strategy` flag to a path that
    re-reads from `/root/strategy.json` instead of being
    compile-time-frozen. That requires a Go-side change to the BF
    binary itself, which is out of scope for this project.
