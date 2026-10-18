#!/usr/bin/env bash
# name|passes|neck_um|automatic_neckdown|optimizer
# Runs on tengri (copied there as run_variants.sh by route_remote.sh push): starts every
# variant detached with setsid/nohup and exits, so ssh returns at once. Freerouting writes
# the .ses only when a variant finishes. With -mt 1 a draw is deterministic, so variants
# that differ only in max passes run identically up to the shorter one's end: the pass
# ladder gets sessions back early, it does not sample.
cd "$(dirname "$0")"
pkill -f "user.home=$PWD/home_" 2>/dev/null; sleep 2   # a new push replaces this directory's running draws
while IFS='|' read -r name passes neck neckdown opt; do
  [ -z "$name" ] && continue
  mkdir -p "home_$name"; rm -f "$name.ses"
  FREEROUTING__ROUTER__FANOUT__ENABLED=false FREEROUTING__ROUTER__OPTIMIZER__ENABLED=${opt:-false} \
  FREEROUTING__ROUTER__NECK_WIDTH_UM=$neck FREEROUTING__ROUTER__AUTOMATIC_NECKDOWN=$neckdown \
    setsid nohup java -Duser.home="$PWD/home_$name" -Xmx2g -jar freerouting-2.5.0.jar -de da3.dsn -do "$name.ses" \
      --router.autorouter.max_passes="$passes" -mt 1 -dct 0 > "$name.log" 2>&1 < /dev/null &
done <<'LIST'
p30|30|200|true|false
p60|60|200|true|false
p120|120|200|true|false
f60|60|200|false|false
o30|30|200|true|true
o60|60|200|true|true
LIST
