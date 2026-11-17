#!/usr/bin/env python3
"""Build a CubeXX hardware prefix from the 0.0.1 RGSP prefix by swapping the
stock-extracted CubeXX boot0 / TOC1(U-Boot) / boot.img kernel+DTB, retaining the
project ramdisk, enforcing cmdline, GPT, env and boot-resource. Offline only."""
import argparse, hashlib, struct, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/AI/H700Android/tools")
from android_bootimg import read_header, component_offsets, pack as pack_boot
from audit_rgsp_single_card_boot import gpt, package

RECON = Path("/mnt/e/AI/H700Android/work/cubexx-recon")
INP = Path("/root/cubexx-build/inputs")
WORK = Path("/root/cubexx-build")

def sha(b): return hashlib.sha256(b).hexdigest()

def main():
    prefix = bytearray((INP/"prefix.raw").read_bytes())
    assert len(prefix) == 222298112
    gpt_before = gpt(prefix)

    # 1. boot0 @ 8KB (64KB)
    boot0 = (RECON/"boot0.bin").read_bytes()
    assert boot0[4:12] == b"eGON.BT0" and len(boot0) == 65536
    prefix[8192:8192+65536] = boot0

    # 2. TOC1 @ LBA 32800 (16MB+0x4000), 1310720 bytes
    slot = (RECON/"uboot_slot.bin").read_bytes()
    toc1 = slot[0x4000:0x4000+1310720]
    pkg = package(toc1)  # validates magic + checksum
    assert pkg["bytes"] == 1310720
    assert {i["name"] for i in pkg["items"]} == {"u-boot","monitor","dtbo","dtb"}
    prefix[16793600:16793600+1310720] = toc1

    # 3. boot.img: template=0.0.1 (enforcing cmdline + project ramdisk),
    #    override kernel+DTB with CubeXX stock-extracted components.
    kernel = (RECON/"bootimg_parts/kernel").read_bytes()
    dtb = (RECON/"bootimg_parts/dtb").read_bytes()
    assert kernel[0x38:0x3c] == b"ARMd" and dtb[:4] == b"\xd0\x0d\xfe\xed"
    tmpl = WORK/"boot-template.raw"
    tmpl.write_bytes((INP/"boot.raw").read_bytes())
    out_boot = WORK/"cubexx-boot.img"
    pack_boot(argparse.Namespace(template=str(tmpl), out=str(out_boot),
              kernel=str(RECON/"bootimg_parts/kernel"), ramdisk=None,
              second=None, dtb=str(RECON/"bootimg_parts/dtb")))
    newboot = out_boot.read_bytes()
    _, h = read_header(out_boot)
    off = component_offsets(h)
    # verify identity: CubeXX kernel + DTB, project ramdisk retained
    assert newboot[off["kernel"]:off["kernel"]+h["kernel_size"]] == kernel
    dsz = h.get("dt_size_detected", h["dt_size"])
    assert newboot[off["dtb"]:off["dtb"]+dsz] == dtb
    _, th = read_header(tmpl)
    toff = component_offsets(th)
    proj_ramdisk = (INP/"boot.raw").read_bytes()[toff["ramdisk"]:toff["ramdisk"]+th["ramdisk_size"]]
    assert newboot[off["ramdisk"]:off["ramdisk"]+h["ramdisk_size"]] == proj_ramdisk
    assert "enforcing" in h["cmdline"] and "permissive" not in h["cmdline"]
    assert len(newboot) == 67108864
    prefix[155189248:155189248+67108864] = newboot

    # 4. GPT must be unchanged
    assert gpt(prefix) == gpt_before, "GPT changed"
    assert package(prefix[16793600:])["sha256"] == pkg["sha256"]

    dest = WORK/"cubexx-prefix.raw"
    dest.write_bytes(prefix)
    report = {
        "prefix_bytes": len(prefix), "prefix_sha256": sha(prefix),
        "boot0_sha256": sha(boot0),
        "toc1": {"offset":16793600,"bytes":pkg["bytes"],"sha256":pkg["sha256"],
                 "items":{i["name"]:{"bytes":i["bytes"],"sha256":i["sha256"]} for i in pkg["items"]}},
        "boot_img": {"offset":155189248,"bytes":len(newboot),"sha256":sha(newboot),
                     "kernel_size":h["kernel_size"],"kernel_sha256":sha(kernel),
                     "dtb_size":dsz,"dtb_sha256":sha(dtb),
                     "ramdisk_size":h["ramdisk_size"],"ramdisk_sha256":sha(proj_ramdisk),
                     "cmdline":h["cmdline"]},
        "gpt": gpt_before,
        "retained":"project ramdisk + enforcing cmdline + GPT + env(p3) + boot-resource(p2)",
    }
    import json
    (WORK/"cubexx-prefix.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__ == "__main__":
    main()