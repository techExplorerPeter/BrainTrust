# NeuSAR技术协议V1.5 功能模块与合同范围审查

审查对象：`C:\Users\Administrator\Downloads\NeuSAR技术协议V1.5-20260707.docx`  
审查基线：`D:\Weifu\Project\CR\BYD_RL\xxx` 量产工程，以及本项目已整理的AUTOSAR/NeuSAR实施基线。  
审查结论：协议目前不建议原样签署。协议覆盖了NeuSAR产品的主要模块，但没有把毫米波雷达主链路和量产验收需要的关键工程工作写实，且存在若干版本、OS等级、芯片和安全范围矛盾。

## 1. 总体结论

协议作为“NeuSAR产品包 + 基础BSW工程服务”基本成形，但作为“基于BYD量产工程实施TI 2944LC毫米波雷达并达到量产交付”的最终技术协议，存在以下三类问题：

1. **关键功能没有进入乙方工程服务范围**：mmWaveLink、Mailbox/IPC、eDMA、共享内存、雷达Task/DPM、RF控制适配、最小APP刷写闭环。
2. **模块虽出现在产品清单，但被星号排除或没有写入里程碑**：NM/CanNm、CanTSyn/StbM、SecOC/Crypto等；如果这些模块不是本合同实施范围，必须明确“不实施”；如果量产需要，必须取消星号并补交付和验收。
3. **工程交付和验收不够可执行**：缺少OS任务/中断/栈、诊断矩阵、NvM 105 Block、Fee布局、XCP/A2L、Wdg实际复位链路、Boot/HSM边界、可复现构建和逐模块验收标准。

## 2. 必须在签署前修改的合同级问题

### 2.1 NeuSAR版本前后不一致

协议正文写的是NeuSAR cCore 4.0 / AUTOSAR CP R21-11，但表2标题写成“NeuSAR cCore 3.0软件模块交付清单”。

建议统一为：

> NeuSAR cCore 4.0，基于AUTOSAR CP R21-11；具体工具、生成器、MCAL适配包和补丁版本以版本清单为准。

同时增加：版本号、配置工具版本、代码生成器版本、编译器版本、License版本、补丁包版本必须作为合同交付物的一部分。

### 2.2 芯片型号不一致

协议写“TI 2E44LC”，用户目标和前期项目输入为TI 2944LC/AM294x R5F系列。BYD工程实际参考目标是AWR2E44/R5平台，但这不能替代新项目最终料号确认。

必须在合同中写成：

> 目标芯片最终料号为________。乙方必须书面确认该料号、SDK、编译器、OS和MCAL支持矩阵。若从2E44LC变更为2944LC或其他兼容料号，需重新评估MCAL、Linker、Memory Map、Boot和外设驱动，不得默认视为无影响替换。

### 2.3 OS等级与BYD基线冲突

协议表2写OS_SC4，T3写OS_SC2（时间保护）；BYD量产工程配置摘要实际是单核RTA-OS SC1，且 `timing_protection=false`、`timing_protection_isr=false`。

这不是文字问题，而是会影响产品授权、配置项、运行时保护、性能和验收。必须明确：

- 本项目最终使用SC1、SC2还是SC4。
- 是否真的要求时间保护。
- 如果要求时间保护，乙方提供哪些配置、监控、故障反应和测试证据。
- 如果按BYD基线采用SC1，协议中删除“T3升级SC2时间保护”或标注为可选变更。

## 3. 关键功能模块遗漏

### 3.1 最高优先级：mmWave/RF主链路完全没有落到乙方交付范围

协议目标是毫米波雷达，但表2和表4主要描述通用BSW、MCAL和Boot，没有明确以下内容：

- mmWaveLink通信接口适配。
- `rlComIfOpen/Close/Read/Write`适配。
- Mailbox/IPC初始化、endpoint、中断和回调。
- R5F与RSS/DSS/M4等协处理核交互。
- 共享内存、IPC vring、数据buffer、cache和对齐。
- eDMA/TPCC通道、完成中断、回调和数据搬运示例。
- `OsTask_MmWaveCtrl`、`OsTask_DPM`、`OsTask_TriggerWave`、`OsTask_Trigger66ms`等雷达相关任务。
- mmWaveLink最小初始化、`rlDevicePowerOn`、RF最小配置下发和错误定位。
- mmWave/RF与RTE、CDD、ASW之间的接口骨架。

