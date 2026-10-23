Field report from Overwatch 2 (RTX 4090, nvidia-open 615.78.08, CachyOS, proton-cachyos 11.0-20261015). Two results that may help with the "What has not been established" section of VALIDATION.md. I didn't run the binary: I wrote a small Python splitter that follows your format rules from `src/cache.rs` (resolve each entry at stored offset + k·2^32, check contiguity, shards under 2^31, copy the 32-byte header) and used the isolated-cache approach by hand.

**1. A warm relaunch works with an isolated cache**

Launch options: `__GL_SHADER_DISK_CACHE_PATH=<private dir> __GL_SHADER_DISK_CACHE_APP_NAME=overwatch __GL_SHADER_DISK_CACHE_SIZE=17179869184 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1`, plus the recovered shards in `__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME` (`;`-separated; the driver opened all 3 shards).

| | First launch | Relaunch |
|---|---|---|
| Game's own cache written, first 3 min | 932 MB | 0 bytes |
| Written, first 10 min | 2.46 GB | 43 MB |
| Written over a whole match | n/a | 65 MB |

At the start of the relaunch there's still a ~4 min burst of `dxvk-shader` threads at ~950 % CPU, even though nothing new reached the driver cache. My guess is that it's DXVK-side work the NVIDIA cache can't skip.

**2. Recovered Steam entries are only partly usable**

I recovered Steam's merged file (262,547 entries, 50,673 wrapped) into 3 verified shards. On the first launch the game recompiled 50,164 of the 108,103 keys in shard 0, and none from shards 1 and 2. For the same 16-byte key, the shard record and the game's fresh record differ in header bytes 20..28, in payload size and in payload content (2,000 of 2,000 sampled pairs). No file contains a key twice. So the TOC key isn't the full identity of a cache entry: the driver seems to check the second field and recompile when it doesn't match. My unverified guess is that those entries came from Steam's `fossilize_replay`, which doesn't get the game's driver application profile.

In practice `recover` restores the bytes faithfully, but some of the recovered entries may never be used, so the copy step may matter less than the isolated cache. A note in the README or in VALIDATION.md might set expectations.

Happy to share the scripts (splitter, key-overlap and record-compare) if that's useful.
