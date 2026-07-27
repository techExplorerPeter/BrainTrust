# AWR2X44P `sbl_qspi` 启动链路、验签与解密设计分析

## 1. 文档范围与结论

本文基于当前仓库中 AWR2X44P 的以下实现进行静态分析：

- `examples/drivers/boot/sbl_qspi/awr2x44p-evm/r5fss0-0_nortos`
- `source/drivers/bootloader`
- `source/drivers/bootloader/soc/awr2x44p`
- `source/drivers/hsmclient`
- `source/board/flash/qspi`
- `tools/boot/out2rprc`
- `tools/boot/multicoreImageGen`
- `tools/boot/signing`

分析覆盖从上电、ROM Bootloader（RBL）装载 SBL，到 SBL 从 QSPI 装载多核 AppImage，最后复位 R5F 并进入应用的完整可见链路。

先给出最重要的结论：

1. 系统中存在两条不同的安全启动链，不能混为一谈：
   - **RBL 校验/解密 SBL 自身**：输入为 flash `0x0` 处的 `sbl_qspi.*.tiimage`，由芯片 ROM 完成。
   - **SBL 请求 HSM 校验 AppImage**：输入为 flash `0xA0000` 处的 `*.appimage.hs`，由 HSM Runtime 的 `PROC_AUTH_BOOT` 服务完成。该 HSM 服务也具备解密语义，但当前 QSPI 直读路径没有把密文搬到可写 RAM，所以不能据此认定“加密 AppImage 可从 QSPI 正常启动”。
2. R5F 侧没有实现 RSA 验签或 AES 解密算法。它只解析证书长度和镜像长度、维护 cache，并通过 Secure IPC 把证书地址交给 HSM。签名 AppImage 的密码学认证由 HSM 执行；若要解密，HSM 需要可写的原地缓冲，而当前地址是只读 QSPI memory-map。
3. 当前 SoC 代码只在 `EFUSE_DEVICE_TYPE == HSSE (0x0A)` 时要求 AppImage 认证。GP 和 HSFS 都按未认证镜像路径启动。
4. 当前 SysConfig 生成项为：
   - AppImage flash 偏移：`0x000A0000`
   - `isAppimageSigned = TRUE`
   - `disableAppImageAuth = FALSE`
   - QSPI memory-map 基址：`0xC6000000`
5. 多核装载顺序为 `RSS R4 -> C66 -> M4 -> 本核 R5F`；放行顺序也是 `RSS R4 -> C66 -> M4 -> 等待 RSS 启动完成 -> 复位本核 R5F`。
6. R5F 应用镜像最后才写入，因为它会覆盖 SBL 当前正在使用的本核向量表和内存。写完后 SBL直接触发 R5F reset，正常情况下不再返回。
7. 静态 review 发现若干需要修正的问题，最严重的是：
   - QSPI boot-media 读函数会吞掉底层读失败并始终返回成功。
   - R5F 镜像加载失败后，`main.c` 仍会无条件覆盖状态并复位进入应用。
   - AppImage/RPRC 元数据缺少充分边界检查，GP/HSFS 上尤其危险。

> 边界说明：RBL 和 HSM Runtime 是芯片 ROM/安全固件，仓库没有它们的内部实现。本文对其内部密码学行为的描述，以构建工具生成的证书、公开的客户端调用接口和调用结果为证据；无法从本仓库证明 HSM 内部密钥读取、反回滚熔丝比较等不可见细节。

## 2. 总体启动视图

```text
上电/复位
   |
   v
Boot ROM / RBL
   |-- 根据 boot mode 从 QSPI flash 0x0 读取 SBL TI image
   |-- 解析 ROM 格式 X.509
   |-- HS：认证 SBL；若有 encryption 扩展则解密 SBL
   |-- 将 SBL 放到 MSS L2 0x10200000（R5 本地地址别名 0x0）
   v
R5F 向量表 -> _c_int00 -> main()
   |
   |-- PLL、MPU/cache、DPL、pinmux、EDMA、QSPI、UART、HSM Client 初始化
   |-- HS-SE：请求 HSM Boot ROM 装载并启动内嵌 HSM Runtime
   |-- 打开 GD25B64C QSPI NOR
   v
Bootloader_open()
   |-- 当前读取位置设为 flash 0xA0000
   v
Bootloader_parseMultiCoreAppImage()
   |
   |-- HS-SE + signed：
   |      解析 App X.509 -> HSM PROC_AUTH_BOOT -> 验签
   |      （HSM API 支持可选原地解密，但本 QSPI 路径没有可写 RAM staging）
   |      -> 跳过证书，读取明文 MSTR
   |
   |-- GP/HSFS：
   |      直接把 0xA0000 当作 MSTR
   |
   |-- 解析各 coreId 对应 RPRC offset
   v
装载 RSS R4 -> C66 -> M4
   |
   |-- 解析 RPRC header/section
   |-- 地址转换
   |-- QSPI memory-map + EDMA 拷贝到目标 RAM
   v
仅初始化本核 R5F，暂不覆盖 SBL
   |
   v
放行 RSS R4 -> C66 -> M4 -> 等待 RSS boot complete
   |
   v
最后装载 R5F RPRC -> 覆盖本核应用区/向量 -> 触发 R5F reset
   |
   v
应用自己的 vector -> _c_int00 -> 应用 main()
```

## 3. Flash 布局和运行内存

### 3.1 Flash 布局

默认烧录配置见：

- `tools/boot/sbl_prebuilt/awr2x44p-evm/default_sbl_qspi.cfg`
- `tools/boot/default_sbl_qspi.cfg`

