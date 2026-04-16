# 芯片安全架构介绍 (Security Intro)

---

## 1. TI芯片级安全架构概览

软件/硬件分层（图例）：

![](.\image\1.png)

### 架构层次

#### 应用层
- **AutoSAR Customer Application Layer**（通过 AutoSAR CSM Interface 接入）
- **Broad Market Customer Application Layer**（通过 PKCS#11 Interface 接入）

#### 中间件层
- **AUTOSAR**：Crypto Services HSM Proxy
- **R5F**：PKCS#11 HSM Proxy

#### HSM 内部架构

| 模块 | 内容 |
|------|------|
| 启动 | Secure Boot |
| 系统 | Security Application、RTOS |
| 服务 | HSM Server、Crypto Drivers、Security Library、Secure Storage |
| 底层驱动 (SA Low Level Drivers) | AES、SHA、TRNG、PKA |
| 外设驱动 (Peripheral Drivers) | DMA、Timer、IRQ |
| 基础组件 | Infra Components |
| 硬件熔丝 | eFUSE、ROM |

---

## 2. AWR 系列芯片安全架构总结

### 安全特性

#### 安全启动 (Secure Boot)
确保只有经过**验证的软件**才能运行，防止恶意软件注入，建立从硬件到应用的链式信任。

#### 硬件加密 (HSM)
硬件加密加速器提供**高性能加密运算**，保护密钥安全，支持多种加密算法。

#### 安全存储 (Secure OTP)
一次性可编程存储器和 eFUSE 用于**存储密钥和敏感数据**，防止未经授权的访问。

#### 调试保护 (JTAG Lockout)
调试接口保护机制防止**未经授权的调试访问**，阻止逆向工程和攻击。

#### 固件更新 (Secure Flash)
安全固件更新机制确保**固件完整性和真实性**，支持 OTA 升级和漏洞修复。

#### 内存隔离 (Access Control)
内存隔离与访问控制机制**防止不同应用间数据泄露**，确保系统安全运行。

### 总结

采用**多层次安全架构设计**，从硬件层到应用层提供全方位保护。通过**安全启动**确保软件完整性，**硬件加密**保障数据机密性，**安全存储**保护密钥安全，**调试保护**防止未授权访问，**固件更新**支持漏洞修复，**内存隔离**确保系统稳定运行。

---

## 3. Secure Device Lifecycle（安全设备生命周期）

![](.\image\2.png)

```
Fresh device         TI Keys             Ship to            Deployment
from FAB    ─────►   Blown    ─────►    Customer   ─────►   in field
    │                   │                   │                   │
Device Type:        Device Type:        Device Type:
   TEST               HS-FS               HS-SE
  No Keys            TI Keys           Customer Keys
    │                   │                   │                   │
    ▼                   ▼                   ▼                   ▼
Complete Testing   Batch Rescreen –   Customer Returns    Field Returns
done before fusing    Re-Test          Testing, Debug     Testing, Debug
as Secure Device
```

| 阶段 | Device Type | 描述 |
|------|-------------|------|
| 出厂裸片 | TEST | 无任何密钥，FAB 完成测试后再熔写为 Secure Device |
| TI 烧入密钥 | HS-FS | TI 密钥已烧录，可批量重测 |
| 发货客户 | HS-SE | 客户密钥已注入，用于客户退回测试和调试 |
| 现场部署 | HS-SE | 部署到现场，支持现场退回测试和调试 |

---

## 4. HS → SE Solution (OTP Writer)

![](.\image\3.png)

### Controlled Delivery (HS-FS) Device

**TI OTP**:
- KEK (256b)
- TI Key Set：MPK hash / MEK w/ BCH

**Customer OTP**：空（待客户写入）

设备状态：Radar MCU 已烧录 TI Keys；通过 SW Package 和工具来烧录 Customer OTP。

### Customer Development and Production (HS-SE) Device

**TI OTP**（保持不变）:
- KEK (256b)
- TI Key Set：MPK hash / MEK w/ BCH

