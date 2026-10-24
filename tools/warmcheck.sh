#!/bin/bash
# Wait for the game to start, then sample: split parts held open, private-cache
# growth, and DXVK compile-thread CPU at +1, +3, +5, +10 minutes.
# Env: GAME (pgrep -f pattern), CACHE_DIR (the __GL_SHADER_DISK_CACHE_PATH value),
#      PREFIX (split part prefix). Defaults are for Overwatch.
GAME=${GAME:-'[S]:.steamapps.common.Overwatch.Overwatch.exe'}
CACHE_DIR=${CACHE_DIR:-$HOME/.cache/nvidia-overwatch}
PREFIX=${PREFIX:-split}
until gp=$(pgrep -f "$GAME" | head -1) && [ -n "$gp" ]; do sleep 5; done
echo "game pid $gp started $(date +%T)"
for m in 1 3 5 10; do
  sleep $(( m == 1 ? 60 : (m == 3 ? 120 : (m == 5 ? 120 : 300)) ))
  kill -0 "$gp" 2>/dev/null || { echo "game exited"; break; }
  # newest driver-hash dir: a driver update starts a fresh one
  d=$(ls -dt "$CACHE_DIR"/GLCache/*/*/ | head -1)
  open=$(ls -l /proc/"$gp"/fd 2>/dev/null | grep -c "$CACHE_DIR.*$PREFIX")
  steamdir=$(ls -l /proc/"$gp"/fd 2>/dev/null | grep -c 'steamapps/shadercache')
  own=$(ls -l "$d" | awk -v p="$PREFIX" '$0 !~ p && /\.bin/ {s+=$5} END {print s+0}')
  cpu=$(top -b -H -n1 -p "$gp" | awk 'NR>7 && $12 ~ /dxvk-sh/ {s+=$9} END {printf "%.0f", s}')
  echo "+${m}m $(date +%T): $PREFIX fds=$open steam-cache fds=$steamdir game-own cache bytes=$own dxvk-shader cpu=${cpu}%"
done