| Flash 偏移 | 内容 | 消费者 |
|---:|---|---|
| `0x00000000` | `sbl_qspi.release.tiimage` 或 HS 版本 | RBL |
| `0x000A0000` | 普通 `.appimage` 或 HS `.appimage.hs` | SBL Bootloader |

当前 flash 配置是 GD25B64C：

- 容量：8 MiB
- JEDEC manufacturer/device：`0xC8/0x4017`
- 读协议：`1S-1S-4S`
- read command：`0x6B`
- 8 个 dummy clock
- 3-byte 地址

QSPI 的 memory-map 窗口为 `0xC6000000`，因此 AppImage 的 memory-map 地址是：

```text
0xC6000000 + 0x000A0000 = 0xC60A0000
```

这个地址正是 HS-SE 路径传给 HSM 的证书起始地址。

### 3.2 SBL 链接与 R5F 地址别名

`linker.cmd` 的关键布局如下：

| 区域 | 地址 | 用途 |
|---|---:|---|
| `R5F_VECS` | `0x00000000` | R5F 本地 vector/run 地址 |
| `MSS_L2_RSVD` | `0x10200000` | vector 和早期启动代码的 SoC load 地址 |
| `MSS_L2` | `0x10200280` 起 | SBL 主体代码、数据、栈、堆 |
| `MSRAM_HSMRT` | `0x10220000` | 内嵌 HSM Runtime 镜像 |
| `MAILBOX_HSM` | `0x44000000` | HSM 侧 Secure IPC queue |
| `MAILBOX_R5F` | `0x44000400` | R5F 侧 Secure IPC queue |

`.sbl_init_code` 的 run 地址为 R5 本地 `0x0`，load 地址为 SoC 地址 `0x10200000`。二者是同一 MSS L2 存储体的不同地址视图。当前 release map 验证了：

- ELF entry symbol：`_vectors`
- `_vectors` run 地址：`0x00000000`
- 对应 load 地址：`0x10200000`
- `main`：`0x10201B6D`

## 4. 镜像是怎样生成的

### 4.1 SBL 自身：ELF -> BIN -> ROM TI image

SBL 的生成链为：

```text
sbl_qspi.release.out
   |
   | tiarmobjcopy --strip-all -O binary
   v
sbl_qspi.release.bin
   |
   | tools/boot/signing/mcu_rom_image_gen.py
   | 生成 ROM 格式 X.509，并把证书前置
   v
sbl_qspi.release.tiimage / sbl_qspi.release.hs.tiimage
```

ROM X.509 的主要扩展为：

| OID | 含义 |
|---|---|
| `1.3.6.1.4.1.294.1.1` | boot sequence：证书类型、目标 core、目标地址、镜像长度 |
| `1.3.6.1.4.1.294.1.2` | image integrity：哈希算法和镜像 hash |
| `1.3.6.1.4.1.294.1.3` | software revision |
| `1.3.6.1.4.1.294.1.4` | 可选 encryption 参数 |
| `1.3.6.1.4.1.294.1.5` | 可选 key derivation salt |
| `1.3.6.1.4.1.294.1.8` | 可选 debug policy |

构建参数中 SBL load address 是 `0x10200000`，core 为 R5，software revision 为 1。

当前 checkout 默认 `DEVICE_TYPE=GP`。实际 release 产物验证结果：

- `sbl_qspi.release.bin`：62,864 bytes
- `sbl_qspi.release.tiimage`：64,601 bytes
- DER X.509：1,737 bytes
- 证书记录的 image size：62,864 bytes
- 签名算法：SHA-512 with RSA
- 证书公钥：RSA-4096

GP 产物使用 SDK 的 `mcu_gpkey.pem` 生成格式合法的证书；HS 构建则改用 `APP_SIGNING_KEY`。HS 的 `ENC_SBL_ENABLED` 默认是 `yes`，因此默认还会对 SBL binary 做 AES-256-CBC 加密，再让 RBL 按证书描述解密。

### 4.2 应用：ELF -> RPRC -> 多核 AppImage

应用构建链为：

```text
每个 core 的 ELF
   |
   | tools/boot/out2rprc/elf2rprc.js
   v
每个 core 的 RPRC
   |
   | tools/boot/multicoreImageGen/multicoreImageGen.js
   v
MSTR meta header + 多个 RPRC = *.appimage
   |
   | HS 时由 mcu_appimage_x509_cert_gen.py
   | 可选加密，并生成 HSM 格式 X.509
   v
X.509 + 明文/密文 AppImage = *.appimage.hs
```

该 SoC 的常用 RPRC core ID 为：

| RPRC core ID | CSL core | `main.c` 启动对象 |
|---:|---|---|
| 0 | `CSL_CORE_ID_R5FSS0_0` | MSS R5F，本核 |
| 1 | `CSL_CORE_ID_C66SS0` | C66 DSP |
| 2 | `CSL_CORE_ID_M4SS0_1` | DSS M4 |
| 3 | `CSL_CORE_ID_RSS_R4` | RadarSS R4 |

#### 4.2.1 多核 Meta Header

AppImage 开头的数据结构为：

```c
struct MetaHeaderStart {
    uint32_t magicStr;   /* "MSTR" = 0x5254534D, little-endian */
    uint32_t numFiles;
    uint32_t devId;      /* AWR2X44P 构建值 55 */
    uint32_t reserved;
};

struct MetaHeaderCore {
    uint32_t coreId;
    uint32_t imageOffset; /* 相对 AppImage 明文起点 */
};

struct MetaHeaderEnd {
    uint32_t reserved;
    uint32_t magicEnd;    /* "MEND" */
};
```

其后顺序拼接各 core 的 RPRC。

