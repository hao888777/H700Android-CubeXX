#!/usr/bin/env python3
"""Fix donor Bluetooth.apk SELinux domain mismatch (no platform key needed).

The donor Bluetooth.apk is signed with the Orange Pi platform cert, not this
project's platform cert, so PackageManager assigns seinfo=default instead of
platform. The stock plat_seapp_contexts only matches `user=bluetooth
seinfo=platform`, so zygote's selinux_android_setcontext fails for the app.

Correct key-free fix: drop the `seinfo=platform` requirement from the bluetooth
user entry so it matches by the dedicated bluetooth uid (sharedUserId
android.uid.bluetooth) regardless of signer. This mirrors the already-valid
`user=shared_relro domain=shared_relro` entry (user-only, no seinfo).

IMPORTANT regression guard: libselinux rejects ANY seapp_contexts line that has
`name=` without a specific `seinfo=` ("insecure configuration! Invalid entry"),
and that aborts loading the WHOLE file -- which also kills the isSystemServer
entry and crash-loops system_server. So we must NOT add a name-only bluetooth
line. This script removes such a line if present and asserts the invariant.

seapp_contexts is plain text loaded by libselinux at boot (not compiled CIL,
not signed). The bluetooth domain is already a hal_bluetooth_client in the
existing policy, so no policy recompile is needed.

Also keep ro.bt.bdaddr_path in /system/build.prop (system-namespace
exported_bluetooth_prop; rejected from /vendor/build.prop).

Offline regular-file only; never touches a device or card.
"""
import subprocess
from pathlib import Path

W = Path("/root/cubexx-build")
INP = W / "inputs"
WORK = W / "bt-inject"
WORK.mkdir(exist_ok=True)
SYS = INP / "system-bt.raw"

SEAPP_CTX = "u:object_r:seapp_contexts_file:s0"
SYS_FILE = "u:object_r:system_file:s0"
BAD_ENTRY = "user=bluetooth name=com.android.bluetooth domain=bluetooth type=bluetooth_data_file"
OLD_BT = "user=bluetooth seinfo=platform domain=bluetooth type=bluetooth_data_file"
NEW_BT = "user=bluetooth domain=bluetooth type=bluetooth_data_file"
BDADDR = "ro.bt.bdaddr_path=/sys/class/addr_mgt/addr_bt"
SYSSERVER = "isSystemServer=true domain=system_server_startup"


def dbg(img, cmds):
    cf = WORK / "patch_cmds.txt"
    cf.write_text(cmds)
    r = subprocess.run(["debugfs", "-w", "-f", str(cf), str(img)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"debugfs failed:\n{r.stderr}\n{r.stdout}")
    return r


def dump(img, dest, host):
    subprocess.run(["debugfs", "-R", f"dump {dest} {host}", str(img)],
                   capture_output=True, check=True)
    return Path(host).read_text()


def put(img, host, dest, mode, ctx):
    L = [f"rm {dest}",
         f"write {host} {dest}",
         f"set_inode_field {dest} mode {mode}",
         f"set_inode_field {dest} uid 0",
         f"set_inode_field {dest} gid 0",
         f"ea_set -f {WORK / 'pctx'} {dest} security.selinux"]
    (WORK / "pctx").write_bytes(ctx.encode() + b"\0")
    dbg(img, "\n".join(L) + "\n")


def validate(lines):
    assert SYSSERVER in lines, "isSystemServer entry lost"
    assert BAD_ENTRY not in lines, "invalid name-only bluetooth entry present"
    assert NEW_BT in lines, "corrected bluetooth uid entry missing"
    assert sum(1 for l in lines if l.startswith("user=bluetooth")) == 1, \
        "expected exactly one user=bluetooth entry"
    for l in lines:
        if " name=" in l:
            assert " seinfo=" in l, f"name without seinfo (would abort load): {l}"


# 1) seapp_contexts: drop seinfo=platform from bluetooth user entry; remove any
#    invalid name-only bluetooth line introduced by the earlier broken patch.
seapp = dump(SYS, "/system/etc/selinux/plat_seapp_contexts", WORK / "seapp_old.txt")
out = []
for ln in seapp.splitlines():
    if ln == BAD_ENTRY:
        continue
    out.append(NEW_BT if ln == OLD_BT else ln)
validate(out)
new = "\n".join(out) + "\n"
(WORK / "seapp_new.txt").write_text(new)
put(SYS, WORK / "seapp_new.txt", "/system/etc/selinux/plat_seapp_contexts",
    "0100644", SEAPP_CTX)
print("seapp_contexts corrected (bluetooth matched by uid, no name-only line)")

# 2) system build.prop: ensure ro.bt.bdaddr_path (system namespace).
bp = dump(SYS, "/system/build.prop", WORK / "sysbp_old.txt")
if "ro.bt.bdaddr_path=" in bp:
    print("ro.bt.bdaddr_path already in system build.prop; skipping")
else:
    if not bp.endswith("\n"):
        bp += "\n"
    bp += BDADDR + "\n"
    (WORK / "sysbp_new.txt").write_text(bp)
    put(SYS, WORK / "sysbp_new.txt", "/system/build.prop", "0100644", SYS_FILE)
    print("system build.prop patched")

# readback verify
chk = dump(SYS, "/system/etc/selinux/plat_seapp_contexts", WORK / "seapp_chk.txt")
validate(chk.splitlines())
chkbp = dump(SYS, "/system/build.prop", WORK / "sysbp_chk.txt")
assert BDADDR in chkbp, "build.prop readback missing bdaddr"
print("READBACK OK")
print("--- bluetooth seapp lines ---")
for ln in chk.splitlines():
    if "bluetooth" in ln:
        print(ln)