On NVIDIA, a game that pre-cached its shaders through Steam stutters as if the cache were cold on the next launch after an exit or a new Shader Swarm bucket, because Steam's shadercachemanager loses entries when it merges NVIDIA cache fragments into `steamapp_merged_shader_cache.bin`. With large pipeline sets (Overwatch 2) that means minutes of 100% CPU DXVK compiling and low fps on most launches, and the ~15 minute "Processing Vulkan shaders" run after each update is largely wasted.

This looks like the root cause of the shrink reported in #11392 (7.5 GB -> 4.5 GB after a game session with `__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1` set), which was attributed to driver pruning there. The size-limit part of #11392 is real and is fixed by `__GL_SHADER_DISK_CACHE_SIZE`; the shrink below is logged by Steam's own merge step, not by the driver.

#### Your system information

* Steam client version: 1788652215
* Distribution: CachyOS, kernel 7.2.5
* Opted into Steam client beta?: No
* Have you checked for system updates?: Yes
* GPU / driver: RTX 4090, nvidia-open 610.57.04 and 615.71.09 (reproduces on both)
* Game: Overwatch 2 (2357570), Proton
* Shader pre-caching and background processing: enabled
* Filesystem: btrfs, 3.4 TB free

#### Please describe your issue in as much detail as possible:

Every time shadercachemanager merges NVIDIA fragments into
`steamapps/shadercache/<appid>/nvidiav1/GLCache/<hash>/<hash>/steamapp_merged_shader_cache.bin`,
`logs/shader_log.txt` prints thousands of `Mismatching key! Entry N/M.` lines,
and the merged file keeps less than it was given or gets smaller:

| When | Merge trigger | `Mismatching key!` lines | Merged .bin |
|---|---|---|---|
| driver 610.57 | merge + crawl (a host hang earlier that day may have contributed) | 18,240 (+ `FOZ underflow, file truncated?`) | 4.3 GB, not used on relaunch |
| driver 610.57 | **game exit**, folding in the game's `steamapp_shader_cache1` fragment | 40,558 | **6.94 GB -> 4.80 GB** |
| driver 615.71.09 | new bucket after a game update | 29,582 | 4.40 GB |
| driver 615.71.09 | after `fossilize_replay` finished: 31 fragments totalling 7.4 GB | 3,469 | 4.40 GB -> 5.21 GB, fragments deleted |

On the 610.57 run the first launch after pre-caching did read the merged file
(4.5 GB read in ~2 minutes, warm). One exit later the merge above ran, and the
second launch was cold again (3 DXVK compiler threads at 100%, +149 MB of new
cache in 70 s).

Log shape:

```
[..23:37:27] Mismatching key! Entry 1053285538/13703.
... 29,580 more lines ...
[..23:37:38] Mismatching key! Entry 111463556/33079.
[..23:37:38] Done with merging potential NVIDIA fragments.
```

Timing detail that matters for workarounds: the fragments are merged and deleted a few seconds after the `fossilize_replay` process exits, before `fossilize_replay completed, remove from build queue.` is logged.

#### Steps for reproducing this issue:

1. NVIDIA GPU, shader pre-caching on, a game with a large pipeline set (Overwatch 2).
2. Let "Processing Vulkan shaders" finish. Launch, play a match, exit.
3. `grep -c 'Mismatching key' ~/.local/share/Steam/logs/shader_log.txt` and compare the size of `steamapp_merged_shader_cache.bin` before and after the exit.
4. Launch again: DXVK compiles as on a cold cache.

#### Workaround (works on 615.71.09)

1. Keep the driver's writable cache away from the merger with launch options:
   `__GL_SHADER_DISK_CACHE_PATH=$HOME/.cache/nvidia-<game> __GL_SHADER_DISK_CACHE_APP_NAME=<game> __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1`
2. When `fossilize_replay` exits, copy the fresh `steamapp_shader_cache*.{bin,toc}` fragments (and the merged file) into the same `GLCache/<hash>/<hash>/` dir under that path, before Steam merges and deletes them. A small watcher polling `pgrep -x fossilize_repla` is enough.
3. List them as read-only caches. The separator is a **semicolon**, and every name must be exact; a comma-separated list or the bare `steamapp_shader_cache` prefix is silently ignored by the driver:
   `__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME="steamapp_merged_shader_cache;steamapp_shader_cache0;steamapp_shader_cache1;...;steamapp_shader_cache30"`

With that, the game holds all 32 read-only caches open, its own cache grows by 0 bytes over the first minutes, and warm launches stay warm across exits.

Related: #11392 (driver size-limit pruning, and the shrink above), #9803 (precompiling into cache dirs the driver never reads).
