# TI AWR2944 / Gen2 Radar 安全架构完整参考指南

> 基于以下五份文档整理：
> 1. `keywriter_x509_certificate.pdf` — X509 证书扩展定义
> 2. `Security_HSM_flow_v1p2.pdf` — HSM 架构与整体安全流程
> 3. `TRM_security_addendum.pdf` — 安全 TRM 附录
> 4. `AWR294x_HSM_Addendum_SPRUIV0_RevB_November2023.pdf` — HSM 补充说明
> 5. `AWR2944_AWR2544_Security_App_Note_SWRU625_v1_0.pdf` — Gen2 Radar Security User's Guide

---

## 第一部分 安全目标与威胁模型

### 1.1 保护的核心资产 (Assets)
三类资产需要保护：
- **Identity（身份）**：设备身份、密钥、证书
- **Intellectual Property（知识产权）**：客户的算法、固件
- **Data（数据）**：运行时产生的敏感数据

### 1.2 暴露点 (Exposure Points)
- **Storage**：静态存储（Flash、eFuse）
- **Runtime**：运行时内存
- **Transfer**：数据传输通道

### 1.3 五大安全支柱
| 支柱 | 内容 |
|---|---|
| Secure Boot | IP 保护、Take-over 保护、Anti-cloning、SW Anti-rollback |
| Runtime Security | 受保护的加解密操作、隔离执行、安全存储 |
| Secure Debug | 调试/跟踪/测试接口的管理；软件可控或永久关闭 |
| Physical Security | 侧信道攻击防护 |
| Cryptographic Acceleration | AES、SHA、MD5、TRNG、RSA 等硬件加速 |

### 1.4 与 SHE 标准的对齐
TI HSM 相对于 SHE 标准做了增强：
- **Confidentiality**：SHE 只有 AES-128；TI 支持 AES-128/192/256
- **Authentication**：除了 CMAC，增加非对称认证（RSA 最大 4K，ECDSA）
- **Key Exchange**：增加 ECDHA
- **Crypto Agility**：HSM 内 M4 是可编程的，算法可升级（SHE 不支持）
- **Data Integrity**：增加 SHA-256/512/HMAC
- **HW Acceleration**：除 AES/TRNG/PRNG 外，还有 SHA-256/512/HMAC、ECC、RSA-2K/4K（通过 PKA engine）

---

## 第二部分 HSM 硬件架构

### 2.1 HSM 模块组成（基于 Cortex-M4 @ 200MHz）

```
┌─────────────────────── HSM ───────────────────────┐
│  Cortex-M4 @ 200MHz + ROM(64KB/96KB) + RAM(192KB) │
│                                                    │
│  HSM L1 Interconnect                               │
│  ├─ Secure RAM (10 KB)                             │
│  ├─ SECURITY MANAGER (Keys, Data, Access control)  │
│  ├─ Secure DMA                                     │
│  ├─ HSM Control, Timer, Watchdog                   │
│  ├─ Safety IPs: DCC, ESM, LBIST, PBIST             │
│  ├─ Debug Auth                                     │
│  └─ TI/Customer Fuse-ROM                           │
│                                                    │
│  DTHE（硬件加解密引擎组）                           │
│  ├─ AES (ECB/CBC/CCM/CTR/GCM) 128/192/256         │
│  ├─ SHA-2 (256/384/512), HMAC                     │
│  ├─ PKA (ECC, up to RSA 4K)                        │
│  └─ TRNG, DRBG                                     │
│                                                    │
│  Interfaces 到 MSS L1 Interconnect：                │
│  - Slave Interface（经 Firewall）                  │
│  - Master Interface                                │
│  - Data Path（经 Firewall）                        │
│  - SecAP Interface                                 │
└────────────────────────────────────────────────────┘
```

### 2.2 架构设计动机
- **最小化可信根（Trust Anchor）**：减少攻击面
- **分层安全**：密钥、证书等秘密隔离于普通运行环境
- **防软件攻击**：即使 R5 侧软件被攻破，HSM 内的密钥依然安全
- **Data/IP 保护**：静态和运行时均受保护

---

## 第三部分 设备类型与生命周期

### 3.1 三种设备类型

| 类型 | 别名 | 特性 |
|---|---|---|
| **GP** | General Purpose（非安全） | 秘钥未烧、安全启动被旁路；HSM、安全 ROM、部分安全外设不可访问；调试全开 |
| **HS-FS** | High Security – Field Securable | TI 密钥已烧入；出厂时的状态；强制认证 HSM-RT 镜像；JTAG 到 MSS 开放；SBL 不验签 |
| **HS-SE** | High Security – Security Enforced | 客户密钥已烧；强制安全启动；HSM 锁定；调试接口默认锁定 |

### 3.2 设备状态转换

```
Fresh FAB → [TEST: No keys] → [HS-FS: TI Keys] → [HS-SE: Customer Keys]
              Complete Testing   Batch Rescreen      Deployment/Returns
```

**关键转换点**：当 **customer keys Revision** 和 **customer keys count** 烧入 eFuse 之后，设备自动从 HS-FS 转变为 HS-SE（下次启动生效）。

### 3.3 HS-FS vs HS-SE 启动行为对比
| 项目 | HS-FS | HS-SE (Prime) | HS-SE (Non-Prime) |
|---|---|---|---|
| SBL 认证 | 不认证 | 客户密钥认证 | 客户密钥认证 |
| HSM-RT 认证 | TI 密钥 | 客户密钥 | TI 密钥（嵌套证书） |
| SBL 解密密钥 | - | 客户 | 客户 |
| HSM-RT 解密密钥 | TI | 客户 | TI |

