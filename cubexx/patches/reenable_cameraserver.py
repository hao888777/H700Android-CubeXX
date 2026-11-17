#!/usr/bin/env python3
"""Re-enable cameraserver on CubeXX (revert the task#14 `disabled` flag).

Root cause (dropbox system_server_watchdog x4, all identical main-thread stack):
  UsbCameraDeviceManagerObserver$BootCompletedReceiver.onReceive ->
  Camera.getNumberOfCameras -> libcamera_client getCameraService ->
  BpServiceManager::getService("media.camera") spins in usleep because
  cameraserver was `disabled` and never published the service -> main thread
  blocked > watchdog timeout -> system_server killed -> recurring soft reboot.

cameraserver runs fine on this camera-less hardware (verified on device:
init.svc.cameraserver=running, `service check media.camera`=found, 0 cameras),
so auto-starting it at class main makes media.camera available before
BOOT_COMPLETED and the receiver returns immediately. incidentd/mediametrics/
statsd stay disabled (they do not trigger this block).

Offline regular-file only; never touches a device or card.
"""
import subprocess
from pathlib import Path

W = Path("/root/cubexx-fontfix")
SYS = W / "system.raw"
SYS_FILE = "u:object_r:system_file:s0"
DEST = "/system/etc/init/cameraserver.rc"


def dbg(cmds):
    cf = W / "cam_cmds.txt"
    cf.write_text(cmds)
    r = subprocess.run(["debugfs", "-w", "-f", str(cf), str(SYS)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"debugfs failed:\n{r.stderr}\n{r.stdout}")


def dump(dest, host):
    subprocess.run(["debugfs", "-R", f"dump {dest} {host}", str(SYS)],
                   capture_output=True, check=True)
    return Path(host).read_text()


txt = dump(DEST, W / "cam_old.rc")
assert "\n    disabled\n" in txt, "cameraserver.rc is not disabled; nothing to revert"
assert txt.count("    class main\n") == 1, "expected exactly one class main"
new = txt.replace("    class main\n    disabled\n", "    class main\n", 1)
assert "\n    disabled\n" not in new, "disabled line not removed"
(W / "cam_new.rc").write_text(new)
(W / "cam_ctx").write_bytes(SYS_FILE.encode() + b"\0")

L = [f"rm {DEST}",
     f"write {W / 'cam_new.rc'} {DEST}",
     f"set_inode_field {DEST} mode 0100644",
     f"set_inode_field {DEST} uid 0",
     f"set_inode_field {DEST} gid 0",
     f"ea_set -f {W / 'cam_ctx'} {DEST} security.selinux"]
dbg("\n".join(L) + "\n")

chk = dump(DEST, W / "cam_chk.rc")
assert "\n    disabled\n" not in chk, "readback still disabled"
assert "service cameraserver /system/bin/cameraserver" in chk
assert "    class main\n" in chk
print("=== cameraserver.rc after revert ===")
print(chk)

r = subprocess.run(["e2fsck", "-f", "-n", str(SYS)], capture_output=True, text=True)
print("e2fsck rc=", r.returncode)
assert r.returncode == 0, r.stdout + r.stderr
print("READBACK + E2FSCK OK")