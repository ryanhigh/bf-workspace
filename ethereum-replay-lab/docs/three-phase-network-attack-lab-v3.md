# 三阶段网络攻击复现平台 — 最终工程化技术方案

> 本文档是**最终版工程化方案**（v3），结合两天实测 + 文献分析 + 两层架构
> （攻击在网络层 EL/devp2p，观测在共识层 CL/PoS），含具体镜像、拓扑、
> 规模、注入接口。**评审后待调整，未运行新实验，版本未最终锁定。**

日期: 2026-09-09
状态: **工程化方案 v3（待用户审阅）**

---

## 〇、版本修正（加观测层后必须调整）

上一版（v2）推荐"路线 B 统一 geth v1.10.x"基于"三攻击都在 devp2p"。
但确定要加**共识层观测**后，此推荐**不成立**，必须修正：

> **geth v1.10.x 是 pre-merge，没有 engine API，无法组成 PoS 链。**
> 观测层要 PoS（proposer boost / 1-block reorg / finality）**必须用
> 支持 engine API 的现代 geth（v1.14+ / latest）**。
> 攻击节点若要和观测层**同一个 devp2p 网络**，也**必须用同代 geth**
> （devp2p 协议版本一致才能互通）。

**最终版本结论**：统一用**现代 geth（latest / 1.17.x）**作为攻击层 + 观测层
共同底座。
- Eclipse：论文 v1.14.3，现代代 ✓（无 GAP）
- Gethlighting：tx-flood 漏洞机制**需移植到现代 geth**（标 `[GAP-移植]`，
  因为 v1.10 无法与观测层同网）
- Nontargeted：傀儡节点 5 处修改**需移植到现代 geth**（标 `[GAP-移植]`）

> 这是加"共识层观测"的必然代价：攻击节点和观测链 EL 必须同代同网。

### 〇.1 三篇论文的 Geth 版本（论文原文核对）

下表依据三篇 PDF 原文逐条核对得出，不是推测：

| 论文 | 论文使用的 Geth 版本 | 发布/研究时点 | Merge 前后 |
|---|---|---|---|
| **Eclipse**（WWW 2026）| **v1.14.3**（原文[45]，2024-05-09 发布）| 2024 | **POST-MERGE** |
| **Gethlighting**（NDSS 2023）| **v1.10.20**（实验版本）| 2022 上半年 | **PRE-MERGE** |
| **Nontargeted Delay**（IEEE TCyb）| **v1.10.19**（修改版）| 2022 前后 | **PRE-MERGE** |

**Merge 分界（关键事实）**：
- The Merge = 2022-09-15（PoW → PoS）
- **Geth v1.10.23 是第一个 post-merge 版本**；v1.10.21 已引入 Sepolia PoS 支持
- **v1.10.20 及之前 = PRE-MERGE（无 engine API，无法组 PoS 链）**
- **v1.14.3 = POST-MERGE（有 engine API，支持 PoS，能组链出块+finalize）**

### 〇.2 各论文的漏洞修复声明（论文原文核对）

| 论文 | 利用的机制/漏洞 | 是否声明后续修复 | 原文证据 |
|---|---|---|---|
| **Eclipse** | 连接槽预占（每节点只收 34 incoming）+ discovery 表/DNS 污染 | **明确"至今未修复"** | "They acknowledged our reported problem... though **no final fix has been released yet**."；早期缓解："Since v1.9.11, Ethereum also uses DNS-based peer discovery" |
| **Gethlighting** | devp2p 消息并发处理不公平 / TX 泛洪（20 SLOC 核心逻辑）| **明确已修复（Geth 1.11.0 hotfix）** | "Ethereum Foundation has acknowledged this vulnerability in September 2022 and one of our countermeasures has been **accepted as a hotfix for Geth 1.11.0**." |
| **Nontargeted Delay** | 连接管理缺陷（大量傀儡连接：抬 maxpeer、伪造 nodeID、绕冗余校验）| **未见弃用/修复声明**（2025 提交，称在 ETHW/premerge 有效；未在 post-merge 复现）| 全文只提 "bypass connection restrictions"，未声明 hotfix |

