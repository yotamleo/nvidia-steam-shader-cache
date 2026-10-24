@kisak-valve could this be relabeled from `NVIDIA drivers` to a Steam client label? The evidence in this thread points at Steam's shadercachemanager, not the driver:

- **The 4 GiB limit is the NVIDIA cache file format** (a `.toc` entry stores the `.bin` offset as a u32). The driver writes its own cache as separate per-app files (`<app>0.bin`, `<app>1.bin`, …).
- **Steam's merge builds one file past 4 GiB.** The merged `steamapp_merged_shader_cache.bin` reaches 5+ GB, entries beyond 2^32 get wrapped offsets, and the merger itself logs `Mismatching key!` and drops them at the next merge. That reproduces on two independent machines with byte-level checks (CS2 native by @edmundselliot, Overwatch 2 under Proton by me: 50,673 of 262,547 entries found only at stored offset + 2^32, 0 unmatched).
- **The same driver works when Steam's merger is kept out of it.** With a private `__GL_SHADER_DISK_CACHE_PATH`, the relaunch wrote 0 bytes of new cache in its first 3 minutes.

A client-side fix would be to cap each merged file below 4 GiB and roll over to a second file. Splitting the merged file into parts under 2 GiB recovers every entry intact (`tools/split.py` in the repo below). The checker I used is public if it helps reproduce: https://github.com/yotamleo/nvidia-steam-shader-cache/blob/main/tools/tocwrap.py
