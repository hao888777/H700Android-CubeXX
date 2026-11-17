# CubeXX 适配（RG CubeXX · H700 · Android 10）

本目录是 **RG CubeXX** 掌机适配成果的自包含合集，作为上游 H700 多机型项目的**增量补充**合并而来。
上游原有内容（十二机型启动选择、Navigation18、Test10 封装链等）保持不变；本目录只新增 CubeXX 专属的方案、修复代码与证据。

- 设备：RG CubeXX，Allwinner H700/H616（sun50iw9p1），**1GB RAM**，**720×720 方屏**，无触摸屏。
- 系统：ARM64 Android 10 ROC OS（user 构建，Android Go 低内存路径，保留 ARM32 应用运行能力）。
- 适配策略：**复用原厂 CubeXX 启动链**（boot0 + U-Boot/TOC1 + 原厂 kernel/DTB），叠加本项目 Android system/vendor 与 ramdisk，**不重编内核**。
- 交付方式：**预构建覆盖（prebuilt-overlay）**——用 debugfs 把修复打进 ext4，再 dd 进整卡 raw、gzip 出包；**不是从源码一键重编**。作者只生成镜像，由使用者用 Rufus 刷到**另一张** TF 卡插机测试。

> 状态摘要：启动链、摇杆、相机看门狗、内核日志默认关闭、蓝牙崩溃环移除、字体崩溃（应用安装）等修复已进入镜像并经实机验证；完整蓝牙、亮度下限、背光热键、系统振动 HAL、原厂桌面字体崩溃等项**搁置**（见下文）。

---

## 镜像下载（已编译）

CubeXX 已编译整卡镜像（`.img.gz`），用 Rufus 刷到**另一张** ≥32GB（建议 64GB）TF 卡，TF2 留空，核对目标卡。两个网盘提取码均为 `cube`：

- 123 云盘：<https://1820052963.share.123pan.cn/123pan/y5lkjv-SgVUh?pwd=cube#>
- 百度网盘：<https://pan.baidu.com/s/1yNzMmNZxrQ-jYIQ1ofiG6A?pwd=cube>

下载后请核对文件名与 SHA256 再刷入；当前构建身份、分区与校验哈希见下文「镜像构建流程」及 `evidence/camfix-result.json`。首启数据区扩容需等待，后续启动复用。

---

## 1. 硬件要点（实测/DTS 核对）

### 输入：event1 `ANBERNIC-keys`
原厂 `gpio-keys-polled`，bus=0x0019 vendor=0x0001 product=0x0001 version=0x0100，带 `FF_RUMBLE`/`FF_PERIODIC` 等力反馈能力（振动电机挂在此设备）。

数字键（Linux code → Android，见 `device/ANBERNIC-keys.kl`）：

| code | 按键 | Android | code | 按键 | Android |
| --- | --- | --- | --- | --- | --- |
| 304 | A | ENTER（兼解锁） | 311 | START | BUTTON_START |
| 305 | B | BUTTON_B | 312 | MODE | BUTTON_MODE（回落 HOME） |
| 306 | X | BUTTON_X | 313 | L3 | BUTTON_THUMBL |
| 307 | Y | BUTTON_Y | 314 | L2 | BUTTON_L2 |
| 308 | L1 | BUTTON_L1 | 315 | R2 | BUTTON_R2 |
| 309 | R1 | BUTTON_R1 | 316 | R3 | BUTTON_THUMBR |
| 310 | SELECT | BUTTON_SELECT | 114/115 | VOL−/VOL+ | VOLUME_DOWN/UP |

摇杆轴（**无 ABS_X/Y**，量程 −4096..4096）：

| Linux 轴 | 物理 | Android 轴 |
| --- | --- | --- |
| ABS_Z (0x02) | 左摇杆 水平 | AXIS_X |
| ABS_RX (0x03) | 左摇杆 垂直 | AXIS_Y |
| ABS_RY (0x04) | 右摇杆 水平 | AXIS_Z |
| ABS_RZ (0x05) | 右摇杆 垂直 | AXIS_RZ |
| HAT0X/Y (0x10/0x11) | 十字键 | HAT_X/HAT_Y |

左摇杆=Z/RX，右摇杆=RY/RZ。四轴已在实机确认移动，使用者已验证左右摇杆端到端可用（无需反转）。`KEY_ESC(1)` 与 Menu 释放脉冲 `KEY_GOTO(0x162)` 故意不映射。

### 背光
PWM 背光（`pwm_bl`）。亮度框架下限修改需 platform 密钥（搁置）；背光热键/程序控制待做（task #17）。

### 整卡分区布局（seed，raw 32,434,554,368 字节）

