# Engine API 握手验证 — Geth v1.14.3 ↔ Lighthouse v8.2.0

> 目的：验证「观测层」Geth v1.14.3 (Engine API v3 / Deneb) 能否与 CL
> (Lighthouse v8.2.0) 通过 Engine API 连接握手并出块。这是方案「阶段1
> 工具链验证」的核心。

日期: 2026-09-09
结果: **成功（chain producing blocks）**

---

## 1. 验证方法

用 Kurtosis (本地 ethpandaops/ethereum-package 仓库副本) 拉起最小 PoS 测试网：
- 1 EL: `ethereum/client-go:v1.14.3`
- 1 CL: `sigp/lighthouse:latest` (v8.2.0)
- 1 VC: `sigp/lighthouse:latest` (validator client)
- 64 validator keys
- preset=minimal, network=kurtosis, deneb_fork_epoch=0, **electra_fork_epoch=far-future**（关键：Geth v1.14.3 只到 Deneb/v3，不支持 Electra/v4）

enclave: `erl-eph-geth114`
args: `work/kurtosis-eph/args-minimal.yaml`

---

## 2. 成功证据（真实日志）

### Lighthouse (CL) 侧 — Engine API 握手成功
```
Execution engine online
Issuing forkchoiceUpdated  head_block_hash: 0x7e638…, safe_block_hash: 0x000…, finalized_block_hash: 0x000…
Prepared beacon proposer   slot: 4, validator: 9
Signed block published     slot: 3, publish_delay_ms: 1
Valid block from HTTP API  slot: 3, proposer_index: 14
```

### Geth (EL) 侧 — 每个 slot 产出 payload 并导入
```
Starting work on payload   id=0x03188c…
Updated payload            number=1 hash=7e6386..c830ee txs=0
Imported new potential chain segment  number=1 hash=7e6386..c830ee blocks=1 txs=0
Updated payload            number=2 hash=4c50d6..889339
Updated payload            number=3 hash=af4286..9bf25c
Imported new potential chain segment  number=3 blocks=1 txs=0
```

---

## 3. 结论

- **Geth v1.14.3 与 Lighthouse v8.2.0 通过 Engine API 成功建立连接、握手、出块**。
- CL 侧 `Execution engine online` + `Issuing forkchoiceUpdated` 证明 Engine API 可用；
  EL 侧 `Imported new potential chain segment` 证明 CL 提交的 payload 被 EL 接受并导入。
- `finalized_epoch: 0` 因单 CL 节点 + `peers: "0"`——finality 需 2/3 验证者见证，
  单节点慢是正常的，**不影响 Engine API 握手成功的结论**。

---

## 4. 过程中修复/解决的问题（对方案的关键意义）

### (a) `--override.genesis` flag — 版本不兼容的真正体现
ethereum-package 给自定义/devnet 网络的 geth 注入 `--override.genesis=/.../genesis.json`。
**Geth v1.14.3 无此 flag**（它是为 Osaka/Prague 时间戳覆盖在后来版本加的）。
→ **证明 v1.14.3 是 Deneb 代；要适配它必须用 `geth init` 而非 `--override.genesis`。**

修复：改本地副本 `src/el/geth/geth_launcher.star`，去掉 `--override.genesis`，
改为先 `geth init --datadir /data/geth/execution-data /network-configs/genesis.json`
再启动。**这是对实验布局(容器 entrypoint)的非侵入适配，不涉及攻击逻辑。**

### (b) fork 高度必须匹配 — `electra_fork_epoch` 必须调远
Geth v1.14.3 只支持到 Deneb (Engine API v3)。若 genesis 配置默认
`electra_fork_epoch: 0`（ethereum-package 默认），CL 会尝试用 Electra/v4
方法，Geth 不支持 → 起不来。**必须把 `electra_fork_epoch` 设为 far-future。**
（对应方案 §〇.4 的结论：genesis 必须显式配 Deneb。）

### (c) 磁盘不足触发 geth 自保关闭
首次运行时 geth 完整启动到 Engine API 8551 后，因宿主机 `available=1.88GiB`
触发 `Low disk space. Gracefully shutting down`。清理 build cache 后磁盘
升至 5.8G，再次运行成功。**确认宿主机磁盘是硬约束，需预留 ≥5GB。**

---

## 5. 对整体方案的意义

1. **观测层可行性确认**：`Geth v1.14.3 + Lighthouse v8.2.0` 能组 PoS 链并出块。
2. **版本适配成本明确**：ethereum-package 需要 geth 支持 `--override.genesis`
   (即"足够新"的版本) 或走非侵入的 `geth init` 适配。v1.14.3 走后者。
3. **fork 配置是成败关键**：genesis 必须显式锁 Deneb（electra far-future），
   否则 CL/EL engine API 版本对不上。

---

## 6. 复现命令

```bash
# 本地已有 ethereum-package 仓库 (绕开 GFW github 克隆)
cd /data/DeAtkVer/ethereum-replay-lab/work/kurtosis-eph
kurtosis run --enclave erl-eph-geth114 --args-file args-minimal.yaml .
# 查看服务
kurtosis enclave inspect erl-eph-geth114
kurtosis service logs erl-eph-geth114 cl-1-lighthouse-geth
kurtosis service logs erl-eph-geth114 el-1-geth-lighthouse
# 清理
kurtosis enclave rm -f erl-eph-geth114
```

args-minimal.yaml 关键项:
```yaml
participants:
  - el_type: geth
    el_image: ethereum/client-go:v1.14.3
    cl_type: lighthouse
    cl_image: sigp/lighthouse:latest
    count: 1
network_params:
  preset: minimal
  network: kurtosis
  deneb_fork_epoch: 0
  electra_fork_epoch: 18446744073709551615   # 关键: far-future, 锁 Deneb/v3
```
