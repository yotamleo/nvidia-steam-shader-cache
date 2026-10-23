#!/usr/bin/env python3
"""How many keys in the game's new cache file already exist in the split parts?
Usage: keyoverlap.py <new.toc> <part.toc>..."""
import sys


def keys(p):
    t = open(p, "rb").read()
    return {t[i:i + 16] for i in range(32, len(t) - 23, 24)}


new = keys(sys.argv[1])
old = set().union(*(keys(p) for p in sys.argv[2:]))
hit = len(new & old)
print(f"new={len(new)} known={len(old)} new-already-known={hit} ({100 * hit / max(len(new), 1):.1f} %)")