| # | 名称 | 起始字节 | 结束（不含） |
| --- | --- | --- | --- |
| 1 | special | 37,748,736 | 104,857,600 |
| 2 | boot-resource | 104,857,600 | 138,412,032 |
| 3 | env | 138,412,032 | 155,189,248 |
| 4 | boot | 155,189,248 | 222,298,112 |
| 5 | system | 222,298,112 | 8,812,232,704 |
| 6 | vendor | 8,812,232,704 | 10,959,716,352 |
| 7 | userdata | 10,959,716,352 | 32,434,552,832 |

prefix（p1–p4 启动链）@0，长 222,298,112 字节；备份 GPT @ disk−1536。首启 `grow --apply` 把 GPT 扩到卡容量并重启，再 `resize2fs` 填满 p7（任意 ≥32GB 卡）。

---

## 2. 已完成修复（含证据与对应代码）

| 修复 | 目标 | 代码/证据 | 状态 |
| --- | --- | --- | --- |
| 启动链复用 | boot0/TOC1/kernel/DTB | `build/build_cubexx_prefix.py`、`build/build_debug_ramdisk.py` | 原厂启动链 + 项目 ramdisk + enforcing，已启动 |
| 摇杆 keylayout | `/system/usr/keylayout/*.kl` | `device/ANBERNIC-keys.kl` | 四轴+15 键 DTS 核对，实机端到端验证 |
| 相机看门狗 | `/system/etc/init/cameraserver.rc` | `patches/reenable_cameraserver.py` | 撤销 `disabled`，消除 system_server 看门狗软重启环 |
| 内核日志默认关闭 | `build.prop` + `logd-kernel-optin.rc` | `patches/modify_logd_optin.py` | 移除 `ro.logd.kernel`，默认 OFF；`setprop debug.logd.kernel 1` 当次开启 |
| 蓝牙崩溃环移除 | `/system/app/Bluetooth/*` + feature xml | `patches/remove_bluetooth.py` | 移除未平台签名的 donor Bluetooth.apk，消除开机崩溃环 |
| 字体崩溃（应用安装） | `/system/lib64/libhwui.so` | trampoline（见下，无独立脚本） | 修复 null-typeface ASSERT 导致的应用安装弹退 |
| userdata 自动扩容 | GPT + p7 | `build/assemble_card_image.py`（grow） | 首启自动扩到卡容量 |
| ADB 使能 | `build.prop`/init | `build/modify_system_adb.py` | `ro.secure=0 ro.debuggable=1 ro.adb.secure=0`，usb=adb + tcp5555 |
| 内存服务裁剪 | init.rc | `patches/patch_mem_services.py` | incidentd/mediametrics/statsd 保持禁用 |
| 游戏振动（input FF） | event1 力反馈 | `tools/fftest.c`、`tools/ffvib/` | 电机物理确认震动，游戏 rumble 可用 |

### 相机看门狗根因（重要陷阱）
禁用 cameraserver 后，system_server 的 `UsbCameraDeviceManagerObserver$BootCompletedReceiver` 在**主线程**调用 `Camera.getNumberOfCameras` → `BpServiceManager::getService(media.camera)` 因服务从未发布而 usleep 自旋 → Watchdog 杀 system_server → 反复软重启（dropbox `system_server_watchdog` ×4，同一相机栈）。本机无摄像头，cameraserver 正常运行（`init.svc.cameraserver=running`、`media.camera` 可找到、0 摄像头），class-main 自启使其在 BOOT_COMPLETED 前就绪。代价约 5.3M PSS，远小于看门狗环。**修复后实测 0 条 watchdog、启动稳定。**

### 字体 trampoline（task #19，无独立脚本，原为内联施加）
在 `/system/lib64/libhwui.so` 文件偏移 **0x2f4fa4**（=3,100,580）处植入 28 字节蹦床，先调 `setRobotoTypefaceForTest`(0x36ef60) 再重载 `gDefaultTypeface`(0x64a820)，修复 null-typeface ASSERT。system .so 未签名，**无需 platform 密钥**。
蹦床指令字（小端序按字排列）：
```
a9bf7bfd 9401e7ee a8c17bfd d0001aaa f9441149 aa1f03e1 17ffffbe
```
对应设备读回字节：`fd7bbfa9 eee70194 fd7bc1a8 aa1a00d0 491144f9 e1031faa beffff17`。
复现方法：从 system.raw 用 debugfs 取出 libhwui.so，在上述偏移写入这 28 字节后 `rm`+`write` 回（debugfs 不覆盖，须先 rm；参考 `patches/` 内其它脚本的 debugfs 模式）。
**局限**：此蹦床未覆盖 `Typeface::resolveDefault` 早路径，原厂 launcher3 仍在开机时因 `gDefaultTypeface` 为空 SIGABRT 崩溃环（task #25，已搁置，见下）。应用安装路径已修复。

