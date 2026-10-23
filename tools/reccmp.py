#!/usr/bin/env python3
"""For keys present in both files, compare record header bytes 20..28 and payloads.
Usage: reccmp.py <a.toc> <b.toc> [samples]"""
import struct, sys, collections


def index(p):
    t = open(p, "rb").read()
    return {t[i:i + 16]: struct.unpack_from("<II", t, i + 16) for i in range(32, len(t) - 23, 24)}


a, b = index(sys.argv[1]), index(sys.argv[2])
fa, fb = open(sys.argv[1][:-4] + ".bin", "rb"), open(sys.argv[2][:-4] + ".bin", "rb")
common = list(set(a) & set(b))
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
stats = collections.Counter()
ex = []
for k in common[:n]:
    (oa, sa), (ob, sb) = a[k], b[k]
    fa.seek(oa); ra = fa.read(32 + sa)
    fb.seek(ob); rb = fb.read(32 + sb)
    stats["size_eq" if sa == sb else "size_diff"] += 1
    stats["hdr20_28_eq" if ra[20:28] == rb[20:28] else "hdr20_28_diff"] += 1
    stats["payload_eq" if ra[32:] == rb[32:] else "payload_diff"] += 1
    if len(ex) < 3 and ra != rb:
        ex.append((k.hex(), ra[:32].hex(), rb[:32].hex(), sa, sb))
print(f"common={len(common)} sampled={min(n, len(common))}", dict(stats))
for e in ex:
    print("key", e[0], "sizes", e[3], e[4]); print("  a", e[1]); print("  b", e[2])
