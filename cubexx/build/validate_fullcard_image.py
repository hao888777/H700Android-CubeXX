#!/usr/bin/env python3
"""Independent offline validation of the full-card CubeXX fix image.
Read-only. Checks GPT primary/backup agreement at the EXACT card end, the full
stock boot chain, and that the userdata ext4 fills p7 (first boot needs no grow)."""
import hashlib, json, struct, sys, uuid, zlib
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
from audit_rgsp_single_card_boot import gpt, package, SECTOR

WORK = Path("/root/cubexx-build")
IMG = WORK/"card-full/ROC_OS_CubeXX_fullcard_adb.img"
RECON = Path("/mnt/e/AI/H700Android/work/cubexx-recon")
DISK_SIZE = 62534975488
USERDATA_OFFSET = 10959716352
UUID = "cd5e86c5-155f-5d96-8e90-12ec44abf24a"

def sha(b): return hashlib.sha256(b).hexdigest()

def main():
    size = IMG.stat().st_size
    assert size == DISK_SIZE, (size, DISK_SIZE)
    with IMG.open("rb") as f:
        head = f.read(8*1024*1024)
        f.seek(size-1536); backup = f.read(1536)
        f.seek(155189248); boot = f.read(64*1024*1024)
        f.seek(32800*SECTOR); toc = f.read(4*1024*1024)
        f.seek(USERDATA_OFFSET+1024); sb = f.read(256)
    parts = gpt(head)
    bh = bytearray(backup[1024:1536])
    assert bh[:8] == b"EFI PART", "backup header magic"
    bsize, bcrc = struct.unpack_from("<II", bh, 12)
    struct.pack_into("<I", bh, 16, 0)
    assert zlib.crc32(bh[:bsize]) == bcrc, "backup header CRC"
    blba, bcount, bentry, bentries_crc = struct.unpack_from("<QIII", bh, 72)
    bentries = backup[:bcount*bentry]
    assert zlib.crc32(bentries) == bentries_crc, "backup entries CRC"
    plba, pcount, pentry, pcrc = struct.unpack_from("<QIII", head[512:1024], 72)
    pentries = head[plba*512:plba*512+pcount*pentry]
    assert pentries == bentries, "primary/backup GPT entries differ"
    cur, alt, first, last = struct.unpack_from("<QQQQ", bh, 24)
    assert cur == size//512-1 and alt == 1 and last == size//512-4, "backup LBAs"
    assert struct.unpack_from("<I", head, 458)[0] == size//512-1, "MBR size"
    assert parts[-1]["name"] == "userdata"
    p7bytes = parts[-1]["end_exclusive"] - parts[-1]["start"]
    assert parts[-1]["end_exclusive"] == size-1536, "p7 must end at card-1536"
    # userdata ext4 must fill p7 so grow --check-volume returns 0.
    # grow_gpt.c compares blocks == bytes/block with INTEGER (floor) division,
    # so the fs fills floor(p7bytes/block) blocks; a sub-block tail is unusable.
    assert sb[56:58] == b"\x53\xef", "ext4 magic"
    blocks = struct.unpack_from("<I", sb, 4)[0]
    logbs = struct.unpack_from("<I", sb, 24)[0]
    bs = 1024 << logbs
    if struct.unpack_from("<I", sb, 96)[0] & 0x80:
        blocks |= struct.unpack_from("<I", sb, 336)[0] << 32
    fsbytes = blocks * bs
    target_blocks = p7bytes // bs
    fsuuid = str(uuid.UUID(bytes=bytes(sb[104:120])))
    assert blocks <= target_blocks, "filesystem larger than partition"
    assert blocks == target_blocks, (blocks, target_blocks)
    assert fsuuid == UUID, (fsuuid, UUID)
    # boot chain
    assert head[8196:8204] == b"eGON.BT0", "boot0 signature"
    boot0 = head[8192:8192+65536]
    pkg = package(toc)
    assert boot[:8] == b"ANDROID!", "boot.img magic"
    ksize, kaddr, rsize, raddr, ssize, saddr, tags = struct.unpack_from("<7I", boot, 8)
    page = struct.unpack_from("<I", boot, 36)[0]
    def align(x): return (x+page-1)//page*page
    koff = page; roff = koff+align(ksize); soff = roff+align(rsize); doff = soff+align(ssize)
    kernel = boot[koff:koff+ksize]
    dtb = boot[doff:]
    dt_magic, dt_total = struct.unpack(">II", dtb[:8])
    assert dt_magic == 0xd00dfeed, "FDT magic"
    dtb = dtb[:dt_total]
    report = {
        "image_bytes": size,
        "gpt_primary_backup_match": True,
        "gpt_partitions": len(parts),
        "userdata_start": parts[-1]["start"],
        "userdata_end_exclusive": parts[-1]["end_exclusive"],
        "userdata_bytes": p7bytes,
        "userdata_ext4_bytes": fsbytes,
        "userdata_ext4_blocks": blocks,
        "userdata_target_blocks_floor": target_blocks,
        "userdata_ext4_fills_p7": blocks == target_blocks,
        "userdata_uuid": fsuuid,
        "backup_gpt_at_card_end": True,
        "boot0_matches_stock": boot0 == (RECON/"boot0.bin").read_bytes(),
        "toc1_items": [i["name"] for i in pkg["items"]],
        "kernel_matches_stock": kernel == (RECON/"bootimg_parts/kernel").read_bytes(),
        "dtb_matches_stock": dtb == (RECON/"bootimg_parts/dtb").read_bytes(),
        "cmdline": boot[64:64+512].split(b"\0")[0].decode(),
        "first_boot_grow_check_expected": 0,
        "first_boot_grow_check_volume_expected": 0,
    }
    print(json.dumps(report, indent=2))
    assert report["boot0_matches_stock"] and report["kernel_matches_stock"] and report["dtb_matches_stock"]
    print("ALL OFFLINE CHECKS PASSED")

if __name__ == "__main__":
    main()