这部分是BYD工程的核心差异，也是我方阶段1必须拿到的底座。必须增加独立工作包：

> **毫米波雷达主链路基础平台**：乙方负责提供和集成OS任务、Mailbox/IPC、eDMA、共享内存、中断、mmWaveLink OSI适配及RTE/项目适配接口；甲方负责RF Profile/Chirp/Frame、信号处理、数据处理和算法业务代码。乙方交付可编译工程、适配代码、配置、示例、测试报告和KnownIssues。

### 3.2 CDD范围不完整，且责任边界不清

协议中乙方负责BSW与底层驱动集成，CDD驱动主要由甲方提供，但没有把BYD实际的CDD和新项目必须的CDD列清楚。

BYD实际存在：

- `Cdd_Ipc`/Mailbox适配。
- `Cdd_Dma`/eDMA适配。
- `LP87745` PMIC及外部Watchdog。
- `TCAN1043` CAN收发器控制。
- `WDGDrv`。
- `SaveErrLog`。
- `Trap`、`RxIdCfg`及测试CDD。

协议必须逐项标注“甲方提供源码、乙方集成配置、乙方修改适配、双方联调”的责任，尤其是IPC/DMA不能只写“甲方提供CDD”，否则阶段1主链路没有合同依据。

### 3.3 NM/CanNm被星号排除，但BYD实际有NM

表2把NM和CanNm标注为仅交付代码包及手册，且表4的T3全功能版没有明确NM/CanNm/ComM/CanSM/BswM的完整工程服务。

BYD工程实际存在并使用：

- CanNm、Nm、ComM、CanSM、BswM。
- `CanNm_Init`、`Nm_Init`、`ComM_Init`。
- 项目侧 `net_NM_schedule()` 调度CanNm。
- ASW读取 `CanNm_GetState()`。

如果新项目需要CAN休眠唤醒、FullCom/NoCom、诊断保持通信和BusOff恢复，NM必须取消星号并纳入T3配置、集成、测试和报告。若确实不做，协议应明确“不实施NM/CanNm网络管理，甲方自行承担相关功能”，不能既放入模块清单又不写实施范围。

### 3.4 时间同步模块没有按BYD实际落地

BYD基线使用CanTSyn + StbM，且存在3个TimeBase，CanTSyn Master/Slave和CRC配置。协议表2有STBM、CANTSYN，但T3没有明确实施、调度和验收；ETHTSYN为星号可不做可以理解，但CanTSyn/StbM不能只作为软件包交付。

需要补充：

- CanTSyn/StbM是否在本项目实施。
- Master/Slave角色、CAN ID、周期、CRC和时间域。
- `CanTSyn_MainFunction`/`StbM_MainFunction`调度。
- 时间同步对雷达帧、DPM和XCP时间戳的影响。

### 3.5 MCAL范围遗漏关键雷达平台模块

协议T2只写MCU/PORT/DIO/CAN，T3写FLS/DIO/PORT/SPI/UART/ADC/FLS，存在重复FLS且遗漏BYD雷达主链路依赖：

- eDMA。
- Ipc。
- Gpt。
- Can_Dma_Interface。
- MpuP_T/MPU保护。
- Mcu在完整配置阶段的时钟/复位细节。

UART不是BYD雷达主链路的核心模块，是否需要应由硬件和调试需求决定；不能用UART替代IPC/eDMA/GPT。

建议将MCAL工程服务明确拆为：

> Mcu、Port、Dio、Can、Gpt、Ipc、eDMA、Can_Dma_Interface、Fls；Spi、Adc、Mpu按新硬件和安全需求实施；UART为可选项。每个模块必须有配置工程、生成代码、集成验证和已知问题。

### 3.6 Bootloader范围明显不足

