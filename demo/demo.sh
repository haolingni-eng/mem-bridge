#!/usr/bin/env bash
# Demo run for MemBridge. Everything happens in a throwaway store, so it is safe to record.
#
#   ./demo/demo.sh          paced for recording (default 1.2s between steps)
#   PAUSE=0 ./demo/demo.sh  no pauses, for a quick check
#
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
STORE="/tmp/membridge-demo"
rm -rf "$STORE"
mkdir -p "$STORE"
export MEMORY_HOME="$STORE"
cd "$REPO" || exit 1
PAUSE="${PAUSE:-1.2}"

step() {
  printf '\n\033[1;36m== %s\033[0m\n' "$1"
  sleep "$PAUSE"
}

say() {
  printf '\033[0;33m# %s\033[0m\n' "$1"
  sleep "$(awk "BEGIN{print $PAUSE*0.5}")"
}

run() {
  printf '\033[0;37m$ %s\033[0m\n' "$*"
  sleep "$(awk "BEGIN{print $PAUSE*0.5}")"
  "$@"
  sleep "$PAUSE"
}

mkdir -p "$STORE/memory/notes"
printf '## Notes\n' > "$STORE/MEMORY.md"

clear
printf '\033[1mMemBridge — one shared memory for every AI coding agent\033[0m\n'
say "Store: $STORE   (nothing outside this temp dir is touched)"

step "1/6  The store is plain text on disk"
run ls -R "$STORE"

step "2/6  Agent A finishes a task and writes what it learned"
say "Agent A is one coding agent. Its only write permission is 'append'."
run python3 mem.py append --tool agentA --task "primer design" \
  --text "- 完成：给 HIP7 设计了一对引物，Tm 差 0.4℃
- 停在哪：已送生工下单
- 下一步：等合成
- 复用结论：[候选] 引物下单默认 1 nmol + HAP 纯化
- 踩坑：同源臂长度低于 20 bp 时重组效率骤降 → 下次先算同源臂再设计引物"

step "3/6  Agent B starts cold, in a different tool"
say "Agent B has never seen agent A's session. It has no context at all."
run python3 mem.py search 同源臂

step "4/6  What agent B's prompt actually gets"
run python3 mem.py inject 同源臂 引物

step "5/6  Two guards that matter"
say "Secret-shaped text is refused before it reaches disk."
run python3 mem.py append --tool agentB --task "leak" --text "- 完成：api_key = sk-abcdefghijklmnopqrstuvwx"
say "Five agents appending at the same instant: all five land, none interleave."
for i in 1 2 3 4 5; do
  python3 mem.py append --tool "p$i" --task race --text "- 完成：并发 $i" >/dev/null &
done
wait
run grep -c "并发" "$STORE/memory/$(date +%F).md"

step "6/6  The whole contract, checked in one command"
run python3 scripts/selfcheck.py

printf '\n\033[1;32mDone.\033[0m  Store left at %s\n' "$STORE"