**Customer OTP**:
- Customer Key Set：SMPK hash / SMEK w/BCH
- Customer Back-up Key Set：BMPK hash / BMEK w/BCH

设备状态：客户密钥已通过 TI 提供的 SW package 和工具写入设备；**TI Keys 失效，后续不再使用**。

---

## 5. HSM Lifecycle

### 状态对照表

| HSM LC State | SoC LC State | 备注 |
|--------------|--------------|------|
| NA (0xFF) | HS-FS | HSMRT 未启动 |
| HSM LC Invalid (0) | HS-FS → HS-SE | Onboard Flash 使能 OTP，FS 变为 SE |
| HSM LC Manufacturing (1) | HS-SE | 工厂状态 |
| HSM LC Development (4) | HS-SE | JTAG unlocked，无需授权即可调试 |
| HSM LC Operation (2) | HS-SE | JTAG locked，series 量产状态 |
| HSM LC Return (3) | HS-SE | — |
| HSM LC Decommission (5) | HS-SE | — |

### 生命周期流转

![](.\image\4.png)


### 样品标识

- **C0** : FS
- **C1** : LC Dev
- **D**  : LC Series

---

## 6. Secure Boot Sequence（启动序列）

![](.\image\5.png)

### 启动后的运行模式

- **默认**：App → CustApp / ProductionAPP
- **安全帧**：PFBoot
- **安全帧**：CustBoot
- ![](.\image\6.png)

---

## 7. Secure Boot Sequence（验证流程详解）

### 启动验证流程

**1. 启动 ROM 执行**
芯片上电后，**Boot ROM** 开始执行，验证第一级引导加载程序 (Boot Manager) 的签名。

**2. Boot Manager 验证**
Boot Manager 验证 **PFBoot** 的完整性和真实性。

**3. PFBoot 验证**
PFBoot 验证升级 App、custboot 的数字签名。

### 安全保障机制

- **密钥验证**：使用 **RSA/ECC 算法**验证数字签名，确保固件来源可信
- **哈希校验**：使用 **SHA-256** 等哈希算法验证固件完整性
- **信任链建立**：从硬件根信任开始，逐级验证，建立完整的**信任链**
- **失败处理**：任何阶段验证失败都会**停止启动**，防止恶意软件运行

---

## 8. Secure Boot Process（详细时序图）

![](.\image\7.png)

---

## 9. Secure Flash

### Block Define

![](.\image\8.png)

![](.\image\9.png)

> 每个 Block 大小为 **64 KB**

| Block Name | Flash Block |
|------------|-------------|
| Boot Manager | Block 0 – 1 |
| PFBoot | Block 2 – 4 |
| CustBoot | Block 5 – 8 |
| CustApp | Block 9 – 40 |
| ProductionApp | Block 9 – 40 |
| Calibration Data | Block 51 |

### 📝 Block Define 格式

| 重要字段 | 说明 |
|------|------|
| start flag | 启动标志 |
| header | 文件头信息 |
| security info | 安全信息 |
| hash of data | 数据哈希值 |
| secure boot signature | 安全启动签名 |
| secure flash signature | 安全烧录签名 |
| 💾 data | 实际数据内容 |

### **FLASH Layout**

![](.\image\10.png)

###  更新安全要求

- **格式定义**：flash 文件需统一按照 block define 格式定义
- **签名要求**：文件需进行签名 (secure boot + flash)
- **地址遵守**：文件在 flash 地址需严格遵守 flash layout
- **云端安全**：更新包签名、密钥管理、版本控制
- **安全传输**：数据完整性保护
- **安全验证**：签名验证、完整性检查、安全存储、防回滚

---

## 10. 密钥管理

###  KMS（Key Management System）密钥管理系统

**系统概述**：服务器在博世德国，主要负责密钥的生命周期管理以及作为后端服务响应来自 PKS 的密钥请求。**所有的根密钥都来源于此**。

| 功能 | 说明 |
|------|------|
| 🔑 根密钥管理 | 生成和保护根密钥 |
| ⚙️ 生命周期管理 | 密钥生成、分发、吊销 |
| 🌐 后端服务 | 响应 PKS 密钥请求 |

