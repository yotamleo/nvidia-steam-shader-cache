Title: shadercachemanager corrupts the NVIDIA merged shader cache ("Mismatching key!"), merged .bin shrinks, games recompile every launch

Repo: ValveSoftware/steam-for-linux

#### Your system information

* Steam client version: 1788652215 (package manifest 2026-09-06)
* Distribution: CachyOS (kernel 7.2.5-cachyos)
* GPU / driver: NVIDIA RTX 4090, nvidia-open 610.57.04 and 615.71.09 (reproduces on both)
* Game: Overwatch 2 (2357570), proton-cachyos-slr
* Shader pre-caching: enabled, background processing enabled
* Filesystem: btrfs, 3.4 TB free (not a space issue)

#### Please describe your issue in as much detail as possible:

When shadercachemanager merges NVIDIA GL cache fragments into
`shadercache/<appid>/nvidiav1/GLCache/<hash>/<hash>/steamapp_merged_shader_cache.bin`,
`logs/shader_log.txt` prints tens of thousands of `Mismatching key! Entry N/M.` lines,
and the merged file ends up SMALLER than before. The game then recompiles
pipelines it had already built, so every launch after an exit (or after a new
Shader Swarm bucket) starts with minutes of DXVK compile stutter.

Observed three times:

| When | Trigger | Mismatching key lines | Merged .bin |
|---|---|---|---|
| 2026-09-06, driver 610.57 | merge + crawl | 18,240 (+ `FOZ underflow, file truncated?`) | 4.3 GB, never read back |
| 2026-09-13 21:52, driver 610.57 | game exit, merging the game's `steamapp_shader_cache1` fragment | 40,558 | 6.94 GB -> 4.80 GB |
| 2026-09-15 23:37, driver 615.71.09 | merging fragments after a new bucket / game update | 29,582 | 4.40 GB after merge |
| 2026-09-15 23:55, driver 615.71.09 | merging 31 replay fragments (7.4 GB) after `fossilize_replay` exited; fragments deleted afterwards | 3,469 | 4.40 GB -> 5.21 GB |

On 09-13 the first launch after Steam's fossilize replay did read the merged
file (4.5 GB read in 2 min), but after a single exit the merge above ran and
the second launch was cold again.

Log shape (09-15):

```
[2026-09-15 23:37:27] Mismatching key! Entry 1053285538/13703.
... 29,580 more ...
[2026-09-15 23:37:38] Mismatching key! Entry 111463556/33079.
[2026-09-15 23:37:38] Done with merging potential NVIDIA fragments.
```

Also: Steam merges the fragments right after `fossilize_replay` exits and
before it logs `fossilize_replay completed`.

#### Steps for reproducing this issue:

1. NVIDIA GPU, shader pre-caching on, play a game with a large pipeline set (Overwatch 2).
2. Let "Processing Vulkan shaders" finish, launch the game, play, exit.
3. Read `~/.local/share/Steam/logs/shader_log.txt`: thousands of `Mismatching key!`
   lines at the merge, and the merged .bin shrinks.
4. Launch again: compile stutter as if the cache were cold.

#### Workaround

Keep the driver's cache out of Steam's reach with launch options:

```
__GL_SHADER_DISK_CACHE_PATH=$HOME/.cache/nvidia-<game> __GL_SHADER_DISK_CACHE_APP_NAME=<game> __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%
```

With that, warm relaunches have the compiler threads idle within 90 s. The cost is
that Steam's pre-compiled output is no longer used, unless you copy the fragments
into that dir when the replay exits and add
`__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME="steamapp_merged_shader_cache;steamapp_shader_cache0;...;steamapp_shader_cache30"`
(script: <gist link>). Note the separator is `;` and each fragment must be named
exactly: a comma-separated list, or the bare prefix `steamapp_shader_cache`, is
silently ignored by the driver (verified with inotify on 615.71.09).

Related but different: #11392 (driver pruning precompiled shaders by size), #9803
(precompiling into dirs the driver never reads).
