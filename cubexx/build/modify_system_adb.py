#!/usr/bin/env python3
"""Offline-edit a sparse copy of system.raw to force early-boot ADB.
Preserves the original default.prop SELinux context (rootfs) and mode 0600.
No device writes; the original system.raw is left untouched for rollback."""
import subprocess, shutil
from pathlib import Path
INP = Path("/root/cubexx-build/inputs")
SYS = INP/"system.raw"
DST = INP/"system-adb.raw"
W = Path("/root/cubexx-build")

def dbg(img, cmd, w=False):
    args = ["debugfs"] + (["-w"] if w else []) + ["-R", cmd, str(img)]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"debugfs {cmd!r} rc={p.returncode}: {p.stderr}")
    return p.stdout

# 1. sparse copy (keep original intact)
if DST.exists(): DST.unlink()
subprocess.run(["cp","--sparse=always",str(SYS),str(DST)], check=True)

# 2. build modified default.prop
orig = dbg(DST, "cat /default.prop")
repl = {
    "ro.secure=1": "ro.secure=0",
    "ro.adb.secure=1": "ro.adb.secure=0",
    "ro.debuggable=0": "ro.debuggable=1",
    "persist.sys.usb.config=none": "persist.sys.usb.config=adb",
    "service.adb.tcp.port=-1": "service.adb.tcp.port=5555",
    "persist.adb.tcp.port=-1": "persist.adb.tcp.port=5555",
}
new = orig
for a,b in repl.items():
    assert new.count(a+"\n") == 1, f"expected exactly one {a!r}, got {new.count(a)}"
    new = new.replace(a+"\n", b+"\n")
(W/"default.prop.new").write_text(new)
ctx = W/"default.prop.ctx"; ctx.write_bytes(b"u:object_r:rootfs:s0\0")

# 3. replace file in ext4, restore context + mode
dbg(DST, "rm /default.prop", w=True)
dbg(DST, f"write {W/'default.prop.new'} /default.prop", w=True)
dbg(DST, f"ea_set -f {ctx} /default.prop security.selinux", w=True)
dbg(DST, "set_inode_field /default.prop mode 0100600", w=True)
dbg(DST, "set_inode_field /default.prop uid 0", w=True)
dbg(DST, "set_inode_field /default.prop gid 0", w=True)

# 4. verify
check = dbg(DST, "cat /default.prop")
for b in repl.values():
    assert b+"\n" in check, f"missing {b}"
assert "persist.sys.usb.config=none" not in check
print("=== modified default.prop (adb lines) ===")
for l in check.splitlines():
    if any(k in l for k in ["secure","debuggable","usb.config","adb.tcp"]):
        print("  ", l)
print("=== context ==="); print(dbg(DST,"ea_get /default.prop security.selinux"))
print("=== inode ==="); print(dbg(DST,"stat /default.prop"))
# 5. filesystem integrity
p = subprocess.run(["e2fsck","-f","-n",str(DST)], capture_output=True, text=True)
print("=== e2fsck rc", p.returncode, "===")
print(p.stdout[-800:]); print(p.stderr[-400:])
assert p.returncode in (0,1), "e2fsck reported errors"
print("SYSTEM-ADB READY:", DST)