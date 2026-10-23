# nvidia-steam-shader-cache

Fix for **Steam shader pre-caching being wasted on NVIDIA + Linux**: after every
game update or new Shader Swarm bucket, Steam shows **"Processing Vulkan
shaders"**, and the game still stutters with DXVK compiling for minutes after
launch. **Local repo, private.** himmel Jira **HIMMEL-3054**.

Current target: **OVERLORD8** (CachyOS, RTX 4090, nvidia-open 615.78.08),
**Overwatch 2** (Steam appid 2357570, proton-cachyos-slr).

## Symptoms → use this

- "Processing Vulkan shaders" after every Overwatch update, then cold-cache
  stutter anyway (FPS drop, `dxvk-sh*` threads pegged in `top -H`).
- `~/.local/share/Steam/logs/shader_log.txt` shows thousands of
  `Mismatching key! Entry N/M.` and/or `FOZ underflow, file truncated?`.
- The merged cache
  `steamapps/shadercache/<appid>/nvidiav1/GLCache/*/*/steamapp_merged_shader_cache.bin`
  shrinks after a game exit.

## Root cause

Two separate problems, both measured on 2026-10-23:

1. **4 GiB offset wraparound in Steam's merge.** A `.toc` entry is a 16-byte key,
   a u32 offset and a u32 size, so a merged `.bin` past 2^32 bytes gets wrapped
   offsets. Steam can't find those entries ("Mismatching key!"), drops them at
   the next merge, the file shrinks, the next session regrows it, and the cycle
   repeats. Stock setup, exit merge: 5,370,772,223 B, 50,673 of 262,547 entries
   (19 %) found only at stored offset + 2^32. Check: `tools/tocwrap.py`.
2. **Steam's precompiled entries partly don't match what the game needs.** With
   all entries recovered into valid parts (`tools/ow-split.py`) and read-only
   for the game, it still recompiled 50,164 keys from the first part. Same
   16-byte key, but different record header bytes 20..28, size and payload. The
   TOC key isn't the full identity of a shader. Unverified guess:
   `fossilize_replay` doesn't get the `Overwatch.exe` driver application profile.

Steam merges the replay fragments seconds after `fossilize_replay` exits and
deletes them, so pointing the game at Steam's cache dir can never stay warm.

## The fix: an isolated driver cache

Point the driver at a private dir in the launch options. Steam's merger never
touches it, and the driver rolls its own files (`overwatch1.bin`, …), so the
4 GiB problem doesn't arise:

```
PROTON_ENABLE_WAYLAND=1 PROTON_ENABLE_HDR=1 PROTON_CPU_TOPOLOGY=16:0,1,2,3,4,5,6,7,16,17,18,19,20,21,22,23 MANGOHUD=1 __GL_SHADER_DISK_CACHE_PATH=/home/overlord/.cache/nvidia-overwatch __GL_SHADER_DISK_CACHE_APP_NAME=overwatch __GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME="owsplit0;owsplit1;owsplit2" __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 taskset -c 0-7,16-23 %command%
```

Size + skip-cleanup stop the driver's own 1 GB pruning (steam-for-linux#11392).
The `owsplit*` read-only list is an optional seed recovered from Steam's merged
file with `tools/ow-split.py`. It's partly useful at best (see root cause 2), so
it can be dropped.

Measured: first launch wrote 2.46 GB in about 8.5 min; the relaunch wrote
**0 bytes in its first 3 min** and 65 MB over a whole match. A ~4 min burst of
`dxvk-shader` threads at ~950 % CPU remains at launch even when warm, probably
DXVK-side work the NVIDIA cache can't skip. `dxvk.conf` with
`dxvk.numCompilerThreads = 6` softens it.

Same approach as a public tool: [Xerrion/steam-shader-guard](https://github.com/Xerrion/steam-shader-guard)
(isolated cache, recover/split, skips Steam's NVIDIA replay).

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

## Previous approach: `ow-shader-sync`

`bin/ow-shader-sync --watch` (systemd user unit, `./install.sh`) copied Steam's
replay fragments + merged file into the private dir before Steam merged and
deleted them, and the game read them via a 32-name read-only list
(`ow-shader-sync --print-ro`). It's disabled now: the merged copy carries the
wrapped offsets, and the replay entries hit root cause 2. The one-shot
`ow-shader-sync` (no `--watch`) is still the way to capture a replay's fragments
for analysis.

## Verify

- Game reads the private dir: `ls -l /proc/$(pgrep -f 'Overwatch.exe' | head -1)/fd | grep -c nvidia-overwatch`.
- Warm: `tools/ow-warmcheck.sh` before launching; it samples game-own cache
  growth and `dxvk-shader` CPU at +1/3/5/10 min. Warm = cache bytes flat.
- Live load: `tools/ow-load.sh` (busy threads, per-core load), `tools/ow-compile.sh`.
- Without restarting the game: `tools/probe-read-only.py '<value>'`.

## Resets

- **Driver update** → new `GLCache/<driver-hash>/` dir; private cache cold once
  (one long compile burst). The old dir stays: prune it by hand.
- **Game / Proton update** → partial recompile once; the cache grows (16 GiB cap).

## Upstream status

- [steam-for-linux#13622](https://github.com/ValveSoftware/steam-for-linux/issues/13622),
  filed 2026-09-16 (body `upstream/steam-for-linux-13622.md`). Still open, no
  Valve reply as of 2026-10-23. `edmundselliot` found the 4 GiB wrap first (CS2).
  Ours: stock confirmation (`upstream/13622-comment.md`) and the isolated-cache /
  same-key-different-record follow-up (`upstream/13622-followup.md`).
- [steam-shader-guard#7](https://github.com/Xerrion/steam-shader-guard/issues/7):
  field report (`upstream/ssg-issue.md`).
- Adjacent: steam-for-linux [#11392](https://github.com/ValveSoftware/steam-for-linux/issues/11392)
  (driver prunes precompiled shaders by size), [#9803](https://github.com/ValveSoftware/steam-for-linux/issues/9803)
  (precompiling into dirs the driver never reads),
  [Proton#9548](https://github.com/ValveSoftware/Proton/issues/9548) (Overwatch
  recompile every relaunch on NVIDIA, closed unresolved),
  [NVIDIA forum thread](https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196).
- NVIDIA `;` separator doc gap: draft `upstream/nvidia-forum-read-only-app-name-draft.md`,
  **not posted** (needs a browser login). Responses on upstream threads are operator-owned.

## Layout

```
tools/tocwrap.py              count wrapped TOC offsets in a merged .toc/.bin
tools/ow-split.py             split a merged file into verified <2 GiB parts, prints the RO list
tools/keyoverlap.py           how many keys of a new .toc already exist in others
tools/reccmp.py               same key in two files: compare record headers/payloads
tools/dupkeys.py              entries vs unique keys per .toc
tools/ow-warmcheck.sh         sample the next Overwatch launch (warm or cold)
tools/ow-load.sh, ow-compile.sh   live load snapshots
tools/probe-read-only.py      which READ_ONLY values the driver honours (inotify, headless)
bin/ow-shader-sync            previous approach: copy / --watch / --print-ro
systemd/ow-shader-sync.service
upstream/                     posted issue/comment texts, NVIDIA forum draft
install.sh
```
