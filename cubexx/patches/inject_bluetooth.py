#!/usr/bin/env python3
"""Inject the donor RTL8821CS Bluetooth stack into CubeXX system/vendor ext4.

Offline regular-file only; never touches a device or card. The donor components
(Orange Pi Zero 2 H616 Android 10) are 32-bit ARM and run in the 32-bit zygote of
the dual-ABI ROC OS system (ro.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi).
The RGSP vendor SELinux policy already carries the same hal_bluetooth_default
rules as the donor, so no policy change is needed; only files + labels + props.

CubeXX BT hardware (stock DTS): RTL8821CS combo, btlpm uart_index=1 (/dev/ttyS1),
bt_rst PG19 / bt_wake PG17 / bt_hostwake PG16, addr_mgt node for the BT MAC.
The stock kernel has sunxi-btlpm built in (no rtl_btlpm.ko insmod needed).
"""
import shutil
import subprocess
from pathlib import Path

W = Path("/root/cubexx-build")
INP = W / "inputs"
DONOR = Path("/mnt/d/AI/h700-bt/bt-donor")
WORK = W / "bt-inject"
WORK.mkdir(exist_ok=True)

SYS_LIB = "u:object_r:system_lib_file:s0"
SYS_FILE = "u:object_r:system_file:s0"
VENDOR_FILE = "u:object_r:vendor_file:s0"
VENDOR_CFG = "u:object_r:vendor_configs_file:s0"
HAL_EXEC = "u:object_r:hal_bluetooth_default_exec:s0"

_ctx_cache = {}


def ctxfile(ctx):
    if ctx not in _ctx_cache:
        p = WORK / ("ctx_%d" % len(_ctx_cache))
        p.write_bytes(ctx.encode() + b"\0")
        _ctx_cache[ctx] = p
    return _ctx_cache[ctx]