### 〇.3 对方案的关键影响

1. **三个版本分属两代，无法在同一 devp2p 网络共存**：
   - Gethlighting / Nontargeted → v1.10.x（pre-merge，devp2p 协议旧）
   - Eclipse → v1.14.3（post-merge，需 engine API）
2. **若三攻击要放同一条链上混合**，必须统一到 **post-merge 现代 geth（v1.14+ / latest）**——唯一同时满足"组 PoS 观测链"和"三攻击 devp2p 协议一致"。
3. **Gethlighting / Nontargeted 是 pre-merge 时代发现/验证的机制**，移植到现代 geth 需重新验证：
   - Gethlighting：v1.10.20 漏洞在 **1.11.0 已修**，移植需判断机制是否重现（或仅部分适用）
   - Nontargeted：post-merge 连接限制已变（v1.14 每节点 34 incoming 为 Eclipse 论文确认），需重测
4. **Eclipse 是三者中唯一"论文版本本身就在 post-merge"**，直接用现代 geth，无 GAP。

---

## 一、总体架构（两层 + 一个编排器）

```
┌─────────────────────────────────────────────────────────────┐
│ 【观测层】共识 PoS 链 (Kurtosis 拉起)                          │
│   EL(现代geth)×1 + CL(信标)×1~3 + validator 进程×N(64~256账户)│
│   → 产出: proposer boost / 1-block reorg / finality /         │
│           missed_attestation / validator奖励惩罚              │
└─────────────────────────────────────────────────────────────┘
                    ▲ 攻击效果在这里裁决
┌─────────────────────────────────────────────────────────────┐
│ 【攻击层】devp2p EL 节点池 (同一 PoS 网络的 EL 节点)            │
│   bootnode + victim + honest×M + attacker×N + delay + sync    │
│   → 三阶段操作发布于 devp2p                                    │
└─────────────────────────────────────────────────────────────┘
                    ▲
┌─────────────────────────────────────────────────────────────┐
│ 【编排器】unified_action.py                                    │
│   全局动作池 + 跨场景执行器 + 统一事件日志                      │
│   Kurtosis 负责拉起整个 enclave, 攻击节点以自定义 EL service 挂入│
└─────────────────────────────────────────────────────────────┘
```

---

## 二、每次重放：网络规模（可配置，受磁盘约束）

磁盘 2GB 可用（硬约束）→ **一次只重放一个三阶段序列，跑完即拆**。
下表为"最小可验证" vs "完整/论文"两档，靠参数切换：

| 角色 | 最小 | 完整/论文 | 说明 |
|---|---|---|---|
| EL (观测链) | 1 | 1 | modern geth, 挂 CL |
| CL 信标 | 1 | 1~3（多版本做对抗）| prysm/lighthouse/teku |
| validator 进程 | 1(≥64 账户) | 1~2(256 账户) | 至少1个诚实足够出块+finalize |
| bootnode | 1 | 1 | EL 握手/发现锚点 |
| victim | 1 | 1 | 被观测节点 |
| honest ×M | 1 | 2~3 | 对照 |
| attacker ×N | 4 | 8~50 | Eclipse 填槽/Nontargeted 傀儡/Gethlighting 泛洪 |
| sync | 1 | 1 | Nontargeted: 供 chain state |
| delay | 1 | 1~2 | Nontargeted: 建傀儡连接 |

**最小可行集**：1 EL + 1 CL + 1 validator + 1 victim + 1 attacker ≈ 6 节点，
即可跑通"攻击→观测到影响"闭环。

---

## 三、镜像清单（几个镜像 × 每阶段用哪个）

