# Two-Layer Network-Attack Lab design (Kurtosis-orchestrated)

> 修订：上一版 `unified-el-three-phase-design.md` 说"不需要共识客户端"是
> **只考虑了攻击侧**。本版修正为**两层架构**：攻击在网络层(EL/devp2p)，
> 观测在共识层(CL/PoS)。三个网络层攻击的效果通过共识层结果来裁决。

日期: 2026-09-09
状态: **设计提案 v2 (待用户确认)** —— 未运行新实验，未锁版本

---

## 0. 为什么需要两层（修正上一版）

上一版把三个攻击归到 geth devp2p 层后，说"环境变轻、不需要 PoS"。
**那是对的**——攻击确实只需要 EL。但**观测影响需要 CL**：

如 Nontargeted 论文 §VI-B 所示，攻击的真实目标是**绕过 proposer boosting、
制造 1-block reorg**（条件：攻击者份额 αW + 被延迟validator份额 βW > (1-β)W）。
这个效果**只能在共识层观测**（proposer boost 是否算对、有没有 reorg、
finality 有没有延迟、validator 有没有 missed attestation）。

注意：论文 §VI-B 因为搭真实 PoS 链成本高，**选择用模拟器算影响**
（"we opt to simulate reorg attacks rather than execute them in a
real-world scenario"）。我们搭**真实私有 PoS 链**做的是论文想省掉的
真实验证 —— 更扎实。

---

## 1. 两层架构

```
┌──────────────────────────────────────────────────────────────┐
│ 观测层  共识层 (CL PoS)                                       │
│  ├─ 信标节点 ×多数(不同CL: prysm/lighthouse/teku 做变更对照)   │
│  ├─ validator 进程 ×多(可配置数量)                            │
│  └─ 观测: proposer boost 计算 / 1-block reorg / finality 延迟 │
│           / missed attestation / validator 奖励惩罚变化       │
└──────────────────────────────────────────────────────────────┘
                    ▲ 网络层攻击效果在此裁决
┌──────────────────────────────────────────────────────────────┐
│ 攻击层  执行层 (EL / devp2p)                                  │
│  ├─ bootnode   (发现/握手锚点)                                │
│  ├─ victim     (目标节点, 50 peer 槽)                         │
│  ├─ honest ×M  (对照)                                         │
│  ├─ attackers ×N  Eclipse填槽 / Gethlighting泛洪 / 傀儡节点    │
│  ├─ sync       (Nontargeted: 提供chain state)                 │
│  ├─ delay      (Nontargeted: 建傀儡连接制造延迟)               │
│  └─ 三阶段动作: ①发现/拓扑 ②传播延迟 ③连接管理/DoS            │
└──────────────────────────────────────────────────────────────┘
                    ▲
┌──────────────────────────────────────────────────────────────┐
│ 编排层                                                         │
│  ├─ unified_action.py  全局动作池 + 跨场景编排器               │
│  └─ Kurtosis           ethpandaops/ethereum-package 拉起环境  │
└──────────────────────────────────────────────────────────────┘
```

## 2. 三阶段模型（网络层）与共识层观测的对应

| 阶段 | 攻击 | 作用层 | 共识层观测指标 |
|---|---|---|---|
| ① 发现/拓扑 | Eclipse | devp2p discovery/槽 | peer 拓扑变化 → 最终性延迟 |
| ② 传播/同步 | Nontargeted | devp2p 消息传播 | block 传播延迟 → proposer boost 被绕 → reorg |
| ③ 连接/资源 | Gethlighting | devp2p 连接/DoS | 无效 tx/连接竞争 → validator 奖励下降 |

## 3. 为何用 Kurtosis

1. **社区标准**：ethpandaops/ethereum-package 用 Kurtosis 编排完整 PoS 测试网
   （多 EL + 多 CL + 多 validator、锁定镜像/版本/节点数）。
2. **可重复**：`kurtosis run` 用同一个 manifest 声明式拉起，一次定义多次复现，
   满足"需要可重复"的核心诉求（比手写 docker compose 更规范）。
3. **本地就绪**：kurtosis engine 1.15.2 + CLI 已运行；
   `ethpandaops/ethereum-genesis-generator:6.1.2` + `dora:latest` 镜像已缓存。

## 4. 关键待验证点（方案落地前确认）

**Kurtosis 能否把「自定义改过的 EL 镜像」作为额外 service 编排进同一网络？**
- Nontargeted 的 delay/sync 节点是**改过的 geth**（v1.10.19 的 5 处修改）
- Eclipse/Gethlighting 的 attacker 需在 EL 网络内、能被 CL 连接规则约束
- ethereum-package 支持 **自定义 EL 镜像 override**；额外攻击节点通常用
  Kurtosis 的 `service` 自定义钩子注册。**需实测**，但方向可行。

## 5. 版本路线（本版不锁定，仅记录备选）

| 攻击 | 论文版本 | 备注 |
|---|---|---|
| Eclipse | v1.14.3 | 本地有 latest(1.17.5)；v1.10.x 可跑但标 GAP |
| Nontargeted | v1.10.19 | 需改 geth 源码（5 处） |
| Gethlighting | v1.10.20 + v1.11.0 | 本地已有 ✓ |

> 版本决策推迟到"两层架构确认"之后。观测层 CL 客户端版本需与 EL geth
> 版本配套（共识层与执行层有版本耦合），届时统一锁定。

## 6. 观测指标定义（共识层裁决攻击效果）

- **proposer boost**：slot n 的 block 是否在头 4s 内被正确收到并计 40% boost
- **1-block reorg**：区块 n+2 是否被 n+1 链取代（论文 §VI-B 步骤 1-3）
- **finality 延迟**：checkpoint 最终化延迟的 slot 数
- **missed attestation**：每个 slot 未收到/延迟的 attestation 数
- **validator 奖励/惩罚**：攻击前后 validator 的奖励变化（对齐论文图 8 收益分析）

## 7. 待用户确认

1. 两层架构（攻击网络层 + 观测共识层 + Kurtosis 编排）作为整体方案？
2. 若同意，先做**最小可行性验证**：用 Kurtosis 拉起 1 EL + 1 CL + N validator
   的最小 PoS 测试网，确认 ethereum-package 可用且能挂自定义 EL 攻击节点。
   （这一步是验证工具链，不是跑攻击。）
