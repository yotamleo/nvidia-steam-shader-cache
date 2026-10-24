#!/usr/bin/env python3
"""Count .toc entries whose u32 .bin offset wrapped past 4 GiB (key found only at offset + 2^32).
Usage: tocwrap.py <merged.toc> <merged.bin>"""
import mmap, struct, sys

if len(sys.argv) < 3:
    sys.exit(__doc__)

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
