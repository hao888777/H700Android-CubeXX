#!/usr/bin/env python3
"""Re-assemble the compact CubeXX debug image with early-boot ADB enabled.
Reuses the validated prefix/userdata/backup_gpt; swaps in system-adb.raw."""
import gzip, hashlib, json, struct, sys, zlib
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
sys.path.insert(0, "/mnt/e/AI/H700Android/tools/public_build")
from audit_rgsp_single_card_boot import gpt, package, SECTOR
from common import sha
from pack import assemble

W = Path("/root/cubexx-build"); INP = W/"inputs"; CARD = W/"card"
OUT = W/"card-adb"; OUT.mkdir(exist_ok=True)
USERDATA_OFFSET = 10959716352
SIZE = 13107201536

def main():
    raw = OUT/"ROC_OS_CubeXX_debug_adb.img"
    if raw.exists(): raw.unlink()
    ranges = [(0, CARD/"prefix.raw"),
              (222298112, INP/"system-adb.raw"),
              (8812232704, INP/"vendor.raw"),
              (USERDATA_OFFSET, CARD/"userdata.raw"),
              (SIZE-1536, CARD/"backup_gpt.raw")]
    assemble(raw, SIZE, ranges)
    with raw.open("rb") as f:
        head = f.read(8*1024*1024)
        f.seek(SIZE-1536); backup = f.read(1536)
        f.seek(155189248); boot = f.read(64*1024*1024)
        f.seek(32800*SECTOR); toc = f.read(4*1024*1024)
        for off in (222298112, 8812232704, USERDATA_OFFSET):
            f.seek(off+1080); assert f.read(2)==b"\x53\xef", f"ext4 @{off}"
    parts = gpt(head)
    assert parts[-1]["name"]=="userdata" and parts[-1]["end_exclusive"]==SIZE-1536
    bh = bytearray(backup[1024:1536]); assert bh[:8]==b"EFI PART"
    bsize,bcrc = struct.unpack_from("<II",bh,12); struct.pack_into("<I",bh,16,0)
    assert zlib.crc32(bh[:bsize])==bcrc
    assert head[8196:8204]==b"eGON.BT0"
    pkg = package(toc); assert {"u-boot","monitor","dtb"} <= {i["name"] for i in pkg["items"]}
    assert boot[:8]==b"ANDROID!"
    raw_hash = sha(raw)
    packed = raw.with_suffix(".img.gz")
    if packed.exists(): packed.unlink()
    with raw.open("rb") as src, packed.open("xb") as dst:
        with gzip.GzipFile(filename="",fileobj=dst,mode="wb",compresslevel=6,mtime=0) as z:
            while block := src.read(1024**2): z.write(block)
    with gzip.open(packed,"rb") as z:
        assert hashlib.file_digest(z,"sha256").hexdigest()==raw_hash
    receipt = {
        "status":"BUILT_PENDING_PHYSICAL_TEST","device":"RG CubeXX (H700,1GB,720x720)",
        "image":raw.name,"raw_bytes":SIZE,"raw_sha256":raw_hash,
        "gz_bytes":packed.stat().st_size,"gz_sha256":sha(packed),
        "change_vs_prev":"system /default.prop: ro.secure=0 ro.debuggable=1 ro.adb.secure=0 persist.sys.usb.config=adb + tcp 5555",
        "adb":{"usb":"adb (unauthenticated, root)","tcp":"5555 (once network up)","start":"on boot via init.usb.rc, independent of framework"},
        "boot_chain":"CubeXX stock boot0/TOC1/kernel/DTB + project ramdisk + enforcing (unchanged)",
        "partitions":parts,"physical_device_tested":False,"card_written":False,
    }
    (OUT/"result.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    print("ALL CHECKS PASSED")

if __name__=="__main__":
    main()