#### 4.2.2 RPRC 格式

每个 RPRC 为：

```c
struct RprcFileHeader {
    uint32_t magic;        /* "RPRC" = 0x43525052 */
    uint32_t entry;
    uint32_t reservedAddr;
    uint32_t sectionCount;
    uint32_t version;
};

struct RprcSectionHeader {
    uint32_t addr;
    uint32_t reservedAddr;
    uint32_t size;
    uint32_t reservedCrc;
    uint32_t reserved;
};

/* 每个 section header 后紧跟 size 字节 section data */
```

## 5. 上电到 `main()` 的链路

### 5.1 RBL 阶段

1. 芯片上电，boot mode 选择 QSPI。
2. RBL 从 flash `0x0` 读取 ROM 格式 TI image。
3. RBL 解析证书中的目标地址、镜像长度、hash、software revision、debug 和可选 encryption 信息。
4. 在要求安全启动的器件生命周期中，RBL 认证证书和镜像；若证书包含 encryption 扩展，则先按安全启动协议处理密文并得到 SBL 明文。
5. SBL 被放到 `0x10200000`，R5F 从本地 vector 地址 `0x0` 对应的别名区域开始执行。

RBL 内部实现不在仓库中，因此第 3～4 步的具体 ROM 密钥层级和失败码无法从源码继续展开。

### 5.2 R5F C Runtime 阶段

`_vectors` 的 reset vector 跳到 `_c_int00`。`_c_int00` 执行：

1. 关闭 IRQ/FIQ。
2. 使能 VFP。
3. 分别建立 FIQ、IRQ、SVC、Abort、Undefined、System mode stack。
4. 调用 `__mpu_init()`：
   - 建立 6 个 MPU region。
   - 使能 cache。
5. 调用 `_system_pre_init()` 和 `__TI_auto_init()`：
   - 清零 BSS。
   - 复制/初始化 C 全局数据。
   - 执行 C/C++ 初始化。
6. 调用 `main()`。

## 6. `main()` 完整执行步骤

以下顺序对应 `awr2x44p-evm/r5fss0-0_nortos/main.c`。

### 6.1 性能统计和 PLL

1. `Bootloader_profileReset()` 清空启动性能统计。
2. `Bootloader_socConfigurePll()`：
   - 配置 DSP DPLL 到 900 MHz，DSP 使用 450 MHz 输出。
   - 配置 PER PLL，提供 200 MHz 外设/RSS 时钟。
   - 根据 eFuse boot frequency 过渡配置 R5/SYSCLK。
   - 临时切 R5 到 XTAL，重配 CORE DPLL。
   - 最终把 R5 切到 CORE DPLL 的 400 MHz 输出。

### 6.2 `System_init()`

生成代码依次执行：

1. `Dpl_init()`：
   - 初始化 VIM/Hwi，但先保持中断关闭。
   - 启用 ERROR/WARN/INFO log zone。
   - 配置 RTI timer/ClockP。
   - 最后全局使能中断。
2. `PowerClock_init()`。
3. `Pinmux_init()`：
   - 配置 QSPI data[0..3]、CLK、CS。
   - 配置 UARTA RX/TX。
4. `QSPI_init()`。
5. `EDMA_init()`。
6. `HsmClient_config()`：
   - 在 `MAILBOX_HSM`/`MAILBOX_R5F` 建立双向 Secure IPC queue。
   - 对端 core 为 HSM。
   - security master 为 R5FSS0-0。
   - 注册 client ID 0，用于接收 HSM boot notify。
7. `Drivers_uartInit()`。

### 6.3 `Drivers_open()`

依次打开：

1. EDMA，启用完成中断。
2. QSPI：
   - input clock 80 MHz。
   - quad RX。
   - memory-map 基址 `0xC6000000`。
   - DMA enabled。
3. UARTA：
   - 115200 8-N-1。
   - interrupt mode。

### 6.4 启动 HSM Runtime

`Bootloader_socLoadHsmRtFw()` 根据 `EFUSE_DEVICE_TYPE` 分支：

| Device type | 行为 |
|---|---|
| HS-SE `0x0A` | 调 `Hsmclient_loadHSMRtFirmware()` |
| HS-FS `0xAA` | 只打印 device type，不加载 |
| GP `0x03` | 不处理 |

HS-SE 的 HSM Runtime 装载步骤为：

1. SBL 中的 `gHsmRtFw[]` 位于 `.rodata.hsmrt`。
2. R5F 构造 `LOAD_HSM (0x9980A1D4)` mailbox 消息，携带镜像地址。
3. 对消息 header + payload 计算 16-bit ones-complement checksum。
4. 把消息写入 HSM mailbox，触发 HSM mailbox interrupt。
5. 忙等 HSM Boot ROM 返回 `LOAD_HSM_RESULT (0xA70915DE)`。
6. 校验返回 checksum 和成功 signature `0x4A43AB6C`。
7. 等待新 HSM Runtime 通过 Secure IPC 发送 `HSM_MSG_BOOT_NOTIFY (0x000A)`。

随后调用 `Keyring_init(&gHSMClient)`。当前例程未在 SysConfig 启用 keyring 模块，因此链接的是 `main.c` 中的 weak 实现，它直接返回成功，不导入任何 key。AppImage 默认使用 keyring slot 0，意味着 HS-SE 产品必须确保 HSM 侧相应 key 已由安全生命周期/其他 provisioning 流程准备好。

特别注意：当前 checkout 的 `source/drivers/hsmclient/soc/awr2x44p/hsmRtImg.h` 是 `HSMRT_IMG_SIZE_IN_BYTES (0U)` 的占位内容。GP 构建不会走 HSM 装载路径；HS-SE 构建和交付前必须确认该头文件已被正确的、带证书的 HSM Runtime 镜像替换。