协议只约定“基于CANFD的PBL+SBL、单BANK、基本烧录”，但没有明确：

- BootManager/PlatformBoot/CustomerBoot边界。
- APP跳Boot、Boot跳APP。
- DCM/EcuM/BswM跳转路径。
- APP有效标志、刷写请求、Fingerprint、ResetReason。
- 镜像格式、链接地址、版本兼容性。
- CRC/签名校验、错误镜像保护。
- 断电/中断刷写恢复。
- HSM/Crypto/Secure Boot是否做。
- 量产包是否包含协处理核、RSS、Boot、APP和数据区。

更重要的是，协议把BT1安排在T0+9周，而T2/T3的基础工程在T0+6/T0+11周，缺少阶段1最小刷写闭环。建议改为：

- T0至T0+2周：冻结Boot范围、Memory Map、镜像和责任边界。
- T0+6周阶段主链路：最小APP刷写/启动闭环。
- T0+9周：完整Boot基本功能和UDS刷写联调。
- T0+11周及以后：量产Boot、HSM/Secure Boot和正式刷写包，是否纳入本合同必须明确。

若合同明确只做单BANK基础Boot，则必须写明：不包含HSM、Secure Boot、回滚、双镜像恢复和量产安全认证；否则“量产交付”表述会与实际范围冲突。

### 3.7 UDS/诊断模块只有名称，没有可执行需求

协议写DCM/DEM/FiM/CanTp，但没有诊断通信坐标、服务矩阵、会话、安全和DID/DTC/Routine矩阵。

至少应把以下内容作为合同附件或冻结输入：

- 物理请求0x7C2、功能请求0x7DF、物理响应0x7CA，或新项目最终坐标。
- 物理/功能寻址、标准寻址、CAN/CANFD类型。
- P2/P2*、N_As/N_Ar/N_Bs/N_Br/N_Cr/N_Cs、STmin、BS、Padding。
- 0x10/0x11/0x14/0x19/0x22/0x27/0x28/0x2E/0x31/0x3E/0x85服务矩阵。
- 0x2F是否支持。BYD实际不支持，IOControl配置为OFF。
- Session、Security Level、ModeRule和NRC。
- DID长度、读写权限、回调、NvM关联。
- DTC、Event、Debounce、OperationCycle、FreezeFrame、ExtendedData、Aging。
- Routine的RID、Start/Stop/Result、输入输出长度和业务回调。

否则乙方只能配置协议框架，无法对“诊断功能完成”负责。

### 3.8 NvM/Fee/Fls只有模块名，没有实际存储策略

协议要求甲方提供Block List，但没有把BYD实际策略和验收写入乙方工作范围。

BYD基线需要明确：

- NvM ID 0至104，共105个Block。
- 0/1为NvM内部Block，用户Block为2至104。
- Fee物理Block属性103项，不能与NvM Block数量混淆。
- Fee两个物理扇区基线：0x00350000-0x0038FFFF、0x00390000-0x003CFFFF；新项目必须按Boot/HSM/Flash重新计算。
- 启动ReadAll。
- DID、标定、EDR、Dem、复位原因、安全计数、刷写状态等运行期显式WriteBlock。
- 不把关机WriteAll作为唯一保存策略。
- 默认值、CRC、冗余、掉电原子性、写频率、寿命评估和异常恢复。

协议应要求乙方交付：NvM Block List、RAM/ROM/NV映射、Fee/Fls布局、写入触发矩阵、寿命评估、掉电测试和与DID/Dem/ASW的接口说明。

### 3.9 WdgM/WdgIf没有明确BYD真实实现方式

协议只写“WdgM/WdgIf与外部看门狗集成”，但没有写Alive/Deadline、Supervised Entity、Checkpoint、外部PMIC和复位记录。

BYD实际口径：

- WdgM配置为1个Alive Supervision Entity和1个Checkpoint。
- 未配置Deadline Supervision。
- `WdgM_MainFunction`为BSW 10ms。
- ASW Wdg Checkpoint代码当前整体处于`#if 0`，不能宣称WdgM Alive已经实际形成复位闭环。
- 真实硬件复位链路为FUSA_WDGDrv + GPT + LP87745 PMIC，LP87745通过SPI访问。
- `FUSA_WDGDrv_SetTriggerCondition()`刷新计数200，GPT回调递减，计数到0后停止喂外部Watchdog。