def dbg(img, cmds):
    cf = WORK / "cmds.txt"
    cf.write_text(cmds)
    r = subprocess.run(["debugfs", "-w", "-f", str(cf), str(img)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"debugfs failed on {img}:\n{r.stderr}\n{r.stdout}")
    return r


def put_file(lines, host, dest, mode, ctx, uid=0, gid=0):
    lines.append(f"write {host} {dest}")
    lines.append(f"set_inode_field {dest} mode {mode}")
    lines.append(f"set_inode_field {dest} uid {uid}")
    lines.append(f"set_inode_field {dest} gid {gid}")
    lines.append(f"ea_set -f {ctxfile(ctx)} {dest} security.selinux")


def put_dir(lines, dest, mode, ctx, uid=0, gid=0):
    lines.append(f"mkdir {dest}")
    lines.append(f"set_inode_field {dest} mode {mode}")
    lines.append(f"set_inode_field {dest} uid {uid}")
    lines.append(f"set_inode_field {dest} gid {gid}")
    lines.append(f"ea_set -f {ctxfile(ctx)} {dest} security.selinux")


def put_symlink(lines, dest, target, ctx):
    lines.append(f"symlink {dest} {target}")
    lines.append(f"set_inode_field {dest} mode 0120644")
    lines.append(f"ea_set -f {ctxfile(ctx)} {dest} security.selinux")


BT_FEATURE = """<?xml version="1.0" encoding="utf-8"?>
<permissions>
    <feature name="android.hardware.bluetooth" />
</permissions>
"""
BT_LE_FEATURE = """<?xml version="1.0" encoding="utf-8"?>
<permissions>
    <feature name="android.hardware.bluetooth_le" />
</permissions>
"""

# CubeXX-specific BT init: stock kernel has sunxi-btlpm built in, so do NOT
# insmod rtl_btlpm.ko (donor used a module). Only set up device/proc permissions.
CUBEXX_BT_RC = """# CubeXX RTL8821CS Bluetooth bring-up (sunxi-btlpm built into stock kernel).
on boot
    chmod 0660 /dev/ttyS1
    chown bluetooth net_bt_admin /dev/ttyS1
    chmod 0660 /sys/class/rfkill/rfkill0/state
    chmod 0660 /sys/class/rfkill/rfkill0/type
    chown bluetooth net_bt_admin /sys/class/rfkill/rfkill0/state
    chown bluetooth net_bt_admin /sys/class/rfkill/rfkill0/type
    write /sys/class/rfkill/rfkill0/state 0
    chown bluetooth net_bt_admin /sys/class/addr_mgt/addr_bt

on property:vendor.init.lpm.load=1
    chmod 0660 /proc/bluetooth/sleep/lpm
    chmod 0660 /proc/bluetooth/sleep/btwrite
    chmod 0660 /proc/bluetooth/sleep/btwake
    chown bluetooth net_bt_admin /proc/bluetooth/sleep/lpm
    chown bluetooth net_bt_admin /proc/bluetooth/sleep/btwrite
    chown bluetooth net_bt_admin /proc/bluetooth/sleep/btwake

on property:persist.vendor.overlay.bluetooth_vendor=realtek
    setprop vendor.init.lpm.load 1

on property:persist.vendor.overlay.bluetooth_vendor=realtek && property:sys.boot_completed=1
    setprop persist.vendor.bluetooth.rtkcoex true

on property:persist.vendor.overlay.bluetooth_vendor=realtek && property:sys.boot_completed=0
    setprop persist.vendor.bluetooth.rtkcoex false
"""

BT_VENDOR_CONF = """# UART device port where Bluetooth controller is attached
UartPort = /dev/ttyS1

# Firmware patch file location
FwPatchFilePath = /vendor/etc/firmware/

# Firmware name
# Do not specify FwPatchFileName = xxx.hcd to enable FwAutoDetection
# FwPatchFileName = bcm4345c5.hcd
"""


def build_system():
    src = INP / "system-force.raw"
    dst = INP / "system-bt.raw"
    print("copying system-force.raw -> system-bt.raw ...", flush=True)
    shutil.copyfile(src, dst)
    L = []
    # 32-bit BT system libraries
    for f in ["libbluetooth.so", "libbluetooth-binder.so", "libbluetooth_jni.so",
              "android.hardware.bluetooth@1.0.so",
              "android.hardware.bluetooth.a2dp@1.0.so",
              "android.hardware.bluetooth.audio@2.0.so"]:
        put_file(L, DONOR / "system/lib" / f, f"/system/lib/{f}", "0100644", SYS_LIB)
    # Bluetooth system app + JNI symlink
    put_dir(L, "/system/app/Bluetooth", "040755", SYS_FILE)
    put_file(L, DONOR / "system/app/Bluetooth/Bluetooth.apk",
             "/system/app/Bluetooth/Bluetooth.apk", "0100644", SYS_FILE)
    put_dir(L, "/system/app/Bluetooth/lib", "040755", SYS_FILE)
    put_dir(L, "/system/app/Bluetooth/lib/arm", "040755", SYS_FILE)
    put_symlink(L, "/system/app/Bluetooth/lib/arm/libbluetooth_jni.so",
                "/system/lib/libbluetooth_jni.so", SYS_LIB)
    # BT stack configs
    put_dir(L, "/system/etc/bluetooth", "040755", SYS_FILE)
    for f in ["bt_did.conf", "bt_stack.conf"]:
        put_file(L, DONOR / "system/etc/bluetooth" / f,
                 f"/system/etc/bluetooth/{f}", "0100644", SYS_FILE)
    # feature declarations
    feat = WORK / "android.hardware.bluetooth.xml"
    feat.write_text(BT_FEATURE)
    featle = WORK / "android.hardware.bluetooth_le.xml"
    featle.write_text(BT_LE_FEATURE)
    put_file(L, feat, "/system/etc/permissions/android.hardware.bluetooth.xml",
             "0100644", SYS_FILE)
    put_file(L, featle, "/system/etc/permissions/android.hardware.bluetooth_le.xml",
             "0100644", SYS_FILE)
    dbg(dst, "\n".join(L) + "\n")
    # readback verify
    out = subprocess.run(["debugfs", "-R", "cat /system/lib/libbluetooth.so", str(dst)],
                         capture_output=True).stdout
    assert out == (DONOR / "system/lib/libbluetooth.so").read_bytes(), "libbluetooth readback"
    out = subprocess.run(["debugfs", "-R", "cat /system/app/Bluetooth/Bluetooth.apk", str(dst)],
                         capture_output=True).stdout
    assert out == (DONOR / "system/app/Bluetooth/Bluetooth.apk").read_bytes(), "apk readback"
    print("system-bt.raw injected + verified", flush=True)
    return dst


def build_vendor():
    src = INP / "vendor.raw"
    dst = INP / "vendor-bt.raw"
    print("copying vendor.raw -> vendor-bt.raw ...", flush=True)
    shutil.copyfile(src, dst)
    L = []
    put_file(L, DONOR / "vendor/bin/hw/android.hardware.bluetooth@1.0-service",
             "/bin/hw/android.hardware.bluetooth@1.0-service", "0100755", HAL_EXEC, gid=2000)
    put_file(L, DONOR / "vendor/lib/hw/android.hardware.bluetooth@1.0-impl.so",
             "/lib/hw/android.hardware.bluetooth@1.0-impl.so", "0100644", VENDOR_FILE)
    put_file(L, DONOR / "vendor/lib/libbt-realtek.so",
             "/lib/libbt-realtek.so", "0100644", VENDOR_FILE)
    put_dir(L, "/etc/bluetooth", "040755", VENDOR_CFG)
    conf = WORK / "bt_vendor.conf"
    conf.write_text(BT_VENDOR_CONF)
    put_file(L, conf, "/etc/bluetooth/bt_vendor.conf", "0100644", VENDOR_CFG)
    put_dir(L, "/etc/firmware", "040755", VENDOR_CFG)
    for f in ["rtl8821cs_fw", "rtl8821cs_config", "rtl8821c_fw", "rtl8821c_config"]:
        put_file(L, DONOR / "vendor/etc/firmware" / f,
                 f"/etc/firmware/{f}", "0100644", VENDOR_CFG)
    put_file(L, DONOR / "vendor/etc/init/android.hardware.bluetooth@1.0-service.rc",
             "/etc/init/android.hardware.bluetooth@1.0-service.rc", "0100644", VENDOR_CFG)
    rc = WORK / "init.bluetooth.cubexx.rc"
    rc.write_text(CUBEXX_BT_RC)
    put_file(L, rc, "/etc/init/init.bluetooth.cubexx.rc", "0100644", VENDOR_CFG)
    # append BT properties to vendor build.prop (preserve existing content)
    bp = subprocess.run(["debugfs", "-R", "cat /build.prop", str(dst)],
                        capture_output=True).stdout.decode()
    add = ""
    for line in ["persist.vendor.bluetooth_port=/dev/ttyS1",
                 "ro.bt.bdaddr_path=/sys/class/addr_mgt/addr_bt",
                 "persist.vendor.overlay.bluetooth_vendor=realtek"]:
        key = line.split("=")[0]
        if key not in bp:
            add += line + "\n"
    if add:
        newbp = bp.rstrip("\n") + "\n" + add
        bpf = WORK / "vendor_build.prop"
        bpf.write_text(newbp)
        L.append("rm /build.prop")
        put_file(L, bpf, "/build.prop", "0100644", VENDOR_CFG)
    dbg(dst, "\n".join(L) + "\n")
    out = subprocess.run(["debugfs", "-R", "cat /lib/libbt-realtek.so", str(dst)],
                         capture_output=True).stdout
    assert out == (DONOR / "vendor/lib/libbt-realtek.so").read_bytes(), "libbt readback"
    out = subprocess.run(["debugfs", "-R", "cat /etc/firmware/rtl8821cs_fw", str(dst)],
                         capture_output=True).stdout
    assert out == (DONOR / "vendor/etc/firmware/rtl8821cs_fw").read_bytes(), "fw readback"
    print("vendor-bt.raw injected + verified", flush=True)
    return dst


if __name__ == "__main__":
    s = build_system()
    v = build_vendor()
    print("DONE", s, v)