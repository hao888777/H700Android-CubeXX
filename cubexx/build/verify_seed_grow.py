#!/usr/bin/env python3
"""Offline verification of the seed auto-expand GPT flow using the REAL grow
binary (compiled from tools/source64/storage/grow_gpt.c) in --image-test fixture
mode. Simulates cards of several sizes, flashes the seed GPT, and confirms:
  - 32GB (== seed): --check=0 (no grow needed)
  - 64GB / 128GB  : --check=4 -> --apply=0 -> --check=0, p7 fills the card,
                    backup GPT relocated to card end.
No device writes; regular sparse files only.
"""
import json, struct, subprocess, sys
from pathlib import Path

W = Path("/root/cubexx-build")
SRC = Path("/mnt/e/AI/H700Android/tools/source64/storage")
IDINC = Path("/mnt/e/AI/H700Android/build-support/public/overlay/device/roc/roc_os_source64/Storage")
SEED = W / "card-seed-debug"
SEED_BYTES = 32434554368
GROW = W / "grow_gpt_test"


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def p7_last_lba(path):
    with open(path, "rb") as f:
        f.seek(1024 + 6 * 128 + 40)
        return struct.unpack("<Q", f.read(8))[0]


def main():
    # Compile the real grow binary fresh from frozen source.
    rc, out = sh(["gcc", "-O2", "-Wall", "-I", str(SRC), "-I", str(IDINC),
                  "-o", str(GROW), str(SRC / "grow_gpt.c")])
    assert rc == 0, out
    prefix = (SEED / "prefix.raw").read_bytes()
    backup = (SEED / "backup_gpt.raw").read_bytes()
    assert len(prefix) >= 2048 and len(backup) == 1536

    targets = [("32GB_seed", SEED_BYTES), ("64GB", 62534975488), ("128GB", 137438953472)]
    results = []
    for label, size in targets:
        sim = W / f"sim_{label}.img"
        with open(sim, "wb") as f:
            f.truncate(size)
            f.seek(0); f.write(prefix[:2048])
            if size == SEED_BYTES:
                f.seek(size - 1536); f.write(backup)
        rc1, o1 = sh([str(GROW), "--check", str(sim), "--image-test"])
        applied = None
        if rc1 == 4:
            rca, oa = sh([str(GROW), "--apply", str(sim), "--image-test"])
            rc2, o2 = sh([str(GROW), "--check", str(sim), "--image-test"])
            applied = rca
        else:
            rc2, o2 = rc1, o1
        last = p7_last_lba(sim)
        expect_last = size // 512 - 4
        ok = (rc2 == 0 and last == expect_last and (applied in (None, 0)))
        results.append({"card": label, "bytes": size, "check_initial": rc1,
                        "apply": applied, "check_final": rc2,
                        "p7_last_lba": last, "expected_last_lba": expect_last,
                        "pass": ok})
        print(f"[{label}] check={rc1} apply={applied} check_final={rc2} "
              f"p7_last={last} expect={expect_last} {'OK' if ok else 'FAIL'}")
        if rc1 == 4:
            print("   apply out:", oa.replace("\n", " | "))
        sim.unlink()
    assert all(r["pass"] for r in results), results
    (W / "seed-grow-verify.json").write_text(json.dumps(results, indent=2))
    print("SEED AUTO-EXPAND VERIFIED ON 32/64/128GB")


if __name__ == "__main__":
    main()