| 镜像 | 版本/tag | 大小 | 用途 | 阶段 | 可改? |
|---|---|---|---|---|---|
| `ethereum/client-go` | `latest`(1.17.x) | 70MB | 观测链EL + 攻击层 victim/honest/bootnode/attacker | ①②③ | 不改 |
| `ethereum/client-go` | `latest`(自构建 `-delay`) | +增量 | Nontargeted delay/sync 傀儡节点 | ② | **改**(源码5处) |
| `sigp/lighthouse` | `latest` | 208MB | 观测 CL 信标(默认) | 观测 | 不改 |
| `local/teku` | `develop` | 446MB | 变体对照 CL | 观测(可选) | 不改 |
| `ethpandaops/ethereum-genesis-generator` | `6.1.2` | 224MB | PoS genesis 生成 | 观测 | 不改 |
| `protolambda/eth2-val-tools` | `latest` | 87MB | 生成 validator keystore | 观测 | 不改 |
| `ethpandaops/dora` | `latest` | 233MB | 浏览器看链状态(观测辅助) | 观测 | 不改 |

> 攻击层 EL 与观测层 EL 共用同一 `ethereum/client-go:latest`（同代才能同网共存）。
> Nontargeted 改动仅在此镜像基础上 build 派生 `-delay` 变体。

---

## 四、网络拓扑（一个具体可部署拓扑）

```
          ┌─ PoS 观测网络 (Geth + Lighthouse + Validator) ─┐
          │                                                   │
   [CL beacon]──engine API──[EL victim]
          │                        │  devp2p
          ▼                        ▼
   [validator×N]            [EL honest×M]
                                    │
   ┌──────────────────────── devp2p P2P 层  ──────────────────┐
   │   [bootnode]   [attacker×N]   [delay]   [sync]            │
   └──────────────────────────────────────────────────────────┘

   * 观测链: EL victim + CL beacon + validator 构成 PoS 链, 出块/质押/最终性
   * 攻击节点: attacker/delay/sync 以 EL 节点身份加入 devp2p 网络
     - Eclipse:     attacker 填 victim discovery 表/占 incoming 槽
     - Nontargeted: delay 建傀儡连接, sync 供 state
     - Gethlighting: attacker 泛洪无效交易
```

所有节点同一 docker network（Kurtosis enclave 内），攻击节点不参与
PoS 共识，只做 devp2p 层扰动。

---

## 五、可配置性 & 可不可改

| 项 | 可配置 | 方式 |
|---|---|---|
| 每角色节点数 | ✓ | Kurtosis manifest / attack.sh 参数 |
| validator 账户数 | ✓ | eth2-val-tools 生成 N 密钥 |
| CL 客户端版本 | ✓ | 切换 prysm/lighthouse/teku 镜像 tag |
| attacker 数 N | ✓ | `attack.sh eclipse-b 8` / `50` |
| 攻击窗口时长 | ✓ | ECLIPSE_WAIT（建议以 slot 为单位）|
| 攻击起始 slot | ✓ | strategy JSON |
| 哪些镜像修改 | 仅 Nontargeted delay/sync 源码改动，其余不改 | 自构建 `client-go:1.17-x-delay` |

---

## 六、最小操作池如何注入网络环境（接口定义）

### 6.1 动作池（unified_action.py，唯一一份，三攻击共享）

每个动作是类，声明三样东西：`exec_kind`（注入方式）、`target`（作用角色）、
`run(ctx, params)`（如何调）。

```python
class Action(ABC):
    name: str            # 动作名, strategy JSON 里引用
    exec_kind: str       # local | rpc_admin | rpc_beacon | rpc_file
    target: str          # bootnode/victim/attacker/delay/sync/beacon/validator
    @abstractmethod
    def run(self, ctx, params): ...   # ctx=运行时上下文(容器名/IP/端口)
```

### 6.2 注入方式的 4 种 `exec_kind`

| exec_kind | 实现 | 用于 |
|---|---|---|
| `local` | controller 进程内(sleep/等slot) | 控制流 |
| `rpc_admin` | `docker exec <c> wget http://<c>:8545` → geth admin RPC | Eclipse 填槽、Gethlighting 泛洪 |
| `rpc_beacon` | `docker exec <c> wget http://<c>:3500` → beacon/validator API | 观测层读写 |
| `rpc_file` | `docker exec sh -c "echo ... > /root/file"` | Nontargeted 改配置 |

