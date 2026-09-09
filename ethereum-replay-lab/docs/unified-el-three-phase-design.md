# Three-Phase Unified EL Attack Lab — Design

> 本文档将 `docs/lit-map.md` 的文献映射 + 3 篇攻击论文 + 2 天复现实验的
> 实证结果综合成一个**统一部署方案**。核心变化：用 **Nontargeted Delay
> Attack** 替换 **BunnyFinder**，使三个攻击统一到 **geth devp2p 层**，
> 从而支持**打散混合操作序列**并在同一批节点上共链部署。

日期: 2026-09-09
状态: **设计提案 (待用户拍板)** —— 未运行任何新实验

---

## 1. 核心思想：网络层的三个阶段

以三个典型攻击代表区块链网络层的三个连续阶段。`打散混合` 指：
一个攻击序列可以横跨这三个阶段，从不同攻击里抽取操作自由组合。

| 阶段 | 网络层机制 | 代表攻击 | 作用对象 | 操作本质 |
|---|---|---|---|---|
| ① 节点发现与拓扑建立 | discovery / 连接槽 | **Eclipse** | geth 的 peer 表 + discovery 表 | 填表、占 incoming slot |
| ② 消息传播与同步 | block/tx 传播 | **Nontargeted Delay** | geth 的 peer 消息传播 | 傀儡连接制造传播延迟 |
| ③ 连接管理与资源控制 | 连接竞争 / 资源消耗 | **Gethlighting** | geth 的连接管理 + 交易池 | 无效交易泛洪、断连竞争 |

## 2. 为什么替换 BunnyFinder

### 2.1 BunnyFinder 的代价（实测）
- 需要完整 PoS 栈：**Prysm 信标 + validator + 256 账户 + genesis.ssz + MySQL**
- `tscel/bf.prysm` 是作者**修改过**的 Prysm（注入攻击 hook），不能换官方
- 拓扑固定 16 容器 + MySQL，磁盘/内存重
- 且 PoS 链必须跑出 block + finality 才能观测 reorg，时间敏感（runtest.sh 默认 3600s）

### 2.2 Nontargeted Delay 的收益（论文 §IV-B 实证）
- 攻击只改 **Geth-v1.10.19**，**纯 EL 层**，无 PoS 依赖
- 5 处修改：抬高 maxpeer、绕过冗余校验（允许重复连同一节点）、
  每次连接伪造新 nodeID、消除全链同步、抑制消息转发只响应 liveness probe
- 建立 8000~40000 个"无功能"傀儡连接制造全局传播延迟

→ 三个攻击**全部落在 geth devp2p 层**，环境从"三条不同重链"变成
"**一条轻量 EL 私链 + 一组节点池 + 三套操作**"，且**可共链混合部署**。

## 3. 版本路线决策

| 攻击 | 论文版本 | 本地已有 |
|---|---|---|
| Eclipse | v1.14.3 | latest(1.17.5) |
| Gethlighting | v1.10.20 (vuln) + v1.11.0 (control) | ✓ ✓ |
| Nontargeted | **v1.10.19 (需改源码)** | 无 → 用 v1.10.20 改造 |

> **推荐路线 B：统一锁定 v1.10.x**
> - Gethlighting / Nontargeted 本来就是 v1.10 代 (devp2p 5.x) → 无缝
> - Eclipse 核心机制 (admin_addPeer 填槽、burst dial、incoming slot 竞争)
>   在 v1.10 **完全可跑**（早期已验证 geth 1.10 建立 RLPx 连接成功）
> - 唯一差异：Eclipse 论文用 v1.14.3，v1.10 下标注 **`[GAP]`**（discovery
>   细节可能不同，但上游已确认连接槽机制一致）
> - Nontargeted 的 5 处源码修改在 v1.10.20 上直接可做

不推荐路线 A（统一 1.17.x）：需把 Gethlighting 的 tx-flood 漏洞和
Nontargeted 的傀儡节点机制**移植**到现代 geth，改动大且容易失真。

## 4. 统一环境模型

```
一个轻量 EL 实验环境 (geth v1.10.x 统一版本)
  ├── 节点池
  │     bootnode   发现/握手锚点
  │     victim     目标节点 (50 peer 槽)
  │     attackers×N  Eclipse 填槽 / Gethlighting 泛洪 / Nontargeted 傀儡
  │     honest×M   对照 + 诚实连接
  │     sync       Nontargeted: 提供 chain state
  │     delay      Nontargeted: 建傀儡连接
  ├── 一条私有 EL 链（独立 genesis + chainID + 独立 Docker 网络）
  ├── 全局动作池（unified_action.py，12+ action，全攻击唯一一份）
  │     阶段① Eclipse:   resolve_enode / add_static_peer / burst_dial / sample_peers
  │     阶段② Nontargeted: inflate_maxpeer / spawn_fake_nodeid / suppress_relay
  │     阶段③ Gethlighting: tx_flood / dial_race / drop_conn
  └── 跨场景编排器（UnifiedExecutor 升级：按 phase 的 scene/role 路由动作到节点池）
```

### 混合操作序列形态

```json
{
  "uid": "three-phase-mixed",
  "scenes": {
    "el": "scene://el/v1.10.x-standard"
  },
  "phases": [
    { "scene": "el", "role": "attacker",
      "actions": [ {"name": "resolve_enode"}, {"name": "burst_dial"} ] },
    { "scene": "el", "role": "delay",
      "actions": [ {"name": "inflate_maxpeer"}, {"name": "spawn_fake_nodeid"} ] },
    { "scene": "el", "role": "attacker",
      "actions": [ {"name": "tx_flood"} ] }
  ]
}
```

三个 phase 在**同一批节点**上串行施加 → 真正的混合，而非三座孤岛。

## 5. 镜像清单（统一 EL 底座）

| 镜像 | 版本 | 用途 | 需修改 |
|---|---|---|---|
| `ethereum/client-go` | `v1.10.20` | 统一 EL 底座 (Gethlighting vuln + Eclipse + Nontargeted 基础) | 否 |
| `ethereum/client-go` | `v1.10.20-delay` (本地 build) | Nontargeted 傀儡节点 | **是 (5 处修改)** |
| `ethereum/client-go` | `v1.11.0` | Gethlighting 对照 (修复版) | 否 |
| `mysql`(可选) | `8.0` | 仅 Gethlighting 结果存储 (可绕) | 否 |

注：Eclipse 若坚持论文 v1.14.3 需另拉镜像；统一 v1.10.x 则无需。

## 6. 与现状代码的差距

| 已有 | 待改 |
|---|---|
| `unified_action.py` 全局动作池 (12 action) | 加 Nontargeted 动作类 (spawn_fake_nodeid 等) |
| `UnifiedExecutor` 单一 ctx 路由 | 加 scene/role 二维路由 |
| `unified_eclipse.py` / `unified_gethlighting.py` | 抽成"场景注册表" x node_pool |
| Strategy JSON (phases) | 加 scenes 引用 + 每 phase 的 scene/role |

## 7. 待用户拍板

1. **是否确认换 Nontargeted（淘汰 BunnyFinder）到统一 EL 层？**
2. **版本路线：推荐 B (统一 v1.10.x)，是否同意？**
3. 若同意，下一步先搭"统一 EL 场景注册表 + 三阶段混合示例"骨架，
   不跑完整攻击，先验证三套操作能在同一批节点上被路由。
