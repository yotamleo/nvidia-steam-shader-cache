#!/bin/bash
# Is DXVK still compiling, and is Steam's cache dir getting new driver-cache fragments?
# Env: GAME (pgrep -f pattern), APPID. Defaults are for Overwatch.
GAME=${GAME:-'[S]:.steamapps.common.Overwatch.Overwatch.exe'}
APPID=${APPID:-2357570}
gp=$(pgrep -f "$GAME" | head -1)
top -b -H -n1 -p "$gp" | awk 'NR>7 && $12 ~ /dxvk-sh/ {n++; s+=$9; t=$11} END {printf "dxvk-shader threads=%d total=%.0f%% cputime_each=%s\n", n, s, t}'
date +%T
# newest driver-hash dir: a driver update starts a fresh one
d=$(ls -dt ~/.local/share/Steam/steamapps/shadercache/"$APPID"/nvidiav1/GLCache/*/*/ | head -1)
echo "newest fragments:"
ls -lt --time-style=+%T "$d" | grep -v 'merged\|steam_shader' | sed -n '2,4p'
echo "fragment count: $(ls "$d" | grep -c 'steamapp_shader_cache.*bin')"
