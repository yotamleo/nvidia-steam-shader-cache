Forum: https://forums.developer.nvidia.com/c/gpu-graphics/linux/148  (Linux category; no public tracker for the userspace driver)
Status: DRAFT, not posted (needs a browser login — operator posts)

Title: __GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME: list separator is ';' (undocumented); ',' and prefixes are silently ignored

Body:

`__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME` accepts several read-only caches, but only when they are separated by a semicolon, and nothing in the driver README says so. Anyone who guesses a comma, which is the usual convention, gets no error and no read-only cache, so games that rely on a pre-built cache (Steam's `steamapp_shader_cache*` fragments) compile everything from scratch.

Driver 615.71.09 (open kernel modules), RTX 4090, CachyOS. Tested headlessly: `vulkaninfo --summary` with `__GL_SHADER_DISK_CACHE_PATH`/`__GL_SHADER_DISK_CACHE_APP_NAME=probe` set, watching `IN_OPEN` on the `GLCache/<hash>/<hash>/` dir with inotify:

| `__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME` | Files opened |
|---|---|
| `a,b` | none |
| `a:b` | none |
| `a b` / `a, b` | none |
| `steamapp_shader_cache` (prefix of `steamapp_shader_cache0..30`) | none |
| `a` | a.bin/.toc |
| `a;b` | both |
| 32 names separated by `;` | all 32 |

Requests:
1. Document the separator (and that names are exact, not prefixes) in the README's OpenGL environment variables section.
2. Consider a warning (e.g. with `__GL_SHADER_DISK_CACHE` debug output) when a named read-only cache does not exist.

Context: Steam issue ValveSoftware/steam-for-linux#13622 (Steam's cache merge corrupts the NVIDIA merged cache; the workaround depends on this variable).