### 6.5 打开 Board Flash

`Board_driversOpen()` -> `Board_flashOpen()` -> `Flash_open()`：

1. 绑定 flash 到 `CONFIG_QSPI0`。
2. 设置 3-byte addressing。
3. 设置 `1S-1S-4S` 协议。
4. 读 JEDEC ID，确认 GD25B64C。

失败会被 `DebugP_assert(status == SystemP_SUCCESS)` 截停。

### 6.6 打开 Bootloader media

`Bootloader_open(CONFIG_BOOTLOADER0, ...)` 调用 `Flash_imgOpen()`：

```text
flashArgs.curOffset = flashArgs.appImageOffset = 0xA0000
```

后续所有 RPRC offset 都相对这个 AppImage 明文起点。

## 7. AppImage 验签和解密

### 7.1 什么时候会验签

`Bootloader_parseMultiCoreAppImage()` 的条件是：

```c
if (Bootloader_socIsAuthRequired() == TRUE &&
    config->isAppimageSigned == TRUE) {
    Bootloader_verifyMulticoreImage(handle);
}
```

当前生成配置 `isAppimageSigned = TRUE`，但 `Bootloader_socIsAuthRequired()` 只对 HS-SE 返回 TRUE：

| Device | 是否调用 HSM 认证 AppImage |
|---|---|
| HS-SE | 是 |
| HS-FS | 否 |
| GP | 否 |

`disableAppImageAuth = FALSE`，所以 HS-SE 上不会走开发期的跳过认证分支。

### 7.2 R5F 侧证书预解析

`Bootloader_verifyMulticoreImage()`：

1. 计算证书 memory-map 地址 `0xC60A0000`。
2. 从 flash 读前 4 bytes。
3. `Bootloader_getX509CertLen()` 读取 DER SEQUENCE 长度：
   - 首字节必须为 `0x30`。
   - 支持短长度或 `0x82 + 2-byte length`。
4. `Bootloader_getMsgLen()` 在证书内搜索 boot sequence OID：

```text
06 09 2B 06 01 04 01 82 26 01 01
           1.3.6.1.4.1.294.1.1
```

5. 从 boot sequence 最后一个 ASN.1 INTEGER 取得 `imageSize`。
6. 对 `certLen + imageLen` 向 128-byte cache line 对齐，执行 `CacheP_wbInv()`。
7. 要求 `0x100 < certLen < 0x800`。

这里的解析只用于找到 HSM 输入范围和认证后 AppImage 的起点，不是密码学验签。

### 7.3 HSM 认证请求

调用链为：

```text
Bootloader_verifyMulticoreImage
  -> Bootloader_socAuthImage(0xC60A0000)
     -> HsmClient_register(clientId = 2)
     -> HsmClient_procAuthBoot(
            cert = 0xC60A0000,
            cert_size = 0x1000,
            timeout = WAIT_FOREVER)
```

`HsmClient_procAuthBoot()` 构造：

- destination client：HSM client 1
- source client：bootloader client 2
- service type：`HSM_MSG_PROC_AUTH_BOOT = 0xC120`
- args：证书物理地址
- args CRC：证书起点固定 4 KiB 的 CRC16-CCITT
- flag：AOP，需要 ACK/NACK

CRC16 只用于 R5F/HSM 消息参数传递的完整性检查，不是镜像安全认证。密码学认证由 HSM 服务执行。

HSM 返回 NACK、超时或 response CRC 错误时，启动失败；返回 ACK 时视为认证成功。

### 7.4 AppImage X.509 中签了什么

`mcu_appimage_x509_cert_gen.py` 生成的 App 证书包含：

| OID | 内容 |
|---|---|
| `1.3.6.1.4.1.294.1.1` | cert type、image length 等 boot sequence 信息 |
| `1.3.6.1.4.1.294.1.2` | SHA OID 和完整 AppImage payload 的 hash |
| `1.3.6.1.4.1.294.1.3` | software revision，默认 1 |
| `1.3.6.1.4.1.294.1.4` | 可选 AES encryption 参数 |
| `1.3.6.1.4.1.294.1.12` | asymmetric signing key ID 和 symmetric encryption key ID |

默认 HS 配置为：

- hash：SHA-512
- signing key：`mcu_custMpk.pem`
- signing keyring ID：0
- encryption key：`mcu_custMek.key`
- encryption keyring ID：0
- RSASSA-PSS：默认关闭；打开时 salt length 默认 0

非 PSS 模式由 `openssl req -new -x509 ... -sha512` 生成自签 X.509。HSM 必须利用安全侧已信任/已导入的 key，而不能只相信证书里自带的 public key；具体 keyring 验证实现位于不可见的 HSM 固件中。

### 7.5 AppImage 加密细节

当 `ENC_ENABLED=yes` 时，签名脚本执行：

1. 读取 256-bit 对称 key。
2. 若提供 `KD_SALT`：
   - 使用 HMAC-SHA512 HKDF。
   - input key material 为制造商 encryption key。
   - salt 为 `kd_salt.txt` 的 hex 内容。
   - 不使用额外 info。
   - 截取 32 bytes 作为 AES-256 key。
3. 用 `openssl rand 16` 生成随机 IV。
4. 用 `openssl rand 32` 生成 random string。
5. 对原始 AppImage 追加零：

```text
zeroPadLen = 16 - (plainLength % 16)
```

即使原长度已经 16-byte 对齐，也会追加 16 bytes。
6. 再追加 32-byte random string。
7. 使用 AES-256-CBC、`-nopad` 加密：

