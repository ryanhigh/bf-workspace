#!/bin/bash
# attack.sh — 一键重放攻击（模仿 bunnyfinder/attack.sh 的形式）
#
# 用法:
#   ./attack.sh <攻击名> [观察窗口秒数]
#
# 可用攻击名:
#   eclipse                 Eclipse 8 攻击者占槽（stage-b，代表性最强）
#   eclipse-a               Eclipse 阶段A：1 攻击者 dial 1 victim
#   eclipse-b               Eclipse 阶段B：8 攻击者并发占槽
#   eclipse-c               Eclipse 阶段C：16 攻击者占槽
#   eclipse-d               Eclipse 阶段D：victim 出生带 attacker 静态节点
#   gethlighting            Gethlighting tx-flood（3 攻击者 × 200 无效交易）
#   gethlighting-txflood    同 gethlighting
#   gethlighting-normal     Gethlighting 基线（clique 出块 + victim 同步）
#
# 示例:
#   ./attack.sh eclipse-b
#   ./attack.sh gethlighting 90
#
# 环境变量（可选覆盖）:
#   ECLIPSE_ATTACKERS   eclipse 攻击者数量（覆盖默认）
#   FLOOD_COUNT         gethlighting 无效交易笔数（默认 200）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

attack="${1:-help}"
wait="${2:-60}"

case "$attack" in
  eclipse)
    profile=eclipse; scenario=stage-b ;;
  eclipse-a)
    profile=eclipse; scenario=stage-a ;;
  eclipse-b)
    profile=eclipse; scenario=stage-b ;;
  eclipse-c)
    profile=eclipse; scenario=stage-c ;;
  eclipse-d)
    profile=eclipse; scenario=stage-d ;;
  gethlighting|gethlighting-txflood)
    profile=gethlighting-legacy; scenario=tx-flood ;;
  gethlighting-normal)
    profile=gethlighting-legacy; scenario=normal ;;
  help|-h|--help)
    sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  *)
    echo "未知攻击名: $attack" >&2
    echo "可用: eclipse, eclipse-a/b/c/d, gethlighting, gethlighting-normal" >&2
    echo "跑 ./attack.sh help 看完整说明" >&2
    exit 1 ;;
esac

run_id="attack-${attack}-$(date +%Y%m%d-%H%M%S)"

echo "=== 重放攻击: $attack ==="
echo "    profile=$profile scenario=$scenario run_id=$run_id wait=${wait}s"
echo ""

ECLIPSE_WAIT="$wait" SKIP_DOCTOR=1 \
  python3 "$SCRIPT_DIR/controller/run.py" "$SCRIPT_DIR" \
  --profile "$profile" --scenario "$scenario" \
  --run-id "$run_id" --skip-doctor

echo ""
echo "=== 分析结果 ==="
RUN_ID="$run_id" ACTIVE_PROFILE="$profile" \
  python3 "$SCRIPT_DIR/controller/analyze.py"

echo ""
echo "=== 完成 ==="
echo "run_id:     $run_id"
echo "证据目录:   $SCRIPT_DIR/runs/$run_id/"
echo "结构化结果: $SCRIPT_DIR/runs/$run_id/result.json"
echo "原始日志:   $SCRIPT_DIR/runs/$run_id/logs/compose.log"
