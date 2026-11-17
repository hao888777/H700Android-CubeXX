#!/usr/bin/env python3
import struct, sys, gzip
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
from android_bootimg import read_header, component_offsets
INP = Path("/root/cubexx-build/inputs")
_, h = read_header(INP/"boot.raw")
print("=== RGSP 0.0.1 boot.img addresses ===")
for k in ("kernel_addr","ramdisk_addr","second_addr","tags_addr","page_size","kernel_size","ramdisk_size"):
    v=h[k]; print(f"  {k}={v:#x}" if isinstance(v,int) and k.endswith('addr') else f"  {k}={v}")
print(f"  cmdline={h['cmdline']!r}")
print("  CubeXX: kernel_addr=0x40080000 ramdisk_addr=0x42000000 tags_addr=0x40000000")
# extract 0.0.1 ramdisk for reuse
off=component_offsets(h)
raw=(INP/"boot.raw").read_bytes()
rd=raw[off['ramdisk']:off['ramdisk']+h['ramdisk_size']]
Path("/root/cubexx-build/project-ramdisk.gz").write_bytes(rd)
print(f"=== saved project ramdisk: {len(rd)} bytes, gzip={rd[:2].hex()} ===")
# env partition p3 @132MB..148MB in prefix
prefix=(INP/"prefix.raw").read_bytes()
env=prefix[138412032:155189248]
# find printable bootargs strings
import re
print("=== env (p3) printable strings (first 40) ===")
seen=0
for m in re.finditer(rb"[ -~]{6,}",env):
    s=m.group(0).decode()
    if any(k in s for k in ("bootargs","console","lcd","disp","root=","mmc","selinux","bootcmd","verify","android")):
        print("  ",s[:160]); seen+=1
        if seen>=40: break