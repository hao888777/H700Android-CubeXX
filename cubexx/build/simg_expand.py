#!/usr/bin/env python3
"""Expand an Android sparse image to a raw image (offline, no simg2img)."""
import struct
import sys

def expand(src, dst):
    with open(src, "rb") as f:
        hdr = f.read(28)
        magic, maj, minr, fhs, chs, bs, tb, tc, ck = struct.unpack("<IHHHHIIII", hdr)
        if magic != 0xED26FF3A:
            raise ValueError("not a sparse image")
        f.seek(fhs)
        written = 0
        with open(dst, "wb") as o:
            for _ in range(tc):
                ch = f.read(chs)
                ctype, _res, csz, tsz = struct.unpack("<HHII", ch[:12])
                nbytes = csz * bs
                if ctype == 0xCAC1:  # raw
                    left = nbytes
                    while left > 0:
                        b = f.read(min(1 << 20, left))
                        o.write(b)
                        left -= len(b)
                elif ctype == 0xCAC2:  # fill
                    val = f.read(4)
                    block = val * (bs // 4)
                    for _ in range(csz):
                        o.write(block)
                elif ctype == 0xCAC3:  # dont care
                    o.seek(nbytes, 1)
                elif ctype == 0xCAC4:  # crc32
                    f.read(4)
                else:
                    raise ValueError(f"unknown chunk type {ctype:#x}")
                written += nbytes
            o.truncate(tb * bs)
    print(f"expanded {src} -> {dst}: {tb * bs} bytes ({written} written)")

if __name__ == "__main__":
    expand(sys.argv[1], sys.argv[2])