### 6.3 Strategy JSON（攻击序列声明格式）

```json
{
  "uid": "three-phase-001",
  "phases": [
    { "t_rel_slot": 10, "scene": "obs", "role": "attacker",
      "actions": [ {"name": "resolve_enode"}, {"name": "burst_dial"} ] },
    { "t_rel_slot": 20, "scene": "attack", "role": "delay",
      "actions": [ {"name": "inflate_maxpeer"}, {"name": "spawn_fake_nodeid"} ] },
    { "t_rel_slot": 30, "scene": "attack", "role": "attacker",
      "actions": [ {"name": "tx_flood"} ] }
  ]
}
```

### 6.4 执行器路由（关键机制）

```python
class UnifiedExecutor:
    def run(self, strat, ctx_factory):   # ctx_factory: role -> 该角色容器信息
        for phase in strat.phases:
            wait_until_slot(phase.t_rel_slot)
            for ad in phase.actions:
                action = ACTION_POOL[ad["name"]]
                if action.target != phase.role:
                    raise ValueError(...)            # 角色校验
                ctx = ctx_factory(action.target)     # 拿到容器名/IP/端口
                result = action.run(ctx, ad["params"])
                append_event({run_id, phase, action, role, ok, t, ...})
```

**注入关键点**：`ctx_factory(role)` 把角色名映射到具体容器，executor 据此
把动作发到正确节点。攻击节点挂进 Kurtosis 网络后，由 `ctx_factory` 提供其
容器/IP。**跨阶段多场景**路由：`scene` 字段区分 obs/attack 子网，`role`
区分角色，`target` 校验动作归属。

### 6.5 统一事件 schema（三攻击可比对）

```json
{ "run_id": "...", "phase": "①", "role": "attacker",
  "action": "burst_dial", "exec_kind": "rpc_admin",
  "ok": true, "t_slot": 12, "target": "victim",
  "evidence": {"inbound_peers": 8} }
```

---

## 七、资源预算（当前宿主机实测）

| 项 | 现状 | 约束 |
|---|---|---|
| 磁盘 | **2GB 可用**(98%满) | **最紧**——一次只跑一个序列，跑完拆 |
| 内存 | 62GiB(59可用) | 充裕，可大规模 |
| CPU | 32 核 | 充裕 |
| Kurtosis | engine 1.15.2 + CLI ✓ | 可用，本地已有 genesis-generator + dora |
| 需新增镜像 | Nontargeted delay 变体(自build) | 现代 geth 源码改动 |

---

## 八、建议落地顺序

1. **阶段1 工具链验证**：Kurtosis 拉起最小 PoS 测试网（1 EL + 1 CL + N
   validator），确认出块 + finalize + 读 proposer boost。**同时验证能否
   挂自定义 EL 攻击节点**。
2. **阶段2 攻击节点接入**：attacker 以自定义 EL service 挂入 enclave，用
   Eclipse `admin_addPeer` 填 victim 槽，确认观测层看到 peer 拓扑变化。
3. **阶段3 三阶段序列**：attacker/delay/sync 上施加 ①Eclipse ②Nontargeted
   ③Gethlighting，统一 events 采集，共识层裁决影响。
4. **阶段4 混合编排**：验收"打散混合"（一个 JSON 跨阶段任意取动作）。

---

## 九、待办 / 待评审确认

- [x] 版本结论：统一现代 geth (latest/1.17.x) 作为攻击+观测共同底座——已按论文原文核对
      （§〇.1：Eclipse=v1.14.3 post-merge，Gethlighting=v1.10.20 pre-merge，
      Nontargeted=v1.10.19 pre-merge；§〇.3 结论）
- [ ] Nontargeted / Gethlighting 机制移植到现代 geth，标 `[GAP-移植]`，是否接受
- [ ] 磁盘 2GB 约束下"一次一序列 + 跑完拆"，是否接受
- [ ] 是否采纳第 8 节落地顺序，从阶段 1 工具链验证开始
