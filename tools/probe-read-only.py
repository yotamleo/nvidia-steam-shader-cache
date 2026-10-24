#!/usr/bin/env python3
"""Which files in the private GLCache dir does the NVIDIA driver open for each
__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME value? Headless: runs `vulkaninfo
--summary` (opens the shader cache without a window) and watches IN_OPEN via
inotify through ctypes, so no strace/inotifywait is needed. Safe while a game
runs. Leaves a 32-byte probe0.bin/.toc pair in the dir; delete it afterwards.

Usage: probe-read-only.py 'name_a;name_b' 'name_a,name_b' ...
Env: CACHE_DIR = the private cache dir (default ~/.cache/nvidia-overwatch).
"""
import ctypes, glob, os, select, struct, subprocess, sys, time

CACHE_PATH = os.path.expanduser(os.environ.get("CACHE_DIR", "~/.cache/nvidia-overwatch"))
IN_OPEN = 0x20
libc = ctypes.CDLL("libc.so.6", use_errno=True)


def opened(cache_dir, ro):
    fd = libc.inotify_init1(os.O_NONBLOCK)
    libc.inotify_add_watch(fd, cache_dir.encode(), IN_OPEN)
    env = dict(os.environ,
               __GL_SHADER_DISK_CACHE_PATH=CACHE_PATH,
               __GL_SHADER_DISK_CACHE_APP_NAME="probe")
    if ro is not None:
        env["__GL_SHADER_DISK_CACHE_READ_ONLY_APP_NAME"] = ro
    subprocess.run(["vulkaninfo", "--summary"], env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)
    names = set()
    while select.select([fd], [], [], 0)[0]:
        buf = os.read(fd, 65536)
        i = 0
        while i < len(buf):
            _wd, _mask, _cookie, ln = struct.unpack_from("iIII", buf, i)
            names.add(buf[i + 16:i + 16 + ln].rstrip(b"\0").decode())
            i += 16 + ln
    os.close(fd)
    return sorted(n for n in names if n and not n.startswith(("probe", "overwatch")))


dirs = glob.glob(os.path.join(CACHE_PATH, "GLCache", "*", "*"))
if not dirs:
    sys.exit(f"no GLCache/<driver>/<gpu> dir under {CACHE_PATH}")
cache_dir = max(dirs, key=os.path.getmtime)
print(f"dir: {cache_dir}")
for ro in [None] + sys.argv[1:]:
    print(f"RO={ro!r}: {opened(cache_dir, ro)}")
