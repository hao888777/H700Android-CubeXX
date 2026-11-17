#!/usr/bin/env python3
import subprocess, re
from pathlib import Path
INP = Path("/root/cubexx-build/inputs")
SYS = INP/"system.raw"; VEN = INP/"vendor.raw"
def dbg(img, cmd):
    return subprocess.run(["debugfs","-R",cmd,str(img)], capture_output=True, text=True).stdout
print("===== system root / ====="); print(dbg(SYS,"ls -l /"))
print("===== /system/etc/init/hw ====="); print(dbg(SYS,"ls -l /system/etc/init/hw"))
print("===== usbd.rc ====="); print(dbg(SYS,"cat /system/etc/init/usbd.rc"))
for p in ["/init.rc","/init.usb.rc","/system/etc/init/hw/init.rc","/system/etc/init/hw/init.usb.rc",
          "/system/etc/init/init.usb.rc","/system/etc/init/hw/init.rgsp.rc","/system/etc/init/hw/init.sun50iw9p1.rc"]:
    out = dbg(SYS,f"cat {p}")
    if out and "not found" not in out.lower():
        print(f"\n===== {p} ({len(out)}B) ====="); print(out[:6000])
# grep all system rc for adb/usb gadget
print("\n===== grep adbd/sys.usb.config/configfs across system rc =====")
listing = dbg(SYS,"ls /system/etc/init")
names = re.findall(r"\s([\w.@-]+\.rc)\s*$", listing, re.M)
for n in names:
    out = dbg(SYS,f"cat /system/etc/init/{n}")
    hits = [l for l in out.splitlines() if any(k in l for k in ["adbd","sys.usb.config","configfs","ffs.ready","usb.config","ro.secure","ro.debuggable","ro.adb.secure"])]
    if hits:
        print(f"--- {n} ---")
        for l in hits: print("   ",l)