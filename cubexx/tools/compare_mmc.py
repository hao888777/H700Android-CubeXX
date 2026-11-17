#!/usr/bin/env python3
import struct, subprocess
from pathlib import Path
W = Path("/root/cubexx-build")
boot = (W/"inputs/boot.raw").read_bytes()  # RGSP 0.0.1 boot partition
assert boot[:8]==b"ANDROID!"
ksize,kaddr,rsize,raddr,ssize,saddr,tags = struct.unpack_from("<7I",boot,8)
page = struct.unpack_from("<I",boot,36)[0]
dt_raw = struct.unpack_from("<I",boot,40)[0]
def align(x): return (x+page-1)//page*page
doff = page+align(ksize)+align(rsize)+align(ssize)
dtb = boot[doff:]
magic,total = struct.unpack(">II",dtb[:8])
assert magic==0xd00dfeed
dtb = dtb[:total]
(W/"rgsp.dtb").write_bytes(dtb)
subprocess.run(["dtc","-I","dtb","-O","dts","-o",str(W/"rgsp.dts"),str(W/"rgsp.dtb")],capture_output=True)
dts = (W/"rgsp.dts").read_text(errors="replace")
print("=== RGSP sd/mmc controller node names ===")
import re
for m in re.finditer(r"^\s*(sdmmc@[\da-f]+|sdc\d@[\da-f]+|mmc@[\da-f]+)\s*\{", dts, re.M):
    print("  node:", m.group(1))
print("=== RGSP aliases sdc ===")
for l in dts.splitlines():
    if re.search(r"sdc\d\s*=", l): print("  ", l.strip())
print("=== RGSP boot_devices ===")
for l in dts.splitlines():
    if "boot_devices" in l: print("  ", l.strip())