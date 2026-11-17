#!/usr/bin/env python3
"""Build a full-card CubeXX image sized to the EXACT target card so first boot
needs NO GPT grow (the compact --apply path is broken on real hardware).
GPT p7 fills the card, backup GPT at card end, userdata ext4 fills p7.
Offline regular-file assembly only; no device writes."""
import gzip, hashlib, json, struct, subprocess, sys, zlib
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
sys.path.insert(0, "/mnt/e/AI/H700Android/tools/public_build")
sys.path.insert(0, "/mnt/e/AI/H700Android/work/cubexx-build")
from audit_rgsp_single_card_boot import gpt, package, SECTOR
from common import sha, run
from pack import assemble
from assemble_cubexx_image import compact_gpt_public

W = Path("/root/cubexx-build"); INP = W/"inputs"; CARD = W/"card"
OUT = W/"card-full"; OUT.mkdir(exist_ok=True)
DISK_SIZE = 62534975488            # exact target card bytes (Get-Disk)
USERDATA_OFFSET = 10959716352
USERDATA_BYTES = DISK_SIZE - 1536 - USERDATA_OFFSET
UUID = "cd5e86c5-155f-5d96-8e90-12ec44abf24a"

def make_userdata(path):
    with path.open("xb") as f: f.truncate(USERDATA_BYTES)
    run(["mke2fs","-q","-F","-t","ext4","-b","4096","-I","256","-L","userdata",
         "-U",UUID,"-O","^orphan_file,^metadata_csum_seed,^metadata_csum,^64bit",
         "-E","root_owner=1000:1000,lazy_itable_init=1,lazy_journal_init=1",str(path)])
    run(["debugfs","-w","-R","set_inode_field / mode 040771",str(path)])
    ctx = path.parent/"ud.ctx"; ctx.write_bytes(b"u:object_r:system_data_file:s0\0")
    run(["debugfs","-w","-R",f"ea_set -f {ctx} / security.selinux",str(path)])
    return path

def main():
    prefix = bytearray((CARD/"prefix.raw").read_bytes())  # CubeXX prefix, compact GPT
    prefix, tail = compact_gpt_public(prefix, DISK_SIZE)
    parts = gpt(prefix)
    assert parts[-1]["name"]=="userdata"
    assert parts[-1]["end_exclusive"]==DISK_SIZE-1536, (parts[-1], DISK_SIZE)
    assert tail[1024:1032]==b"EFI PART"
    (OUT/"prefix.raw").write_bytes(prefix)
    (OUT/"backup_gpt.raw").write_bytes(tail)
    print("GPT full-card OK; p7 bytes =", USERDATA_BYTES)
    for p in parts:
        print(f"  p{p['number']} {p['name']:14s} {p['start']}..{p['end_exclusive']}")

    ud = make_userdata(OUT/"userdata.raw")
    raw = OUT/"ROC_OS_CubeXX_fullcard_adb.img"
    if raw.exists(): raw.unlink()
    ranges = [(0, OUT/"prefix.raw"),
              (222298112, INP/"system-adb.raw"),
              (8812232704, INP/"vendor.raw"),
              (USERDATA_OFFSET, ud),
              (DISK_SIZE-1536, OUT/"backup_gpt.raw")]
    print("assembling (readback verifies every range)...", flush=True)
    assemble(raw, DISK_SIZE, ranges)
    with raw.open("rb") as f:
        head = f.read(8*1024*1024)
        f.seek(DISK_SIZE-1536); backup = f.read(1536)
        f.seek(155189248); boot = f.read(64*1024*1024)
        f.seek(32800*SECTOR); toc = f.read(4*1024*1024)
        for off in (222298112, 8812232704, USERDATA_OFFSET):
            f.seek(off+1080); assert f.read(2)==b"\x53\xef", f"ext4 @{off}"
    gpt(head)
    bh = bytearray(backup[1024:1536]); assert bh[:8]==b"EFI PART"
    bsize,bcrc = struct.unpack_from("<II",bh,12); struct.pack_into("<I",bh,16,0)
    assert zlib.crc32(bh[:bsize])==bcrc
    assert head[8196:8204]==b"eGON.BT0"
    pkg = package(toc); assert {"u-boot","monitor","dtb"} <= {i["name"] for i in pkg["items"]}
    assert boot[:8]==b"ANDROID!"
    raw_hash = sha(raw)
    packed = raw.with_suffix(".img.gz")
    if packed.exists(): packed.unlink()
    print("compressing...", flush=True)
    with raw.open("rb") as src, packed.open("xb") as dst:
        with gzip.GzipFile(filename="",fileobj=dst,mode="wb",compresslevel=6,mtime=0) as z:
            while block := src.read(1024**2): z.write(block)
    with gzip.open(packed,"rb") as z:
        assert hashlib.file_digest(z,"sha256").hexdigest()==raw_hash
    receipt = {
        "status":"BUILT_PENDING_PHYSICAL_TEST","device":"RG CubeXX (H700,1GB,720x720)",
        "image":raw.name,"raw_bytes":DISK_SIZE,"raw_sha256":raw_hash,
        "gz_bytes":packed.stat().st_size,"gz_sha256":sha(packed),
        "fix":"full-card GPT (p7 fills card, backup at card end) + userdata fs fills p7 => first boot grow --check=0 --check-volume=0, NO --apply",
        "target_card_bytes":DISK_SIZE,
        "adb":"enabled (system /default.prop: ro.secure=0 ro.debuggable=1 ro.adb.secure=0 usb=adb tcp5555)",
        "boot_chain":"CubeXX stock boot0/TOC1/kernel/DTB + project ramdisk + enforcing",
        "partitions":parts,"userdata_bytes":USERDATA_BYTES,
        "physical_device_tested":False,"card_written":False,
    }
    (OUT/"result.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    print("ALL CHECKS PASSED")

if __name__=="__main__":
    main()