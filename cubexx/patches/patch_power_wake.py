#!/usr/bin/env python3
"""Add WAKE flag to POWER/VOLUME keys in Generic.kl (offline, system.raw only).

The axp2202-pek power key (vendor/product=0) falls back to Generic.kl, whose
`key 116 POWER` lacks WAKE. Without FLAG_WAKE, a short power press while the
display is off (non-interactive) does not turn the screen on; only a long press
(global-actions path) wakes it. Kernel wake is fine (DTS pmu wakeup-source +
wakeup_rising/falling), so this is purely an Android keylayout flag fix.

Preserves SELinux context / mode / uid / gid. No device or card writes here.
"""
import re, subprocess
from pathlib import Path

SYS = Path("/root/cubexx-fontfix/system.raw")
W = Path("/root/cubexx-fontfix")
DEST = "/system/usr/keylayout/Generic.kl"
TARGETS = {"114", "115", "116"}  # VOLUME_DOWN, VOLUME_UP, POWER


def dbg(cmd, w=False):
    args = ["debugfs"] + (["-w"] if w else []) + ["-R", cmd, str(SYS)]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"debugfs {cmd!r} rc={p.returncode}: {p.stderr}")
    return p.stdout


def get_ctx(path):
    out = dbg(f"ea_get {path} security.selinux")
    m = re.search(r'"([^"]*)"', out)
    assert m, f"no ctx for {path}: {out}"
    return m.group(1).replace("\\000", "")


orig = dbg(f"cat {DEST}")
ctx = get_ctx(DEST)
stat = dbg(f"stat {DEST}")
# debugfs stat shows permission bits only (e.g. "0644") plus a separate Type.
# Reconstruct the FULL i_mode (file-type bits | perms) or the inode is corrupted.
perm = re.search(r"Mode:\s*(\d+)", stat).group(1)
ftype = re.search(r"Type:\s*(\w+)", stat).group(1)
uid = re.search(r"User:\s*(\d+)", stat).group(1)
gid = re.search(r"Group:\s*(\d+)", stat).group(1)
TYPE_BITS = {"regular": 0o100000, "directory": 0o040000, "symlink": 0o120000}
assert ftype in TYPE_BITS, f"unexpected type {ftype}"
full_mode = TYPE_BITS[ftype] | int(perm, 8)
mode = f"0{full_mode:o}"

lines = orig.split("\n")
changed = []
for i, ln in enumerate(lines):
    m = re.match(r"^key\s+(\d+)\s+(\S+)\s*$", ln)
    if m and m.group(1) in TARGETS and "WAKE" not in ln:
        lines[i] = f"key {m.group(1):<5} {m.group(2):<17} WAKE"
        changed.append(m.group(1))
assert set(changed) == TARGETS, f"expected to change {TARGETS}, changed {changed}"
new = "\n".join(lines)

(W / "Generic.kl.new").write_text(new)
ctxf = W / "Generic.kl.ctx"
ctxf.write_bytes(ctx.encode() + b"\0")

cmds = "\n".join([
    f"rm {DEST}",
    f"write {W/'Generic.kl.new'} {DEST}",
    f"set_inode_field {DEST} mode {mode}",
    f"set_inode_field {DEST} uid {uid}",
    f"set_inode_field {DEST} gid {gid}",
    f"ea_set -f {ctxf} {DEST} security.selinux",
]) + "\n"
cf = W / "pw_cmds.txt"
cf.write_text(cmds)
p = subprocess.run(["debugfs", "-w", "-f", str(cf), str(SYS)],
                   capture_output=True, text=True)
if p.returncode != 0:
    raise RuntimeError(f"debugfs write failed: {p.stderr}\n{p.stdout}")

# readback
chk = dbg(f"cat {DEST}")
for ln in chk.split("\n"):
    m = re.match(r"^key\s+(\d+)\s+", ln)
    if m and m.group(1) in TARGETS:
        assert "WAKE" in ln, f"readback missing WAKE: {ln}"
        print("  ", ln)
assert get_ctx(DEST) == ctx, "context changed"
st2 = dbg(f"stat {DEST}")
perm2 = re.search(r"Mode:\s*(\d+)", st2).group(1)
ftype2 = re.search(r"Type:\s*(\w+)", st2).group(1)
assert (TYPE_BITS[ftype2] | int(perm2, 8)) == full_mode, "mode changed"
print(f"ctx={ctx} mode={mode} uid={uid} gid={gid}")

p = subprocess.run(["e2fsck", "-f", "-n", str(SYS)], capture_output=True, text=True)
print("e2fsck rc", p.returncode)
print(p.stdout[-400:])
assert p.returncode in (0, 1), "e2fsck errors"
print("POWER-WAKE PATCH OK")