###  PKS（Production Key Server）生产密钥服务器

**系统概述**：面向工厂，生产的执行前端，目前产线连接的都是 PKS。负责从 KMS 获取密钥并注入到设备中。

| 功能 | 说明 |
|------|------|
| 工厂前端 | 面向生产线的执行端 |
| 密钥获取 | 从 KMS 获取密钥 |
| 密钥注入 | 注入密钥到设备 |

###  密钥管理架构

KMS 和 PKS 构成**两级密钥管理体系**：

- **KMS** 作为**根密钥管理中心**，负责生成和保护所有根密钥；
- **PKS** 作为**生产执行前端**，面向工厂生产线，从 KMS 获取密钥并注入到设备中。

这种架构既保证了密钥的**安全性**，又满足了生产的**效率要求**，实现了密钥全生命周期的安全管理。

### **部分代码附录**

![](.\image\11.png)

![](.\image\12.png)

![](.\image\13.png)

![](.\image\14.png)

### **注意**

1.闭口件切lifecycle之前是可以刷回去的。

2.切完lifecycle之后没有办法切回去，除非用串口刷magic value后才能重刷 

```
# LifeCycle Magic Num
--file=D:/LocalCR/binaray/mytest/dev0905/Padding_Magic_Value.bin --operation=flash --flash-offset=0x3E0000
```

1. 烧写lifecycle magic number 到0x3E'2000-0x3E'2FFF [Padding_LC_Magic_Value.bin](https://inside-docupedia.bosch.com/confluence/download/attachments/6207409718/Padding_LC_Magic_Value.bin?version=1&modificationDate=1756804038000&api=v2) （注意: uniflash烧写需要从0x3E0000开始，因此[Padding_LC_Magic_Value.bin](https://inside-docupedia.bosch.com/confluence/download/attachments/6207409718/Padding_LC_Magic_Value.bin?version=1&modificationDate=1756804038000&api=v2)的前8K pad了FF） 

2. 切HSM LC 为HSM_LC_Manufactoring（01）           

​				1003->1060           

​				2763 get challenge （challenge的实际字节数会根据项目会有所改变，challenge实际长度开发给一下？）           				2764 send respond （真正的respond，填充成2000字节） 

​		截断规则：  2763 get challenge （challenge的实际字节数会根据项目会有所改变，challenge实际长度开发给一下？或者自己					算一下，比如3081BFxxxx，实际challenge长度是0xBF+3 = 194)）            2764 send respond （真正的	respond，填充成2000字节）

3. hard reset 

4. 读lifecycle  1003->1060->22FD15， 是否回 62 FD15 0102 

5. 5. 切HSM LC 为量产状态，HSM_LC_Operation（02）  

       1003->1060-> 2761 -> 2762(内容无所谓,长度要对，2000字节)->2E FD15 0200 

6. hard reset 

7. 读lifecycle  1003->1060 ->22FD15， 是否回 62 FD15 0203 
8. 清lifecycle magic number（31 01 FD00）

-------------------------------------------------------------------------------

​			FD15	R/W	2	 

lifecycle切换 R: Byte0 HSM lifecycle, Byte1 ECU LC 

​		      W:Byte0 HSM lifecycle, Byte1 Reserved

-------------------------------------------------------------------------------

### **密钥说明**

**私钥放在服务器 公钥放在板子里进行解密**

**efuse里存的是HASH值**

![](.\image\15.png)

**动态修改key**- 为了满足部分客户需求

1.因为有secure boot存在，所以芯片上运行的程序是完全可信的。 

2.可以将客户的key通过efuse中的某个aes key加密之后存储到flash中。 

3.每次上电后之后将key从flash中读出解密存储到ram中，可以用PMP对相应的ram加个读写保护。 这一切的前提是认为有了secure boot，所以所有运行在该芯片上的程序和数据都是安全的，不会被盗取。

**RSA2048 ** -（非对称加密，公钥+私钥）：数量很少（通常 1~5 对）