**HS-SE Non-Prime 嵌套证书**：HSM-RT 的外层证书是 `certType=0x3`（Outer Cert），内层是 `certType=0x2`（hsmRT Firmware Cert）。

---

## 第四部分 密钥管理体系（CPFROM 安全存储）

### 4.1 所有密钥总览

| 简称 | 全称 | 所有者 | 长度 | 用途 |
|---|---|---|---|---|
| **KEK** | Key Encryption Key | 设备 | 256-bit | 每颗芯片唯一的随机数；用于设备绑定 |
| **MPK Hash** | Manufacture Public Key Hash | TI | 512-bit | TI 非对称公钥 SHA 哈希；带 BCH 纠错 |
| **MEK** | Manufacture Encryption Key | TI | 256-bit | TI 初始对称加密密钥；带 BCH 纠错 |
| **SMPK Hash** | Secondary Manufacture Public Key Hash | 客户 | 512-bit | 客户非对称公钥 SHA 哈希；带 BCH |
| **SMEK** | Secondary Manufacture Encryption Key | 客户 | 256-bit | 客户对称加密主密钥；带 BCH |
| **BMPK Hash** | Backup MPK Hash | 客户 | 512-bit | 根撤销用的备份公钥哈希 |
| **BMEK** | Backup MEK | 客户 | 256-bit | 根撤销用的备份对称密钥 |
| **TIFEK** | TI Factory Encryption Key | TI | RSA 密钥对 | 工厂置入客户对称密钥时的"信封加密"公钥 |

### 4.2 CPFROM（eFuse）布局

```
┌─── Standard TI OTP ────────────┐
│  Unique ID                      │
│  KEK (256-bit, 每芯片唯一)      │────→ HSM (On POR)
│  TI Key Set:                    │
│    MPK hash + MEK (with BCH)    │────→ HSM
└─────────────────────────────────┘

┌─── Customer OTP ───────────────┐
│  Customer Key Set:              │
│    SMPK hash + SMEK (with BCH)  │────→ HSM
│  Customer Backup Key Set:       │
│    BMPK hash + BMEK (with BCH)  │────→ HSM
│                                 │
│  SWRV_SBL (64 bits)             │
│  SWRV_HSM (64 bits)             │
│  SWRV_APP (192 bits)            │
│  Customer Data fields           │
│  JTAG 永久禁用位                │
└─────────────────────────────────┘

┌─── Secure RAM ──────────────────┐
│  额外派生密钥（10 KB）           │
└─────────────────────────────────┘
```

### 4.3 根密钥撤销机制
- 客户在 OTP 中同时烧入 **主密钥组** (SMPK/SMEK) 和 **备份密钥组** (BMPK/BMEK)
- **Key Revision** 字段：
  - `1` = 使用 SMPK/SMEK（默认）
  - `2` = 使用 BMPK/BMEK（主密钥被泄露后切换）
- 切换由客户固件管理，写入 KEYREV 字段

### 4.4 密钥派生（HKDF）
- ROM 支持 **HKDF**（HMAC-based Key Derivation Function），用 `key_derivation` 扩展中的 salt/info 派生出新密钥
- 派生密钥通过 Asset Interface 交给 HSM-RT 使用
- **安全原则**：只允许使用派生密钥，不直接使用根密钥；派生发生在完整性验证通过之后

### 4.5 KEK 与设备绑定（Re-Authoring）
- KEK 是每颗芯片独有的 256-bit 随机数
- **Re-Authoring 流程**：
  1. 客户上传 **签名+SMEK加密** 的启动镜像（内含 Re-authoring code）到设备
  2. 设备上 Re-authoring code 先用 SMEK 解密，再用本机 KEK 重新加密
  3. 设备输出 KEK 加密后的镜像交给客户烧回 Flash
- 第二次启动起，ROM 先尝试 SMEK 解密失败后会自动尝试 KEK 解密
- **效果**：镜像绑定到特定芯片，防 IP 被拷贝到其他芯片
- **注意**：ROM 只负责 KEK 解密；"绑定"逻辑需客户固件实现

---

## 第五部分 X.509 证书体系

### 5.1 基础规范
- 基于 **ITU-T X.509 (2012)**、**ASN.1 (X.680)**、**DER (X.690)**
- 使用 **自签名证书**（Self-signed），不走 CA 链
- 使用 `openssl` 工具生成（不依赖特定版本）
- 证书版本 **v2**

### 5.2 TI OID 命名空间
```
1.3.6.1.4.1.294.1 = Texas Instruments Device-Boot
```
层级含义：`iso(1) → identified-organization(3) → dod(6) → internet(1) → private(4) → enterprise(1) → TI(294) → Device-Boot(1)`

### 5.3 Image 证书扩展总表（ROM X509 Parser 支持）

| 扩展名 | 用途 | OID | SBL | HSM-RT |
|---|---|---|---|---|
| `boot_seq` | 启动信息（**必须**） | `…294.1.1` | ✓ | ✓ |
| `image_integrity` | SHA-512 镜像哈希 | `…294.1.2` | 可选 | 必须（HS-FS/HS-SE） |
| `swrv` | 软件版本号（反回滚） | `…294.1.3` | SE 必须 | SE 必须 |
| `encryption` | AES-CBC 解密参数 | `…294.1.4` | 可选 | 可选 |
| `key_derivation` | HKDF 派生参数 | `…294.1.5` | SE 必须 | 见下 |
| `debug` | JTAG 解锁 | `…294.1.8` | 可选 | 忽略 |

### 5.4 boot_seq 详细（强制扩展）

