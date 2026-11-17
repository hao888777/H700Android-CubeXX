#!/usr/bin/env python3
"""Remove the injected Bluetooth app + feature declarations (offline, system.raw).

The donor Bluetooth.apk is not platform-signed, so it lacks
INTERACT_ACROSS_USERS_FULL and crash-loops at boot (8 crashes, then AM backs off
>1h). Removing the app + feature xmls eliminates the boot crash bursts; BT is
cleanly absent (it never worked without the platform key). The 32-bit BT libs
and vendor HAL are left in place but inert (no app/framework consumes them).
No device or card writes here.
"""
import subprocess
from pathlib import Path

SYS = Path("/root/cubexx-fontfix/system.raw")
W = Path("/root/cubexx-fontfix")

RM_FILES = [
    "/system/app/Bluetooth/Bluetooth.apk",
    "/system/app/Bluetooth/lib/arm/libbluetooth_jni.so",
    "/system/etc/permissions/android.hardware.bluetooth.xml",
    "/system/etc/permissions/android.hardware.bluetooth_le.xml",
]
RMDIRS = [
    "/system/app/Bluetooth/lib/arm",
    "/system/app/Bluetooth/lib",
    "/system/app/Bluetooth",
]


def dbg(cmd, w=False):
    args = ["debugfs"] + (["-w"] if w else []) + ["-R", cmd, str(SYS)]
    return subprocess.run(args, capture_output=True, text=True)


cmds = [f"rm {p}" for p in RM_FILES] + [f"rmdir {p}" for p in RMDIRS]
cf = W / "bt_rm_cmds.txt"
cf.write_text("\n".join(cmds) + "\n")
p = subprocess.run(["debugfs", "-w", "-f", str(cf), str(SYS)],
                   capture_output=True, text=True)
print("=== debugfs rm/rmdir output ===")
print(p.stdout[-600:])
if p.returncode != 0:
    raise RuntimeError(f"debugfs failed rc={p.returncode}: {p.stderr}")

# verify gone
for path in RM_FILES + RMDIRS:
    r = dbg(f"stat {path}")
    assert "File not found" in (r.stdout + r.stderr) or r.returncode != 0, \
        f"still present: {path}\n{r.stdout}"
print("all BT app paths removed")

# parent dirs clean
print("=== /system/app (bluetooth?) ===")
print(dbg("ls /system/app").stdout)
print("=== permissions bluetooth? ===")
out = dbg("ls /system/etc/permissions").stdout
assert "bluetooth" not in out.lower(), "bluetooth feature still present"
print("no bluetooth feature xml")

p = subprocess.run(["e2fsck", "-f", "-n", str(SYS)], capture_output=True, text=True)
print("e2fsck rc", p.returncode)
print(p.stdout[-400:])
assert p.returncode in (0, 1)
print("BT APP REMOVAL OK")