### 振动两条路径（关键结论）
1. **游戏 rumble**：`InputDevice.getVibrator()` → InputManagerService → event1 input FF → 真实电机。**已物理确认可用**（`tools/fftest.c` 走 evdev FF_RUMBLE；`tools/ffvib/` 走框架 API，`Vibrating:true` 且使用者 felt 到震动）。
2. **系统 Vibrator API**：VibratorService → **HIDL `IVibrator`**（AOSP 源码确认 Android 10 仅 HIDL；legacy `vibrator.default.so` 不被使用，且其目标 `timed_output`/LED 节点在本机不存在）。完整 HIDL 服务 + `hal_vibrator_default` 的 input_device sepolicy **搁置**（task #23）。

---

## 3. 未完成 / 搁置项（含原因）

| 项 | task | 原因 / 阻碍 |
| --- | --- | --- |
| 完整蓝牙 | #12 | donor Bluetooth.apk 非平台签名，缺 `INTERACT_ACROSS_USERS_FULL`；需官方 platform 密钥（CN=ROC OS platform），本机缺失。已从镜像移除 apk 止崩溃环，vendor BT HAL/libs 留 inert |
| 亮度下限 10→2 | #13 | 改 framework-res 需 platform 密钥；错签致开机循环 |
| 背光热键/程序控制 | #17 | 待定位可写背光节点并接热键（`tools/disp_probe.py` 辅助） |
| 系统振动 HAL | #23 | VibratorService 仅 HIDL；AOSP 源码树已移除、hidl-gen/secilc 缺失、设备无 root 只能刷机验证。电机仅经 input FF 可达（游戏 rumble 已确认） |
| 原厂 launcher3 字体崩溃 | #25 | #19 蹦床未覆盖 resolveDefault 早路径 → 开机 SIGABRT 崩溃环。**使用者用三方桌面规避，不影响使用，应用安装正常**，故搁置 |
| KernelWakelockReader wtf 刷屏 | — | 良性（`neither /proc/wakelocks nor /d/wakeup_sources exists`），抑制需 framework/platform 密钥；不影响功能 |

> 搁置不等于故障清单：早期测试系统的问题保留在历史记录，不直接作为当前镜像的现存故障。

---

## 4. 镜像构建流程（prebuilt-overlay）

**这不是从干净克隆一键重编。** 流程为：以 seed 整卡 raw 为底，用 debugfs 把 system/vendor 修复打进 ext4，dd 进 raw 对应分区偏移，校验后 gzip 出包。

1. 准备 seed raw（含原厂启动链 prefix + 项目 system/vendor/userdata）。
2. 施加修复：`patches/*.py`（debugfs 编辑 ext4）。
3. 组装整卡：`build/assemble_card_image.py`（seed/full 模式），按上表偏移 dd；备份 GPT @ disk−1536。
   - 依赖上游 `tools/audit_rgsp_single_card_boot.py`（gpt/package/SECTOR）、`tools/public_build/common.py`（sha/run）、`tools/public_build/pack.py`（assemble）；CubeXX 专属 `build/assemble_cubexx_image.py`（compact_gpt_public）。
4. 校验：`build/validate_cubexx_image.py` / `validate_fullcard_image.py` / `verify_seed_grow.py`（GPT 主备一致、entry CRC、ext4 magic、boot0 `eGON.BT0` 签名、e2fsck）。
5. gzip 出包，记录 raw/gz 字节数与 SHA256（见 `evidence/camfix-result.json`）。
6. **使用者用 Rufus 刷到另一张 ≥32GB（建议 64GB）TF 卡**，TF2 留空，核对目标卡。首启数据区扩容 + 创建交换需等待，后续启动复用。

最新 camfix 包（构建回执，详见 evidence）：
- 文件名 `ROC_OS_CubeXX_seed_fontfix_camfix.img.gz`
- gz 596,068,492 字节，SHA256 `0cad1345dad978e22baa7e970b1755e14f8143ab3b6ff637a6d4038840fa7343`
- raw 32,434,554,368 字节，SHA256 `34d2845268ebab531b5569636bd247728ad4ab23cff0b9beca38cd0415ab58f5`
- 仅改 system(p5)；启动链/vendor/userdata/GPT 与 seed_bt 逐字一致。

---

## 5. 目录结构

