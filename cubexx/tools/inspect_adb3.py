#!/usr/bin/env python3
import subprocess
from pathlib import Path
INP = Path("/root/cubexx-build/inputs")
SYS = INP/"system.raw"; VEN = INP/"vendor.raw"
def dbg(img, cmd):
    return subprocess.run(["debugfs","-R",cmd,str(img)], capture_output=True, text=True).stdout
print("===== SYSTEM /system/build.prop (full) =====")
print(dbg(SYS,"cat /system/build.prop"))
print("===== VENDOR /build.prop (full) =====")
print(dbg(VEN,"cat /build.prop"))
print("===== VENDOR /etc/init/init.rgsp.rc =====")
print(dbg(VEN,"cat /etc/init/init.rgsp.rc"))
print("===== VENDOR /etc/init/roc-user-input.rc =====")
print(dbg(VEN,"cat /etc/init/roc-user-input.rc"))
# find usb / adbd rc files in system init dir
print("===== system init dir: usb/adb candidates =====")
listing = dbg(SYS,"ls /system/etc/init")
import re
names = re.findall(r"\s([\w.@-]+\.rc)\s*$", listing, re.M)
for n in names:
    if any(k in n for k in ["usb","adb","init.","rgsp","h700","sunxi"]):
        print("  candidate:", n)
for n in ["init.usb.rc","init.rgsp.usb.rc","init.sunxi.usb.rc","init.h700.usb.rc","adbd.rc","init.rc"]:
    out = dbg(SYS, f"cat /system/etc/init/{n}")
    if out and "not found" not in out.lower():
        print(f"\n----- /system/etc/init/{n} -----"); print(out)