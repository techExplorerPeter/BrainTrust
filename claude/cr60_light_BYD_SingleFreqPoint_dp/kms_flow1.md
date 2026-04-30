╭─── Claude Code v2.1.119 ─────────────────────────────────────────────────────╮
│                                                    │ Tips for getting        │
│               Welcome back PeterZhu!               │ started                 │
│                                                    │ Run /init to create a … │
│                       ▐▛███▜▌                      │ ─────────────────────── │
│                      ▝▜█████▛▘                     │ Recent activity         │
│                        ▘▘ ▝▝                       │ No recent activity      │
│ Sonnet 4.6 · Claude Pro · peterzhu0312@gmail.com's │                         │
│  Organization                                      │                         │
│ D:\Weifu\Project\CR\BYD_RL\cr60_light_BYD_SingleF… │                         │
╰──────────────────────────────────────────────────────────────────────────────╯

✻ Conversation compacted (ctrl+o for history)

  ⎿  Read ..\..\..\hex2bin.py (38 lines)
  ⎿  Read ..\..\ContainerGen\dummy_KMS_Signning.py (95 lines)
  ⎿  Read make_dummy_root.py (133 lines)
  ⎿  Read ..\..\ContainerGen\ContainerGen_preprocess.py (155 lines)
  ⎿  Referenced file ..\..\ContainerGen\BlockProcessor.py
  ⎿  Skills restored (init)

● 让我先读几个关键文件来给出准确的答案。

  Searched for 7 patterns, read 8 files, listed 1 directory (ctrl+o to expand)