```asn1
boot_seq := SEQUENCE {
    certType     INTEGER,      -- 证书类型
    bootCore     INTEGER,      -- 启动哪个核
    bootCoreOpts INTEGER,      -- 核的配置选项
    destAddr     OCTET STRING, -- 加载地址
    imageSize    INTEGER       -- 镜像大小
}
```

**certType 取值**：
| 值 | 含义 | 适用设备 |
|---|---|---|
| 0x1 | Primary Boot Image (R5 SBL) | All |
| 0x2 | hsmRT Firmware Image | HS-FS, HS-SE Prime |
| 0x3 | Outer Cert for hsmRT Firmware Cert | HS-SE Non-Prime |
| 0x80000001 | WIR Override | RMA |
| 0x80000002 | WIR Unlock | RMA |

**bootCore 取值**：
| 值 | 含义 |
|---|---|
| 0 | HSM (Cortex-M4) |
| 8 | HSM 证书由 TI MPK 签名（HS-SE non-prime） |
| 16 | MCU Pulsar R5 子系统 |

**bootCoreOpts（仅 R5 SBL 有效，其他证书忽略）**：
| 值 | 含义 |
|---|---|
| 0x0 | MCU Pulsar 默认（eFuse 驱动，**Lock Step**） |
| 0x1 | R5 Start mode in Thumb |
| 0x2 | R5 Start in split mode（需 Lockstep 设备） |

**典型 Load Address**：
- R5 SBL：`0x10200000`（L2 RAM）
- HSM Runtime：`0x0`

### 5.5 image_integrity

```asn1
image_integrity := SEQUENCE {
    shaType  OID,         -- 必须是 SHA-512: 2.16.840.1.101.3.4.2.3
    shaValue OCTET STRING -- 镜像 SHA-512
}
```

### 5.6 swrv（软件版本与反回滚）

```asn1
swrv := SEQUENCE {
    swrev INTEGER  -- 32-bit 版本号
}
```

**检查逻辑**（HS-SE 设备的 SBL 与 HSM-RT）：
| eFuse 版本 | 证书版本 | 结果 |
|---|---|---|
| 0 | 0 | 忽略检查，总是加载 |
| 0 | >0 | 设备未要求版本检查，加载 |
| >0 | 0 | **永不加载**（eFuse 版本 > 证书版本） |
| >0 | >0 | 证书版本 ≥ eFuse 版本时才加载 |

### 5.7 encryption 扩展

```asn1
encryption := SEQUENCE {
    initalVector OCTET STRING, -- 16 字节 IV
    randomString OCTET STRING, -- 32 字节（附加在镜像末尾校验解密正确性）
    iterationCnt INTEGER,      -- 0 = 不派生，非 0 = HKDF 派生
    salt         OCTET STRING  -- 32 字节（iterCnt 非 0 时用）
}
```

**解密模式**：AES-256-CBC；`randomString` 用于验证解密成功（比对镜像末尾 32 字节）。

### 5.8 key_derivation 扩展

```asn1
key_derivation := SEQUENCE {
    salt OCTET STRING, -- 32 字节
    info OCTET STRING  -- 32 字节（可选）
}
```

**使用规则**：
| 设备类型 | SBL | HSM-RT |
|---|---|---|
| GP | 忽略 | 忽略 |
| HS-FS | 忽略 | 用 TI 密钥派生 |
| HS-SE | 必须；用激活的客户密钥（不管 Prime/Non-Prime） | 忽略（复用 SBL 证书中的派生） |

### 5.9 debug 扩展

```asn1
debug := SEQUENCE {
    debugUID     OCTET STRING, -- 设备唯一 ID（全 0 表示通配）
    debugType    INTEGER,      -- 调试控制
    coreDbgEn    INTEGER,      -- 保留，默认 0
    coreDbgSecEn INTEGER       -- 保留，默认 0
}
```

**debugType 位字段（Gen2）**：
- Bit[15:0] Debug Type
- Bit[16] CUST（1 = 禁止访问客户密钥）
- Bit[31:18] 保留

**Debug Type 取值**：
| 值 | 含义 |
|---|---|
| 0 | Disable debug / Permanently Disable JTAG during ROM |
| 1 | Preserve debug state / Set Debug to SoC default |
| 2 | Enable non-secure debug (Public Debug) |
| 4 | Enable secure + non-secure debug (Full Debug) |

**重要**：上述设置只有 `debugUID` 匹配当前设备的 Unique ID 时才生效。

---

## 第六部分 Keywriter 专用扩展（`…294.1.64` 到 `.81`）

这些扩展**只有 Keywriter 使用**，不出现在普通 boot 证书中。

| OID | 扩展名 | 作用 |
|---|---|---|
| `.64` | Encrypted AES extension | TIFEK(pub) 加密的 AES-256 随机密钥 |
| `.65` | Encrypted SMPK Signed AES | TIFEK 加密、SMPK(priv) 签名的 AES-256 |
| `.66` | Encrypted BMPK Signed AES | TIFEK 加密、BMPK(priv) 签名的 AES-256 |
| `.67` | AES Encrypted SMPKH | 用上述 AES 加密的 SMPK 哈希 |
| `.68` | AES Encrypted SMEK | 用上述 AES 加密的 SMEK |
| `.69` | MPK Options | 保留 |
| `.70` | AES Encrypted BMPKH | 用上述 AES 加密的 BMPK 哈希 |
| `.71` | AES Encrypted BMEK | 用上述 AES 加密的 BMEK |
| `.72` | MEK Options | 保留 |
| `.73` | AES Encrypted extended OTP | 保留 |
| `.74` | key revision | KEYREV（1=SMPK/SMEK, 2=BMPK/BMEK） |
| `.76` | MSV | MSV 字段 |
| `.77` | key count | Key count |
| `.78` | software revision hsmRT | HSM-RT 的 SWREV |
| `.79` | software revision SBL | SBL 的 SWREV |
| `.80` | software revision APP | APP 的 SWREV |
| `.81` | version | Keywriter 版本 |

