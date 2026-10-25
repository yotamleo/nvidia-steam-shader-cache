# nvidia-steam-shader-cache

Diagnostic toolkit for **Steam shader pre-caching being wasted on NVIDIA +
Linux**: after every game update or new Shader Swarm bucket Steam shows
**"Processing Vulkan shaders"**, and the game still stutters with DXVK compiling
for minutes after launch. Tracking issue:
[steam-for-linux#13622](https://github.com/ValveSoftware/steam-for-linux/issues/13622).

> **Just want the fix?** Use [Xerrion/steam-shader-guard](https://github.com/Xerrion/steam-shader-guard).
> It applies the same isolated-cache fix described below to any game, with an
> installer and releases. This repo is the measurement side: tools to check
> whether your cache is hit by the bug, recover what Steam lost, and verify that
> a fix works.

Measured on CachyOS, RTX 4090, nvidia-open 615.78.08, Overwatch 2 (appid
2357570, Proton). The file-format tools work for any game; the live-process
tools default to Overwatch and take env vars for others.

## Symptoms

- "Processing Vulkan shaders" after every update, then cold-cache stutter
  anyway (FPS drop, `dxvk-sh*` threads pegged in `top -H`).
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
   (19 %) found only at stored offset + 2^32. First reported by `edmundselliot`
   on #13622 (CS2). Check yours with `tools/tocwrap.py`.
2. **Steam's precompiled entries partly don't match what the game needs.** With
   all entries recovered into valid parts (`tools/split.py`) and read-only for
   the game, it still recompiled 50,164 keys from the first part. Same 16-byte
   key, but different record header bytes 20..28, size and payload
   (`tools/reccmp.py`). The TOC key isn't the full identity of a shader.
   Unverified guess: `fossilize_replay` doesn't get the game's driver
   application profile.

Steam merges the replay fragments seconds after `fossilize_replay` exits and
deletes them, so pointing the game at Steam's cache dir can never stay warm.

## The fix: an isolated driver cache

Point the driver at a private dir in the game's launch options. Steam's merger
never touches it, and the driver rolls its own files (`<name>1.bin`, …), so the
4 GiB problem doesn't arise:

```
__GL_SHADER_DISK_CACHE_PATH=$HOME/.cache/nvidia-<game> __GL_SHADER_DISK_CACHE_APP_NAME=<game> __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%
```

Size + skip-cleanup stop the driver's own 1 GB pruning (steam-for-linux#11392).
Optional seed: recover Steam's merged file with `tools/split.py` into the
private dir and add
`__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME="split0;split1;split2"` (the names
`split.py` prints). It's partly useful at best (root cause 2).

Measured on Overwatch: first launch wrote 2.46 GB in about 8.5 min; the relaunch
wrote **0 bytes in its first 3 min** and 65 MB over a whole match. A ~4 min burst
of `dxvk-shader` threads remains at launch even when warm; see the next section.

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

## The launch burst that no cache removes

Even with both caches warm, every launch starts with minutes of DXVK compile
threads pegging the CPU, and the game is barely playable until they finish
(~50 fps instead of 300+ here).

**What it is.** DXVK 2.0+ uses `VK_EXT_graphics_pipeline_library`: it builds
a pipeline library for every shader the game loads, at load time, on worker
threads named `dxvk-shader-h` (work a frame is waiting on), `-n` (shaders the
game loaded, prepared ahead of use) and `-l` (background optimized rebuilds).
DXVK's README warns about this "prolonged periods of very high CPU
utilization". The caches only make each step cheaper:

- the NVIDIA cache barely grew during the burst (+55 KB), so the driver isn't
  compiling;
- DXVK 3.x's own shader cache (`pfx/drive_c/users/steamuser/AppData/Local/dxvk/*.dxvk.bin`,
  1.3 GB for Overwatch) was held open and unchanged, so every shader was a hit;
- the old `.dxvk-cache` state cache was removed in DXVK 2.7. There is nothing
  left to turn on.

**Why pinning makes it worse.** A common X3D setup pins the game to the V-Cache
CCD (`taskset -c 0-7,16-23`, `PROTON_CPU_TOPOLOGY=16:...`). Every DXVK thread
inherits that pin. DXVK's default `numCompilerThreads = 0` means one per CPU
the game sees (16), part of them reserved for `-h`, so only 10 threads do the
burst, on the same 16 CPUs the game needs, while the other CCD sits idle.

**The fix.** More compile threads, and let only the background ones out of the
pin:

1. `dxvk.conf` next to the game exe:
   ```
   dxvk.numCompilerThreads = 40
   ```
2. `tools/burstpin.sh` as a wrapper, right before the command it launches:
   ```
   <your env vars> /path/to/tools/burstpin.sh taskset -c 0-7,16-23 %command%
   ```
   It notes which game processes (`COMM`, default `Overwatch.exe`) already
   exist, starts the game, then for 10 minutes moves every
   `dxvk-shader-n`/`-l` thread of the new process to 90 % of the CPUs (`PCT`;
   CPUs 0-27 of 32, the left-out ones are SMT siblings on AMD) at nice 10, so
   the desktop and the game's own threads keep priority. `-h` threads stay with
   the game. It exits with the game. The script must be executable
   (`chmod +x`); its log lines (`burstpin: ...`) land in Steam's console output.

Measured on a 7950X3D, warm caches, same evening (burst end = `-n` + `-l`
threads back near 0 %):

| Setup | Burst threads | Burst length |
|---|---|---|
| stock, game pinned to CCD0 | 10 | ~230 s |
| stock threads moved to CCD1 | 10 | ~230 s (smoother, some hitches) |
| 22 threads, `-n`/`-l` on CCD1 | 15 | ~190 s |
| 40 threads, `-n`/`-l` on all 32 CPUs, nice 10 | 27 | ~115 s, then a light tail to ~207 s |

Peak was ~3,700 % CPU and load 62 with no hang. Watch memory: each extra thread
costs a little, and the game already uses ~14 GB.

**Which CPUs this helps:**

- **Dual-CCD X3D (7900X3D, 7950X3D, 9900X3D, 9950X3D) with the game pinned to
  the cache CCD:** the case above. Biggest win.
- **Any CPU where the game is pinned to a subset** (Intel P-cores only, a
  `taskset` for any reason): same mechanism, same fix.
- **Single-CCD X3D (7800X3D, 9800X3D) or no pinning:** the compile threads
  already see every CPU, so `burstpin.sh` only adds the nice level. Raising
  `numCompilerThreads` above the CPU count gains little here. Untested.

Revert: delete `dxvk.conf` and drop `/path/to/tools/burstpin.sh` from the launch options.

## Tools

Python 3 standard library and bash only; nothing to install. The file tools only
read their inputs (`split.py` writes new files to its output dir).

| Tool | What it answers |
|---|---|
| `tools/tocwrap.py <merged.toc> <merged.bin>` | Are you hit by the 4 GiB wrap? Counts entries found at the stored offset vs only at offset + 2^32 |
| `tools/split.py <merged.toc> <out-dir> [prefix]` | Recover every entry, wrapped ones included, into verified parts under 2 GiB; prints the read-only list |
| `tools/reccmp.py <a.toc> <b.toc> [samples]` | Same key in two caches: are header, size and payload the same? |
| `tools/keyoverlap.py <new.toc> <part.toc>...` | How many keys the game wrote are already in the recovered parts |
| `tools/dupkeys.py <a.toc>...` | Entries vs unique keys (one key stored more than once = variants) |
| `tools/probe-read-only.py '<value>'...` | Which files the driver opens for a READ_ONLY_APP_NAME value (headless, via `vulkaninfo`) |
| `tools/warmcheck.sh` | Run before launching: samples cache growth + `dxvk-shader` CPU at +1/3/5/10 min. Warm = cache bytes flat |
| `tools/burstpin.sh` | Not a diagnostic: shortens the launch compile burst of a pinned game (see above) |
| `tools/load.sh`, `tools/compile.sh` | Live snapshots: busy game threads, per-core load, new Steam fragments |

Live-process tools read env vars: `GAME` (a `pgrep -f` pattern for the game
process), `APPID`, `CACHE_DIR` (your `__GL_SHADER_DISK_CACHE_PATH`), `PREFIX`
(split part prefix), and for `burstpin.sh` `COMM` (process name, first 15
chars), `PCT`, `NICE`, `DURATION`. Example for another game:

```sh
GAME='[C]yberpunk2077.exe' CACHE_DIR=~/.cache/nvidia-cp77 tools/warmcheck.sh
```

The merged cache lives at
`~/.local/share/Steam/steamapps/shadercache/<appid>/nvidiav1/GLCache/<driver>/<gpu>/steamapp_merged_shader_cache.{toc,bin}`.

## Resets

- **Driver update** → new `GLCache/<driver-hash>/` dir; private cache cold once
  (one long compile burst). The old dir stays: prune it by hand.
- **Game / Proton update** → partial recompile once; the cache grows (16 GiB cap).

## Previous approach: `ow-shader-sync` (Overwatch only)

`bin/ow-shader-sync --watch` (systemd user unit, `./install.sh`) copied Steam's
replay fragments + merged file into the private dir before Steam merged and
deleted them. Retired: the merged copy carries the wrapped offsets, and the
replay entries hit root cause 2. The one-shot `ow-shader-sync` (no `--watch`)
is still a way to capture a replay's fragments for analysis.

## Upstream

- [steam-for-linux#13622](https://github.com/ValveSoftware/steam-for-linux/issues/13622):
  the main issue (our original report, stock-setup confirmation of the wrap,
  isolated-cache follow-up). Texts in `upstream/`.
- [steam-shader-guard#7](https://github.com/Xerrion/steam-shader-guard/issues/7):
  field report from this setup.
- [Steam Client Beta bug report](https://steamcommunity.com/groups/SteamClientBeta/discussions/0/569301136947844269/)
  and a [reply on the NVIDIA forum](https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196/5)
  asking whether the u32 offset is a hard 4 GiB per-file limit.
- Adjacent: steam-for-linux [#11392](https://github.com/ValveSoftware/steam-for-linux/issues/11392)
  (driver prunes precompiled shaders by size), [#9803](https://github.com/ValveSoftware/steam-for-linux/issues/9803)
  (precompiling into dirs the driver never reads),
  [Proton#9548](https://github.com/ValveSoftware/Proton/issues/9548) (Overwatch
  recompile every relaunch on NVIDIA),
  [NVIDIA forum thread](https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196).
- The NVIDIA cache file format: [therontarigo/nvcachetools](https://github.com/therontarigo/nvcachetools/blob/main/format.txt).

## License

MIT
