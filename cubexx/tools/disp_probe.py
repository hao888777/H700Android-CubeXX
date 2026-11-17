#!/usr/bin/env python3
import subprocess
from pathlib import Path
INP = Path("/root/cubexx-build/inputs")
OUT = Path("/root/cubexx-build/dump"); OUT.mkdir(exist_ok=True)
def dfs(img, cmd):
    r = subprocess.run(["debugfs","-R",cmd,str(INP/img)],capture_output=True,text=True)
    return r.stdout + r.stderr
def dump(img, path):
    dest = OUT/(path.replace("/","_"))
    subprocess.run(["debugfs","-R",f"dump {path} {dest}",str(INP/img)],capture_output=True,text=True)
    return dest.read_text(errors="replace") if dest.is_file() else None
print("=== vendor /etc/dispconfigs ===")
print(dfs("vendor.raw","ls -l /etc/dispconfigs"))
for f in ["h700-rgsp-lcd.json","h700-auto-display.json","display-config.json"]:
    t = dump("vendor.raw", f"/etc/dispconfigs/{f}")
    if t: print(f"--- /etc/dispconfigs/{f} ---\n{t}")
print("=== vendor /etc/init (input/disp) ===")
print(dfs("vendor.raw","ls -l /etc/init"))
print("=== vendor build.prop (density/product) ===")
t = dump("vendor.raw","/build.prop")
if t:
    for line in t.splitlines():
        if any(k in line for k in ("density","product","device","lcd","sf.")): print("  ",line)