Confirming the 4 GiB wraparound from @edmundselliot's comment, now on a fully stock shader setup (Overwatch 2, RTX 4090, nvidia-open 615.78.08, Steam client 1788652215, proton-cachyos 11.0-20261015). No `__GL_SHADER_DISK_CACHE_*` or other shader env vars, no custom cache path, no `dxvk.conf`, no `steam_dev.cfg`; Steam's own shadercachemanager is the only thing touching the cache. The same bug shows up with CS2 (native, no Proton) above, so the Proton build shouldn't matter.

After one stock session, the exit merge wrote `steamapp_merged_shader_cache.bin` at 5,370,772,223 bytes (5.00 GiB), with a `.toc` of 262,547 entries.

Checking each TOC entry's 16-byte key against the section header at its stored offset:

- 211,874 entries match at the stored offset
- 50,673 entries (19 %) match only at stored offset + 2^32
- 0 entries are unmatched

The first wrapped entry is index 211,874, the one right after the last good entry, whose section ends at 4,294,973,767, just past 2^32. Every record is physically intact and only the 32-bit offset in the `.toc` overflowed.

The cycle is visible across one session:

| Merge | `.bin` size | Wrapped entries |
|---|---|---|
| Steam restart, before playing | 4,403,315,492 | 3,444 of 203,109 |
| Game launch | 6,170,928,386 | (replaced before I could check) |
| Game exit, after adding a new 1,075,803,069-byte fragment | 5,370,772,223 | 50,673 of 262,547 |

The exit merge came out 1.87 GB smaller than the launch merge plus the new fragment. `shader_log.txt` logged "Mismatching key!" at least 131,769 times between 21:19:44 and 21:20:01, during the merge and during the upload pass that reads the new merged file. The log hit its 4 MB rotation twice in that window, so the real count is higher. So the merger drops what it can't find through the wrapped offsets, the file shrinks, the next session pushes it over 4 GiB again, and the cycle repeats. Those dropped shaders presumably get compiled again in the next session.

The TOC entry's offset field is 4 bytes, so a single merged file can't address more than 4 GiB. A fix on the Steam side would be to stop merging at 4 GiB and start a second merged file (`steamapp_merged_shader_cache1.bin`), or to keep the per-fragment files instead of merging past that size.

The checker is about 30 lines of Python:

```python
import mmap, struct, sys

toc_path, bin_path = sys.argv[1], sys.argv[2]
toc = open(toc_path, "rb").read()
f = open(bin_path, "rb")
b = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
size = len(b)
n = (len(toc) - 0x20) // 0x18
ok = wrap = bad = 0
first_wrap = None
max_ok_end = 0
for i in range(n):
    e = toc[0x20 + i * 0x18: 0x20 + (i + 1) * 0x18]
    key, off, sz = e[:0x10], struct.unpack("<I", e[0x10:0x14])[0], struct.unpack("<I", e[0x14:0x18])[0]
    if b[off + 4:off + 0x14] == key:
        ok += 1
        max_ok_end = max(max_ok_end, off + sz)
    elif off + 2**32 + 0x14 <= size and b[off + 2**32 + 4:off + 2**32 + 0x14] == key:
        wrap += 1
        if first_wrap is None:
            first_wrap = i
    else:
        bad += 1
print(f"bin={size} ({size / 2**30:.2f} GiB) entries={n} ok={ok} wrapped_by_2^32={wrap} unmatched={bad}")
print(f"first wrapped entry index={first_wrap} max matched end offset={max_ok_end} (2^32={2**32})")
```

Run it as `python3 tocwrap.py steamapp_merged_shader_cache.toc steamapp_merged_shader_cache.bin` in `shadercache/<appid>/nvidiav1/GLCache/<driverhash>/<hash>/`.
