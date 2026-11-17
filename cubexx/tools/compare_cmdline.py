#!/usr/bin/env python3
import struct
from pathlib import Path
def cmdline(p):
    b = Path(p).read_bytes()
    if b[:8]!=b"ANDROID!": return f"{p}: not android boot"
    page = struct.unpack_from("<I",b,36)[0]
    name = b[48:64].split(b"\0")[0].decode(errors="replace")
    cl = b[64:64+512].split(b"\0")[0].decode(errors="replace")
    extra = b[608:608+1024].split(b"\0")[0].decode(errors="replace")
    ksize,rsize,ssize = struct.unpack_from("<III",b,8)[0],struct.unpack_from("<I",b,16)[0],struct.unpack_from("<I",b,24)[0]
    dt = struct.unpack_from("<I",b,40)[0]
    return f"{p}\n  page={page} name={name!r}\n  kernel={ksize} ramdisk={rsize} second={ssize} dt_raw={dt}\n  cmdline={cl!r}\n  extra={extra!r}"
for p in ["/mnt/e/AI/H700Android/work/cubexx-recon/boot.img",
          "/root/cubexx-build/inputs/boot.raw",
          "/root/cubexx-build/cubexx-boot.img"]:
    print(cmdline(p)); print()