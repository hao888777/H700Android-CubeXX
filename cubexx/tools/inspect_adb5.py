#!/usr/bin/env python3
import subprocess
from pathlib import Path
SYS = Path("/root/cubexx-build/inputs/system.raw")
def dbg(cmd): return subprocess.run(["debugfs","-R",cmd,str(SYS)], capture_output=True, text=True).stdout
for p in ["/default.prop","/init.usb.rc","/init.usb.configfs.rc","/init.environ.rc"]:
    print(f"\n========== {p} =========="); print(dbg(f"cat {p}"))
print("\n========== init.rc: adbd / usb / secure lines ==========")
rc = dbg("cat /init.rc")
for i,l in enumerate(rc.splitlines()):
    if any(k in l for k in ["adbd","sys.usb","usb.config","ffs","configfs","ro.secure","ro.debuggable","ro.adb.secure","service.adb","persist.sys.usb"]):
        print(f"  {i}: {l}")