#!/usr/bin/env python3
import subprocess, os, gzip, shutil
from pathlib import Path
W = Path("/root/cubexx-build")
RD = W/"rd-inspect"
if RD.exists(): shutil.rmtree(RD)
RD.mkdir()
# unpack project ramdisk
with gzip.open(W/"project-ramdisk.gz","rb") as f:
    data = f.read()
(RD/"ramdisk.cpio").write_bytes(data)
subprocess.run(["cpio","-idm","--no-absolute-filenames","-F","ramdisk.cpio"], cwd=RD,
               capture_output=True)
print("=== ramdisk top-level ===")
for p in sorted(RD.iterdir()):
    print(" ", p.name, "(dir)" if p.is_dir() else p.stat().st_size)
print("\n=== *.rc / prop files in ramdisk ===")
for p in sorted(RD.rglob("*")):
    if p.is_file() and (p.suffix in (".rc",".prop") or p.name in ("default.prop","prop.default","build.prop")):
        print(" ", p.relative_to(RD), p.stat().st_size)
def grep_file(p, pats):
    try: txt = p.read_text(errors="replace")
    except Exception: return
    hits = [l for l in txt.splitlines() if any(k in l for k in pats)]
    if hits:
        print(f"\n--- {p} ---")
        for l in hits: print("   ", l)
pats = ["adb","usb","secure","debuggable","ro.secure","sys.usb","adbd","ffs","configfs"]
print("\n=== ramdisk init/prop grep ===")
for p in sorted(RD.rglob("*")):
    if p.is_file() and (p.suffix in (".rc",".prop") or "prop" in p.name or p.name=="init"):
        grep_file(p, pats)