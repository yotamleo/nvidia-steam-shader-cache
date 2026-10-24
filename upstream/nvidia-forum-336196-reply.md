Thread: https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196
Status: posted 2026-10-24: https://forums.developer.nvidia.com/t/pre-compiled-shader-cache-cleaned-by-nvidia-driver-causing-stutter-when-launching-vulkan-apps/336196/5

Body:

An update for whoever owns the internal bug for this thread. The shrink of Steam's precompiled cache turned out to be more than size-based pruning. It is a 4 GiB offset wraparound in the file Steam's merger builds:

- A `.toc` entry is a 16-byte key + u32 offset + u32 size. Steam merges NVIDIA cache fragments into a single `steamapp_merged_shader_cache.bin` that grows past 2^32 bytes, so later entries get wrapped offsets. Overwatch 2, RTX 4090, 615.78.08: 5,370,772,223 B merged file, 50,673 of 262,547 entries match only at stored offset + 2^32, 0 unmatched. Same result on CS2 (native) from another user.
- With `__GL_SHADER_DISK_CACHE_PATH` pointed at a private dir, out of reach of Steam's merger, the cache stays warm across relaunches (0 bytes of new cache in the first 3 minutes).

Details and the checker: https://github.com/ValveSoftware/steam-for-linux/issues/13622 and https://github.com/yotamleo/nvidia-steam-shader-cache

Two questions for NVIDIA, since Valve labeled the Steam issue `NVIDIA drivers`:

1. Is the u32 offset a hard limit of the cache format, so that any single cache file must stay under 4 GiB? A confirmation here would let Valve fix the merger on its side.
2. Is the list separator for `__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME` officially `;`? It is undocumented; a comma list is silently ignored (tested with `vulkaninfo --summary` and inotify: `a,b`, `a:b`, `a b` open nothing, `a;b` opens both).
