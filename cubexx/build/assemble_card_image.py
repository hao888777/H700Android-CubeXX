#!/usr/bin/env python3
"""Parameterized CubeXX card image assembler (offline regular-file only).

Two modes:
  seed : fixed SEED_BYTES (32434554368) image, GPT p7 at the grow minimum
         (last LBA 63348735, 20GiB userdata). Flash the SAME seed to any card
         >= 32GB; first boot grow --apply expands GPT to fill the card, then
         resize2fs expands the filesystem => auto-adapts to different cards.
  full : image sized to the EXACT --card-size; p7 fills the card, backup GPT at
         card end, userdata fs fills p7 => first boot needs NO grow.

--prefix selects the hardware prefix (default cubexx-prefix.raw; use
cubexx-prefix-debug.raw for the framebuffer boot-progress ramdisk).
Never writes a device or card.
"""
import argparse, gzip, hashlib, json, struct, sys, zlib
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
sys.path.insert(0, "/mnt/e/AI/H700Android/tools/public_build")
sys.path.insert(0, "/mnt/e/AI/H700Android/work/cubexx-build")
from audit_rgsp_single_card_boot import gpt, package, SECTOR
from common import sha, run
from pack import assemble
from assemble_cubexx_image import compact_gpt_public

W = Path("/root/cubexx-build")
INP = W / "inputs"
USERDATA_OFFSET = 10959716352
UUID = "cd5e86c5-155f-5d96-8e90-12ec44abf24a"
SEED_BYTES = 32434554368          # grow_gpt.c capacity minimum (line 69)
P7_MIN_LAST_LBA = SEED_BYTES // 512 - 4   # 63348735 (line 93)


def make_userdata(path, nbytes):
    with path.open("xb") as f:
        f.truncate(nbytes)
    run(["mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096", "-I", "256", "-L", "userdata",
         "-U", UUID, "-O", "^orphan_file,^metadata_csum_seed,^metadata_csum,^64bit",
         "-E", "root_owner=1000:1000,lazy_itable_init=1,lazy_journal_init=1", str(path)])
    run(["debugfs", "-w", "-R", "set_inode_field / mode 040771", str(path)])
    ctx = path.parent / "ud.ctx"
    ctx.write_bytes(b"u:object_r:system_data_file:s0\0")
    run(["debugfs", "-w", "-R", f"ea_set -f {ctx} / security.selinux", str(path)])
    return path


