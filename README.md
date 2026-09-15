# nvidia-steam-shader-cache

Fix for **Steam shader pre-caching being wasted on NVIDIA + Linux**: after every
game update or new Shader Swarm bucket, Steam shows **"Processing Vulkan
shaders"**, and the game still stutters with DXVK compiling for minutes after
launch. **Local repo, private.** himmel Jira **HIMMEL-3054**.

Current target: **OVERLORD8** (CachyOS, RTX 4090, nvidia-open 615.71.09),
**Overwatch 2** (Steam appid 2357570, proton-cachyos-slr).

## Symptoms → use this

- "Processing Vulkan shaders" after every Overwatch update, then cold-cache
  stutter anyway (60 fps, GPU idle, `dxvk-sh*` threads pegged in `top -H`).
- `~/.local/share/Steam/logs/shader_log.txt` shows thousands of
  `Mismatching key! Entry N/M.` and/or `FOZ underflow, file truncated?`.
- The merged cache
  `steamapps/shadercache/<appid>/nvidiav1/GLCache/*/*/steamapp_merged_shader_cache.bin`
  shrinks after a game exit.

## Root cause

1. Steam's fossilize replay compiles Valve's pipeline set through the NVIDIA
   driver into 31 fragments, `steamapp_shader_cache0..30.{bin,toc}` (one per
   replay thread).
2. **Seconds after `fossilize_replay` exits** — before Steam logs
   `fossilize_replay completed` — shadercachemanager merges the fragments into
   `steamapp_merged_shader_cache.bin` and **deletes them**.
3. That merge (and the one at game exit, which folds in the game's own
   fragment) logs "Mismatching key!" and loses entries: 2026-09-13 exit merge =
   40,558 mismatches, merged .bin 6.94 GB → 4.80 GB; next launch cold again.
   Reproduced on drivers 610.57 and 615.71.09.

So pointing the game at Steam's cache dir can never stay warm on this driver.

## The fix

Three parts:

1. **Private driver cache** in the launch options, so Steam's merger never
   touches what the game writes:
   `__GL_SHADER_DISK_CACHE_PATH=/home/overlord/.cache/nvidia-overwatch __GL_SHADER_DISK_CACHE_APP_NAME=overwatch __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1`
   (size + skip-cleanup also stop the driver's own 1 GB pruning, steam-for-linux#11392).
2. **`bin/ow-shader-sync --watch`** (systemd user unit) reflink-copies Steam's
   fragments + merged file into the private cache dir the moment the replay
   process exits — before Steam merges and deletes them. A size guard keeps a
   later small replay from overwriting a full run's same-named fragment.
3. **Read-only list** in the launch options, so the game reads Steam's set
   without writing to it:
   `__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME="steamapp_merged_shader_cache;steamapp_shader_cache0;…;steamapp_shader_cache30"`.
   Generate the exact value with `ow-shader-sync --print-ro`.

### Gotcha: the separator is `;`, names must be exact (undocumented)

Verified with `tools/probe-read-only.py` on 615.71.09:

| Value | Files the driver opens |
|---|---|
| `a,b` (comma) | none — silently ignored |
| `steamapp_shader_cache` (bare prefix) | none |
| `a:b`, `a b`, `a, b` | none |
| `a;b` | both |
| full `;` list, 32 names | all 32 |

The `;` must be inside quotes in Steam launch options (Steam runs them through a shell).

## Full launch options (Overwatch, OVERLORD8)

```
PROTON_ENABLE_WAYLAND=1 PROTON_ENABLE_HDR=1 PROTON_CPU_TOPOLOGY=16:0,1,2,3,4,5,6,7,16,17,18,19,20,21,22,23 MANGOHUD=1 __GL_SHADER_DISK_CACHE_PATH=/home/overlord/.cache/nvidia-overwatch __GL_SHADER_DISK_CACHE_APP_NAME=overwatch __GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME="steamapp_merged_shader_cache;steamapp_shader_cache0;steamapp_shader_cache1;steamapp_shader_cache2;steamapp_shader_cache3;steamapp_shader_cache4;steamapp_shader_cache5;steamapp_shader_cache6;steamapp_shader_cache7;steamapp_shader_cache8;steamapp_shader_cache9;steamapp_shader_cache10;steamapp_shader_cache11;steamapp_shader_cache12;steamapp_shader_cache13;steamapp_shader_cache14;steamapp_shader_cache15;steamapp_shader_cache16;steamapp_shader_cache17;steamapp_shader_cache18;steamapp_shader_cache19;steamapp_shader_cache20;steamapp_shader_cache21;steamapp_shader_cache22;steamapp_shader_cache23;steamapp_shader_cache24;steamapp_shader_cache25;steamapp_shader_cache26;steamapp_shader_cache27;steamapp_shader_cache28;steamapp_shader_cache29;steamapp_shader_cache30" __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 taskset -c 0-7,16-23 %command%
```

The fragment count (31) follows Steam's `fossilize_replay --num-threads`. If a
future replay writes a different count, re-run `--print-ro` and update the list.

## Install

```bash
./install.sh   # symlinks bin + unit, enables ow-shader-sync.service
```

After that: let "Processing Vulkan shaders" finish, then play. Nothing else.

## Verify

- Copy happened: `journalctl --user -u ow-shader-sync` shows `synced N files`.
- Game reads it: `ls -l /proc/$(pgrep -x Overwatch.exe)/fd | grep -c 'nvidia-overwatch.*steamapp'`
  → 64 (32 × bin+toc). 0 means the READ_ONLY value is wrong (see gotcha).
- Warm: `overwatch1.bin` in the private dir does not grow during the first minutes.
- Without restarting the game: `tools/probe-read-only.py '<value>'`.

## Resets

- **Driver update** → new `GLCache/<driver-hash>/` dir; everything cold once.
  The watcher copies into whatever hash dir Steam's replay used.
- **Game / Proton update** → partial invalidation; Steam's replay covers it.

## Upstream status (checked 2026-09-16)

No existing report of the merge corruption on steam-for-linux, Proton, DXVK,
NVIDIA's tracker or forum, or CachyOS. Adjacent: steam-for-linux
[#11392](https://github.com/ValveSoftware/steam-for-linux/issues/11392) (driver
prunes precompiled shaders by size), [#9803](https://github.com/ValveSoftware/steam-for-linux/issues/9803)
(precompiling into dirs the driver never reads),
[Proton#9548](https://github.com/ValveSoftware/Proton/issues/9548) (Overwatch
recompile every relaunch on NVIDIA, closed unresolved),
[NVIDIA forum thread](https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196).
The `;` separator is not documented anywhere found. Draft report:
`upstream/steam-for-linux-issue-draft.md` — **not filed; operator-gated.**

## Layout

```
bin/ow-shader-sync            copy / --watch / --print-ro
systemd/ow-shader-sync.service
tools/probe-read-only.py      which READ_ONLY values the driver honours (inotify, headless)
upstream/                     draft issue for ValveSoftware/steam-for-linux
install.sh
```