### 6.1 action_flags 公共字段
几乎所有 keywriter 扩展都带 `action_flags`，编码为：
```
action_flags = WP | RP | OVRD | ACTIVE
```
- **WP**：Write Protect（写保护）
- **RP**：Read Protect（读保护）
- **OVRD**：Override（允许覆盖现有值）
- **ACTIVE**：使能该字段写入

### 6.2 三种 AES 信封加密结构
```asn1
-- 最基本：只加密
KEYWR-ENC-AES := SEQUENCE { val OCTET STRING, size INTEGER }

-- 加密 + SMPK 签名
KEYWR-ENC-SMPK-SIGN-AES := SEQUENCE { val, size }

-- 加密 + BMPK 签名
KEYWR-ENC-BMPK-SIGN-AES := SEQUENCE { val, size }
```
三者结构相同，签名方式不同，对应不同的信任来源。

### 6.3 客户密钥封装结构（以 SMPKH 为例）
```asn1
KEYWR-AES-ENC-SMPKH := SEQUENCE {
    val          OCTET STRING, -- AES-256 加密后的 SMPKH
    iv           OCTET STRING, -- 128-bit IV
    rs           OCTET STRING, -- 256-bit Random String
    size         INTEGER,
    action_flags INTEGER
}
```
SMEK、BMPKH、BMEK 均使用同样结构。

---

## 第七部分 OTP Keywriter（出厂密钥置入）

### 7.1 Keywriter 组成
- **HSM M4 Firmware**（TI 签名+加密，不可改）：负责实际写 eFuse
- **R5 SBL / OTP Writer App**（源码开放，客户可改）：基于 PDK SBL，负责加载 HSM-RT + IPC

### 7.2 Keywriter 镜像布局
```
┌─── X509 Cert – Whole Image ────────────┐
│  ┌─ X509 – TI-Cert HSM                ─┐│
│  │  HSM RT Binary (含 OTP Driver)     ─│   >380 KB
│  └─────────────────────────────────────┘│
│  ┌─ OTP Writer App                    ─┐│
│  └─────────────────────────────────────┘│
│  ┌─ X509 – OTP Cfg                    ─┐│  104 KB
│  │   SMPK, BMPK, SMEK Cust Efuse, TIFEK│
│  └─────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

### 7.3 Keywriter 运行时架构
```
┌─ MSS R5 ──────────────┐       ┌─ HSM Subsystem ──┐
│                        │       │  HSM RT (SEC)    │
│  OTP APP               │ ←IPC→ │  ┌─ OTP Driver  │
│    ├─ GPIO Driver (VPP)│ MBOX  │  └──────────────│
│    ├─ UART Driver (log)│       │  Efuse Cntlr    │
│    └─ MAILBOX (IPC)    │       │  OTP Efuse      │
└────────────────────────┘       └───────────────── ┘
```

### 7.4 Keywriter 加载方式
| 模式 | SOP[2:0] | 说明 |
|---|---|---|
| SOP5 | `101` | UART 加载（XMODEM 协议） |
| SOP4 | `100` | QSPI Flash 0x0 加载 |
| SOP6（仅 AWR2544） | - | JTAG 加载 |

### 7.5 TIFEK 非对称信封加密机制
1. TI 生成 TIFEK 密钥对，**TIFEK(priv)** 嵌入在 Keywriter HSM-RT 内部（加密存储）
2. **TIFEK(pub)** 公开给客户
3. 客户：
   - 自选一个 AES-256 随机密钥 K_rand
   - 用 TIFEK(pub) 加密 K_rand
   - 用 K_rand 加密实际的 SMPKH/SMEK/BMPKH/BMEK
4. Keywriter 运行时：
   - HSM 用 TIFEK(priv) 解出 K_rand
   - 再用 K_rand 解出真实密钥
   - 写入对应 eFuse 行
5. 完成后 **TI 密钥在设备中不再生效**（HS-SE 切换）

### 7.6 硬件要求
- **VPP (1.7V)**：烧 eFuse 时必须供电；需专用 GPIO 控制 VPP LDO
- 必须支持通过非 Flash 的替代方式启动（UART/JTAG 或测试治具）
- VPP 和 pinmux 信息属于非安全的 R5 Application

---

## 第八部分 安全启动流程（Secure Boot）

### 8.1 整体时序

```
Time →
HSM Core  │ HSM ROM ──────────→│ HSM RunTime ────→
R5 Core   │         │ R5F ROM →│ R5F SBL → R5F RT →
C66 Core  │         │          │            │ C66 RT →
          0    HW Startup   RBL Process  SBL Process
```

关键点：**HSM 最先上电执行**，R5 等待 HSM 释放。

### 8.2 外部接口
- **① HSM ↔ SBL Messaging Interface**（Mailbox IPC）
- **② HSM ROM ↔ HSM Runtime Asset Interface**（`asset.h`）

### 8.3 IPC: R5 Boot ROM ↔ HSM Boot ROM（加载 SBL 阶段）

```
R5 Boot ROM                    HSM Boot ROM (200MHz)
    │                               │
    │──── Hello ───────────────→│ Wait for Hello
    │                               │
    │──── Get SOC Id ──────────→│
    │←── SOC Id Info ────────────│ Wait for Certificate
    │──── Certificate ─────────→│
    │                               │
    │──── Image Chunk-1 (≥2K) ─→│
    │──── Image Chunk-2 ───────→│ Receive Image
    │       …                       │
    │──── Image Chunk-N ───────→│
    │←── Result (Good/Retry) ────│
    │──── Result-Ack ──────────→│ R5 Wait Sleep
    │                               │
