# Kurtosis PoS — Geth v1.14.3 + ethpandaops Prysm (develop-minimal) producing blocks

> Goal: minimal PoS testnet via Kurtosis, geth v1.14.3 (EL) + ethpandaops
> prysm (CL/VC) producing blocks via Engine API. Path C's Genesis-gen
> incompatibility was bypassed by switching CL to a newer spec-compatible
> image (user accepted dropping BF's Prysm v5.2.0 version pin).

日期: 2026-09-09
状态: **出块，链在跑**

---

## 1. 环境配置

```yaml
# args-prysm-minimal.yaml
participants:
  - el_type: geth
    el_image: ethereum/client-go:v1.14.3
    cl_type: prysm
    cl_image: ethpandaops/prysm-beacon-chain:develop-minimal
    use_separate_vc: true
    vc_type: prysm
    vc_image: ethpandaops/prysm-validator:develop-minimal
    count: 1
network_params:
  preset: minimal
  network: kurtosis
  network_id: "3151911"
  seconds_per_slot: 12
  genesis_delay: 20
  num_validator_keys_per_node: 64
  deneb_fork_epoch: 0
  electra_fork_epoch: 18446744073709551615
  fulu_fork_epoch: 18446744073709551615
```

镜像全部本地缓存（6 个）：
- `ethereum/client-go:v1.14.3`
- `ethpandaops/prysm-beacon-chain:develop-minimal` (235MB)
- `ethpandaops/prysm-validator:develop-minimal` (222MB)
- `ethpandaops/ethereum-genesis-generator:6.1.2`
- `protolambda/eth2-val-tools:latest`
- `badouralix/curl-jq`

---

## 2. 真实证据（enclave erl-prysm114-52）

### EL (Geth v1.14.3) — 持续出块
```
Imported new potential chain segment  number=1 hash=fb08b7..3f08e8 blocks=1 txs=0
Imported new potential chain segment  number=2 hash=3a7586..711868 blocks=1 txs=0
Imported new potential chain segment  number=3 hash=849e29..6f136f blocks=1 txs=0
Imported new potential chain segment  number=4 hash=3e571a..ffc8ba blocks=1 txs=0
Starting work on payload  number=5 hash=374925..5a7317  (slot 5 in progress)
```

### CL (ethpandaops Prysm develop-minimal) — Engine API 正常
```
blockchain: Finished applying state transition  attestations=2
  payloadHash=0x3e571ae694b4  slot=4  syncBitsCount=32  txCount0
blockchain: Forkchoice updated with payload attributes for proposal
  blockRoot=0xd16afa202691  headSlot=4  nextSlot=5  payloadID=0x0
```

---

## 3. 关键事实
- **Geth v1.14.3 (DENEB) ↔ ethpandaops Prysm develop-minimal** 通过 Engine API
  持续握手 + 出块。
- 每 12 秒一个 slot，每 slot 一个块。
- **Prysm v5.2.0（BunnyFinder 原版）已被替换**——因为 ethereum-package 的
  genesis-generator 6.1.2 生成最新 spec (Electra+) 的 genesis，Deneb 时代
  的 v5.2.0 unmarshal 失败（`detected fork=deneb: incorrect size`）。
  这与方案文档 §〇.3 的判断一致。
- EL/CL/VC + validator-key-generation 共 4 个服务全部 RUNNING。

---

## 4. 已知限制（诚实标注）
- **CL 不再是 BunnyFinder 的 Prysm v5.2.0**——ethpandaops develop-minimal
  镜像（更新版）。如需精确复现 BunnyF 路线 验证走走改 ethereum-package
  的 genesis 模板（侵入性大）或在 docker compose 路线继续用 tscel v5.2.0。
- 当前最小配置（1 EL + 1 CL + 1 VC），未做攻击节点接入。

---

## 5. 复现命令

```bash
cd /data/DeAtkVer/ethereum-replay-lab/work/kurtosis-eph
kurtosis run --enclave erl-prysm114-52 --args-file args-prysm-minimal.yaml .
kurtosis service logs erl-prysm114-52 el-1-geth-prysm
kurtosis service logs erl-prysm114-52 cl-1-prysm-geth
kurtosis enclave rm -f erl-prysm114-52
```