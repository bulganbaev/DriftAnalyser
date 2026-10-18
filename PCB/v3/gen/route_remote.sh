#!/usr/bin/env bash
# Route the board on the compute server (tengri) and bring the sessions back.
#   bash gen/route_remote.sh push    # write the DSN, copy it + the Freerouting jar, start the variants
#   bash gen/route_remote.sh status  # one line per variant from the server logs
#   bash gen/route_remote.sh pull    # every .ses/.log back to fab/route/remote/<remote dir>/
#   bash gen/route_remote.sh stop    # kill whatever of ours is still running there
# Then pick one: cp fab/route/remote/da3route/<variant>.ses fab/route.ses && bash gen/build.sh
# ROUTE_RDIR=<dir> runs a second batch beside the first (each push only replaces its own dir).
# Adapted from edash hw/a1/gen/route_remote.sh. Lessons from there: fanout off, -mt 1 is
# deterministic, setsid + nohup + </dev/null or ssh keeps the channel open, -Duser.home per
# run for Freerouting's config. Neck 200 um here: 0.2 mm is this board's minimum track.
set -euo pipefail
cd "$(dirname "$0")/.."
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
# tengri answers on whichever VPN address is up; 10.30.0.3 first, ROUTE_HOST overrides
if [ -z "${ROUTE_HOST:-}" ]; then
  for h in server@10.30.0.3 server@172.31.17.14; do
    ssh -o ConnectTimeout=5 -o BatchMode=yes -n "$h" true 2>/dev/null && { ROUTE_HOST=$h; break; }
  done
fi
HOST=${ROUTE_HOST:-server@10.30.0.3}
RDIR=${ROUTE_RDIR:-da3route}
JAR=/Applications/freerouting.app/Contents/app/freerouting-executable.jar   # 2.5.0, Java 25 (server has 25.0.3)
DSN=fab/route/driftanalyser-v3.dsn
VARIANTS="$(grep -E '^[A-Za-z0-9]+\|[0-9]+\|' gen/route_variants.sh | cut -d'|' -f1 | tr '\n' ' ')"

case "${1:-}" in
push)
  # the DSN is cut from an unrouted board: rebuild it first
  "$KPY" -m gen.pcb_builder >/dev/null 2>&1
  DA3_STAGE=dsn "$KPY" -m gen.route 2>/dev/null | grep '^dsn:'
  ssh -n "$HOST" "mkdir -p $RDIR"
  scp -q "$DSN" "$HOST:$RDIR/da3.dsn"
  scp -q gen/route_variants.sh "$HOST:$RDIR/run_variants.sh"
  ssh -n "$HOST" "test -s $RDIR/freerouting-2.5.0.jar" || scp -q "$JAR" "$HOST:$RDIR/freerouting-2.5.0.jar"
  ssh -n "$HOST" "cd $RDIR && bash run_variants.sh"
  sleep 15; bash "$0" status
  ;;
status)
  ssh -n "$HOST" "uptime | sed 's/.*load/load/'"
  for name in $VARIANTS; do
    ssh -n "$HOST" "cd $RDIR && p=\$(grep -oE 'Auto-routing pass #[0-9]+ .*with score [0-9.]+ \\([0-9]+ unrouted[^)]*\\)' $name.log | tail -1 | sed -E 's/ on board.*with score/ score/'); \
      s=\$(test -s $name.ses && echo 'SES ready'); r=\$(pgrep -f \"[u]ser.home=\$HOME/$RDIR/home_$name \" >/dev/null && echo running || echo stopped); \
      echo \"$name: \$r \${p:-pass 1 in progress} \$s\"" || true
  done
  ;;
pull)
  mkdir -p "fab/route/remote/$RDIR"
  scp -q "$HOST:$RDIR/*.ses" "$HOST:$RDIR/*.log" "fab/route/remote/$RDIR/" 2>/dev/null || true
  ls -la "fab/route/remote/$RDIR/"
  ;;
stop)
  ssh -n "$HOST" "pkill -f '[u]ser.home=.*/$RDIR/home_' ; sleep 3; pgrep -fa '[f]reerouting-2.5.0.jar' | grep '$RDIR/' || echo 'nothing of ours running in $RDIR'"
  ;;
*)
  sed -n 2,7p "$0"; exit 1 ;;
esac