(R5 SBL 开始执行)              (Retry on error)
```

**Watchdog**：HSM Boot ROM 有 180 秒超时。若 SBL 加载失败或超时，系统复位。

### 8.4 SBL 加载流程 Boot Flow（HSM ROM 内部）

```
Certificate ───→┌──────────────┐    ┌─── Secure Parser
                 │              │    │      ├─ Key Manager + BCH
Image Chunks ──→│  SBL Boot    │    │      └─ PKCS + PKA Driver
                 │  Loop        │────┤ (1) Public Key Verification
                 │              │    │ (2) Certificate Verification
                 │              │    │
                 │  (3) SW Rev  │────┤ SHA → SHA Driver
                 │              │    │ (4) Image Integrity
                 │              │    │
                 └──────────────┘    └─── AES (可选) → AES Driver
                        │                  (5) AES Decryption
                        ↓                  Key: HS-FS=TI, HS-SE=Customer
             Result (Good or Retry)
```

### 8.5 R5 SBL 加载完成后 Handoff（Eclipse）
```
Step 1: R5 SBL Image 位于 L2 (0x10200000)
Step 2: Boot ROM 把 IVT + Init Code（640 字节）拷到 TCMA (0x00020000)
Step 3: Eclipse — R5 Boot ROM 隐身，SBL IVT 出现在 0x00000000
```
此刻：
- `TCMA: 0x00000000` = SBL IVT + Init Code
- `L2: 0x10200000` = R5 SBL 主体
- Boot ROM Code/Data 全部被 "eclipse"（隐藏）

### 8.6 R5 SBL → HSM Runtime 加载阶段（第二次 IPC）
```
R5 SBL                            HSM Boot ROM
  IPC Initialized                   Boot Loop Runtime
    │                                   │
    │──── HSM Load (Address) ────→│
    │                                   │ Load HSM Runtime
    │                                   │  ├─ Public Key Verify
    │                                   │  ├─ Cert Verify
    │                                   │  ├─ Image Integrity
    │                                   │  └─ AES Decrypt (可选)
    │←── HSM Load Result ──────────│
    │                                   │ IPC Deinit
    │                                (Success) Eclipse HSM
    │                                HSM Runtime 开始执行
    │ IPC Deinitialized
```

### 8.7 HSM Runtime Handoff 内存布局
Boot ROM **总是**把 HSM-RT 拷贝到内部 RAM（完整性校验、解密都在内部 RAM 完成）。

```
Step 1: HSM-RT 镜像位于 L2
Step 2: Boot ROM 拷贝到 RAM: 0x00020000（放 HSM-RT IVT + 主体）
Step 3: Boot ROM Data 移到 Secure RAM: 0x46050000
Step 4: Eclipse — HSM-RT IVT 出现在 0x00000000
        Secure RAM 被清零（但保留 Assets）
```

### 8.8 Boot ROM 支持的 SOP 模式

| SOP[2:0] | 模式 |
|---|---|
| `001` | QSPI boot（从 Flash 加载） |
| `011` | SOP2 Development Mode → **WIR 模式** |
| `100` | SOP4（Keywriter 的 QSPI 模式） |
| `101` | UART boot（XMODEM，115200 8N1） |

### 8.9 QSPI Flash 要求与偏移
- 仅支持 **JESD216 SFDP** 的 Flash
- Quad Enable：JESD216 >9 words 表自动读；=9 words 表需外部工具预设
- **不支持** 1-4-4 模式（硬件限制）
- Fast Read 顺序：`1-1-4 (0x6B)` → `1-1-2 (0x3B)` → `1-1-1 (0x0B)`

**SBL Flash 偏移**：
| 镜像 | 偏移 |
|---|---|
| Primary SBL | `0x00000000` |
| Secondary (Fallback) SBL | `0x00040000` |

**R5 SBL 最大尺寸**：952 KB（不含证书）；加密镜像上限 974,816 字节（加 32 字节 RS）。

### 8.10 UART 启动参数
| 参数 | 值 |
|---|---|
| Port | 0 |
| 波特率 | 115200 |
| 数据 | 8-N-1-None |
| 协议 | XMODEM，1KB 块 |
| Ping | 每 3 秒 "C" |

### 8.11 SOCID 信息（外设模式下首先发出）
包含：
- Boot ROM 版本
- Device Type (HS-FS / HS-SE / GP)
- Key Count & Revision（安全设备）
- TI & Customer Public Key Hash
- 设备 Unique ID

（见 `socid_export.h`）

---

## 第九部分 镜像创建与验证流程（核心密码学步骤）

### 9.1 创建流程（PC/Secure Server 侧）

```
                           x.509 Certificate
                           ┌─────────────────┐
                          │ (1a) SW Version  ←── (1c)
                          │     Public Key   │
                          │     Image HASH   ←── (3b)
                          │     Load Address ←── (1b) Magic Number
                          │     …            │
                          │     Signature    ←── (4c)
                          └───────↑─────────┘
   HSM RT ─── Symmetric Key ──(2)─┐      │
   (binary)    └─→ [Encrypt AES-CBC]     │
                      │                  │
                      ↓                  │
              [Encrypted Code] ──(3a)─→[Hash SHA-512]
                                         │
                                  Private Key ─→ [Encrypt] ──(4b)
                                         ↑           │
                                     (4a) [Hash]     │
                                         │           ↓
                                  [Certificate] → [Sig 插入]
