#!/bin/bash
# 极简:随机挑一个 attack case,复用 runtest.sh 已经写好的 testcase(),
# 用 docker compose up/down / mv data / grep reorg 这些都交给它。
#
# 用法:  ./tool/random_attack.sh [duration_seconds]
#        默认 300s。比 ./attack.sh 的 3600 短,适合快速 sanity check。
#
# 看到 "casetype is ..." 一行就能确认这次抽到哪个策略。

set -u
WORKDIR="/data/DeAtkVer/Bunnyfinder/bf_workspace"
cd "$WORKDIR"
export BASEDIR="$WORKDIR/"

DURATION="${1:-300}"

# v5/runtest.sh 里支持的全部 case(对应 attack-*.yml)
CASES=(basic exante sandwich staircase unrealized withholding selfish staircaseii sync
       ext-exante ext-sandwich ext-staircase ext-unrealized ext-withholding
       mix rlstaircase)

# 抽签
PICK="${CASES[$((RANDOM % ${#CASES[@]}))]}"
echo ">>> random pick: $PICK   (duration=${DURATION}s)"

# 直接调用 v5/runtest.sh 的 testcase() 走完整流程
bash v5/runtest.sh "$PICK" "$DURATION"