```
cubexx/
├── README.md            本文件
├── device/              CubeXX 设备覆盖层
│   ├── ANBERNIC-keys.kl     摇杆/按键 keylayout（左 Z/RX 右 RY/RZ）
│   └── rgsp-kmsg-start.sh   kmsg 日志变体（setgid root:log，shell 无需 root 读有界内核日志）
├── build/               整卡组装与校验
│   ├── assemble_card_image.py      主组装器（seed/full）
│   ├── assemble_cubexx_image.py    CubeXX compact_gpt_public
│   ├── assemble_adb_image.py / assemble_fullcard_image.py
│   ├── build_cubexx_prefix.py      原厂启动链 prefix
│   ├── build_debug_ramdisk.py      项目 ramdisk
│   ├── simg_expand.py / make_force_system.py / modify_system_adb.py
│   ├── validate_cubexx_image.py / validate_fullcard_image.py / verify_seed_grow.py
│   └── check_addr_env.py
├── patches/             system/vendor ext4 覆盖修复（debugfs）
│   ├── reenable_cameraserver.py    相机看门狗修复
│   ├── modify_logd_optin.py        内核日志默认关闭
│   ├── remove_bluetooth.py         移除蓝牙崩溃环（inject_bluetooth.py / patch_bt_seapp.py 为搁置的反向/尝试）
│   ├── patch_mem_services.py       内存服务裁剪
│   ├── patch_disable_telephony.py / remove_telephony_disable.py
│   └── patch_power_wake.py / revert_power_wake.py
├── tools/               修复/测试/探测代码（仅源码）
│   ├── fftest.c                 evdev FF_RUMBLE 振动测试（电机物理确认）
│   ├── ffvib/FfVib.java + build.sh   框架 InputDevice 振动测试（app_process jar）
│   ├── fbprint.c / setlabel.c / hello.c   framebuffer/ ext4 label/原生测试
│   ├── disp_probe.py / ls_parts.py / inspect_env.py / compare_cmdline.py / compare_mmc.py
│   ├── inspect_adb*.py          ADB bring-up 迭代探测
│   └── read_card.ps1 / read_userdata.ps1 / elevate_read.ps1 / elevate_ud.ps1   Windows 读盘辅助
└── evidence/
    └── camfix-result.json       camfix 构建回执（哈希/分区/修复/结构校验，已脱敏）
```

`tools/ffvib` 运行：`CLASSPATH=/data/local/tmp/ffvib.jar app_process /system/bin FfVib <ms>`（需 `Looper.prepareMainLooper()` + `ActivityThread.systemMain()`，源码已含）。构建用 WSL javac + d8（`build.sh`）。

---

## 6. 工作区假设与复用注意

- 脚本内硬编码原工作区路径：WSL 下仓库 `/mnt/e/AI/H700Android`、构建目录 `/root/cubexx-*`。在本 Fork 复用时需按实际布局调整这些路径（未做重构以保持与原始成果一致）。
- 组装脚本依赖上游 `tools/audit_rgsp_single_card_boot.py`、`tools/public_build/common.py`、`tools/public_build/pack.py`（Fork 已含）。
- 大型基础源码与镜像通过网盘获取，不在本目录；本目录只含适配层源码、修复脚本与脱敏证据。
- 构建约束（上游 AGENTS.md）：低压构建 `tools/build_h700_low_pressure.ps1 -Execute`（单 CPU、亲和 0-1、`-j1`、6GiB RAM、512MiB swap、nice 19）；新 Android shell/init 用 LF；冻结快照保留原始字节不重排。

## 7. 实测验证状态（camfix 已刷另一张卡）

使用者已用 Rufus 把 camfix 刷到独立 TF 卡插机：
- 左右摇杆端到端可用；应用安装正常（三方桌面）。
- 相机看门狗已修复：0 条 `system_server_watchdog`，`media.camera` 可找到，启动稳定。
- 内核日志默认 OFF 确认；userdata 自动扩容；调试开销已关闭。
- 振动电机经 input FF 物理确认（游戏 rumble 可用）。
- 原厂 launcher3 字体崩溃由三方桌面规避（搁置）。

## 8. 安全与隐私

本目录**不含**镜像（*.img/*.img.gz/*.raw）、私钥/签名材料、原始设备/会话日志、设备序列号、本地保全目录、`.dsh-diag/`。原始侦察（boot.dts/boot0.bin/boot.img/dmesg/serial 等）仅保留在作者本地，未公开。`evidence/camfix-result.json` 为脱敏构建回执。各第三方组件保留各自许可；不提供游戏 ROM 或商业资源。

## 9. 与上游的关系

本目录为**纯增量**：上游 H700 多机型内容（README、docs、tools、android 覆盖层）未被改写。CubeXX 作为 720×720 机型已在上游机型表中列出；本目录补充其专属适配细节与修复代码。反馈请通过上游 [Issues](https://github.com/LPF970915/H700Android/issues)，注明机型、镜像文件名/哈希、触发步骤并去除设备标识与账户/网络信息。