```

**7 步流程**：
1. 创建 X.509 证书（1a）
2. 填 boot_seq：Load Address + Magic Number（1b）
3. 填 SW Version（1c）
4. AES-256-CBC 用（可派生的）对称密钥加密 binary（2）
5. 对加密后的镜像做 SHA-512（3a），写入证书（3b）
6. Public Key（RSA 或 ECDSA）写入证书
7. 对整个证书 SHA-512（4a）+ 私钥签名（4b）→ 插回 signature 字段（4c）

**命令**：
```bash
# 密钥对
openssl genrsa -out <out_key> 4096

# AES-CBC-256 加密镜像
openssl aes-256-cbc -e -K <enc_key> -iv <IV> -in <RS> -out <out> -nopad

# 生成 DER 证书
openssl req -new -x509 -key <key> -nodes -outform DER -out <x509cert.bin> \
    -config <template.txt> -sha512 -days 365
```

### 9.2 验证流程（HSM ROM/Runtime 侧）

```
Image with Certificate
   ┌─── x.509 Cert ────┐   fuseROM
   │ Public Key ───────┼─→ [SHA-512](1a) ──→ [Compare](1b) ← SMPKH/BMPKH
   │ SW Revision ──────┼──────────────────→ [Compare](3)  ← fuseROM SWRV
   │ Image HASH ───────┼──────────────→ [Compare](4b)
   │ Load Address      │
   │ Magic Number      │
   │ Signature ────────┼─→ [Decrypt w/ PubKey](2b)
   └─── 整个 Cert ─────┴─→ [SHA-512](2a) ──→ [Compare](2c)
                                              ↓
   ┌─── Encrypted Image ──→ [SHA-512](4a) ──→ (4b)
   │   │
   │   └─→ [AES-CBC Decrypt w/ Derived Key](5a) → Binary
   │                                                │
   │                                                └─ Magic Number → [Compare](5b)
   └─────────────────────────────────────────────────↑
```

**7 步验证**：
1. 对证书内 Public Key 做 SHA-512（1a），与 eFuse 内 SMPKH（或 BMPKH）比较（1b） → **认证**
2. 对整个证书做 SHA-512（2a），用 Public Key 解签名（2b），比较（2c） → **完整性+真实性**
3. 证书 SW Revision vs eFuse SWRV 比较（3） → **反回滚**
4. 拷贝镜像到 Load Address
5. 对加密镜像做 SHA-512（4a），与证书内哈希比较（4b） → **镜像完整性**
6. 用 SMEK/BMEK 派生的密钥做 AES-256-CBC 解密（5a）（可选）→ **机密性**
7. 比较解密后明文开头的 Magic Number 与证书中值（5b）

### 9.3 侧信道攻击缓解原则
- **先完整性、后机密性**：只有完整性验证通过后才调用密钥
- **只用派生密钥**：根密钥绝不直接参与运算

---

## 第十部分 HSM Runtime（TIFS）

### 10.1 TIFS 概念
- **TIFS** = TI Foundational Security
- **TIFS-MCU**：在 Cortex-M4 上的 baremetal 安全栈
- 作为 MCU+ SDK 之上的 **add-on package**
- **不是 AUTOSAR-HSM 栈的替代品**，而是为其提供基础设施

### 10.2 HSM 软件栈分层

```
┌── Customer App Layer (AUTOSAR / Broad Market) ──┐
│      AutoSAR CSM Interface │ PKCS#11 Interface   │
│      Crypto Services HSM Proxy │ PKCS#11 Proxy    │   ← AUTOSAR / R5F
└──────────────────────────────────────────────────┘
             │
