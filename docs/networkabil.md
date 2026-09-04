# 网络层攻击能力对共识攻击的影响 —— 候选动作清单

## 1. 背景

现有针对 PoS 共识的激励缺陷研究（代表工作 BunnyFinder）默认攻击者只具备
"共识层 Byzantine 能力"：能修改自己消息的发送时机和内容，但不能影响诚实
节点之间的网络可达性、消息顺序或时间观。

本文研究的核心前提是：现实攻击者同时具备网络层能力（如造成分区、丢包、
延迟、流量整形、时间偏移等），且两类能力可以协同放大攻击效果。本文件
梳理所有"对共识层有可观察影响"的网络层候选动作，作为扩展 SSF 动作空间
的依据。

## 2. 候选动作清单

### A. 消息可达性控制（直接影响 fork choice）

| 动作 | 含义 | 共识层影响 | 实现成本 |
|---|---|---|---|
| NetPartition | 把若干 peer 隔成子网，子网内可通，子网间不通 | 每个子网独立 fork choice，攻击者只需在最小子网内占多数 | 低（iptables） |
| MsgDrop | 按 topic 选择性丢消息 | 被丢节点 attestation 永远进不了 block tree，权重归零 | 低（gossipsub filter） |
| MsgDelay | 跨节点消息延迟 | 等价于把"按时到达"变成"过时"，权重降 | 中（libp2p 层） |
| Eclipse | 定向隔离单节点 | 被隔离节点永远 fork 到 attacker 的链上 | 中（改 libp2p） |

### B. 消息内容与顺序（libp2p 层）

| 动作 | 含义 | 共识层影响 | 实现成本 |
|---|---|---|---|
| MsgReorder | 同一 topic 内消息重排序 | fork choice 视图合并按"最新"权重选，重排序可让旧消息先到 | 中 |
| MsgDuplicate | 复制某条消息广播给所有 peer | gossipsub 去重后无效，但可放大"权重计算 bug"攻击面 | 中 |

### C. 流量整形（带宽/连接数）

| 动作 | 含义 | 共识层影响 | 实现成本 |
|---|---|---|---|
| BandwidthLimit | 按 peer 限速 | 消息在 buffer 堆积超时作废 | 低（tc） |
| ConnRefuse | 拒绝 TCP 连接 | 目标节点掉线，重连后落后几个 epoch | 低（iptables） |

### D. 时序层（全局时间影响）

| 动作 | 含义 | 共识层影响 | 实现成本 |
|---|---|---|---|
| ClockSkew | 节点本地时钟漂移 | 目标节点以为还在 slot N-1，所有消息被认为"过早" | 中（NTP 劫持） |
| SlotFreeze | 节点卡在某个 slot 不出块 | 错过 attestation 时机被惩罚 | 中 |

## 3. 优先级评估

按"对共识影响强度 + 实现成本"两个维度综合排序：

| 动作 | 共识影响强度 | 实现成本 | 论文价值 | 备注 |
|---|---|---|---|---|
| NetPartition | ★★★★★ | 低 | 高 | 网络分区是攻击者最经典的能力 |
| Eclipse | ★★★★★ | 中 | 高 | 单节点版分区，stake 阈值可降到接近 0 |
| ClockSkew | ★★★★ | 中 | 中 | 需要 NTP 假设，但攻击效果独特 |
| MsgDrop | ★★★ | 低 | 中 | 验证"网络层能力是否真的影响共识"的最佳入门动作 |
| BandwidthLimit | ★★★ | 低 | 中 | 实现简单但攻击效果可预测 |
| MsgDelay | ★★★ | 中 | 中 | 与"按时 attestation 才奖励"机制配合 |
| ConnRefuse | ★★ | 低 | 低 | 攻击效果和 Drop 类似但粒度更粗 |
| SlotFreeze | ★★ | 中 | 低 | 时序控制可被 ClockSkew 替代 |
| MsgReorder | ★★ | 中 | 低 | 攻击效果边界条件多 |
| MsgDuplicate | ★ | 中 | 低 | 现有 gossipsub 防御完善，攻击面小 |

## 4. 优先级推荐（第一版建议）

按"能产生新攻击类别"和"实现成本"权衡，建议第一版实现 3 个最有代表性
的动作：

1. **NetPartition** —— 网络分区的代表能力，论文强调"stake 阈值降低"
   的核心论点
2. **Eclipse** —— 单节点版分区，stake 阈值降到接近 0，最有冲击力
3. **MsgDrop** —— 实现最简单（gossipsub 已有 filter 机制），能快速
   验证"网络层能力是否真的影响共识"

## 5. SSF 扩展示例

以 NetPartition 为例，扩展后的 SSF schema 示意：

```json
{
  "uid": "xxx",
  "category": "ext_partition_staircase",
  "slots": [
    {
      "slot": "64",
      "level": 0,
      "actions": {
        "AttestAfterSign": "addAttestToPool",
        "AttestBeforeBroadCast": "return",
        "NetPartition:beacon3,beacon4,beacon5": "duration:96"
      }
    },
    {
      "slot": "95",
      "level": 1,
      "actions": {
        "BlockBeforeSign": "packPooledAttest",
        "BlockBeforeBroadCast": "delayWithSecond:480"
      }
    }
  ]
}
```

含义：epoch 2 的 32 个 slot 把 beacon3/4/5 隔开，beacon1（attacker 控
制的）和 beacon2 独占通信；恶意 proposer 在 slot 95 打包所有 withhold
的 attestation 并延迟广播到 epoch 4 中段。该攻击的 stake 阈值从
BunnyFinder 同样攻击的 1/3 降到 1/5（按节点数计）甚至更低（按 stake
权重计，因为被分区的节点 attestation 权重全部失效）。
