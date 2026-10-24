#!/bin/bash
# Snapshot: busy game threads, per-core load, CPU clocks.
# Env: GAME (pgrep -f pattern). Default is Overwatch.
GAME=${GAME:-'[S]:.steamapps.common.Overwatch.Overwatch.exe'}
gp=$(pgrep -f "$GAME" | head -1)
echo "== game threads >20% (pid $gp, affinity $(taskset -cp "$gp" 2>/dev/null | sed 's/.*: //')):"
top -b -H -n1 -p "$gp" | awk 'NR>7 && $9>20 {print $9, $12}' | sort -rn | head -20
echo "== per-core busy % over 2s:"
a=$(grep '^cpu[0-9]' /proc/stat); sleep 2; b=$(grep '^cpu[0-9]' /proc/stat)
paste <(echo "$a") <(echo "$b") | awk '{t1=0;t2=0;for(i=2;i<=11;i++)t1+=$i;for(i=13;i<=22;i++)t2+=$i; idle=($16+$17)-($5+$6); printf "%s:%d ", substr($1,4), 100*(1-idle/(t2-t1))}'
echo
echo "== MHz per core:"
grep MHz /proc/cpuinfo | awk '{print int($4)}' | tr '\n' ' '; echo
uptime
