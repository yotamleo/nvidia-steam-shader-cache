#!/bin/bash
# Is DXVK still compiling, and is the game writing new driver-cache fragments?
gp=$(pgrep -f 'S:.steamapps.common.Overwatch.Overwatch.exe' | head -1)
top -b -H -n1 -p "$gp" | awk 'NR>7 && $12 ~ /dxvk-sh/ {n++; s+=$9; t=$11} END {printf "dxvk-shader threads=%d total=%.0f%% cputime_each=%s\n", n, s, t}'
date +%T
d=$(echo ~/.local/share/Steam/steamapps/shadercache/2357570/nvidiav1/GLCache/*/f092fc0dc8367a7c)
echo "newest fragments:"
ls -lt --time-style=+%T "$d" | grep -v 'merged\|steam_shader' | sed -n '2,4p'
echo "fragment count: $(ls "$d" | grep -c 'steamapp_shader_cache.*bin')"
