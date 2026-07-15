# NeuSAR技术协议 V1.5 签署前修改清单

## 一、必须纳入合同的范围澄清

1. **责任边界**：甲方提供并维护射频/mmWave、信号处理、数据处理及算法应用代码；乙方负责将其集成到目标工程，完成 AUTOSAR 平台、BSW、MCAL、必要 CDD/适配层、启动加载、烧录、联调和问题定位闭环。不得以甲方应用代码为手写代码、未提供完整 ARXML 等理由拒绝 RTE 骨架、适配接口、ASW Stub 或集成调试。
2. **完整 AUTOSAR 平台范围**：乙方应对 OS、RTE、SchM、EcuM、BswM、ComM、Com/PduR、CanIf/CanTp/CanSM、Nm/CanNm、Dcm/Dem/Det/FiM、NvM/MemIf/Fee、WdgM/WdgIf、Xcp、StbM/CanTSyn、Crc、E2E/ComXf/E2EXf 的配置、生成、集成和基本调试负责。原协议中带星号的 Nm/CanNm、SecOC/CryIf/CSM/KeyM 等“仅供代码手册、不做工程”表述，不能用于排除本项目实际承诺的集成工作。
3. **MCAL 与 CDD 平台适配**：除 Mcu/Port/Dio/Can/Fls/Spi/Uart/Adc 外，必须明确 Can_Dma_Interface、Gpt、Ipc、eDMA、Mpu 及量产硬件实际需要的外设配置、驱动集成和调试。甲方可提供 PMIC、外部看门狗、CAN 收发器、外部 Flash 等 CDD 源码；乙方仍须承担其 AUTOSAR 侧调用、初始化顺序、任务/中断及诊断/故障接口集成。
4. **mmWave 主链路集成**：以 BYD 量产架构为参照，乙方须完成 OS 任务和中断、mmWave 控制/DPM/触发链路、Mailbox/IPC、共享内存、eDMA/TPCC、DMA 中断回调、缓存一致性、MemoryMap、mmWaveLink OSI，以及 RTE 或工程手写接口的适配。验收至少应包括上电启动、射频初始化/控制应答、数据搬运及 CAN/CANFD 最小状态输出。
5. **Bootloader 必须拆分交付**：不能只约定“PBL+SBL 单 Bank 基础刷写”。应分别交付：
   - BootManager：上电启动、镜像选择/加载/校验、Boot 到 APP 跳转、异常启动处理；
   - PFBoot：基于 CAN/CANFD 诊断的擦除、写入、校验、版本/刷写状态管理。
   同时交付源代码、配置、链接脚本、分区/镜像布局、打包/刷写脚本、异常刷写恢复及测试报告。APP 有效性、重刷标志、指纹/版本、复位原因、APP 跳 Boot、刷写中断恢复均应有测试证据。
6. **功能安全与信息安全机制**：本项目可不以 ISO 26262 或 ISO/SAE 21434 认证为交付目标，但不得将安全工作完全排除。乙方至少应完成与 BYD 工程同级的工程机制集成：外部看门狗和任务监控、故障记录/诊断、Trap、MPU（或等效隔离）、安全任务/中断；HSM/Crypto 集成接口、安全启动/完整性校验、诊断 SecurityAccess、签名/验签或等效流程、密钥/证书接口及量产调试权限控制。密钥、证书和 OEM 专有固件由甲方/OEM 提供时，乙方负责项目侧集成与测试。
7. **交付和验收物**：除可执行文件外，应交付全部工程源代码、配置和生成物、生成/编译/打包/刷写脚本及版本锁定清单；接口文档；模块测试与集成测试报告；Release Note、Known Issues；DID/DTC/Routine 矩阵、NvM Block/Fee 布局、NM 状态策略、Wdg 监督策略、XCP/A2L、Boot/MemoryMap 证据。工程必须可由甲方在约定环境中复现生成、编译、打包和刷写。

## 二、签署前必须冻结或纠正的原协议冲突

1. **产品版本**：正文出现 cCore 4.0/AUTOSAR CP R21-11，而表格标题为 cCore 3.0；必须在签署版统一为实际采购和交付版本。
2. **芯片型号**：正文为 TI 2E44LC；项目沟通中出现 TI 2944LC。必须按原理图、BOM 和 TI SDK 的正式型号冻结，避免后续 MCAL、Boot、HSM 和内存布局责任争议。
3. **OS 安全等级与时序保护**：协议同时出现 OS_SC4 和 OS_SC2，而 BYD 基线为单核 OS_SC1，时序保护为关闭。目标项目如需提升等级或打开保护，须明确为新增需求，写清任务/中断/资源和验收；不能沿用互相矛盾的默认描述。
4. **硬件边界**：以 PortList、BOM、IO/中断/DMA 分配、MemoryMap、Flash 分区为正式输入；原理图可按保密规则受控提供。未冻结的 CANFD 收发器、SBC、外部 Flash、以太网器件等，须列出“甲方供驱动/乙方集成”或“乙方负责”的明确边界。
5. **OEM 强相关输入与节奏**：DBC、诊断矩阵、NM、NvM Block List、XCP/A2L、刷写策略、安全策略应作为受控输入和变更项。未到位时，乙方先基于 BYD 基线/占位配置推进平台，不得导致第一阶段的主链路交付停滞；收到正式输入后按约定变更流程闭环。

## 三、非默认承诺，需由双方明确选择

- DoIP、完整以太网协议栈、以太网时间同步：BYD 合同清单中为仅供代码手册，若本项目没有以太网诊断/通信需求，可保留为非本期范围。
- SecOC：若没有 OEM 的密钥、PDU、Freshness 和验收定义，不应空泛承诺“完整 SecOC 功能”；应至少保留 Crypto/HSM、Secure Boot 和诊断安全接口的集成范围。
- SPI：BYD 射频主链路并非以 SPI 为必需依赖；SPI 是否实施以 PMIC、外部看门狗或其他板级器件的实际连接为准。

## 四、已形成的红字版合同文件

`NeuSAR技术协议V1.5-20260707_补充条款红字版.docx` 已在原协议签署页前追加“附件一：本项目补充技术条款（红字新增）”。原协议正文未改动；新增 16 段文字均已标红。
