#!/usr/bin/env python3
"""Revert the POWER/VOLUME WAKE change in Generic.kl (offline, system.raw only).

The refined on-device symptom proved short-press power DOES wake the display
(backlight comes on); the black screen was first-boot UI crash-loop (font
defect), not a missing WAKE flag. Restore Generic.kl to its original bytes so
the deliverable contains only the actual root-cause fix (fontfix).
"""
import re, subprocess
from pathlib import Path

SYS = Path("/root/cubexx-fontfix/system.raw")
W = Path("/root/cubexx-fontfix")
DEST = "/system/usr/keylayout/Generic.kl"
TARGETS = {"114", "115", "116"}


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


orig = dbg(f"cat {DEST}")
ctx = get_ctx(DEST)
lines = orig.split("\n")
reverted = []
for i, ln in enumerate(lines):
    m = re.match(r"^key\s+(114|115|116)\s+(\S+)\s+WAKE\s*$", ln)
    if m:
        lines[i] = f"key {m.group(1)}   {m.group(2)}"
        reverted.append(m.group(1))
assert set(reverted) == TARGETS, f"expected revert {TARGETS}, got {reverted}"
new = "\n".join(lines)
(W / "Generic.kl.revert").write_text(new)
ctxf = W / "Generic.kl.ctx"
ctxf.write_bytes(ctx.encode() + b"\0")

cmds = "\n".join([
    f"rm {DEST}",
    f"write {W/'Generic.kl.revert'} {DEST}",
    f"set_inode_field {DEST} mode 0100644",
    f"set_inode_field {DEST} uid 0",
    f"set_inode_field {DEST} gid 0",
    f"ea_set -f {ctxf} {DEST} security.selinux",
]) + "\n"
cf = W / "pw_revert_cmds.txt"
cf.write_text(cmds)
p = subprocess.run(["debugfs", "-w", "-f", str(cf), str(SYS)],
                   capture_output=True, text=True)
if p.returncode != 0:
    raise RuntimeError(f"debugfs write failed: {p.stderr}\n{p.stdout}")

chk = dbg(f"cat {DEST}")
for ln in chk.split("\n"):
    m = re.match(r"^key\s+(114|115|116)\s+", ln)
    if m:
        assert "WAKE" not in ln, f"WAKE still present: {ln}"
        print("  ", ln)
assert get_ctx(DEST) == ctx
p = subprocess.run(["e2fsck", "-f", "-n", str(SYS)], capture_output=True, text=True)
print("e2fsck rc", p.returncode)
assert p.returncode in (0, 1)
print("WAKE REVERT OK")