```text
ciphertext = AES-256-CBC(
    key,
    IV,
    appimage || zero-padding || random-string)
```

8. 对**密文**计算 SHA-512，并把 hash、密文长度、IV、random string、KDF iteration flag/salt、keyring ID 写入 X.509。
9. 对 X.509 进行 RSA 签名。
10. 最终输出：

```text
DER X.509 certificate || encrypted AppImage
```

因此工具生成的是“证书绑定密文 hash”的形式。`PROC_AUTH_BOOT` 服务的接口语义允许 HSM 按 encryption 扩展选择 keyring 中的对称 key，并对 payload 原地解密。

但要特别区分“工具/API 支持”与“这个 QSPI SBL 路径实际可用”：

- `certLoadAddr` 是 `0xC60A0000`，即外部 NOR flash 的 QSPI memory-map 地址。
- NOR flash 不是可由 HSM 当作普通 RAM 覆盖的原地解密缓冲。
- 当前 `sbl_qspi` 没有先把 `certificate || ciphertext` 搬到 MSS L2/DSS L3 等可写 RAM。
- HSM 响应中也没有返回另一个 plaintext 地址。
- 认证后 Bootloader 仍通过 `Flash_read()` 从原 flash offset 读取 AppImage。

所以从当前可见实现判断：

> **签名但不加密的 `.appimage.hs` 是这条 QSPI 安全启动链的可证明路径；`ENC_ENABLED=yes` 虽可生成加密文件，但本 `sbl_qspi` 没有完成让它可启动所需的 RAM staging，不能作为已支持功能使用。**

TI 其他 MCU+ SDK 对相同的 HSM 原地解密模型也明确说明：直接从 OSPI/QSPI flash 装载时，因 flash 不可直接写，应用镜像加密不可用。除非 AWR2X44P 的受控 HSM 包另有仓库外机制或 TI 给出专门说明，否则本项目应遵循这一限制。

### 7.6 认证/解密完成后的 cache 和 offset

公共 Bootloader 在 HSM 返回后执行：

```c
CacheP_inv(certLoadAddr, cacheAlignedLen, CacheP_TYPE_ALL);
```

这段代码兼容“HSM 对 RAM buffer 原地解密”的其他 boot media。对当前 QSPI 的**签名、未加密**路径，它主要保证 HSM 访问前后的 cache coherency，不会把 flash 密文变成明文。

认证成功后，把 boot media 起点从证书头移动到 AppImage：

```text
appImageOffset = 0xA0000 + certLen
curOffset      = appImageOffset
```

之后 `Bootloader_parseMultiCoreAppImage()` 读到的第一个字必须是 `MSTR`。未加密 signed AppImage 满足此条件；当前 QSPI 路径下的 encrypted AppImage 仍是密文，通常会在这里因 magic 不匹配而失败。

## 8. 多核 AppImage 解析与装载

### 8.1 Meta Header 解析

1. 初始化最多 10 个 `MetaHeaderCore` 为 `0xFF`。
2. 读取 `MetaHeaderStart`。
3. 检查 `magicStr == "MSTR"`。
4. 根据 `numFiles` 读取 core header。
5. 对每个非 `0xFFFFFFFF` core ID：
   - AWR2X44P 上 RPRC ID 与 CSL core ID 直接相同。
   - 保存 `rprcOffset`。
   - 将 core bit 置入 `coresPresentMap`。

解析阶段不搬运 section，只建立每个 CPU 的 RPRC 索引。

### 8.2 QSPI 数据搬运路径

每次读取的调用链为：

```text
Bootloader imgRead
  -> Flash_read()
     -> Flash_norQspiRead()
        -> QSPI_readMemMapMode()
           -> QSPI_spiMemMapRead()
              -> EDMA copy from 0xC6000000 + flash offset to destination RAM
```

非 4-byte 对齐的头尾由 CPU byte copy，中间 4-byte 对齐部分用 EDMA。

### 8.3 RPRC section 地址转换

RPRC 保存的是各目标 CPU 看到的 local/virtual address。SBL 在 R5F 上搬运时转换为 SoC 地址：

| 目标 core | RPRC 地址范围 | R5F 可访问的 SoC 地址 |
|---|---:|---:|
| R5F | `0x00000000` TCMA | `0x00000000` |
| R5F | `0x00080000` TCMB | `0x00080000` |
| R5F | `0x10200000` MSS L2 | `0x10200000` |
| C66 | `0x00800000` L2 | `0x80800000` |
| C66 | `0x00E00000` L1P | `0x80E00000` |
| C66 | `0x00F00000` L1D | `0x80F00000` |
| RSS R4 | `0x00000000` shared RAM | `0xA0000000` |
| RSS R4 | `0x00080000` TCMA | `0xA0080000` |
| RSS R4 | `0x01000000` TCMB | `0xA1000000` |
| RSS R4 | `0x04020000` static RAM | `0xA4020000` |
| M4 | `0x00000000` RAM | `0x28000000` |

不在表内的地址保持原值。

### 8.4 非本核装载

对 RSS R4、C66、M4，`Bootloader_loadCpu()` 的意图是：

1. request CPU。
2. 设置 CPU clock。
3. power-on reset。
4. 初始化目标 core memory。
5. seek 到该 core 的 RPRC offset。
6. 检查 `RPRC` magic。
7. 记录 entry point。
8. 对每个 section：
   - 读取 section header。
   - 转换目标地址。
   - 检查是否落入 SBL reserved memory。
   - 从 QSPI 拷贝 section data 到目标 RAM。

目标 core 默认时钟：

