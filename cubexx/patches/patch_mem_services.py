#!/usr/bin/env python3
"""Trim non-essential native daemons on the 1GB CubeXX (no platform key needed).

CubeXX has no camera and is a handheld; these diagnostics/capture daemons are
safe to stop auto-starting. init .rc files are plain text (not signed), so we
add the `disabled` option to each service block. statsd also honours
ro.statsd.enable=false; traced/traced_probes are already `disabled` and only
run when persist.traced.enable=1, so we pin that to 0.

Savings (PSS observed on device): cameraserver ~5.3M, mediametrics ~3.2M,
statsd ~2.3M, incidentd ~2M, plus traced/traced_probes when triggered.

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

# service rc -> insert `disabled` after its single `class main` line
RC_DISABLED = ["cameraserver", "incidentd", "mediametrics", "statsd"]
BP_ADD = ["ro.statsd.enable=false", "persist.traced.enable=0"]


def dbg(img, cmds):
    cf = WORK / "mem_cmds.txt"
    cf.write_text(cmds)
    r = subprocess.run(["debugfs", "-w", "-f", str(cf), str(img)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"debugfs failed:\n{r.stderr}\n{r.stdout}")


def dump(img, dest, host):
    subprocess.run(["debugfs", "-R", f"dump {dest} {host}", str(img)],
                   capture_output=True, check=True)
    return Path(host).read_text()


def put(img, host, dest, mode="0100644"):
    (WORK / "mctx").write_bytes(SYS_FILE.encode() + b"\0")
    L = [f"rm {dest}", f"write {host} {dest}",
         f"set_inode_field {dest} mode {mode}",
         f"set_inode_field {dest} uid 0", f"set_inode_field {dest} gid 0",
         f"ea_set -f {WORK / 'mctx'} {dest} security.selinux"]
    dbg(img, "\n".join(L) + "\n")


for name in RC_DISABLED:
    dest = f"/system/etc/init/{name}.rc"
    txt = dump(SYS, dest, WORK / f"{name}_old.rc")
    if "\n    disabled\n" in txt:
        print(f"{name}.rc already disabled; skip")
        continue
    assert txt.count("    class main\n") == 1, f"{name}: expected one class main"
    new = txt.replace("    class main\n", "    class main\n    disabled\n", 1)
    (WORK / f"{name}_new.rc").write_text(new)
    put(SYS, WORK / f"{name}_new.rc", dest)
    print(f"{name}.rc -> disabled")

bp = dump(SYS, "/system/build.prop", WORK / "membp_old.txt")
want = dict(l.split("=", 1) for l in BP_ADD)
seen = set()
out = []
for ln in bp.splitlines():
    key = ln.split("=", 1)[0] if "=" in ln else None
    if key in want:
        out.append(f"{key}={want[key]}")
        seen.add(key)
    else:
        out.append(ln)
for k, v in want.items():
    if k not in seen:
        out.append(f"{k}={v}")
(WORK / "membp_new.txt").write_text("\n".join(out) + "\n")
put(SYS, WORK / "membp_new.txt", "/system/build.prop")
print("build.prop set: " + ", ".join(BP_ADD))

# readback
for name in RC_DISABLED:
    chk = dump(SYS, f"/system/etc/init/{name}.rc", WORK / f"{name}_chk.rc")
    assert "\n    disabled\n" in chk, f"{name} readback missing disabled"
chkbp = dump(SYS, "/system/build.prop", WORK / "membp_chk.txt")
for l in BP_ADD:
    assert l in chkbp, f"build.prop readback missing {l}"
print("READBACK OK")