● 现在我有了所有需要的信息，可以给出完整的解答了。

  ---
  JTAG 解锁机制 — 完整说明

  在这个项目里，JTAG 解锁分 两个独立层次，对应硬件启动链的两个层。

  ---
  层 1：TI ROM 层 — eFUSE + X.509 Debug Extension

  这一层在 芯片上电、ROM 执行 BootManager 时生效，直接决定 JTAG
  引脚是否物理可用。

  控制参数：certificateConfig_BM.cfg:32

  # -1: 不添加 debug extension（JTAG 完全由 eFUSE 决定）
  #  0: Debug port disabled（量产必须用这个）
  #  1: SoC 默认（基于 device type）
  #  2: Public debug enabled（仅 HS-SE 开发阶段，量产禁止）
  DEVICE_DEBUG_TYPE = -1

  当前配置 -1：不向 BM X.509 证书中注入 debug extension，JTAG 访问权限完全由
  eFUSE 烧录时的 coreDbgEn/coreDbgSecEn 字段决定。

  如需开发期打开 JTAG：
  1. 改 DEVICE_DEBUG_TYPE = 2
  2. SoC_UID = ../localCR_DevKeys/socUID.txt → 该 64 字节 UID 会嵌入证书的
  debugUID 字段（设备专属，防止证书通用化）
  3. 重新用 TI_secure_boot_certificate_gen_kms.py 生成并签名 BM
  4. 烧写含新证书的 BM → ROM 解析证书，打开 JTAG

  ---
  层 2：HSM 层 — JTAG Password 认证

  这一层是 HSM Firmware 在运行时的 JTAG 密码保护，即使 TI ROM 层放开了 JTAG
  引脚，也需要先过这关。这是本项目重点使用的机制。

  密钥来源

  # tools/Security/kms_tools/kms_keys.cfg
  [jtag_pw_keyinfo]
  kms_service = PBDP        ← Bosch KMS PBDP 密钥派生服务
  key_id      = 1186147     ← KMS 中的根密钥 ID
  label       = Label
  context     = ECU_DMC     ← 派生上下文标识（ECU Device Master Credential）
  length      = 32          ← 256-bit 密码

  量产时通过 Bosch KMS PBDP（Password-Based Derivation Protocol）从 root key
  1186147 + context ECU_DMC 派生出 32 字节 JTAG 密码，本地开发版本就是：

  tools/Security/localCR_DevKeys/JTAG_PWD_Dev.txt  →
  d175b74a77c8660aa7032b4e652f2eb3710f08afb33d153a063f5a13092a9a7c
  tools/Security/localCR_DevKeys/JTAG_PWD_Dev.bin  → 对应的二进制（32 字节）
  tools/Security/localCR_DevKeys/JTAG_PWD_Dev_Hash.txt  → SHA-512 哈希，烧入
  eFUSE/HSM

  解锁流程（Trace32 执行 .cmm 脚本）

  脚本 tools/Security/Jtag_UnlockingScripts/OpenJtagByPassword.cmm，通过
  SECAP（Security Awareness Protocol） 寄存器组与 HSM 通信：

  SECAP_TX_DATA = 0x40000800   发送数据
  SECAP_TX_CTRL = 0x40000804   发送控制
  SECAP_RX_DATA = 0x40000808   接收数据
  SECAP_RX_CTRL = 0x4000080C   接收控制

  完整握手序列：

  1. Trace32 进入 SYStem.Mode.Prepare（半连接状态，JTAG
  时钟可走但不能读写寄存器）
  2. 等待 500ms（HSM Firmware 启动完成）
  3. 发送 Feature Request: 0xC0DE0001（申请"密码解锁 JTAG"功能）
  4. HSM 回应 2（FEATURE_ID_ACCEPTED）
  5. Sync 序列：连发 3× 0xFACEDEAD，HSM 回 0xC0DEC0DE（同步完成）
  6. 发送 256-bit 密码：8× 32-bit word（来自 Host_JTAG_pasword.txt，/LongSWAP
  格式）
  7. HSM 验证密码（对比 eFUSE 中烧录的 SHA-512 Hash）
     - 匹配 → 回 0xACEFACED（PASS_ACCEPTED），然后 SYSTEM.ATTACH
     - 不匹配 → 回 0x1BADC0DE（PASS_INCORRECT），JTAG 保持锁定

  操作步骤：

  1. 把正确的密码（hex 格式）写入:
     tools/Security/Jtag_UnlockingScripts/Host_JTAG_pasword.txt

     开发版密码 = JTAG_PWD_Dev.txt 的内容：
     d175b74a77c8660aa7032b4e652f2eb3710f08afb33d153a063f5a13092a9a7c

  2. 在 Trace32 中运行:
     DO OpenJtagByPassword.cmm

  3. 看到 "Password accepted, Host JTAG port opened" 后，Trace32 自动
  SYSTEM.ATTACH

  ---
  层 3：UDS 诊断层 — Security Access（运行时，非 JTAG 本身）

  这一层不直接控制 JTAG 引脚，而是 通过 CAN/车载总线的 UDS 协议管理 ECU 
  的调试权限（DiaBoschSecurity.c）。

  ┌───────────────────┬───────────────┬─────────────────────────────────────┐
  │       Level       │   适用状态    │                算法                 │
  ├───────────────────┼───────────────┼─────────────────────────────────────┤
  │                   │ NoSecurity /  │                                     │
  │ L31               │ OnBoard /     │ 简单时间种子                        │
  │ (Dia_GetSeed_L31) │ Customizing / │ (rbDiaSecurityAccess_GetSeed)       │
  │                   │  Development  │                                     │
  ├───────────────────┼───────────────┼─────────────────────────────────────┤
  │                   │ Operation /   │ CycurSoC 挑战响应                   │
  │ L31 in Operation+ │ Return /      │ (rbDiaSecurityAccess_GetChallenge,  │
  │                   │ Decommission  │ UseCase=0)                          │
  ├───────────────────┼───────────────┼─────────────────────────────────────┤
  │ L32               │ 全生命周期    │ CycurSoC 挑战响应 (UseCase=1)，10   │
  │ (Dia_GetSeed_L32) │               │ 次失败 → 锁定 30 秒                 │
  └───────────────────┴───────────────┴─────────────────────────────────────┘

  认证成功后 authenticatedStatus = TRUE，30 
  秒超时后自动清零（DiaBoschSecurity_StateMachine case 1，counter 3000 ×
  10ms）。

  ---
  整体关系图

  上电
   │
   ▼
  TI ROM（Layer 1）
   ├─ 读 BM X.509 证书的 debug extension（OID 294.1.8）
   ├─ DEVICE_DEBUG_TYPE = -1 → 不注入，eFUSE 说了算
   └─ eFUSE coreDbgEn=0 → JTAG 物理锁定
           ↓ coreDbgEn=1 → JTAG 引脚可用，进入 Layer 2 ↓

  HSM Firmware（Layer 2）— SECAP 密码验证
   ├─ Trace32 运行 OpenJtagByPassword.cmm
   ├─ 发送 JTAG_PWD_Dev（32 字节，KMS key 1186147/ECU_DMC 派生）
   └─ HSM 对比 eFUSE 中的 SHA-512 Hash
           ✓ → SYSTEM.ATTACH 成功，可以打断点、读内存
           ✗ → 保持锁定

  运行时（Layer 3）— UDS L31/L32
   └─ 通过 CAN 诊断管控 ECU 权限（与 JTAG 引脚无关）

  开发阶段实际操作：开发版 ECU 通常 eFUSE 允许 JTAG（Layer 1 通过），主要用
  Layer 2 密码认证保护。把 JTAG_PWD_Dev.txt 的内容填入
  Host_JTAG_pasword.txt，运行 OpenJtagByPassword.cmm 即可完成 JTAG 解锁。