| Core | 默认频率 |
|---|---:|
| R5F | 400 MHz |
| C66 | 450 MHz |
| M4 | 200 MHz |
| RSS R4 | 200 MHz |

### 8.5 为什么本核 R5F 要延后

首次处理 R5F 时调用：

```c
Bootloader_loadSelfCpu(..., skipLoad = TRUE);
```

它只解析 RPRC entry、初始化本核 memory，不搬运 section。原因是 R5F App 通常包含本地 vector/TCM/MSS L2 内容，立即加载会覆盖仍在运行的 SBL vector、代码、数据或栈。

当前 AWR2X44P 的 `Bootloader_socCpuSetEntryPoint()` 是空实现。真正的控制转移依赖最后把应用 vector 写到 R5 本地 `0x0`，再做本核 reset。

## 9. 各 core 的放行和最终跳转

### 9.1 RSS R4

`Bootloader_runCpu(RSS_R4)`：

1. `SOC_rcmPopulateBSSControl()`。
2. 若 RBL 启用了 TOP PBIST，保存 RBL 测过的 memory bitmap并关闭 TOP PBIST。
3. `SOC_rcmBSSR4Unhalt()`。
4. 随后主流程执行 `Bootloader_socConfigurePllPostApllSwitch()`：
   - 配置 fast-charge bias。
   - 切换 HSI clock。
   - 配置 Ethernet clock。
   - 关闭未使用的 PLL HSDIV 输出。

### 9.2 C66

`Bootloader_runCpu(C66)` -> `SOC_rcmC66xStart()`。

### 9.3 M4

`Bootloader_runCpu(M4)` -> `SOC_rcmCM4Unhalt()`。

### 9.4 等待 RadarSS

在放行本核 R5F 前调用 `SOC_rcmWaitBSSBootComplete()`。这样 RSS 可与其他 core 的启动并行，又能保证 MSS App 开始运行前 RadarSS 已完成启动。

### 9.5 最后装载并复位 R5F

若 AppImage 包含 R5F：

1. `Bootloader_rprcImageLoad()` 真正把 R5F RPRC section 写入目标内存。
2. 应用 vector 覆盖本地地址 `0x0`。
3. `Bootloader_runSelfCpu()`：

```text
SOC_rcmR5PowerOnReset()
SOC_rcmR5TriggerReset()
```

4. R5F 从应用自己的 reset vector 重新开始，进入应用 `_c_int00 -> main()`。

正常情况下第 3 步不会返回，因此后面的 `Bootloader_close()`、`Drivers_close()`、`System_deinit()` 只属于失败/异常返回路径。

## 10. 失败路径

| 失败点 | 当前行为 |
|---|---|
| HSM Runtime 装载失败 | assert，停在 SBL |
| Keyring init 失败 | assert |
| flash open/JEDEC/protocol 失败 | assert |
| Bootloader open 失败 | 跳到尾部清理 |
| AppImage auth NACK/timeout | 不解析、不启动 core，打印失败 |
| `MSTR` 错误 | 不启动 core，打印失败 |
| 非本核 core load/run 失败 | 后续由 `status == SUCCESS` 保护，停止继续启动 |
| RSS boot complete | API 无返回值，主流程无法传播错误 |
| R5F load 失败 | **当前代码仍会无条件触发本核 reset，见 review finding R2** |

系统没有实现 A/B slot、备用镜像、失败计数、回滚到 recovery SBL 或 watchdog recovery。

## 11. Device/构建模式矩阵

| 模式 | SBL 文件 | SBL 认证/解密主体 | App 文件 | App 认证/解密主体 |
|---|---|---|---|---|
| GP | `.tiimage` | RBL 按 GP 策略装载 | `.appimage` | 不认证，SBL直接解析 |
| HS-FS | HS 构建产物 | RBL 安全生命周期策略 | 当前代码可能使用 signed 标记，但 `socIsAuthRequired()` 返回 FALSE | 不调用 HSM，直接解析 |
| HS-SE | `.hs.tiimage` | RBL；默认 SBL encryption enabled | 未加密的 signed `.appimage.hs` | HSM Runtime `PROC_AUTH_BOOT` 认证 |

烧录文件必须与 device type 和构建选项匹配。特别是：

- GP/HSFS 直接解析路径期望 `0xA0000` 开头是 `MSTR`，不能把未被处理的 X.509 当作普通 AppImage。
- HS-SE signed 路径期望 `0xA0000` 开头是 DER `0x30`。
- 当前 `sbl_qspi` 不应启用 App encryption；若产品必须加密 AppImage，应先增加“整包搬到可写 RAM -> HSM 原地认证/解密 -> 从 RAM 解析/装载”的路径，并校核 RAM 容量及 reserved range。

## 12. Source Review 发现

下面的问题按建议修复优先级排序。它们是对当前代码的 review 结论，不代表已在本文任务中修改源码。

### R1 — 高：`ENC_ENABLED=yes` 与 QSPI 直接装载路径不闭环

构建系统允许生成 encrypted `.appimage.hs`，HSM API 也支持原地解密，但 QSPI Bootloader 把外部 NOR memory-map 地址直接交给 HSM，且认证后继续从 flash 读取。代码中不存在可写 RAM staging。

结果是“构建成功”不等于“可从 QSPI 解密启动”。建议：

1. 在 `sbl_qspi` 构建中显式拒绝 `ENC_ENABLED=yes`；或
2. 为 encrypted image 分配足够的可写、non-overlap RAM，先读取完整证书和密文，再调用 HSM，最后从 RAM boot-media 解析；或
3. 仅在 TI 明确确认并交付 AWR2X44P 专用透明解密机制后启用。

### R2 — 高：R5F 加载失败后仍触发本核 reset

