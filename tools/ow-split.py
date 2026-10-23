#!/usr/bin/env python3
"""Split a Steam-merged NVIDIA shader cache (.toc/.bin) into parts under 2 GiB
with rebuilt TOCs, recovering entries whose 32-bit TOC offset wrapped past 4 GiB.
Payload bytes are copied verbatim. Source files are only read.

Record layout (32-byte header + payload): magic 9da14698, key[16] at +4,
payload size u32 at +28. TOC: the same 32-byte file header, then 24-byte
entries: key[16], offset u32, size u32.

Usage: ow-split.py <merged.toc> <out-dir> [part-prefix]
Prints the ';'-joined part names for __GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME.
"""
import os, struct, sys

WRAP = 1 << 32
LIMIT = 1 << 31
MAGIC = b"\x9d\xa1\x46\x98"


def stamp(p):
    s = os.stat(p)
    return (s.st_ino, s.st_size, s.st_mtime_ns)


def resolve(toc_path):
    """Return (header, rows sorted by real offset, bin length, wrapped count)."""
    bin_path = toc_path[:-4] + ".bin"
    toc = open(toc_path, "rb").read()
    if toc[:4] != b"CDVN" or (len(toc) - 32) % 24:
        sys.exit(f"{toc_path}: not a CDVN toc")
    with open(bin_path, "rb") as f:
        length = os.fstat(f.fileno()).st_size
        if f.read(32) != toc[:32]:
            sys.exit(f"{bin_path}: header differs from its toc")
        rows, wrapped = [], 0
        for i in range(32, len(toc), 24):
            key = toc[i:i + 16]
            off, size = struct.unpack_from("<II", toc, i + 16)
            hits = []
            cand = off
            while cand + 32 + size <= length:
                if cand >= 32:
                    f.seek(cand)
                    h = f.read(32)
                    if h[:4] == MAGIC and h[4:20] == key and struct.unpack_from("<I", h, 28)[0] == size:
                        hits.append(cand)
                cand += WRAP
            if len(hits) != 1:
                sys.exit(f"entry {(i - 32) // 24}: {len(hits)} matches, refusing to guess")
            wrapped += hits[0] != off
            rows.append((hits[0], key, size))
    rows.sort()
    cursor = 32
    for off, _key, size in rows:
        if off != cursor:
            sys.exit(f"gap/overlap at {cursor} (next record at {off})")
        cursor = off + 32 + size
    if cursor != length:
        sys.exit(f"bin has {length - cursor} bytes not covered by the toc")
    return toc[:32], rows, length, wrapped


def main():
    toc_path, out_dir = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else "owsplit"
    bin_path = toc_path[:-4] + ".bin"
    before = (stamp(toc_path), stamp(bin_path))
    header, rows, length, wrapped = resolve(toc_path)
    print(f"source: {len(rows)} entries, {wrapped} wrapped, {length} bytes")
    os.makedirs(out_dir, exist_ok=True)
    names, start, part = [], 0, 0
    src = open(bin_path, "rb")
    while start < len(rows):
        end, size = start, 32
        while end < len(rows) and size + 32 + rows[end][2] < LIMIT:
            size += 32 + rows[end][2]
            end += 1
        if end == start:
            sys.exit(f"entry larger than {LIMIT} bytes")
        name = f"{prefix}{part}"
        base = os.path.join(out_dir, name)
        lo = rows[start][0]
        hi = rows[end - 1][0] + 32 + rows[end - 1][2]
        with open(base + ".bin.tmp", "wb") as out:
            out.write(header)
            src.seek(lo)
            left = hi - lo
            while left:
                buf = src.read(min(left, 1 << 24))
                out.write(buf)
                left -= len(buf)
            out.flush()
            os.fsync(out.fileno())
        toc = bytearray(header)
        for off, key, sz in rows[start:end]:
            toc += key + struct.pack("<II", 32 + off - lo, sz)
        with open(base + ".toc.tmp", "wb") as out:
            out.write(toc)
            out.flush()
            os.fsync(out.fileno())
        os.replace(base + ".bin.tmp", base + ".bin")
        os.replace(base + ".toc.tmp", base + ".toc")
        _h, check, plen, pw = resolve(base + ".toc")
        if pw or len(check) != end - start or [r[1] for r in check] != [r[1] for r in rows[start:end]]:
            sys.exit(f"{name}: verification failed")
        print(f"{name}: {end - start} entries, {plen} bytes, 0 wrapped, verified")
        names.append(name)
        part += 1
        start = end
    if before != (stamp(toc_path), stamp(bin_path)):
        sys.exit("source changed while splitting; output is not trustworthy")
    print("READ_ONLY_APP_NAME=" + ";".join(names))


main()