def inject_adb_keys(path, keyfile, workdir):
    """Pre-seed /data/misc/adb/adb_keys so adbd trusts this host without the
    on-screen authorization dialog, regardless of ro.adb.secure."""
    keyfile = Path(keyfile)
    assert keyfile.is_file(), keyfile
    cmds = workdir / "adb_keys.cmds"
    c_misc = workdir / "ctx_misc"; c_misc.write_bytes(b"u:object_r:system_data_file:s0\0")
    c_adb = workdir / "ctx_adb"; c_adb.write_bytes(b"u:object_r:adb_data_file:s0\0")
    c_keys = workdir / "ctx_keys"; c_keys.write_bytes(b"u:object_r:adb_keys_file:s0\0")
    cmds.write_text(
        "mkdir /misc\n"
        "mkdir /misc/adb\n"
        f"write {keyfile} /misc/adb/adb_keys\n"
        "set_inode_field /misc mode 040771\n"
        "set_inode_field /misc/adb mode 040755\n"
        "set_inode_field /misc/adb/adb_keys mode 0100644\n"
        f"ea_set -f {c_misc} /misc security.selinux\n"
        f"ea_set -f {c_adb} /misc/adb security.selinux\n"
        f"ea_set -f {c_keys} /misc/adb/adb_keys security.selinux\n"
    )
    run(["debugfs", "-w", "-f", str(cmds), str(path)])
    out = run(["debugfs", "-R", "cat /misc/adb/adb_keys", str(path)]).stdout
    assert out.encode() == keyfile.read_bytes(), "adb_keys readback mismatch"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["seed", "full"], required=True)
    ap.add_argument("--card-size", type=int, default=62534975488,
                    help="exact target card bytes (full mode only)")
    ap.add_argument("--prefix", default=str(W / "cubexx-prefix.raw"))
    ap.add_argument("--system", default=str(INP / "system-adb.raw"))
    ap.add_argument("--vendor", default=str(INP / "vendor.raw"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--adb-keys", default=None,
                    help="host adb public key to pre-seed into /data/misc/adb/adb_keys")
    args = ap.parse_args()

    if args.mode == "seed":
        disk = SEED_BYTES
    else:
        disk = args.card_size
        assert disk >= SEED_BYTES, "full card smaller than grow minimum"
    assert disk % 512 == 0
    ud_bytes = disk - 1536 - USERDATA_OFFSET
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    prefix = bytearray(Path(args.prefix).read_bytes())
    assert len(prefix) == 222298112
    prefix, tail = compact_gpt_public(prefix, disk)
    parts = gpt(prefix)
    assert parts[-1]["name"] == "userdata"
    assert parts[-1]["end_exclusive"] == disk - 1536
    assert parts[-1]["start"] == USERDATA_OFFSET
    p7_last_lba = (disk - 1536) // 512 - 1
    assert p7_last_lba >= P7_MIN_LAST_LBA, (p7_last_lba, P7_MIN_LAST_LBA)
    if args.mode == "seed":
        assert p7_last_lba == P7_MIN_LAST_LBA, "seed p7 must sit at grow minimum"
    assert tail[1024:1032] == b"EFI PART"
    (out / "prefix.raw").write_bytes(prefix)
    (out / "backup_gpt.raw").write_bytes(tail)
    print(f"GPT {args.mode} OK; disk={disk} p7 bytes={ud_bytes} p7_last_lba={p7_last_lba}")
    for p in parts:
        print(f"  p{p['number']} {p['name']:14s} {p['start']}..{p['end_exclusive']}")

    ud = make_userdata(out / "userdata.raw", ud_bytes)
    if args.adb_keys:
        inject_adb_keys(ud, args.adb_keys, out)
        print("pre-seeded /data/misc/adb/adb_keys:", args.adb_keys)
    raw = out / args.name
    if raw.exists():
        raw.unlink()
    ranges = [(0, out / "prefix.raw"),
              (222298112, Path(args.system)),
              (8812232704, Path(args.vendor)),
              (USERDATA_OFFSET, ud),
              (disk - 1536, out / "backup_gpt.raw")]
    print("assembling (readback verifies every range)...", flush=True)
    assemble(raw, disk, ranges)
    with raw.open("rb") as f:
        head = f.read(8 * 1024 * 1024)
        f.seek(disk - 1536); backup = f.read(1536)
        f.seek(155189248); boot = f.read(64 * 1024 * 1024)
        f.seek(32800 * SECTOR); toc = f.read(4 * 1024 * 1024)
        for off in (222298112, 8812232704, USERDATA_OFFSET):
            f.seek(off + 1080); assert f.read(2) == b"\x53\xef", f"ext4 @{off}"
    gpt(head)
    bh = bytearray(backup[1024:1536]); assert bh[:8] == b"EFI PART"
    bsize, bcrc = struct.unpack_from("<II", bh, 12); struct.pack_into("<I", bh, 16, 0)
    assert zlib.crc32(bh[:bsize]) == bcrc
    assert head[8196:8204] == b"eGON.BT0"
    pkg = package(toc); assert {"u-boot", "monitor", "dtb"} <= {i["name"] for i in pkg["items"]}
    assert boot[:8] == b"ANDROID!"
    raw_hash = sha(raw)
    packed = raw.with_suffix(".img.gz")
    if packed.exists():
        packed.unlink()
    print("compressing...", flush=True)
    with raw.open("rb") as src, packed.open("xb") as dst:
        with gzip.GzipFile(filename="", fileobj=dst, mode="wb", compresslevel=6, mtime=0) as z:
            while block := src.read(1024 ** 2):
                z.write(block)
    with gzip.open(packed, "rb") as z:
        assert hashlib.file_digest(z, "sha256").hexdigest() == raw_hash

    if args.mode == "seed":
        fix = ("auto-expand seed: GPT p7 at grow minimum (20GiB), first boot on any card "
               ">=32GB runs grow --apply (GPT fills card, reboot) then resize2fs (fs fills p7)")
    else:
        fix = ("full-card GPT (p7 fills card, backup at card end) + userdata fs fills p7 "
               "=> first boot grow --check=0 --check-volume=0, NO --apply")
    receipt = {
        "status": "BUILT_PENDING_PHYSICAL_TEST", "device": "RG CubeXX (H700,1GB,720x720)",
        "mode": args.mode, "image": raw.name, "raw_bytes": disk, "raw_sha256": raw_hash,
        "gz_bytes": packed.stat().st_size, "gz_sha256": sha(packed),
        "fix": fix, "target_card_bytes": disk,
        "min_card_bytes": SEED_BYTES if args.mode == "seed" else disk,
        "prefix_sha256": sha(Path(args.prefix)),
        "adb": "enabled (system /default.prop: ro.secure=0 ro.debuggable=1 ro.adb.secure=0 usb=adb tcp5555)",
        "boot_chain": "CubeXX stock boot0/TOC1/kernel/DTB + project ramdisk + enforcing",
        "partitions": parts, "userdata_bytes": ud_bytes,
        "physical_device_tested": False, "card_written": False,
    }
    (out / "result.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()