位置：`main.c:168-175`

```c
status = Bootloader_rprcImageLoad(...);
status = Bootloader_runSelfCpu(...);
```

第二句无条件覆盖第一句的失败状态。若 R5F section 读取、magic 或地址检查失败，SBL 仍可能复位到不完整/旧的 vector。

建议：

```c
if (status == SystemP_SUCCESS) {
    status = Bootloader_runSelfCpu(bootHandle, &bootImageInfo);
}
```

### R3 — 高：QSPI Bootloader read 吞掉所有底层错误

位置：`source/drivers/bootloader/bootloader_flash.c:61-76`

问题：

1. `Flash_read()` 返回值被忽略。
2. 地址越界时不读数据，但仍返回 `SystemP_SUCCESS`。
3. 使用 `< flashSize`，导致恰好读到 flash 末尾的合法范围被拒绝。
4. `curOffset + len` 可能发生 32-bit overflow。

这会让上层继续解析未初始化或旧数据，并使 R2 更容易触发。

建议使用防 overflow 的边界判断，并原样传播 `Flash_read()` 状态：

```c
if ((len <= flashSize) && (curOffset <= flashSize - len)) {
    status = Flash_read(...);
    if (status == SystemP_SUCCESS) {
        curOffset += len;
    }
} else {
    status = SystemP_FAILURE;
}
```

### R4 — 高（GP/HSFS）：`numFiles` 和 `coreId` 未做边界检查

位置：`source/drivers/bootloader/bootloader.c:657-708`

- 栈数组只有 `BOOTLOADER_MAX_INPUT_FILES == 10`。
- 代码直接循环到不可信的 `mHdrStr.numFiles`，可能越界写 `mHdrCore[]`。
- `cslCoreId` 未检查 `< CSL_CORE_ID_MAX`，随后被用作 `cpuInfo[]` 下标及 shift 位数。

HS-SE 上成功认证的镜像可视为可信；GP/HSFS 上 flash 损坏或恶意镜像可直接触发内存破坏。

建议在任何读循环前验证：

```text
1 <= numFiles <= BOOTLOADER_MAX_INPUT_FILES
coreId < CSL_CORE_ID_MAX
imageOffset 位于已知 AppImage 长度内
coreId 不重复
```

### R5 — 高（GP/HSFS）：RPRC section 对 SBL reserved memory 的重叠判断不完整

位置：`source/drivers/bootloader/bootloader.c:306-323`

当前只判断 section 起点严格位于 `(start, end)`：

```c
section.addr > start && section.addr < end
```

会漏掉：

- `section.addr == start`
- section 从 reserved 区域之前开始、但尾部覆盖 reserved 区域
- `addr + size` overflow

应检查完整半开区间是否相交：

```text
sectionStart < reservedEnd && sectionEnd > reservedStart
```

且先验证 `sectionEnd = sectionStart + size` 不溢出。

### R6 — 中高：HS-SE 在认证前解析不可信 X.509，空指针路径未保护

位置：`Bootloader_getMsgLen()`、`Bootloader_verifyMulticoreImage()`

`Bootloader_getMsgLen()` 调用 `Bootloader_findSeq()` 后没有检查 NULL，立即执行 `++boot_seq_ptr`。攻击者可在认证发生前放置畸形证书，使 SBL data abort/DoS。

另外，证书长度校验是在 `getMsgLen()` 之后才执行，顺序不安全。

建议：

1. 先验证 DER header 和 cert length 范围。
2. 检查 OID 搜索结果。
3. 所有 ASN.1 游标移动都验证仍在 `[certStart, certEnd)`。
4. 解析失败以显式错误返回，不 assert、不解引用 NULL。

### R7 — 中：Meta Header 验证不完整

位置：`Bootloader_parseMultiCoreAppImage()`

当前只检查 `MSTR`：

- 没有验证 `devId == 55`。
- 没有读/验证 `MEND`。
- 没有验证各 RPRC offset 单调、非重叠且位于镜像内。
- 没有验证重复 core ID。

建议补齐这些结构完整性检查，即使 HS-SE 已认证也有助于阻止构建错误导致的不可诊断启动失败。

### R8 — 中：`Bootloader_socAuthImage()` 覆盖 client 注册失败

位置：`source/drivers/bootloader/soc/awr2x44p/bootloader_soc.c:419-428`

```c
status = HsmClient_register(...);
status = HsmClient_procAuthBoot(...);
```

注册失败后仍继续使用 client，并覆盖注册状态；函数退出也未 unregister client ID 2。

建议只在 register 成功时发送请求，并在所有出口统一 unregister。

### R9 — 中：`Bootloader_loadCpu()` 覆盖 CPU request 失败

位置：`source/drivers/bootloader/bootloader.c:105-126`

`Bootloader_socCpuRequest()` 的结果被紧接着的 `Bootloader_socCpuSetClock()` 覆盖。当前 AWR2X44P 的 request 实现固定返回成功，所以现版本未触发，但公共 Bootloader 逻辑不稳健。

建议每一步只在前一步成功时执行。

### R10 — 中：HS-SE HSM Runtime 产物必须纳入构建门禁

当前源码头中的 HSM Runtime size 为 0。建议在 `DEVICE_TYPE=HS` 时增加编译期断言或 make 检查：

```text
HSMRT_IMG_SIZE_IN_BYTES > 0
HSM Runtime X.509 可解析
HSM Runtime hash/版本与发布清单一致
```

仅 `touch hsmRtImg.h` 不能证明内容有效。

### R11 — 中：缺少认证失败后的恢复策略

HSM auth、flash read、RSS boot 等任一路径失败都只停机或返回，没有：