✻ Crunched for 4m 24s

> /export kms_flow.md                                                           
  ⎿  Conversation exported to: D:\Weifu\Project\CR\BYD_RL\cr60_light_BYD_SingleF
     reqPoint_dp\tools\Security\CVC_Validator\kms_flow.md

> 这几对密钥分别是用来干什么的 作用是什么                                       

  Searched for 5 patterns, read 1 file, listed 1 directory (ctrl+o to expand)

● 现在信息完整，可以给出清晰的说明了。

  ---
  localCR_DevKeys 密钥总览

  共 5 组密钥，分属三个安全层，用途完全不同。

  ---
  一、TI ROM 层（Layer 1）— BootManager / HSM 镜像保护

  SMPK_Pri_Dev.pem + SMPK_Pub_Dev.pem/.der + SMPK_Pub_Dev_Hash.txt

  Secondary Manufacture Public Key — 客户主签名密钥对

  - 用途：对 BootManager 和 HSM 的 TI X.509 启动证书进行签名
  - 私钥（Pri）在 PC 上用 TI_secure_boot_certificate_gen
  工具签名，公钥哈希（Hash）烧入芯片 eFUSE
  - 芯片上电时 TI ROM 从 eFUSE 读出哈希，验证证书中的公钥，再用公钥验证 BM
  镜像完整性
  - 量产等价：KMS Key 6479253（Boot_sign_BmAndHsm）

  BMPK_Pri_Dev.pem + BMPK_Pub_Dev.pem/.der + BMPK_Pub_Dev_Hash.txt

  Back-up Manufacture Public Key — 备份签名密钥对

  - 用途：SMPK 泄露/失效后的紧急备份，功能与 SMPK 完全相同
  - 公钥哈希同样烧入 eFUSE（另一组 fuse 位），平时不用
  - 一旦启用 BMPK 撤销 SMPK（通过 OTP keywriter 配置 SMPKREV=1），ROM 改从
  BMPK_Hash 验证证书

  SMEK_Dev.txt（32 字节 AES-256 密钥）

  Secondary Manufacture Encryption Key — BM/HSM 镜像加密密钥

  - 用途：加密 BootManager 和 HSM 固件镜像本身（AES-CBC/CTR，TI ROM 负责解密）
  - 明文存在 certificateConfig_BM.cfg 里，由证书生成工具写入 X.509 加密扩展
  - 量产等价：KMS PBDP 服务 Key 1186142，context=SMEK 派生

  BMEK_Dev.txt（32 字节 AES-256 密钥）

  Back-up Manufacture Encryption Key — BM/HSM 加密备份密钥

  - SMEK 的备份，与 BMPK 配对使用，当前项目中备用（BMEK_Dev.key
  是相同内容的二进制格式）

  ---
  二、Bosch SwBlock 层（Layer 2）— CustApp / CLDA / CustBoot 等保护

  HOST_SB_Pri_Dev.pem + HOST_SB_Pub_Dev.pem

  Host Secure Boot Key — SwBlock BootSig 签名密钥

  - 用途 1 (BootSig)：对 SwBlock 头部前段数据签名，ECU 启动时由 HSM
  验证，防止篡改
  - 用途 2 (CVC Root)：作为 CVC 证书链的根私钥，给 OtaCrt（用户 CVC 证书）的
  body 签名
  - 量产等价：KMS Key 6479283（Boot_sign_App）
  - 本地 dummy 版：Dummy_Root.der 就是用这对密钥生成的自签名根证书

  CLDA_FLAH_Pri_Dev.pem + CLDA_FLAH_Pub_Dev.pem

  CLDA Flash Key — SwBlock OtaSig + OtaCrt 密钥

  - 用途 1 (OtaSig)：对 SwBlock 全部数据（含 payload）签名，OTA 时 ECU
  验证，防止替换
  - 用途 2 (OtaCrt 持有者)：公钥被嵌入 SwBlock 的 OtaCrt 字段（用户 CVC
  证书），证明这个签名者的合法性
  - 两者关系：HOST_SB_Pri 签发 OtaCrt（内含 CLDA_FLAH_Pub），CLDA_FLAH_Pri
  做实际的数据签名，ECU 先验 CVC 链再验数据签名
  - 量产等价：KMS Key 6476702（SecFlash_sign）

  HostSEK_Dev.txt（32 字节 AES-256 密钥）

  Host Software Encryption Key — CustApp 加密密钥

  - 用途：对 04_CustApp、04_CustBoot 等 SwBlock 的有效载荷进行 AES-GCM 加密
  - 量产等价：KMS PBDP 服务 Key 1186143，context=HostSEK 派生
  - 注意：CLDA（09_ClibData）不加密，只有 --boot --flash 签名

  ---
  三、JTAG 层

  JTAG_PWD_Dev.txt/.bin（32 字节密码）+ JTAG_PWD_Dev_Hash.txt（SHA-512）

  JTAG 解锁密码

  - 用途：通过 SECAP 寄存器组向 HSM 提交密码，通过验证后 HSM 打开 JTAG 引脚
  - 哈希值烧入 HSM eFUSE，HSM 上电后验证提交密码的哈希
  - 量产等价：KMS PBDP 服务 Key 1186147，context=ECU_DMC 派生

  socUID.txt（64 字节设备唯一 ID）

  芯片唯一标识符

  - 非密钥，是特定芯片的 UID
  - 用于 TI X.509 证书的 debugUID 字段（DEVICE_DEBUG_TYPE ≠ -1 时），将 JTAG
  debug 权限绑定到该具体芯片，防止证书被挪用

  ---
  汇总表

  ┌──────────┬─────────┬────────┬────────────────────────┬────────────────┐
  │   密钥   │  类型   │ 所属层 │          作用          │ 量产 KMS 等价  │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │          │ RSA-409 │        │ BM/HSM X.509证书签名+e │                │
  │ SMPK     │ 6       │ TI ROM │ FUSE验证               │ Key 6479253    │
  │          │ 非对称  │        │                        │                │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │          │ RSA-409 │        │                        │                │
  │ BMPK     │ 6       │ TI ROM │ SMPK 备份              │ —              │
  │          │ 非对称  │        │                        │                │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │ SMEK     │ AES-256 │ TI ROM │ BM/HSM 镜像加密        │ Key            │
  │          │  对称   │        │                        │ 1186142/SMEK   │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │ BMEK     │ AES-256 │ TI ROM │ SMEK 备份              │ —              │
  │          │  对称   │        │                        │                │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │          │ RSA-409 │ SwBloc │                        │                │
  │ HOST_SB  │ 6       │ k      │ BootSig + CVC Root签名 │ Key 6479283    │
  │          │ 非对称  │        │                        │                │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │ CLDA_FLA │ RSA-409 │ SwBloc │                        │                │
  │ H        │ 6       │ k      │ OtaSig + OtaCrt 持有者 │ Key 6476702    │
  │          │ 非对称  │        │                        │                │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │ HostSEK  │ AES-256 │ SwBloc │ CustApp payload        │ Key 1186143/Ho │
  │          │  对称   │ k      │ AES-GCM加密            │ stSEK          │
  ├──────────┼─────────┼────────┼────────────────────────┼────────────────┤
  │ JTAG_PWD │ 256-bit │ HSM    │ JTAG 密码解锁          │ Key 1186147/EC │
  │          │  密码   │        │                        │ U_DMC          │
  └──────────┴─────────┴────────┴────────────────────────┴────────────────┘

  核心关系：SMPK/SMEK 保护 Layer 1（谁能启动芯片），HOST_SB/CLDA_FLAH/HostSEK
  保护 Layer 2（谁能更新固件），两层完全独立，各有自己的信任根。