- **Secure Boot (安全启动)**：雷达上电时，为了验证各级Bootloader、FreeRTOS/Linux内核以及应用程序的完整性，设备端通常只需存 **1个** OEM或Tier 1的**根公钥 (Root Public Key)**。私钥在外部服务器严格保管，雷达端绝对不存。

- **身份认证与TLS/IPsec握手**：雷达作为一个网络节点（比如连入车载以太网），需要证明“我是合法的雷达”。此时设备里会烧录 **1对** 唯一的设备密钥对（Device Key）。私钥保存在雷达本地，公钥生成证书发给其他节点。

- *注：现在车载领域为了性能，非对称加密越来越倾向于使用 ECC（如 ECDSA / Ed25519），RSA 更多停留在 Secure Boot 阶段。*

**AES-256（对称加密）：数量庞大且动态（少则几十，多则上百）**

- **主密钥 (Master Key)**：通常只有 **1~2 个**，作为“密钥的密钥”，用于推导其他工作密钥。
- **SecOC (安全车载通讯) 密钥**：雷达和主控（如ADAS域控）交互时，每条关键报文（如目标级数据、控制指令）的认证都需要MAC（基于AES-CMAC）。这可能会按照通信流分配**多个**密钥。
- **会话密钥 (Session Keys)**：在系统运行时，由非对称算法（如RSA/ECDHE）协商生成的临时 AES 密钥。这些密钥驻留在 RAM 中，每次上电或固定周期（如几十毫秒到几分钟）就会轮换一次。

**密钥可以存在HSM/HSE以及Secure NVM或者OTP/Efuse,绝对不会存在应用核(CortexA53或者M4)能直接访问的普通的Flash或者RAM里。**

### Hash 有什么关系？

Hash（如 SHA-256）和加密密钥是**配合工作**的关系，各司其职：

- **数字签名（配合 RSA）**：非对称加密很慢，通常不能直接用 RSA 去加密整个雷达固件或几百兆的数据。我们是先用 Hash 算法把固件跑出一个 32 字节的**摘要 (Digest)**，然后再用 RSA 私钥对这个摘要进行加密，生成**签名**。雷达启动时，先自己算一遍 Hash，再用公钥解密签名对比，一致才允许启动。
- **消息认证码 MAC（配合 AES）**：在 SecOC 中，发送方用 AES 密钥对“报文+Hash”计算出一个 MAC 值附加在报文后。接收方用同样的 AES 密钥算一遍来校验。这保证了数据没被篡改。
- **密钥推导 (KDF)**：利用 Hash 算法（通常是 HMAC-SHA256）从一个主密钥中衍生出成百上千个工作密钥。

### 存储的是 Hash 还是密钥值？

这是一个常见的误区，答案是：**必须存储密钥值本身的二进制流**，但也存在只存 Hash 的特殊情况。

- **AES 和 RSA 密钥：存的是真实的密钥值。** 因为加密和解密是数学运算，你如果只存了 AES 密钥的 Hash，你是无法逆向还原出密钥去解密数据的（Hash 是单向不可逆的）。所以 HSM 的安全存储区里，存放的是实打实的 256-bit 或 2048-bit 的高熵随机数。
- **密码 (Password) vs 密钥 (Key)**：如果是人的密码（比如进入 debug 模式的密码），系统里存的是密码的 **Hash 值**。输入密码后，系统算一个 Hash 和存的 Hash 比对。但雷达信息安全里的对称/非对称 Key，必须存原值。
- **特例（Golden Hash）**：为了节省昂贵的 eFuse 空间，有时候 OEM 不会把 256 字节的 RSA 根公钥直接烧在硬件熔丝里。而是把 RSA 根公钥放在普通的 Flash 里，然后在 eFuse 里烧录这个**公钥的 Hash 值**。上电时，硬件先计算普通 Flash 里公钥的 Hash，如果和 eFuse 里的一致，就信任这个公钥，再用它去验启动代码。

![](.\image\16.png)

### **CR60SE**

![](.\image\17.png)

![](.\image\18.png)

![](.\image\19.png)

![](.\image\20.png)

![](.\image\21.png)

![](.\image\22.png)

![](.\image\23.png)
