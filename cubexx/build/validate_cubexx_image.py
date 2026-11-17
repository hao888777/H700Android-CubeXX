#!/usr/bin/env python3
"""Independent offline validation of the assembled CubeXX debug image.
Read-only; checks GPT primary/backup agreement and the full boot chain."""
import hashlib, json, struct, sys, zlib
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
from audit_rgsp_single_card_boot import gpt, package, SECTOR

WORK = Path("/root/cubexx-build")
IMG = WORK/"card/ROC_OS_CubeXX_debug.img"
RECON = Path("/mnt/e/AI/H700Android/work/cubexx-recon")

def sha(b): return hashlib.sha256(b).hexdigest()

def main():
    size = IMG.stat().st_size
    with IMG.open("rb") as f:
        head = f.read(8*1024*1024)
        f.seek(size-1536); backup = f.read(1536)
        f.seek(155189248); boot = f.read(64*1024*1024)
        f.seek(32800*SECTOR); toc = f.read(4*1024*1024)
    # primary GPT
    parts = gpt(head)
    # backup GPT: entries(1024) + header(512)
    bh = bytearray(backup[1024:1536])
    assert bh[:8] == b"EFI PART", "backup header magic"
    bsize, bcrc = struct.unpack_from("<II", bh, 12)
    struct.pack_into("<I", bh, 16, 0)
    assert zlib.crc32(bh[:bsize]) == bcrc, "backup header CRC"
    blba, bcount, bentry, bentries_crc = struct.unpack_from("<QIII", bh, 72)
    bentries = backup[:bcount*bentry]
    assert zlib.crc32(bentries) == bentries_crc, "backup entries CRC"
    # compare primary vs backup entry arrays
    plba, pcount, pentry, pcrc = struct.unpack_from("<QIII", head[512:1024], 72)
    pentries = head[plba*512:plba*512+pcount*pentry]
    assert pentries == bentries, "primary/backup GPT entries differ"
    cur, alt, first, last = struct.unpack_from("<QQQQ", bh, 24)
    assert cur == size//512-1 and alt == 1 and last == size//512-4, "backup LBAs"
    # MBR protective size
    mbr_sectors = struct.unpack_from("<I", head, 458)[0]
    assert mbr_sectors == size//512-1, "MBR size"
    # boot0
    assert head[8196:8204] == b"eGON.BT0", "boot0 signature"
    boot0 = head[8192:8192+65536]
    # TOC1 @ LBA 32800
    pkg = package(toc)
    # boot.img
    assert boot[:8] == b"ANDROID!", "boot.img magic"
    ksize, kaddr, rsize, raddr, ssize, saddr, tags = struct.unpack_from("<7I", boot, 8)
    dt_size_raw = struct.unpack_from("<I", boot, 40)[0]
    page = struct.unpack_from("<I", boot, 36)[0]
    def align(x): return (x+page-1)//page*page
    koff = page
    roff = koff+align(ksize)
    soff = roff+align(rsize)
    doff = soff+align(ssize)
    kernel = boot[koff:koff+ksize]
    dtb = boot[doff:]
    dt_magic, dt_total = struct.unpack(">II", dtb[:8])
    assert dt_magic == 0xd00dfeed, "FDT magic"
    dtb = dtb[:dt_total]
    report = {
        "image_bytes": size,
        "gpt_primary_backup_match": True,
        "gpt_partitions": len(parts),
        "userdata_end_exclusive": parts[-1]["end_exclusive"],
        "backup_gpt_valid": True,
        "boot0_sha256": sha(boot0),
        "boot0_matches_stock": boot0 == (RECON/"boot0.bin").read_bytes(),
        "toc1_bytes": pkg["bytes"], "toc1_sha256": pkg["sha256"],
        "toc1_items": [i["name"] for i in pkg["items"]],
        "bootimg_kernel_bytes": ksize, "bootimg_kernel_sha256": sha(kernel),
        "kernel_matches_stock": kernel == (RECON/"bootimg_parts/kernel").read_bytes(),
        "bootimg_dtb_bytes": dt_total, "bootimg_dtb_sha256": sha(dtb),
        "dtb_matches_stock": dtb == (RECON/"bootimg_parts/dtb").read_bytes(),
        "bootimg_dt_size_raw_field": dt_size_raw,
        "cmdline": boot[64:64+512].split(b"\0")[0].decode(),
    }
    print(json.dumps(report, indent=2))
    assert report["boot0_matches_stock"] and report["kernel_matches_stock"] and report["dtb_matches_stock"]
    print("ALL OFFLINE CHECKS PASSED")

if __name__ == "__main__":
    main()