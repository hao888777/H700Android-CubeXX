#!/usr/bin/env python3
import subprocess, re
from pathlib import Path
SYS = Path("/root/cubexx-build/inputs/system.raw")
W = Path("/root/cubexx-build")
def dbg(cmd): return subprocess.run(["debugfs","-R",cmd,str(SYS)], capture_output=True, text=True).stdout
print("=== default.prop selinux xattr ===")
print(dbg("ea_get /default.prop security.selinux"))
print("=== init.environ.rc ===")
print(dbg("cat /init.environ.rc"))
# dump real init binary and grep prop file paths
subprocess.run(["debugfs","-R","dump /system/bin/init /root/cubexx-build/init.bin",str(SYS)],capture_output=True)
data = (W/"init.bin").read_bytes()
print(f"=== init.bin {len(data)} bytes; prop-path strings ===")
strs = re.findall(rb"[\x20-\x7e]{6,}", data)
seen=set()
for s in strs:
    t=s.decode()
    if (".prop" in t or "build.prop" in t or "prop.default" in t) and "/" in t and t not in seen:
        seen.add(t); print("  ", t)