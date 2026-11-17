#!/usr/bin/env python3
import subprocess
from pathlib import Path
INP = Path("/root/cubexx-build/inputs")
def dfs(img, cmd):
    r = subprocess.run(["debugfs","-R",cmd,str(INP/img)],capture_output=True,text=True)
    return r.stdout + r.stderr
print("=== vendor root ===")
print(dfs("vendor.raw","ls -l /"))
print("=== vendor /etc ===")
print(dfs("vendor.raw","ls -l /etc")[:1500])
print("=== system root ===")
print(dfs("system.raw","ls -l /")[:1500])