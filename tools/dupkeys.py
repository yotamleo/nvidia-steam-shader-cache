#!/usr/bin/env python3
"""Per .toc: entries vs unique 16-byte keys (same key stored more than once = variants).
Usage: dupkeys.py <a.toc>..."""
import collections, sys

for p in sys.argv[1:]:
    t = open(p, "rb").read()
    c = collections.Counter(t[i:i + 16] for i in range(32, len(t) - 23, 24))
    multi = sum(1 for v in c.values() if v > 1)
    print(f"{p.rsplit('/', 1)[-1]}: entries={sum(c.values())} unique={len(c)} keys-with-variants={multi} max-per-key={max(c.values())}")
