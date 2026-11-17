#!/usr/bin/env python3
"""Create system-force.raw from system-adb.raw by appending insecure ADB props
to /system/build.prop (preserving its system_file:s0 context and 0600 mode).
Belt-and-suspenders alongside /default.prop and the pre-seeded adb_keys, so adbd
accepts hosts without the on-screen dialog and listens on tcp5555. Offline only.
"""
import shutil, subprocess
from pathlib import Path

W = Path("/root/cubexx-build")
SRC = W / "inputs" / "system-adb.raw"
DST = W / "inputs" / "system-force.raw"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def main():
    shutil.copyfile(SRC, DST)
    bp = run(["debugfs", "-R", "cat /system/build.prop", str(DST)]).encode()
    add = (b"\n# force insecure adb (debug image)\n"
           b"ro.secure=0\nro.adb.secure=0\nro.debuggable=1\n"
           b"service.adb.tcp.port=5555\npersist.adb.tcp.port=5555\n"
           b"persist.sys.usb.config=adb\n")
    if b"ro.adb.secure=0" in bp:
        print("build.prop already has ro.adb.secure=0; skipping append")
    else:
        (W / "build.prop.new").write_bytes(bp + add)
    ctx = W / "bp.ctx"; ctx.write_bytes(b"u:object_r:system_file:s0\0")
    cmds = W / "force_bp.cmds"
    cmds.write_text(
        "rm /system/build.prop\n"
        f"write {W / 'build.prop.new'} /system/build.prop\n"
        "set_inode_field /system/build.prop mode 0100600\n"
        f"ea_set -f {ctx} /system/build.prop security.selinux\n"
    )
    run(["debugfs", "-w", "-f", str(cmds), str(DST)])
    # verify
    tail = run(["debugfs", "-R", "cat /system/build.prop", str(DST)])
    assert "ro.adb.secure=0" in tail and "ro.secure=0" in tail
    assert "persist.adb.tcp.port=5555" in tail
    ea = run(["debugfs", "-R", "ea_get /system/build.prop security.selinux", str(DST)])
    assert "system_file:s0" in ea, ea
    st = run(["debugfs", "-R", "stat /system/build.prop", str(DST)])
    assert "0600" in st, st
    print("system-force.raw build.prop updated; context system_file:s0, mode 0600")
    print("tail:\n" + "\n".join(tail.splitlines()[-9:]))


if __name__ == "__main__":
    main()