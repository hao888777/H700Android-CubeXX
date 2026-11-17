#!/usr/bin/env python3
import subprocess
from pathlib import Path
W = Path("/root/cubexx-build"); RD = W/"rd-inspect"; INP = W/"inputs"
def dbg(img, cmd):
    p = subprocess.run(["debugfs","-R",cmd,str(img)], capture_output=True, text=True)
    return p.stdout
print("=== ramdisk /init script ===")
print((RD/"init").read_text(errors="replace"))
print("=== ramdisk /etc listing ===")
for p in sorted((RD/"etc").rglob("*")):
    print("  ", p.relative_to(RD))
SYS = INP/"system.raw"; VEN = INP/"vendor.raw"
def probe(img, label, paths):
    print(f"\n########## {label} ##########")
    for path in paths:
        out = dbg(img, f"cat {path}")
        if out and "File not found" not in out and "not found" not in out.lower():
            print(f"\n--- {path} ({len(out)} bytes) ---")
            for l in out.splitlines():
                if any(k in l for k in ["adb","secure","debuggable","usb","ro.build.type","ro.build.tags","sys.usb","configfs","ffs"]):
                    print("   ", l)
        else:
            print(f"  [absent] {path}")
probe(SYS, "SYSTEM", ["/build.prop","/system/build.prop","/etc/prop.default","/system/etc/prop.default","/prop.default"])
probe(VEN, "VENDOR", ["/build.prop","/default.prop","/etc/prop.default","/prop.default"])
print("\n=== vendor /etc/init listing ===")
print(dbg(VEN, "ls -l /etc/init"))
print("\n=== system init rc dirs ===")
for d in ["/etc/init","/system/etc/init","/init.rc","/system/etc/init/hw"]:
    print(f"--- {d} ---"); print(dbg(SYS, f"ls -l {d}")[:1500])