┌── HSM Subsystem ─────────────────────────────────┐
│  Secure Boot          HSM Server                  │
│  Security Application Crypto Drivers              │
│  RTOS                 Security Library            │
│  SA Low Level Drivers Secure Storage              │
│    ├ AES, SHA, TRNG, PKA                          │
│    ├ Peripheral Drivers (DMA, Timer, IRQ)         │
│    └ Infra Components                             │
│  eFUSE, ROM                                        │
└──────────────────────────────────────────────────┘
```

### 10.3 TIFS 功能
1. 设备可信根和基础安全服务
2. 可被第三方 AUTOSAR-HSM 栈消费
3. 可被客户用于扩展功能

---

## 第十一部分 反回滚机制详解

### 11.1 涉及的三个 eFuse 字段
| 字段 | 长度 | 解释者 |
|---|---|---|
| SWRV_SBL | 64 bits | ROM bootloader |
| SWRV_HSM | 64 bits | ROM bootloader |
| SWRV_APP | 192 bits | HSM Runtime（Boot ROM 仅透传给 Asset Interface） |

### 11.2 Marching 1's 编码
- eFuse 支持 **双冗余** → 64 bit 最多 **32 次版本升级**
- 每次升版需在 OTP Writer 烧掉一位

### 11.3 SW Update 流程
1. 新软件生成时，证书的 swrv 字段递增
2. 需要版本更新时，用 OTP Writer 更新 eFuse 的 SWRV_* 字段
3. 运行时由 HSM Runtime 负责最终在 eFuse 中烧位

### 11.4 硬件要求
- VPP 1.7V 必须可控供电（同 Keywriter）

---

## 第十二部分 SFLASH 布局与 OTA

### 12.1 SFLASH 整体结构

```
┌─── SFLASH ──────────────────────────┐
│  SBL Image              ←── 由 BootROM 加载
│    X.509 Cert                        │
│    ├─ Public Key                     │
│    ├─ Extension Fields               │
│    └─ Signature                      │
│    SBL Binary (flat)                 │
│                                      │
│  SBL Secondary/Fallback Image        │
│                                      │
│  HSM Runtime Image     ←── 由 SBL+HSM ROM 加载
│    X.509 Cert                        │
│    HSM RT Binary (flat)              │
│    Fallback 也支持                   │
│                                      │
│  ───────────────────────             │
│  META Header          ←── 由 SBL+HSM RT 加载
│  Certificate                         │
│    ├─ Public Key                     │
│    ├─ Extension Fields               │
│    └─ Signature                      │
│  Image/s                             │
│    ├─ MSS Application                │
│    └─ DSS Application                │
└──────────────────────────────────────┘
```

### 12.2 三层管理
1. **BootROM**：管 SBL 的加载
2. **SBL + HSM ROM**：管 HSM RT 的加载
3. **SBL + HSM Runtime FW**：管 Application（MSS/DSS）的加载

### 12.3 OTA 更新
由 SBL 负责更新 SFLASH 中的镜像；Fallback 镜像用于更新失败回滚。

---

## 第十三部分 安全调试（Secure Debug）

### 13.1 默认锁定
- 所有调试端口在上电时默认锁定
- 唯一开放的是 HSM 的 Challenge-Response 通道

### 13.2 三种解锁方式

#### (A) ROM 证书解锁（开发阶段）
- 在 SBL 证书里填 `debug` extension
- ROM 认证 SBL 后，**在交给 SBL 执行之前**，按 `debugType` 打开 JTAG
- **仅打开 SoC 调试**，**HSM 调试不解锁**
- Debug Type 可选：0（禁用）、1（保留当前）、2（Public Debug）
- **HS-FS**：只能选 Debug Type = 0 或 1（R5 JTAG 本来就开着）
- **HS-SE**：可选 0、1、2；**不可选 4**

#### (B) HSM Runtime 解锁（运行时）
- HSM-RT 加载后继承 Security Manager 控制权
- 任意握手机制，例如 **SHE CMD_DEBUG**
- 最灵活但需客户实现

#### (C) WIR 模式解锁（RMA 返厂）
- SOP = `011`（Development Mode）
- 进入 Wait-In-Reset
- 通过 JTAG **SEC-AP** 口发送证书

### 13.3 WIR 支持的请求
1. **Request SoC Information** — 返回 SOCID + UDID
2. **Unlock debugging** — 基于挑战响应解锁调试
3. **Security override** — 加载并运行测试代码（更强；会先做 HW zeroization）
4. **Resume boot process** — 退出 WIR

### 13.4 WIR Unlock vs Override 区别

| 项目 | WIR Unlock | WIR Override |
|---|---|---|
| certType | 0x80000002 | 0x80000001 |
| 证书结构 | **双层证书** | 单证书 |
| 外层验签 | TI Public Key | — |
| 内层验签 | 客户公钥 | 客户公钥 |
| UID | 内层必须匹配；外层可通配 | 必须匹配 |
| Debug Type | 4（Full Debug） | 0（Disable Debug） |
| Key Protection | 强制 | CUST=1（禁用客户密钥访问） |
| 前提 | 开 JTAG 保资产；HSM 保密钥 | 硬件 zeroization 擦除所有片上内存 |
| 典型用途 | TI 返厂调试 | 客户认证的测试设备加载 |

### 13.5 Security Override 的硬件 zeroization
执行时硬件依次：
1. 锁定 Secure RAM
2. 擦除所有片上内存
3. 开放所有 Debug TAP
4. Warm Reset → 重进 WIR
5. 外部设备可以加载测试代码

### 13.6 R&D 证书配置示例
```
[ req ]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no
dirstring_type = nobmp

[ req_distinguished_name ]
C = US
ST = MD
L = Germantown
O = Texas Instruments., Inc.
OU = RADAR PROCESSOR
CN = Anonymous, Anonymous

[ v3_ca ]
basicConstraints = CA:true
1.3.6.1.4.1.294.1.1=ASN1:SEQUENCE:boot_seq
1.3.6.1.4.1.294.1.8=ASN1:SEQUENCE:debug

[ boot_seq ]
certType     = INTEGER:0x80000001   ; WIR Override
bootCore     = INTEGER:0
bootCoreOpts = INTEGER:0
destAddr     = FORMAT:HEX,OCT:00000000
imageSize    = INTEGER:0

[ debug ]
debugUID     = FORMAT:HEX,OCT:1d42...（128 字节 UDID）
debugType    = INTEGER:65536   ; 0x10000 = CUST=1, Debug Type=0
coreDbgEn    = INTEGER:0
SeccoreDbgEn = INTEGER:0
```

### 13.7 RMA Credential Handshake（TI-客户握手）
1. 客户提取 RMA 设备的唯一 Public ID
2. 客户签名 R&D Certificate，授权 TI 调试权限
3. 客户连同设备一起寄回 TI
4. TI 接收后创建 QEM ticket
5. TI 在 QEM 加载 Cert + Public Key
6. TI 按失败报告执行台架调试

### 13.8 永久 JTAG 禁用
- 可通过 eFuse **Global JTAG Disable** 位永久关闭调试
- **一旦置位，TI 和客户都无法再调试该设备**（RMA 彻底失败）

---

## 第十四部分 端到端完整链路

### 14.1 完整流程图
```
┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌────────────────┐
│ HS-FS    │→│ OTP-Writer   │→│ HS-SE    │→│ Secure Image    │
│ Device   │  │ Utility      │  │ Device   │  │ Creation (离线) │
└──────────┘  └──────────────┘  └──────────┘  └──────────────────┘
                                                        │