- 备用 slot
- recovery image
- watchdog reset policy
- 持久化失败原因
- 防止无限 boot loop 的计数器

产品化时建议把恢复策略和安全回滚策略一起设计，避免“认证是安全的，但设备永久不可服务”。

## 13. 建议的修复与验证顺序

1. 先决定 AppImage confidentiality 方案：禁止 QSPI App encryption，或实现 RAM staging。
2. 修 R2、R3，确保任何 flash/load 错误都不会进入应用。
3. 修 R4、R5、R6、R7，形成完整的证书、Meta Header、RPRC 边界验证。
4. 修 R8、R9，保证状态不被覆盖，HSM client 生命周期闭合。
5. 为 HS 构建加入 HSM Runtime 非空和证书检查。
6. 建立以下启动测试矩阵：

| 测试 | 期望结果 |
|---|---|
| GP + 正常 unsigned AppImage | 正常启动 |
| HS-SE + 正常 signed AppImage | HSM ACK，正常启动 |
| 当前 QSPI SBL + `ENC_ENABLED=yes` | 构建门禁拒绝该组合 |
| 增加 RAM staging 后的 encrypted AppImage | HSM ACK，RAM 中恢复 `MSTR`，正常启动 |
| 修改 AppImage 任一 payload byte | HSM NACK，不放行任何 core |
| 修改证书 signature | HSM NACK |
| signing key ID 不匹配 | HSM NACK |
| RAM staging 方案中 encryption key ID/key 不匹配 | HSM NACK或解密完整性失败 |
| `numFiles = 11` | 安全返回格式错误，不越界 |
| 非法 core ID | 安全返回格式错误 |
| RPRC section 与 SBL reserved range 相交 | 拒绝装载 |
| QSPI read 注入失败 | 不 reset 本核，不启动后续 core |
| AppImage 被截断 | 明确报错，不读取 flash 边界之外 |
| HSM Runtime size 为 0 的 HS build | 构建直接失败 |

建议同时在 UART log 中区分：

```text
CERT_PARSE_FAIL
HSM_AUTH_NACK
HSM_AUTH_TIMEOUT
META_HEADER_INVALID
RPRC_HEADER_INVALID
RPRC_RANGE_INVALID
FLASH_READ_FAIL
CORE_LOAD_FAIL(coreId)
CORE_RUN_FAIL(coreId)
```

这样现场问题可以区分“密码学拒绝”“镜像结构错误”“flash/EDMA 传输错误”和“目标 core 启动错误”。

## 14. 最终链路摘要

```text
制作阶段：
  SBL ELF -> flat BIN -> ROM X.509 [+ AES-CBC] -> TI image -> flash 0x0
  App ELF(s) -> RPRC(s) -> MSTR multicore AppImage
             -> HSM X.509 [+ AES-CBC] -> appimage.hs -> flash 0xA0000

运行阶段：
  RBL -> 验证/可选解密 SBL -> R5F 运行 SBL
  SBL -> 初始化时钟/MPU/cache/EDMA/QSPI/HSM IPC
  HS-SE -> 装载 HSM Runtime
  SBL -> 定位 0xC60A0000
  HS-SE -> HSM PROC_AUTH_BOOT 验签 AppImage
  （若要解密 AppImage，必须先增加可写 RAM staging；当前 QSPI 直读路径不闭环）
  SBL -> cache invalidate -> 跳过 cert -> 解析 MSTR
  SBL -> 解析各 RPRC -> 地址转换 -> QSPI/EDMA 搬运 sections
  SBL -> 放行 RSS R4/C66/M4 -> 等待 RSS
  SBL -> 最后覆盖本核 R5F image -> R5F reset
  App vector -> App C runtime -> App main()
```

这条链路的核心安全边界是：**RBL 信任并启动 SBL，SBL 信任 HSM 的 AppImage 认证结果，HSM 依据安全侧 key/keyring 对 AppImage 证书和 payload 做认证。SBL 自身的解密可由 RBL在装载到 RAM 时完成；AppImage 若要解密，则必须给 HSM 提供可写的 RAM 镜像，而当前 QSPI 直读实现没有这一环。**

## 15. 外部交叉证据

本文以仓库源码为主，另外用以下 TI 官方资料交叉确认了两个仓库外事实：

1. [MMWAVE MCU+ SDK 4.7.0.1 Release Notes](https://dr-download.ti.com/software-development/software-development-kit-sdk/MD-U4MY7aGNn5/04.07.00.01/mmwave_mcuplus_sdk_release_notes.pdf)：明确说明本发布包中的 AWR2X44P MCU+ SDK 版本为 `10.00.00.07`，且包内没有有效 HSM Runtime；HS-SE secure boot/crypto 要求从受控 TIFS 包取得有效镜像并替换 `hsmRtImg.h`。
2. [TI AM243x MCU+ SDK Secure Boot](https://software-dl.ti.com/mcu-plus-sdk/esd/AM243X/09_00_00_35/exports/docs/api_guide_am243x/SECURE_BOOT.html)：明确描述同类 HSM 服务采用原地认证/解密，因此直接从不可写 OSPI flash 装载时不能解密应用镜像。该资料不是 AWR2X44P 专用规格，本文只将其作为对当前源码数据流判断的旁证；AWR2X44P 若存在例外，必须以 TI 针对该器件的受控 HSM 文档为准。
3. [AWR294x/AWR2x44P/AWR2544 Primary and Secondary Bootloader](https://www.ti.com/lit/an/swra760b/swra760b.pdf)：TI 对该雷达 SoC 家族 PBL/SBL 分阶段启动和 secure variant 软件认证的总体说明。
