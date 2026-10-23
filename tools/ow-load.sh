#!/bin/bash
# Snapshot: busy Overwatch threads, per-core load, background affinity, CPU clocks.
gp=$(pgrep -f 'S:.steamapps.common.Overwatch.Overwatch.exe' | head -1)
echo "== Overwatch threads >20% (pid $gp):"
top -b -H -n1 -p "$gp" | awk 'NR>7 && $9>20 {print $9, $12}' | sort -rn | head -20
echo "== per-core busy % over 2s (game pin = 0-7,16-23):"
a=$(grep '^cpu[0-9]' /proc/stat); sleep 2; b=$(grep '^cpu[0-9]' /proc/stat)
paste <(echo "$a") <(echo "$b") | awk '{t1=0;t2=0;for(i=2;i<=11;i++)t1+=$i;for(i=13;i<=22;i++)t2+=$i; idle=($16+$17)-($5+$6); printf "%s:%d ", substr($1,4), 100*(1-idle/(t2-t1))}'
echo
echo "== background affinity:"
for p in $(pgrep -f '[V]BoxHeadless') $(pgrep -x npm) $(pgrep -x node | head -3) $(pgrep -x shellcheck | head -3); do
  printf '%s %s ' "$p" "$(ps -o comm= -p "$p")"; taskset -cp "$p" 2>/dev/null | sed 's/.*: //'
done
echo "== MHz cores 0-7 / 8-15:"
grep MHz /proc/cpuinfo | awk '{print int($4)}' | head -16 | tr '\n' ' '; echo
uptime