┌──────────┐  ┌────────────┐  ┌─────────┐  ┌───────────▼──┐
│ Secure   │←│ Secure     │←│ Secure  │←│ Flashing      │
│ Image    │  │ Debug      │  │ Boot    │  │               │
│ Update   │  │            │  │ Flow    │  │               │
└──────────┘  └────────────┘  └─────────┘  └────────────────┘
```

### 14.2 典型客户工程化落地步骤
1. **出厂**：拿到 HS-FS 设备（已有 TI 密钥）
2. **离线生成**：RSA-4096 密钥对 → SMPK/BMPK；随机 AES-256 → SMEK/BMEK
3. **OTP 配置证书**：用 TIFEK(pub) 加密 SMEK/BMEK；填入 Keywriter 证书
4. **生产烧写**：运行 Keywriter（UART/QSPI/JTAG），烧入 eFuse → HS-SE 转换
5. **镜像签名链**：为每份 SBL / HSM-RT / App 生成 X.509 证书 + 加密
6. **OTA/Flash**：把证书+镜像写入 SFLASH
7. **运行时**：HSM-RT 提供 TIFS/AUTOSAR-HSM 服务
8. **反回滚**：每次升版递增 SWRV_*，HSM-RT 负责烧 eFuse
9. **RMA**：失败设备返厂走 WIR 流程

### 14.3 启动时密钥使用的决策树
```
启动 SBL:
├─ GP       → 不认证，不解密
├─ HS-FS    → 不认证 SBL
└─ HS-SE    → 认证 SMPK/BMPK + 解密 SMEK/BMEK

启动 HSM-RT:
├─ GP                 → N/A
├─ HS-FS              → 认证 TI MPK + 解密 TI MEK
├─ HS-SE Prime        → 认证 SMPK/BMPK + 解密 SMEK/BMEK
└─ HS-SE Non-Prime    → 双证书
                        ├─ 外层：TI MPK 认证
                        └─ 内层：SMPK 认证 + SMEK 解密
```

---

## 附录 A  OID 速查表

| OID | 名称 |
|---|---|
| `1.3.6.1.4.1.294.1.1` | boot_seq |
| `1.3.6.1.4.1.294.1.2` | image_integrity |
| `1.3.6.1.4.1.294.1.3` | swrv |
| `1.3.6.1.4.1.294.1.4` | encryption |
| `1.3.6.1.4.1.294.1.5` | key_derivation |
| `1.3.6.1.4.1.294.1.8` | debug |
| `1.3.6.1.4.1.294.1.64` | KW: Encrypted AES |
| `1.3.6.1.4.1.294.1.65` | KW: Encrypted SMPK Signed AES |
| `1.3.6.1.4.1.294.1.66` | KW: Encrypted BMPK Signed AES |
| `1.3.6.1.4.1.294.1.67` | KW: AES Encrypted SMPKH |
| `1.3.6.1.4.1.294.1.68` | KW: AES Encrypted SMEK |
| `1.3.6.1.4.1.294.1.69` | KW: MPK Options（保留） |
| `1.3.6.1.4.1.294.1.70` | KW: AES Encrypted BMPKH |
| `1.3.6.1.4.1.294.1.71` | KW: AES Encrypted BMEK |
| `1.3.6.1.4.1.294.1.72` | KW: MEK Options（保留） |
| `1.3.6.1.4.1.294.1.73` | KW: AES Encrypted Extended OTP（保留） |
| `1.3.6.1.4.1.294.1.74` | KW: key revision (KEYREV) |
| `1.3.6.1.4.1.294.1.76` | KW: MSV |
| `1.3.6.1.4.1.294.1.77` | KW: key count |
| `1.3.6.1.4.1.294.1.78` | KW: SWREV hsmRT |
| `1.3.6.1.4.1.294.1.79` | KW: SWREV SBL |
| `1.3.6.1.4.1.294.1.80` | KW: SWREV APP |
| `1.3.6.1.4.1.294.1.81` | KW: version |

## 附录 B  SHA-512 相关 OID
| OID | 用途 |
|---|---|
| `2.16.840.1.101.3.4.2.3` | SHA-512（RFC 5754） |

## 附录 C  缩写表
| 缩写 | 全称 |
|---|---|
| ASN.1 | Abstract Syntax Notation One |
| BCH | Bose–Chaudhuri–Hocquenghem（纠错码） |
| BMEK | Backup Manufacture Encryption Key |
| BMPK | Backup Manufacture Public Key |
| CPFROM | Customer Programmable Fuse ROM |
| DER | Distinguished Encoding Rules |
| DTHE | Data Transfer Hash Engine |
| eFuse | Electronically Programmable Fuse |
| HKDF | HMAC-based Key Derivation Function |
| HSM | Hardware Security Module |
| HSM-RT | HSM Runtime Firmware |
| KEK | Key Encryption Key（设备级） |
| MEK | Manufacture Encryption Key |
| MPK | Manufacture Public Key |
| MSS | Main Subsystem |
| OTP | One-Time Programmable |
| PKA | Public Key Accelerator |
| RBL | ROM Boot Loader |
| SBL | Secondary Boot Loader |
| SECAP | Secure Access Port |
| SHE | Secure Hardware Extension |
| SMEK | Secondary MEK（客户对称根） |
| SMPK | Secondary MPK（客户非对称根） |
| SOCID | System-on-Chip Identifier |
| SOP | Sense-On-Power |
| TIFEK | TI Factory Encryption Key |
| TIFS | TI Foundational Security |
| UDID | Unique Device ID |
| WIR | Wait-In-Reset |