合同应明确：乙方负责WdgM/WdgIf配置和集成，甲方提供或确认外部Watchdog CDD；验收分别覆盖WdgM状态、外部Watchdog喂狗、任务卡死复位、复位原因记录和诊断读取。除非新增需求，不要把Deadline写成默认交付。

### 3.10 XCP范围过于笼统

协议只写“XCP RAM变量标定”，没有明确BYD基线的实际能力：

- XCP over CAN，Rx 0x332、Tx 0x778，位于CANNODE_1。
- CAL/PAG/DAQ开启。
- STIM和XCP Flash Programming关闭。
- MAX_CTO/MAX_DTO为64。
- DAQ RAM 1024字节。
- Xcp MainFunction 10ms，ASW XCP Runnable 100ms。
- A2L、测量变量、标定变量、地址、类型、访问权限和量产开关。

必须要求乙方交付XCP配置、A2L生成流程、变量清单、Seed&Key/权限策略和CANape/INCA测试报告，并要求A2L从最终ELF/MAP和配置生成。BYD仓库静态A2L模板存在8/255等与运行配置不一致的值，不能直接复制模板。

### 3.11 RTE与手写ASW边界不完整

协议写“客户提供ASW ARXML，乙方导入生成RTE接口”，但我方实际ASW可能包含手写代码，且BYD是RTE与项目适配接口共存：

- 周期Runnable由生成RTE/OsTask调度。
- mmWave/IPC/eDMA通过项目适配层、CDD、共享内存和手写任务接入。
- 需要Rte、SchM、Rte_BSWMD、osNeeds、Rte_ASW接口和OS任务生成物。

合同应写明：甲方不一定在阶段1提供完整ASW ARXML；乙方需先交RTE骨架、Runnable映射、SchM、ASW Stub和项目级适配接口，支持我方ASW并行移植。否则“ASW ARXML未完成”会成为阶段1主链路延期的免责理由。

## 4. 表2模块清单的建议修订

### 4.1 应从“星号仅代码交付”改为工程实施范围的模块

若项目目标包含BYD量产级功能，以下模块不能只交软件包和手册：

- NM、CanNm。
- CanTSyn、StbM。
- WdgM、WdgIf。
- Dcm、Dem、FiM、CanTp。
- NvM、MemIf、Fee、Fls。
- XCP。
- RTE、SchM、OS任务。
- CDD_Ipc、CDD_Dma、外部Watchdog/PMIC/收发器集成。

### 4.2 可保留为可选或明确不实施的模块

结合BYD参考工程和当前硬件输入，以下模块可以作为可选项，但必须明确是否实施：

- DoIP、TCP/IP、SoAd、EthSM、EthIf、SD、UDP NM。
- SOME/IP、SOMEIPXF、LDCOM。
- ETHTSYN。
- SecOC、CryIf、CSM、KeyM、HSM/Crypto。
- UART、外部EEPROM、外部ETH Switch相关驱动。

如果外部ETH Switch最终启用，则需要同步增加Eth MCAL/Phy/Transceiver、EthIf、EthSM、SoAd、TcpIp、DoIP或SOME/IP、诊断通道、网络管理和测试范围，不能只在表2放一组带星号的软件模块。

## 5. 建议新增的合同交付物

协议表4目前的“NeuSAR配置工程、MCAL配置工程、集成编译工程、BSW自测报告”过于宽泛，建议明确必须交付：

