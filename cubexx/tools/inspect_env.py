#!/usr/bin/env python3
import struct, re, zlib
from pathlib import Path
W = Path("/root/cubexx-build")
pre = (W/"inputs/prefix.raw").read_bytes()
ENV_OFF = 138412032
env = pre[ENV_OFF:ENV_OFF+131072]
# U-Boot env: 4-byte CRC32 then null-separated key=value (redundant env may have flags byte)
crc = struct.unpack_from("<I",env,0)[0]
body = env[4:4+131068]
calc = zlib.crc32(body) & 0xffffffff
print(f"env CRC stored={crc:#x} calc={calc:#x} match={crc==calc}")
# extract printable key=value pairs
txt = body.split(b"\0\0")[0]
pairs = [x.decode(errors="replace") for x in txt.split(b"\0") if b"=" in x]
print(f"=== {len(pairs)} env vars ===")
for p in pairs:
    print("  ", p)