✻ Churned for 1m 8s

> /export kms_flow1.md                                                          
  ⎿  Conversation exported to: D:\Weifu\Project\CR\BYD_RL\cr60_light_BYD_SingleF
     reqPoint_dp\tools\Security\CVC_Validator\kms_flow1.md

> 非常好 那每一个密钥都是怎么产生的呢                                           

● 让我先看看项目中有没有密钥生成脚本。

  Searched for 4 patterns, read 3 files (ctrl+o to expand)

● 现在我有了足够的信息，来给出详尽的密钥生成说明。

  ---
  每个密钥的生成方式

  整个密钥体系分两套并行：量产密钥（KMS 生成，不可导出） 和
  本地开发密钥（OpenSSL 生成，用于调试）。

  ---
  一、RSA 非对称密钥对（SMPK / BMPK / HOST_SB / CLDA_FLAH）

  量产版（Bosch KMS）

  私钥 从不离开 Bosch KMS 的 HSM 硬件模块，只能通过智能卡 PIN 授权后调用签名
  API：

  # kms_sign_mcu.py — 实际签名调用
  kms = proxy.SigningProxy()
  kms.set_pin(smart_card_pin)          # 智能卡 PIN 鉴权
  signer = KmsRsaSigner(key_id=6479283, hash_algo="SHA512", padding="PKCS_V1_5")
  signature = signer.sign_data(data=buf)   # 私钥在 HSM 
  内部运算，结果只返回签名值

  KMS 中的 Key ID 对应关系：
  SMPK  ←→  Key 6479253  (Boot_sign_BmAndHsm)
  HOST_SB ←→ Key 6479283  (Boot_sign_App)
  CLDA_FLAH ←→ Key 6476702 (SecFlash_sign，走 ECUPKI 接口)

  公钥可以通过 signer.get_public_cert() 从 KMS 读取（用于后续 hash 计算和 eFUSE
  烧录）。

  开发版（本地 OpenSSL）

  # 1. 生成 RSA-4096 私钥（.pem）
  openssl genrsa -out SMPK_Pri_Dev.pem 4096
  openssl genrsa -out BMPK_Pri_Dev.pem 4096
  openssl genrsa -out HOST_SB_Pri_Dev.pem 4096
  openssl genrsa -out CLDA_FLAH_Pri_Dev.pem 4096

  # 2. 提取公钥（PEM 格式）
  openssl rsa -in SMPK_Pri_Dev.pem -pubout -out SMPK_Pub_Dev.pem
  openssl rsa -in HOST_SB_Pri_Dev.pem -pubout -out HOST_SB_Pub_Dev.pem
  # 以此类推...

  # 3. 转换公钥为 DER 格式（TI 工具链需要 DER）
  openssl rsa -in SMPK_Pub_Dev.pem -pubin -outform DER -out SMPK_Pub_Dev.der
  openssl rsa -in BMPK_Pub_Dev.pem -pubin -outform DER -out BMPK_Pub_Dev.der

  公钥哈希文件（SMPK_Pub_Dev_Hash.txt / BMPK_Pub_Dev_Hash.txt）

  这两个文件是 eFUSE 烧录值的来源，ROM 启动验签时对比的就是这个哈希：

  # 提取 RSA 公钥 modulus 二进制，计算 SHA-512
  openssl rsa -in SMPK_Pub_Dev.pem -pubin -modulus -noout \
    | sed 's/Modulus=//' | xxd -r -p | openssl dgst -sha512

  实际项目中这一步由 TI_secure_boot_certificate_gen.py 内部自动完成并写入 X.509
  证书的 OTP keywriter 扩展字段。

  ---
  二、AES 对称密钥（SMEK / BMEK / HostSEK）

  量产版（KMS PBDP 派生）

  不是随机生成，而是从一个 根密钥通过 PBDP（Password-Based Derivation 
  Protocol）确定性派生，保证同一个 ECU 每次派生结果一致：

  # kms_keyderive_mcu.py
  kms_pbdp = proxy1.PbdpProxy()
  kms_pbdp.set_pin(smart_card_pin)
  key = kms_pbdp.get_password_from_keyid(
      key_id=1186143,          # 根密钥 ID
      label=b"Label",
      context=b"HostSEK",      # 派生上下文，不同上下文→不同密钥
      password_len=32          # 输出 256-bit
  )

  三个 AES 密钥的派生参数：

  ┌─────────┬────────────────────────────┬─────────┐
  │  密钥   │      KMS root key_id       │ context │
  ├─────────┼────────────────────────────┼─────────┤
  │ SMEK    │ 1186142                    │ SMEK    │
  ├─────────┼────────────────────────────┼─────────┤
  │ HostSEK │ 1186143                    │ HostSEK │
  ├─────────┼────────────────────────────┼─────────┤
  │ BMEK    │ （SMEK 的 backup，同一根） │ —       │
  └─────────┴────────────────────────────┴─────────┘

  开发版（随机生成）

  # 生成 32 字节随机 AES 密钥（hex 文本格式）
  openssl rand -hex 32 > SMEK_Dev.txt
  openssl rand -hex 32 > HostSEK_Dev.txt
  openssl rand -hex 32 > BMEK_Dev.txt

  # 同时生成对应的二进制格式（部分工具需要 .key 文件）
  cat SMEK_Dev.txt | xxd -r -p > SMEK_Dev.key
  cat BMEK_Dev.txt | xxd -r -p > BMEK_Dev.key

  ---
  三、JTAG 密码（JTAG_PWD）

  量产版（KMS PBDP 派生，绑定到具体设备）

  key = kms_pbdp.get_password_from_keyid(
      key_id=1186147,
      label=b"Label",
      context=b"ECU_DMC",   # Device Master Credential — 每台 ECU 通过 socUID 
  绑定
      password_len=32
  )

  量产时每台 ECU 的 JTAG 密码通常通过将 socUID（芯片唯一
  ID）混入派生上下文来实现设备绑定，避免一个密码通杀所有 ECU。

  开发版（随机生成 + SHA-512 哈希）

  # 1. 随机 32 字节密码
  openssl rand -hex 32 > JTAG_PWD_Dev.txt
  cat JTAG_PWD_Dev.txt | xxd -r -p > JTAG_PWD_Dev.bin

  # 2. 计算 SHA-512 哈希（烧入 eFUSE/HSM 的是哈希，不是明文）
  cat JTAG_PWD_Dev.bin | openssl dgst -sha512 | awk '{print $2}' >
  JTAG_PWD_Dev_Hash.txt

  ECU 上电后 HSM 验证：SHA-512(提交的密码) == eFUSE 中存储的 Hash

  ---
  四、socUID.txt（设备唯一 ID）

  不是密钥，是从芯片中读出来的：

  # 通过 Trace32 / JTAG 从 AWR2X44P 的 eFUSE 区域读取唯一 ID
  # 或由 TI 出厂时写入，通过专用工具导出
  # 文件格式：64 字节十六进制 ASCII

  在 certificateConfig_BM.cfg:35 中配置：SoC_UID = 
  ../localCR_DevKeys/socUID.txt，用于 X.509 debug extension 的 debugUID 字段（将
   JTAG 权限绑定到该具体芯片）。

  ---
  完整生成流程图

  【量产密钥建立（一次性，工厂离线操作）】

  Bosch KMS HSM
    ├─ 生成 RSA-4096 密钥对（不可导出）
    │     SMPK  (Key 6479253)  ─── 公钥导出 → eFUSE SHA-512 Hash
    │     BMPK  (Key backup)   ─── 公钥导出 → eFUSE SHA-512 Hash
    │     HOST_SB (Key 6479283) ── 公钥导出 → CVC Root 证书
    │     CLDA_FLAH (Key 6476702) 公钥导出 → CVC User 证书
    │
    └─ 持有 KDF Root Keys
          Key 1186142  ─PBDP/SMEK──→  SMEK（32B，写入 BM/HSM X.509证书扩展）
          Key 1186143  ─PBDP/HostSEK→ HostSEK（32B，SwBlock AES-GCM加密）
          Key 1186147  ─PBDP/ECU_DMC→ JTAG_PWD（32B，SHA-512→eFUSE）

  【开发密钥建立（openssl 本地生成，一次性）】

  openssl genrsa 4096
    → SMPK_Pri_Dev.pem + SMPK_Pub_Dev.pem + SMPK_Pub_Dev.der + Hash.txt
    → HOST_SB_Pri_Dev.pem + HOST_SB_Pub_Dev.pem
    → CLDA_FLAH_Pri_Dev.pem + CLDA_FLAH_Pub_Dev.pem
    → BMPK_Pri_Dev.pem + ...

  openssl rand -hex 32
    → SMEK_Dev.txt  / BMEK_Dev.txt  / HostSEK_Dev.txt
    → JTAG_PWD_Dev.txt → SHA-512 → JTAG_PWD_Dev_Hash.txt

  核心区别：量产密钥私钥永远在 KMS HSM
  内部，工程师只能触发签名操作；开发密钥私钥在本地磁盘上，仅用于无 KMS
  网络的本地联调。

✻ Worked for 1m 21s

> /plugin                                                                       
  ⎿  (no content)