1. NeuSAR配置源工程和工程导入说明。
2. MCAL配置工程和目标芯片支持矩阵。
3. CDD源码、接口、配置和集成说明。
4. RTE/SchM/OS生成代码、ASW Stub和接口映射。
5. OS Task/ISR/Resource/Stack配置表和实测报告。
6. mmWaveLink/IPC/eDMA/共享内存适配代码、配置和测试报告。
7. CAN/CANFD PDU、DBC导入结果、路由表和BusOff测试。
8. UDS通信坐标、Service/DID/DTC/Routine矩阵和诊断测试报告。
9. NvM Block List、默认值、Fee/Fls布局、写策略和寿命评估。
10. NM/ComM/CanSM/BswM配置、状态机和休眠唤醒测试报告。
11. WdgM/WdgIf/外部Watchdog集成、复位策略和故障记录测试报告。
12. XCP配置、A2L、测量/标定变量清单和工具测试报告。
13. Bootloader源码、链接/分区、刷写手顺、异常恢复和测试报告。
14. 编译脚本、代码生成脚本、镜像打包/签名/刷写脚本。
15. 工具链和许可证版本清单、ReleaseNote、KnownIssues、问题闭环清单。

## 6. 建议新增的阶段验收标准

### T2初版工程，T0+6周

除协议原有内容外，必须增加：

- 上电启动、OS调度和任务心跳。
- mmWave控制Task/DPM/触发Task可运行。
- Mailbox/IPC双向收发、中断回调和超时检测通过。
- eDMA真实搬运、共享内存地址/对齐/cache验证通过。
- mmWaveLink最小初始化和RF控制接口可调用。
- 最小CAN/CANFD状态报文可收发。
- APP可刷写、可启动，不长期依赖JTAG。

### T3全功能版，T0+11周

除协议原有内容外，必须增加：

- Dcm/Dem/FiM/CanTp按矩阵测试通过。
- NvM关键Block读写、掉电保持、Fee/Fls布局和寿命评估通过。
- NM/ComM/CanSM/BswM休眠唤醒、BusOff恢复和诊断保持通过。
- WdgM Alive与外部Watchdog复位链路分别验证。
- XCP连接、DAQ、标定、A2L一致性通过。
- ASW与RTE/适配接口集成，mmWave主链路和BSW完整功能并行运行。

### BT1 Bootloader交付，建议T0+9周并行

必须明确是“基础单BANK Boot”还是“量产完整Boot”。如果只是基础单BANK，验收边界应明确不含HSM、Secure Boot、回滚和量产包；如果项目要达到量产交付，则必须增加完整Boot/HSM/Secure Boot/正式包和异常恢复验收。

## 7. 功能安全与信息安全条款的审查

协议第六章写“无功能安全认证需求”，第七章写“无信息安全认证需求”，同时表2又列出SecOC、CryIf、CSM、KeyM，乙方职责又排除SafeTlib/HSE/HSM配置。

需要把以下三种情况选定一种写进合同：

1. **确实不需要安全能力**：删除或标注SecOC/Crypto/HSM为不实施；Boot只做非安全基础刷写。
2. **需要安全机制但不做认证**：明确HSM、Crypto、Secure Boot、SecurityAccess、签名/验签、密钥流程由谁负责，交付哪些接口和测试，不宣称认证。
3. **后续可能量产导入安全**：写成阶段3可选工作包，明确触发条件、费用、周期、输入和验收。

不能一边写无信息安全需求，一边保留SecurityAccess、HSM相关模块而不定义责任，否则后期刷写和诊断安全会产生合同争议。

## 8. 建议签署前的结论

本协议不是“模块完全遗漏很多”，而是“产品模块清单基本齐，但毫米波项目工程实施范围没有完全落地”。最需要补的不是更多普通AUTOSAR模块，而是以下六项：

1. mmWaveLink + Mailbox/IPC + eDMA + 共享内存主链路。
2. OS任务、ISR、栈、RTE/SchM和手写适配层。
3. NM/CanNm/CanTSyn/StbM等被星号或里程碑遗漏的量产功能。
4. 诊断、NvM、Wdg、XCP的具体配置矩阵和验收条件。
5. Bootloader从最小刷写到量产Boot/HSM的清晰边界。
6. 版本、芯片、OS等级、安全范围和交付物的一致性。

在这些内容补充到技术协议或正式附件后，东软才能按协议展开配置，双方也才能在T2/T3/BT1验收时判断“完成”还是“只交了软件包”。
