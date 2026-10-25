#!/bin/bash
# Shorten DXVK's launch compile burst when the game is pinned to a CPU subset:
# move the background compile threads (dxvk-shader-n/-l) of the game this
# wrapper launches onto PCT % of all CPUs at low priority. dxvk-shader-h
# (compiles a frame waits on) stays with the game. Pair with
# dxvk.numCompilerThreads in dxvk.conf.
# Steam launch options: <env vars> /path/to/burstpin.sh taskset -c 0-7,16-23 %command%
# Without a command it only watches: run it in a terminal, then launch the game.
# Env: COMM (game process name, default Overwatch.exe), PCT (share of CPUs,
#      default 90), NICE (default 10), DURATION (seconds to keep pinning,
#      default 600), START_TIMEOUT (default 600).
COMM=${COMM:-Overwatch.exe}
PCT=${PCT:-90}
NICE=${NICE:-10}
DURATION=${DURATION:-600}
START_TIMEOUT=${START_TIMEOUT:-600}
MATCH='dxvk-shader-[nl]*'

n=$(getconf _NPROCESSORS_ONLN)
use=$(( n * PCT / 100 ))
(( use < 1 )) && use=1
# AMD and non-hybrid Intel number SMT siblings last, so the CPUs left out are
# hyperthreads; on Intel hybrid they are E-cores
CPUS=0-$(( use - 1 ))

# the kernel truncates comm to 15 chars; matching comm, not argv, cannot hit
# this wrapper or Steam's launch shell
name=${COMM:0:15}
old=" $(pgrep -d ' ' -x "$name") "

watch() {
  local gp="" deadline end t tid c cur
  declare -A seen
  deadline=$(( $(date +%s) + START_TIMEOUT ))
  while [ -z "$gp" ]; do
    (( $(date +%s) > deadline )) && { echo "burstpin: $name did not start"; return; }
    # the launched command died before the game appeared (Steam's proton
    # waitforexitandrun lives as long as the game)
    [ -n "$launcher" ] && ! kill -0 "$launcher" 2>/dev/null && return
    for p in $(pgrep -x "$name"); do
      [[ $old == *" $p "* ]] || { gp=$p; break; }
    done
    sleep 1
  done
  echo "burstpin: $name pid $gp at $(date +%T); compile threads -> CPUs $CPUS, nice $NICE"
  end=$(( $(date +%s) + DURATION ))
  while (( $(date +%s) < end )) && kill -0 "$gp" 2>/dev/null; do
    for t in /proc/"$gp"/task/*; do
      tid=${t##*/}
      c=$(cat "$t/comm" 2>/dev/null) || continue
      [[ $c == $MATCH ]] || continue
      # absolute nice: setpriority on a TID is per-thread on Linux
      [ -n "${seen[$tid]}" ] || renice -n "$NICE" -p "$tid" >/dev/null 2>&1
      cur=$(taskset -cp "$tid" 2>/dev/null | sed 's/.*: //')
      [ "$cur" = "$CPUS" ] && { seen[$tid]=1; continue; }
      taskset -cp "$CPUS" "$tid" >/dev/null 2>&1 &&
        echo "burstpin: $(date +%T) $c $tid: $cur -> $CPUS${seen[$tid]:+ (re-pinned)}"
      seen[$tid]=1
    done
    sleep 1
  done
  echo "burstpin: done $(date +%T)"
}

# no command: watch only, for starting by hand before launching the game
launcher=""
[ $# -eq 0 ] && { watch; exit; }
# after exec this pid is the launched command
launcher=$$
watch &
exec "$@"
