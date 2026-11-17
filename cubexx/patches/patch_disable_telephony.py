#!/usr/bin/env python3
"""Persistently disable the telephony (baseband) stack on the no-modem CubeXX.

com.android.phone is a PERSISTENT system app, so it auto-starts at boot even
though the device declares no telephony feature and ro.radio.noril=yes. Shell
uid can only disable-user (which does not stop a persistent app); a global
`pm disable` (enabled=2) requires root uid and makes AMS kill the process and
skip it on subsequent boots.

We bake a one-shot init service that runs as root (seclabel shell:s0 so it may
call the package manager) on boot_completed, globally disables the telephony
packages once, and logs the result to /data/local/tmp/telephony_disable.log.
The disabled state persists in /data; the flag avoids re-running each boot.

Offline regular-file only; never touches a device or card.
"""
import subprocess
from pathlib import Path

W = Path("/root/cubexx-build")
INP = W / "inputs"
WORK = W / "bt-inject"
WORK.mkdir(exist_ok=True)
SYS = INP / "system-bt.raw"
SYS_FILE = "u:object_r:system_file:s0"

SCRIPT = """#!/system/bin/sh
LOG=/data/local/tmp/telephony_disable.log
FLAG=/data/local/tmp/.roc_telephony_disabled
{
  echo "uid=$(id -u) $(date)"
  if [ -f "$FLAG" ]; then echo "already disabled"; exit 0; fi
  pm disable com.android.phone
  pm disable com.android.providers.telephony
  touch "$FLAG"
  echo "done"
} >> "$LOG" 2>&1
"""

RC = """service roc_disable_telephony /system/bin/sh /system/etc/roc_disable_telephony.sh
    class late_start
    user root
    group root shell log
    disabled
    oneshot
    seclabel u:r:shell:s0

on property:sys.boot_completed=1
    start roc_disable_telephony
"""


def dbg(img, cmds):
    cf = WORK / "tel_cmds.txt"
    cf.write_text(cmds)
    r = subprocess.run(["debugfs", "-w", "-f", str(cf), str(img)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"debugfs failed:\n{r.stderr}\n{r.stdout}")


def put(host, dest, mode):
    (WORK / "tctx").write_bytes(SYS_FILE.encode() + b"\0")
    L = [f"rm {dest}", f"write {host} {dest}",
         f"set_inode_field {dest} mode {mode}",
         f"set_inode_field {dest} uid 0", f"set_inode_field {dest} gid 0",
         f"ea_set -f {WORK / 'tctx'} {dest} security.selinux"]
    dbg(SYS, "\n".join(L) + "\n")


(WORK / "roc_disable_telephony.sh").write_text(SCRIPT, newline="\n")
(WORK / "roc-disable-telephony.rc").write_text(RC, newline="\n")
put(WORK / "roc_disable_telephony.sh", "/system/etc/roc_disable_telephony.sh", "0100755")
put(WORK / "roc-disable-telephony.rc", "/system/etc/init/roc-disable-telephony.rc", "0100644")

# readback
for dest, expect in [("/system/etc/roc_disable_telephony.sh", "pm disable com.android.phone"),
                     ("/system/etc/init/roc-disable-telephony.rc", "roc_disable_telephony")]:
    out = subprocess.run(["debugfs", "-R", f"cat {dest}", str(SYS)],
                         capture_output=True, text=True).stdout
    assert expect in out, f"readback missing {expect} in {dest}"
print("telephony disable service injected + verified")