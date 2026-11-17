#!/usr/bin/env python3
"""Make kernel logging opt-in, default OFF (offline, system.raw only).

ro.logd.kernel=true keeps a persistent klogd thread reading /dev/kmsg plus a
256KB buffer -- continuous overhead that violates the default-off log policy.
logd only reads ro.logd.kernel at startup (ro = set-once), so:
  * remove ro.logd.kernel from build.prop (unset => logd defaults false, no klogd)
  * add an init trigger: setprop debug.logd.kernel 1 -> set ro.logd.kernel true
    + restart logd. debug.* is non-persistent (debug_prop, shell-settable), so
    every boot starts OFF; opt-in lasts for the session, off again next boot.
No sepolicy change. No device or card writes here.
"""
import re, subprocess
from pathlib import Path

SYS = Path("/root/cubexx-fontfix/system.raw")
W = Path("/root/cubexx-fontfix")
SYS_FILE = "u:object_r:system_file:s0"
TYPE_BITS = {"regular": 0o100000, "directory": 0o040000, "symlink": 0o120000}


def dbg(cmd, w=False):
    args = ["debugfs"] + (["-w"] if w else []) + ["-R", cmd, str(SYS)]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"debugfs {cmd!r} rc={p.returncode}: {p.stderr}")
    return p.stdout


def get_ctx(path):
    out = dbg(f"ea_get {path} security.selinux")
    m = re.search(r'"([^"]*)"', out)
    return m.group(1).replace("\\000", "")


def full_mode(path):
    st = dbg(f"stat {path}")
    perm = re.search(r"Mode:\s*(\d+)", st).group(1)
    ftype = re.search(r"Type:\s*(\w+)", st).group(1)
    return f"0{TYPE_BITS[ftype] | int(perm, 8):o}"


def put(host, dest, mode, ctx):
    ctxf = W / "lo_ctx"
    ctxf.write_bytes(ctx.encode() + b"\0")
    cmds = "\n".join([
        f"rm {dest}",
        f"write {host} {dest}",
        f"set_inode_field {dest} mode {mode}",
        f"set_inode_field {dest} uid 0",
        f"set_inode_field {dest} gid 0",
        f"ea_set -f {ctxf} {dest} security.selinux",
    ]) + "\n"
    cf = W / "lo_cmds.txt"
    cf.write_text(cmds)
    p = subprocess.run(["debugfs", "-w", "-f", str(cf), str(SYS)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"debugfs write failed: {p.stderr}\n{p.stdout}")


# 1. build.prop: drop ro.logd.kernel=true (keep ro.logd.size.kernel for when enabled)
bp = dbg("cat /system/build.prop")
bp_ctx = get_ctx("/system/build.prop")
bp_mode = full_mode("/system/build.prop")
lines = bp.split("\n")
kept = [l for l in lines if not re.match(r"^ro\.logd\.kernel\s*=", l)]
removed = len(lines) - len(kept)
assert removed == 1, f"expected 1 ro.logd.kernel line, removed {removed}"
assert any(l.startswith("ro.logd.size.kernel=") for l in kept), "size.kernel missing"
(W / "build.prop.optin").write_text("\n".join(kept))
put(W / "build.prop.optin", "/system/build.prop", bp_mode, bp_ctx)
print(f"build.prop: removed ro.logd.kernel ({removed} line), ctx={bp_ctx} mode={bp_mode}")

# 2. init trigger for runtime opt-in
RC = (
    "# Opt-in kernel log into logcat -b kernel. Default OFF (no klogd overhead).\n"
    "# Enable for this boot session:  setprop debug.logd.kernel 1\n"
    "# debug.* is non-persistent, so the next boot starts OFF again.\n"
    "on property:debug.logd.kernel=1\n"
    "    setprop ro.logd.kernel true\n"
    "    restart logd\n"
)
rcf = W / "logd-kernel-optin.rc"
rcf.write_bytes(RC.encode())  # LF
put(rcf, "/system/etc/init/logd-kernel-optin.rc", "0100644", SYS_FILE)
print("added /system/etc/init/logd-kernel-optin.rc")

# 3. readback
chk = dbg("cat /system/build.prop")
assert not re.search(r"^ro\.logd\.kernel\s*=", chk, re.M), "ro.logd.kernel still set"
assert "ro.logd.size.kernel=262144" in chk
rc_chk = dbg("cat /system/etc/init/logd-kernel-optin.rc")
assert "on property:debug.logd.kernel=1" in rc_chk and "restart logd" in rc_chk
assert get_ctx("/system/etc/init/logd-kernel-optin.rc") == SYS_FILE
assert full_mode("/system/etc/init/logd-kernel-optin.rc") == "0100644"
assert b"\r" not in rcf.read_bytes(), "CRLF in rc"
print("readback OK; rc LF confirmed")

p = subprocess.run(["e2fsck", "-f", "-n", str(SYS)], capture_output=True, text=True)
print("e2fsck rc", p.returncode)
assert p.returncode in (0, 1)
print("LOGD OPT-IN DEFAULT-OFF OK")