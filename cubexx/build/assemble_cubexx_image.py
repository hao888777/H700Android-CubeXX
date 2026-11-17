#!/usr/bin/env python3
"""Assemble a compact CubeXX debug card image: CubeXX prefix + 0.0.1 system/vendor
+ small empty userdata that auto-grows to fill the target card on first boot.
Offline regular-file assembly only; no device or card writes."""
import gzip, hashlib, json, struct, sys, zlib
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
sys.path.insert(0, "/mnt/e/AI/H700Android/tools/public_build")
from audit_rgsp_single_card_boot import gpt
from common import sha, copy_sparse
from pack import clean_userdata, assemble

WORK = Path("/root/cubexx-build")
INP = WORK/"inputs"
USERDATA_BYTES = 2 * 1024**3
USERDATA_OFFSET = 10959716352
SIZE = USERDATA_OFFSET + USERDATA_BYTES + 1536

def compact_gpt_public(head, size):
    result = bytearray(head)
    gpt(result)
    table = bytearray(result[1024:2048])
    struct.pack_into("<Q", table, 6*128+40, size//512-4)  # p7 userdata last LBA
    def header(current, alternate, array):
        h = bytearray(result[512:1024])
        struct.pack_into("<QQQQ", h, 24, current, alternate, 4, size//512-4)
        struct.pack_into("<QIII", h, 72, array, 8, 128, zlib.crc32(table))
        struct.pack_into("<I", h, 16, 0)
        struct.pack_into("<I", h, 16, zlib.crc32(h[:92]))
        return h
    primary = header(1, size//512-1, 2)
    tail = table + header(size//512-1, 1, size//512-3)
    result[512:1024] = primary
    result[1024:2048] = table
    struct.pack_into("<I", result, 458, size//512-1)
    return result, tail

def main():
    out = WORK/"card"; out.mkdir(exist_ok=True)
    prefix = bytearray((WORK/"cubexx-prefix.raw").read_bytes())
    prefix, tail = compact_gpt_public(prefix, SIZE)
    parts = gpt(prefix)
    assert parts[-1]["name"] == "userdata"
    assert parts[-1]["end_exclusive"] == SIZE - 1536, (parts[-1], SIZE)
    # validate backup GPT header
    assert tail[1024:1032] == b"EFI PART"
    (out/"backup_gpt.raw").write_bytes(tail)
    (out/"prefix.raw").write_bytes(prefix)
    print("GPT compact OK; partitions:")
    for p in parts:
        print(f"  p{p['number']} {p['name']:14s} {p['start']}..{p['end_exclusive']} ({(p['end_exclusive']-p['start'])/1048576:.0f}MiB)")

    userdata = clean_userdata(out/"userdata.raw",
        {"userdata_bytes": USERDATA_BYTES, "userdata_uuid": "cd5e86c5-155f-5d96-8e90-12ec44abf24a"},
        android_tools=None)

    raw = out/"ROC_OS_CubeXX_debug.img"
    ranges = [(0, out/"prefix.raw"),
              (222298112, INP/"system.raw"),
              (8812232704, INP/"vendor.raw"),
              (USERDATA_OFFSET, userdata),
              (SIZE-1536, out/"backup_gpt.raw")]
    assemble(raw, SIZE, ranges)
    # ext4 superblock readback
    with raw.open("rb") as f:
        for off in (222298112, 8812232704, USERDATA_OFFSET):
            f.seek(off+1080); assert f.read(2) == b"\x53\xef", f"ext4 missing @{off}"
    raw_hash = sha(raw)
    packed = raw.with_suffix(".img.gz")
    with raw.open("rb") as src, packed.open("xb") as dst:
        with gzip.GzipFile(filename="", fileobj=dst, mode="wb", compresslevel=6, mtime=0) as z:
            while block := src.read(1024**2):
                z.write(block)
    with gzip.open(packed, "rb") as z:
        assert hashlib.file_digest(z, "sha256").hexdigest() == raw_hash
    receipt = {
        "status": "BUILT_PENDING_PHYSICAL_TEST", "device": "RG CubeXX (H700, 1GB, 720x720)",
        "image": raw.name, "raw_bytes": SIZE, "raw_sha256": raw_hash,
        "gz_bytes": packed.stat().st_size, "gz_sha256": sha(packed),
        "partitions": parts, "userdata_bytes": USERDATA_BYTES,
        "auto_expand": "GPT p7 + ext4 resize on first boot (grow-userdata.sh)",
        "boot_chain": "CubeXX stock boot0/TOC1/kernel/DTB + project ramdisk + enforcing",
        "android_userspace": "0.0.1 RGSP system/vendor (display auto-framebuffer)",
        "prefix_sha256": sha(out/"prefix.raw"),
        "physical_device_tested": False, "card_written": False,
    }
    (out/"result.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))

if __name__ == "__main__":
    main()