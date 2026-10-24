Where: Steam Community, Steam Client Beta group, "Bug Reports" discussions
https://steamcommunity.com/groups/SteamClientBeta/discussions/0/
Status: draft, not posted.

Title: [Linux][NVIDIA] Shader pre-cache merge corrupts steamapp_merged_shader_cache past 4 GiB (games recompile shaders after every exit)

Body:

Steam client: 1788652215 (stable)
OS: CachyOS (Arch), RTX 4090, nvidia-open 615.78.08
Games: Overwatch 2 (Proton); CS2 (native) confirmed by another user

Problem: on NVIDIA, Steam's shadercachemanager merges the driver's cache fragments into one `steamapp_merged_shader_cache.bin`. The NVIDIA `.toc` format stores offsets as 32-bit values, so once the merged file passes 4 GiB, later entries get wrapped offsets. Steam then logs thousands of `Mismatching key!` lines in `logs/shader_log.txt`, drops those entries at the next merge, and the file shrinks. The game then compiles shaders from scratch for minutes after launch, even after "Processing Vulkan shaders" completed.

Measured: merged file 5,370,772,223 bytes; 50,673 of 262,547 entries found only at their stored offset + 2^32; 0 unmatched otherwise.

Suggested fix: cap each merged file below 4 GiB and roll over to a second file. Splitting the merged file into parts under 2 GiB recovers every entry intact.

Full report with byte-level evidence: https://github.com/ValveSoftware/steam-for-linux/issues/13622
Checker script: https://github.com/yotamleo/nvidia-steam-shader-cache
