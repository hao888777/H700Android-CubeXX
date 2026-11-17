#!/usr/bin/env python3
"""Remove the broken telephony-disable feature from system-bt.raw.

com.android.phone (TeleService) is a PERSISTENT app: AMS starts/restarts it
regardless of `pm disable` (enabled=2). Disabling its telephony provider made
PhoneApp crash on content://telephony/siminfo, and AMS respawned it forever
(crash loop confirmed across reboot). Shell has no root to re-enable on device.
Cleanly de-persisting TeleService needs the platform key (re-sign without
android:persistent), which is parked. So remove the disable script + rc;
telephony stays enabled and the crash loop is gone. Fresh userdata on reflash
means the packages start enabled and stay enabled.

Everything else is preserved: seapp bluetooth uid fix, memory daemon disabling
(cameraserver/incidentd/mediametrics/statsd + ro.statsd.enable=false +
persist.traced.enable=0), ro.bt.bdaddr_path. Offline regular-file only.
"""
import subprocess
from pathlib import Path

W = Path("/root/cubexx-build")
INP = W / "inputs"
WORK = W / "bt-inject"
WORK.mkdir(exist_ok=True)
SYS = INP / "system-bt.raw"

REMOVE = [
    "/system/etc/roc_disable_telephony.sh",
    "/system/etc/init/roc-disable-telephony.rc",
]


def dbg(cmds):
    cf = WORK / "rm_tel_cmds.txt"
    cf.write_text(cmds)
    r = subprocess.run(["debugfs", "-w", "-f", str(cf), str(SYS)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"debugfs failed:\n{r.stderr}\n{r.stdout}")
    return r


def cat(dest):
    r = subprocess.run(["debugfs", "-R", f"cat {dest}", str(SYS)],
                       capture_output=True)
    return r.stdout


def exists(dest):
    # debugfs returns exit 0 even for missing files; judge by stat output.
    r = subprocess.run(["debugfs", "-R", f"stat {dest}", str(SYS)],
                       capture_output=True, text=True)
    return "Inode:" in r.stdout


# 1) Remove the telephony-disable script + rc (idempotent).
dbg("\n".join(f"rm {p}" for p in REMOVE) + "\n")
for p in REMOVE:
    assert not exists(p), f"{p} still present after rm"
print("removed telephony-disable script + rc")

# 2) Sanity: preserved fixes still intact.
stext = cat("/system/etc/selinux/plat_seapp_contexts").decode()
assert "isSystemServer=true domain=system_server_startup" in stext
assert "user=bluetooth domain=bluetooth type=bluetooth_data_file" in stext
assert "name=com.android.bluetooth" not in stext, "invalid name-only line back"
btext = cat("/system/build.prop").decode()
assert "ro.bt.bdaddr_path=/sys/class/addr_mgt/addr_bt" in btext
assert "ro.statsd.enable=false" in btext
assert "persist.traced.enable=0" in btext
cam = cat("/system/etc/init/cameraserver.rc")
assert b"disabled" in cam, "cameraserver disable lost"
print("preserved: seapp bluetooth uid fix, build.prop props, cameraserver disabled")
print("READBACK OK")