# Unified Action DSL — Eclipse × BunnyFinder 调用流程对比

## 目标

把所有攻击（Eclipse 的 P2P 层动作 + BunnyFinder 的共识层动作）放进
**同一个动作池**，用**同一个 Executor** 执行，Strategy JSON 用同一格式。
本文件记录一次 Eclipse 攻击和一次 BunnyFinder 攻击的实际调用流程对比，
证明流程一致。

## 架构

```
profiles/unified_action.py          ← 单一 Action 池 (12 个动作) + 单一 UnifiedExecutor
profiles/unified.py                 ← 纯策略执行器（无 compose）
profiles/unified_eclipse.py         ← 继承 eclipse.Adapter，复用其 prepare，仅覆盖 run_actions
profiles/unified_bunnyfinder.py     ← 最小 2 节点 smoke（attacker + beacon），复用 unified executor
profiles/unified/strategies/*.json  ← 统一格式的 Strategy JSON
```

### Action 池（12 个动作，按 exec_kind 分类）

| exec_kind | 动作 | 来源 | 底层调用 |
|---|---|---|---|
| `local` | sleep / return / abort / delay_to_next_slot | 控制流 | Python 进程内 |
| `rpc_admin` | resolve_enode / add_static_peer / burst_dial / sample_peers / wait_peers | Eclipse | `docker exec … wget http://127.0.0.1:8545` → geth admin RPC |
| `rpc_file` | set_strategy / modify_parent_root / store_signed_attest | BunnyFinder | `docker exec … sh -c "echo … > /root/strategy.json"` |

Executor 只看 `exec_kind`，不看动作名，更不看攻击来源。

## 执行链对比（真实 events.jsonl）

### Eclipse: `unified-eclipse-004`（stage-a，1 attacker）

```
PHASE PREP (t+0s)
  ▶ sleep            [local]      ✓
  ▶ resolve_enode    [rpc_admin]  ✓ enode=…@172.80.1.20:30303
  ▶ add_static_peer  [rpc_admin]  ✓ result=True
PHASE ATTACK (t+20s)
  ▶ burst_dial       [rpc_admin]  ✓ sent=3
  ▶ sample_peers     [rpc_admin]  ✓ victim_net_peerCount=1   ← 攻击者成功连上 victim
PHASE SETTLE (t+40s)
  ▶ sample_peers     [rpc_admin]  ✓ victim_net_peerCount=1
actions.done: 6 actions, 6 ok
```

### BunnyFinder: `unified-bf-001`（smoke，1 attacker + 1 beacon）

```
PHASE PREP (t+0s)
  ▶ sleep              [local]     ✓
  ▶ set_strategy       [rpc_file]  ✓ strategy=withholding, write_rc=0
  ▶ delay_to_next_slot [local]     ✓ slept_fallback_s=12
PHASE ATTACK (t+15s)
  ▶ modify_parent_root [rpc_file]  ✓ directive_appended=True, slot_offset=1
  ▶ store_signed_attest[rpc_file]  ✓ write_rc=0
PHASE SETTLE (t+30s)
  ▶ set_strategy       [rpc_file]  ✓ strategy=settle, write_rc=0
actions.done: 6 actions, 6 ok
```

## 流程一致性结论

两边的 events.jsonl 事件序列**完全相同**：

```
unified.actions.scheduled
  strategy.phase          (PREP)
  strategy.action.start   (sleep)
  strategy.action.done
  strategy.action.start   (…)
  strategy.action.done
  strategy.phase          (ATTACK)
  strategy.action.start / done × N
  strategy.phase          (SETTLE)
  strategy.action.start / done × N
actions.done
```

唯一的差异在**叶子节点**（action 的 `exec_kind` 和具体实现）：
- Eclipse 的 action 走 `rpc_admin`（docker exec → geth admin RPC）
- BunnyFinder 的 action 走 `rpc_file`（docker exec → 写 /root/strategy.json 给 Go 攻击者）

调度、日志、事件结构、结果汇总（n_actions/n_ok）全部一致。

## 混用示例（未来可直接跑）

```json
{
  "uid": "composed-withhold-then-eclipse",
  "phases": [
    {"t_rel_seconds": 0,  "phase": "PREP", "actions": [
        {"name": "set_strategy", "params": {"strategy": "withholding"}}]},
    {"t_rel_seconds": 15, "phase": "ATTACK", "actions": [
        {"name": "modify_parent_root", "params": {"slot_offset": 1}},
        {"name": "resolve_enode", "params": {}},
        {"name": "burst_dial", "params": {"repeats": 30}}]}
  ]
}
```

同一个数组里既有 BF 动作（set_strategy / modify_parent_root）又有
Eclipse 动作（resolve_enode / burst_dial），Executor 按各自的
exec_kind 分发，互不感知。

## 本次开发修复的 bug

1. **容器命名漂移**：wrapper 若覆盖 `profile` 会导致 `project_name()`
   变成 `erl_unified-eclipse-…`，与 compose 文件里的 `erl_eclipse-…`
   不一致。修法：`unified_eclipse.py` 继承 eclipse.Adapter 且**不覆盖**
   profile；`unified_bunnyfinder.py` 用 `self.project_name()` 动态构造
   容器名（不硬编码）。
2. **共享 ctx**：Executor 原来每次 action 都调 `ctx_provider` 拿到一个
   新 dict，导致 `resolve_enode` 写入的 `ctx["peer_enode"]` 无法被后续
   `add_static_peer` 读到。修法：Executor 维护单一共享 ctx，把每次
   `ctx_provider(action)` 的结果 `ctx.update()` 合并进去，同一个 dict
   对象贯穿整个 strategy。
3. **`_POOL` 命名**：下划线前缀导致 import 失败，改为 `ACTION_POOL`。

## 验证记录

- `runs/unified-eclipse-004/`：6/6 动作 ok，victim_net_peerCount=1
- `runs/unified-bf-001/`：6/6 动作 ok，write_rc 全 0
- 两个 run 的 events.jsonl 都完整记录 strategy.phase / action.start /
  action.done 三级事件

## 尚未完成（后续）

- BunnyFinder wrapper 目前是「最小 2 节点 smoke」，用的是
  `ethereum/client-go` 当占位，**不是**真正的 `tscel/bunnyfinder`
  攻击者进程。真实 BF 攻击需要接 `bf_workspace/v5/runtest.sh` 那套
  MySQL + 16 容器拓扑，rpc_file 动作写文件后由真实 Go 攻击者读。
- 混用攻击（同一 strategy 里跨 eclipse + bf）尚未跑端到端。
