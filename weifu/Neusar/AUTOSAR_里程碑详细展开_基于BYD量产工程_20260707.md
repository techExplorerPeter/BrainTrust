# AUTOSAR项目里程碑详细展开

基于以下输入整理：

- 量产参考工程：`D:\Weifu\Project\CR`
- 东软输入表：`D:\Weifu\Docs\BrainTrust\weifu\Neusar\毫米波雷达控制器开发计划.xlsx`
- 项目目标：基于 TI AWR2944LC / AM294x R5F 平台，快速完成 AUTOSAR 跑通、Bootloader刷写闭环、ASW集成，并支撑量产。

## 1. 总体判断

现有 BYD 量产工程不是一个“纯 AUTOSAR 生成工程”，而是典型的量产混合架构：

1. BSW/MCAL/RTE/OS 是 AUTOSAR 工具链生成和集成。
2. ASW、mmWave、RF、信号处理、感知算法、通信平台胶水代码是项目手写和移植。
3. RTE 是存在的，位于 `coem\BYD_UKE\gen_rte`，但业务代码并不是全部通过标准 SWC 抽象隔离。
4. 网络管理、Bootloader、存储、诊断、看门狗、XCP 等都在量产工程中有对应形态。
5. 新项目如果由东软做 NeuSAR，需要复用 BYD 工程的“范围和集成逻辑”，不能直接照搬 ETAS RTA 配置。

因此，项目计划不能只写“交付 BSW”。应该拆成：

- AUTOSAR基础平台：OS、RTE、EcuM、BswM、ComM、CanSM、CanIf、PduR、Com。
- 通信和网络管理：CAN/CANFD、CanNm、Nm、ComM、BswM、Dcm通信控制。
- 诊断：Dcm、Dem、FiM、DTC、DID、Routine、Session、Security。
- 存储：NvM、MemIf、Fee、Fls、Block List、掉电写策略。
- Bootloader：BootManager、PlatformBoot、CustomerBoot、UDS刷写、APP跳转、HSM/签名。
- 安全与HSM：HSM固件、Crypto、Secure Boot、镜像校验。
- 看门狗：WdgM、WdgIf、外部Wdg/PMIC/SBC、Alive Supervision。
- XCP和标定：XCP over CAN/CANFD、A2L、RAM变量标定、量产标定边界。
- CDD和外设：SBC、TCAN1043、外部Flash、PMIC、温压监控、错误日志等。
- ASW集成：RF移植、mmWave控制、信号处理、数据处理、感知输出、任务优先级、RTE/BSW接口适配。

## 2. BYD量产工程关键参考点

### 2.1 目录与模块

BYD量产工程主目录包括：

| 目录 | 作用 |
|---|---|
| `asw` | 应用层 SWC/手写业务逻辑，如 ASW_COM、ASW_NVM、ASW_WDG、ASW_CORE0、CDD_CORE0。 |
| `adas` | 雷达算法、感知、RF配置、DSP/eDMA相关处理。 |
| `mmwave` | TI毫米波控制、mmwavelink、mailbox、adc、monitor等。 |
| `bswpf\autosar` | AUTOSAR BSW模块。 |
| `bswpf\mcal` | MCAL模块。 |
| `bswpf\cdd` | 自定义驱动和外设适配。 |
| `coem\BYD_UKE\gen_rte` | RTE/SchM/OsTask生成代码。 |
| `coem\BYD_UKE\gen_bsw` | BSW生成配置代码。 |
| `coem\BYD_UKE\tools\RTA_CAR` | AUTOSAR工具配置、ARXML、DBC、ECU配置。 |
| `coem\BYD_UKE\tools\container_input` | Bootloader、HSM、APP、数据区、量产包输入。 |
| `integration` | EcuM集成、OS Hook、Protection Hook、Startup、时序计算等。 |
| `rte` | mmWave相关手写任务胶水，例如 `OsTask_MMW.c`。 |

### 2.2 BSW模块参考

BYD工程里已有的 AUTOSAR BSW 模块包括：

`BswM`、`CanIf`、`CanNm`、`CanSM`、`CanTp`、`CanTSyn`、`Com`、`ComM`、`Dcm`、`Dem`、`Det`、`EcuM`、`Fee`、`MemIf`、`Nm`、`NvM`、`PduR`、`StbM`、`WdgIf`、`WdgM`、`Xcp` 等。

新项目中，东软至少要覆盖同等级别的 BSW 范围；如果某些功能首版不做，也要在范围表里明确“暂不启用/后续阶段启用”，不能空着。

### 2.3 MCAL模块参考

BYD工程里已有的 MCAL 模块包括：

`Adc`、`Can`、`Can_Dma_Interface`、`Dio`、`eDMA`、`Fls`、`Gpt`、`Ipc`、`Mcu`、`MpuP_T`、`Port`、`Spi`。

新项目 T1 至少要跑通 `Mcu/Port/Dio/Gpt/Can`，T2 要覆盖 `Fls/Spi/Adc/eDMA/Ipc` 中与项目相关的部分。

### 2.4 RTE与OS任务参考

BYD工程里有真实生成式 RTE：

- `coem\BYD_UKE\gen_rte\Rte.c`
- `coem\BYD_UKE\gen_rte\Rte.h`
- `coem\BYD_UKE\gen_rte\Rte_ASW_*.h`
- `coem\BYD_UKE\gen_rte\SchM_*.h`
- `coem\BYD_UKE\gen_rte\OsTask_ASW_10ms.c`
- `coem\BYD_UKE\gen_rte\OsTask_BSW_10ms.c`

但 mmWave和部分调度是手写胶水：

- `rte\OsTask_MMW.c`
- `asw\ASW_COM\src\SWC_Com.c`
- `bswpf\framework\pf_com\net_Scheduler\net_Scheduler.c`
- `bswpf\framework\pf_com\net_Nm\net_Mngmt.c`

BYD工程的任务模型可以作为新项目初版参考：

| 任务 | 参考优先级 | 作用 |
|---|---:|---|
| `OsTask_TriggerWave` | 70 | 雷达波形/触发相关高优先级任务。 |
| `OsTask_ECU_Startup` | 60 | ECU启动。 |
| `OsTask_DPM` | 55 | mmWave DPM处理。 |
| `OsTask_MmWaveCtrl` | 50 | mmWave控制。 |
| `OsTask_BSW_10ms` | 30 | BSW周期主函数。 |
| `OsTask_ASW_20ms` | 20 | ASW 20ms逻辑。 |
| `OsTask_BSW_SwcRequest` | 15 | BSW/RTE服务请求。 |
| `OsTask_ASW_10ms` | 10 | ASW 10ms主链路。 |
| `OsTask_Trigger66ms` | 6 | 66ms触发任务。 |
| `OsTask_ASW_100ms` | 5 | ASW 100ms低频任务。 |

注意：优先级不能机械照抄，需要按 NeuSAR OS、AWR2944LC中断、mmWave实时链路重新验证。

### 2.5 Bootloader参考

BYD量产工程 `coem\BYD_UKE\tools\container_input` 里有完整Boot交付结构：

| 目录 | 含义 |
|---|---|
| `01_BootManager` | BootManager镜像、ELF、map、ReleaseNote。 |
| `02_PlatformBoot` | 平台Boot。 |
| `03_CustBoot` | 客户Boot，含hex/BLU/xFlash等。 |
| `04_CustApp` / `04_CustApp_1M` | 客户APP镜像。 |
| `04_ProductionApp` / `04_ProductionApp_1M` | 量产APP镜像。 |
| `06_Hsm` | HSM固件。 |
| `07_WeifuData` | 威孚数据区。 |
| `08_CustData` | 客户数据区。 |
| `09_ClibData` | 标定/库数据区。 |

所以新项目里 Bootloader 必须作为 P0 范围，不应放到后期。

## 3. 里程碑总览

建议把东软表格里的里程碑扩展为以下结构：

| 里程碑 | 建议时间 | 主目标 | 核心验收 |
|---|---|---|---|
| 项目启动/T0 | 合同后立即 | 范围、输入、环境、责任冻结 | 输入物齐套，责任边界冻结，风险清单建立。 |
| BT0 | T0+1周 | Boot需求冻结 | Flash分区、镜像格式、刷写流程、HSM边界冻结。 |
| T1 | T0+6周 | 基础BSW Bring-up | 上电启动、OS调度、CAN通信、基础EcuM/BswM/ComM、基础MCAL跑通。 |
| BT1 | T0+6周 | 最小刷写闭环 | 能进Boot、能刷APP、APP能启动、失败可恢复。 |
| T2 | T1+5周 | 完整BSW功能集成 | NvM/诊断/NM/Wdg/XCP/RTE/ASW接口完成自测。 |
| BT2 | T0+10~11周 | 量产刷写闭环 | 安全启动、HSM、正式镜像、量产包结构完成。 |
| ASW集成 | 全程并行 | mmWave/RF/算法/数据链路跑通 | ASW主链路和BSW接口联调通过。 |
| 验收 | T2/BT2后 | 功能、交付、测试验收 | 交付包、测试报告、问题闭环、验收单。 |

## 4. T0 项目启动与输入冻结

### 4.1 要做的事情

T0阶段的目标不是写代码，而是把项目后续不会反复扯皮的基础输入冻结。

必须完成：

1. 确认目标芯片：TI AWR2944LC / AM294x R5F。
2. 确认 AUTOSAR 平台：NeuSAR cCore 4.0 / AUTOSAR R21-11。
3. 确认编译器：ARM Clang / TI ARM LLVM具体版本。
4. 确认调试器、烧录器、硬件板、线束数量。
5. 确认项目复用边界：BYD工程作为参考，不直接照搬ETAS配置。
6. 冻结责任矩阵：东软负责什么，我方负责什么，哪些联合完成。
7. 冻结首版功能范围：T1必须跑通什么，T2必须完整什么。
8. 建立问题闭环机制：QA List、风险清单、每周例会、交付包命名规则。

### 4.2 输入物

| 输入物 | 提供方 | 用途 |
|---|---|---|
| BYD量产工程参考包 | 我方 | 参考模块范围、任务、RTE、Boot、诊断、通信、存储。 |
| 硬件原理图/IO Map/测试点 | 我方 | MCAL、CDD、SBC、Flash、CAN收发器配置。 |
| DBC/通信矩阵 | 我方/OEM | Com、PduR、CanIf、CanTp、CanNm、Dcm配置。 |
| 诊断需求/ODX/Excel | 我方/OEM | Dcm、Dem、DID、DTC、Routine配置。 |
| Memory Map | 双方 | Boot、APP、NvM、HSM、数据区分区。 |
| ASW ARXML | 我方初版，东软导入 | RTE生成、接口联调。 |
| Boot需求 | 双方 | 刷写、跳转、安全启动、镜像格式。 |
| MCAL支持矩阵 | 东软 | 确认AWR2944LC支持程度。 |
| NeuSAR工具和授权 | 东软 | 配置生成和编译。 |

### 4.3 交付物

| 交付物 | 说明 |
|---|---|
| 项目范围说明 | 明确包含/不包含模块。 |
| 责任矩阵 | 每个模块的主责/支持/验收方。 |
| 输入物检查表 | T0输入是否齐套，不齐套项的责任和日期。 |
| 初版里程碑计划 | T1/T2/BT1/BT2详细计划。 |
| 风险清单 | MCAL、Boot、HSM、Flash、ASW接口、性能等风险。 |

### 4.4 验收标准

T0验收不是板上功能，而是项目可执行性：

- 所有P0输入物有明确提供时间。
- 东软确认 NeuSAR 对 AWR2944LC 的支持状态。
- Bootloader 是否东软负责已经明确。
- ASW由我方主责、BSW/RTE/MCAL由东软主责已经写入计划。
- 每个里程碑的交付包内容和验收标准已经确认。

## 5. BT0 Bootloader需求冻结

### 5.1 为什么BT0必须前置

Bootloader决定测试闭环。没有Boot刷写能力，后续每次联调都依赖JTAG/CCS手工烧录，量产测试、诊断刷写、失败恢复、安全启动都无法验证。

BYD量产工程已经说明Boot不是可选项，而是量产包的一部分。

### 5.2 要做的事情

1. 确定 Bootloader 范围：
   - BootManager是否由东软开发。
   - PlatformBoot是否复用TI/东软平台。
   - CustomerBoot是否按OEM刷写规范实现。
   - APP跳转和回退策略。

2. 确定刷写协议：
   - UDS on CAN 或 UDS on CANFD。
   - 是否使用 ISO-TP/CanTp。
   - Session/Security/Routine/TransferData流程。
   - 刷写地址、块大小、擦写粒度、校验算法。

3. 确定镜像格式：
   - hex/bin/tiimage/自定义container。
   - APP镜像头。
   - 版本号、CRC、签名、长度、入口地址。

4. 确定Memory Map：
   - Boot区。
   - APP区。
   - HSM区。
   - NvM/Fee区。
   - 客户数据区。
   - 标定/库数据区。
   - 备份/回滚区。

5. 确定APP到Boot跳转：
   - Dcm ECU Reset中的 JumpToBootloader。
   - EcuM BootTarget。
   - BswM模式切换。
   - Reset Reason保存。

6. 确定安全边界：
   - HSM是否参与安全启动。
   - CryptoDriver是否AUTOSAR化。
   - 是否要求签名验签。
   - 密钥和证书由谁提供。

### 5.3 模块涉及

| 模块 | 作用 |
|---|---|
| BootManager | 判断启动目标、镜像有效性、回退策略。 |
| PlatformBoot | 芯片平台初始化、Flash/时钟/基础启动。 |
| CustomerBoot | OEM刷写规范、UDS服务、镜像接收。 |
| Dcm | APP侧诊断跳转Boot、ECU Reset。 |
| EcuM | BootTarget选择、Reset路径管理。 |
| BswM | 模式切换、诊断请求触发动作。 |
| CanTp/CanIf/Can | 刷写通信链路。 |
| Fls/Fee/MemIf | Flash擦写和数据管理。 |
| HSM/Crypto | 安全启动、签名、校验。 |

### 5.4 交付物

- Bootloader需求规格说明。
- Memory Map初版。
- 镜像格式说明。
- UDS刷写流程说明。
- APP-Boot跳转接口说明。
- HSM/安全启动边界说明。
- Bootloader开发计划和风险清单。

### 5.5 验收标准

- 能明确回答“刷哪块Flash、刷什么格式、怎么跳转、失败怎么恢复”。
- 东软确认最小刷写闭环日期。
- Dcm/EcuM/BswM/Boot之间的接口已定义。
- Memory Map已能支撑APP、Boot、NvM、HSM、数据区并存。

## 6. T1 基础BSW Bring-up

东软表格中 T1 写的是“软硬件环境搭建、系统bring-up、OS、CAN通信、系统服务、基础MCAL、系统集成”。这一阶段要拆成以下模块。

### 6.1 环境和工程框架

#### 要做的事情

1. 安装 NeuSAR cCore 工具。
2. 配置编译器和license。
3. 建立工程目录结构。
4. 建立编译脚本和生成脚本。
5. 建立基础链接脚本和Memory Map。
6. 导入MCAL和BSW配置工程。
7. 生成代码并完成首次全量编译。

#### 参考BYD工程

- `SConstruct`
- `scons_gen.bat`
- `coem\BYD_UKE\buildscripts`
- `coem\BYD_UKE\settings.py`
- `bswpf\ld\TPR12_MCU_LS.lds`

#### 交付物

- NeuSAR配置工程。
- MCAL配置工程。
- 可编译集成工程。
- 编译说明。
- 工具版本说明。

#### 验收标准

- 一键生成代码成功。
- 一键编译成功。
- 产物包含 elf/map/hex/bin。
- 编译环境可在我方电脑复现。

### 6.2 OS配置

#### 要做的事情

1. 配置R5F目标核。
2. 配置AUTOSAR OS SC等级，建议首版按SC1。
3. 配置任务、Alarm、Counter、ISR。
4. 配置启动任务、BSW周期任务、ASW周期任务。
5. 配置任务优先级和栈大小。
6. 配置Protection Hook、Error Hook、Startup Hook、Shutdown Hook。
7. 确认mmWave高实时任务与AUTOSAR任务的关系。

#### 参考BYD任务

| 任务 | 新项目建议 |
|---|---|
| `OsTask_BSW_10ms` | 保留，用于 EcuM/ComM/WdgM/NvM/Com 等BSW周期。 |
| `OsTask_ASW_10ms` | 保留，用于通信平台、ASW主链路。 |
| `OsTask_ASW_20ms` | 用于中频感知/状态逻辑。 |
| `OsTask_ASW_100ms` | 用于低频监控、诊断辅助。 |
| `OsTask_MmWaveCtrl` | 用于mmWave控制，需我方和东软共同定义调度。 |
| `OsTask_DPM` | 用于DPM/雷达数据路径。 |
| `OsTask_TriggerWave` | 用于高优先级波形触发。 |

#### 交付物

- OS配置文件。
- 任务清单。
- ISR清单。
- 周期和优先级说明。
- 栈使用初始评估。

#### 验收标准

- 所有任务能按周期运行。
- Hook能记录错误。
- 无异常复位、HardFault、任务饿死。
- 10ms/20ms/100ms任务周期误差在双方约定范围内。
- mmWave相关任务不会被BSW低优先级任务阻塞。

### 6.3 基础MCAL

#### T1必须完成模块

| MCAL模块 | T1目标 |
|---|---|
| `Mcu` | 时钟、电源、复位基础配置。 |
| `Port` | 引脚复用配置。 |
| `Dio` | GPIO读写验证。 |
| `Gpt` | OS/周期调度所需定时器。 |
| `Can` | CAN/CANFD控制器初始化、收发中断。 |
| `Can_Dma_Interface` | 如通信链路依赖DMA，T1需明确是否启用。 |

#### 要做的事情

1. 按硬件IO Map配置Port/Dio。
2. 按芯片手册配置时钟树。
3. 配置CAN/CANFD控制器、波特率、采样点、Filter。
4. 配置中断优先级。
5. 验证CAN收发。
6. 验证错误中断和BusOff恢复基础行为。

#### 交付物

- MCAL配置工程。
- MCAL生成代码。
- CAN收发自测代码或测试工程。
- T1 MCAL Bring-up报告。

#### 验收标准

- 板子上电后MCU初始化成功。
- CAN/CANFD可以收发指定ID。
- CAN中断正常进入。
- BusOff能被检测。
- Gpt周期稳定。

### 6.4 系统服务 EcuM/BswM/ComM

#### 要做的事情

1. EcuM上电初始化顺序配置。
2. BswM初始化动作列表配置。
3. ComM通道和用户配置。
4. CanSM网络状态管理配置。
5. Dcm和ComM交互基础配置。
6. 上电后进入通信FullCom。
7. 支持后续NM休眠唤醒扩展。

#### 参考BYD工程

BYD工程中 BswM 初始化动作包含：

- `CanNm_Init(NULL_PTR)`
- `Nm_Init(NULL_PTR)`
- `ComM_Init(NULL_PTR)`
- `ComPlatform_Init()`

这说明新项目需要把 BSW初始化和项目通信平台初始化统一纳入启动顺序。

#### 交付物

- EcuM配置。
- BswM配置。
- ComM配置。
- CanSM配置。
- 初始化顺序说明。

#### 验收标准

- 上电后EcuM正常进入RUN。
- BswM动作列表按预期执行。
- ComM能请求 `COMM_FULL_COMMUNICATION`。
- CanSM进入FullCom后CAN报文可发送。
- 诊断请求能保持通信。

### 6.5 CAN通信基础链路

#### 要做的事情

1. 导入DBC/通信矩阵。
2. 配置Com信号、IPDU、Group。
3. 配置PduR路由。
4. 配置CanIf Tx/Rx PDU。
5. 配置CanTp基础链路，为诊断和刷写预留。
6. 验证周期报文发送。
7. 验证接收信号更新。

#### 参考BYD工程

BYD工程通信配置参考：

- `coem\BYD_UKE\tools\RTA_CAR\DBC`
- `bswpf\framework\pf_com`
- `asw\ASW_COM`
- `coem\BYD_UKE\components\com`

#### 交付物

- 通信配置工程。
- DBC导入说明。
- CAN通信自测报告。
- 报文收发清单。

#### 验收标准

- 指定周期Tx报文按DBC发送。
- 指定Rx报文可被Com接收并更新到信号。
- CanIf/PduR/Com链路无DET错误。
- CANoe/CANalyzer或等效工具可观测报文。

### 6.6 T1交付物汇总

东软T1必须交付：

- NeuSAR配置工程。
- MCAL配置工程。
- 集成编译工程。
- 生成代码。
- elf/map/hex/bin。
- T1 Bring-up报告。
- CAN通信自测报告。
- OS任务和ISR清单。
- 当前问题清单。

我方T1必须同步交付：

- 硬件板和线束。
- DBC/诊断/IO Map/Memory Map初版。
- ASW空跑版本或接口Stub。
- mmWave最小启动接口说明。

### 6.7 T1验收标准

T1过关标准建议定义为：

1. 上电启动到EcuM RUN。
2. OS任务按周期运行。
3. 基础MCAL初始化成功。
4. CAN/CANFD基础收发成功。
5. Com/PduR/CanIf链路成功。
6. ComM/CanSM进入FullCom。
7. 工程可以一键生成、一键编译。
8. 无阻塞性HardFault、异常复位、链接错误。

## 7. BT1 最小刷写闭环

BT1建议和T1并行，不要等T2之后。

### 7.1 要做的事情

1. Bootloader基础工程建立。
2. CAN/CANFD刷写通信初始化。
3. UDS基础服务：
   - `0x10 DiagnosticSessionControl`
   - `0x11 ECUReset`
   - `0x27 SecurityAccess`，若首版可先Stub，但要定义接口。
   - `0x31 RoutineControl`
   - `0x34 RequestDownload`
   - `0x36 TransferData`
   - `0x37 RequestTransferExit`
   - `0x3E TesterPresent`
4. Flash擦写和写入。
5. 镜像完整性校验。
6. APP有效性标志。
7. Boot到APP跳转。
8. APP到Boot跳转。
9. 刷写失败恢复。

### 7.2 交付物

- Bootloader源码工程。
- Bootloader配置工程。
- Bootloader elf/map/hex/bin。
- APP测试镜像。
- 烧录及调试手顺。
- 最小刷写自测报告。

### 7.3 验收标准

- JTAG初次烧入Boot后，可通过CAN/CANFD刷APP。
- 刷写完成后APP可启动。
- APP内触发诊断跳转后能进入Boot。
- 刷写中断电后不会启动非法APP。
- 镜像CRC或等效校验生效。
- Boot和APP版本号可读。

## 8. T2 完整BSW功能集成

T2是在T1基础上补齐量产需要的BSW功能，不只是“继续集成”。

### 8.1 NvM/MemIf/Fee/Fls 存储

#### 要做的事情

1. 配置Fls底层Flash驱动。
2. 配置Fee虚拟扇区。
3. 配置MemIf抽象。
4. 配置NvM Block。
5. 定义Block List。
6. 定义默认值、RAM Mirror、ROM Block、Write Once策略。
7. 定义掉电写、周期写、立即写策略。
8. 定义诊断DID与NvM Block映射。
9. 验证擦写寿命和写入频率。

#### 参考BYD工程

- `bswpf\autosar\NvM`
- `bswpf\autosar\Fee`
- `bswpf\autosar\MemIf`
- `bswpf\mcal\Fls`
- `asw\ASW_NVM`
- `coem\BYD_UKE\components\NvmBlockDefine`

#### 交付物

- NvM/Fee/Fls配置。
- Block List。
- 存储策略说明。
- NvM自测报告。

#### 验收标准

- NvM读写成功。
- 掉电重启后数据保持。
- 默认值恢复机制正常。
- Fee/Fls无DET/DEM异常。
- 诊断写DID后能持久化。

### 8.2 Dcm/Dem/FiM 诊断

#### 要做的事情

1. 配置诊断会话：
   - Default Session。
   - Extended Session。
   - Programming Session。
2. 配置Security Access。
3. 配置DID读写。
4. 配置Routine。
5. 配置DTC和故障状态。
6. 配置Dem事件。
7. 配置Snapshot/Extended Data，按OEM要求。
8. 配置通信控制。
9. 配置ECU Reset和JumpToBootloader。
10. 配置Dcm与ComM交互，诊断期间保持通信。

#### 参考BYD工程

- `bswpf\autosar\Dcm`
- `bswpf\autosar\Dem`
- `coem\BYD_UKE\components\diag`
- `coem\BYD_UKE\components\fm`
- `coem\BYD_UKE\gen_rte\SchM_Dcm_Type.h`

BYD工程里存在与Boot跳转相关的模式：

- `RTE_MODE_DcmEcuReset_JUMPTOBOOTLOADER`
- `RTE_MODE_DcmEcuReset_JUMPTOSYSSUPPLIERBOOTLOADER`

#### 交付物

- Dcm配置。
- Dem配置。
- 诊断服务清单。
- DID/DTC/Routine矩阵。
- 诊断自测报告。

#### 验收标准

- UDS基础服务响应正确。
- 诊断会话切换正确。
- 安全访问流程符合约定。
- DID读写正确。
- DTC设置、读取、清除正确。
- ECU Reset和JumpToBootloader成功。

### 8.3 NM网络管理

#### 要做的事情

1. 配置CanNm。
2. 配置Generic Nm。
3. 配置ComM用户和通道。
4. 配置CanSM网络状态。
5. 配置BswM对网络状态的动作。
6. 配置NM PDU。
7. 配置主动唤醒、被动唤醒、休眠、PrepareBusSleep。
8. 定义本地事件保持网络唤醒条件。
9. 定义诊断请求对网络保持的影响。

#### 参考BYD工程

BYD工程有真实NM链路：

- `bswpf\autosar\CanNm`
- `bswpf\autosar\Nm`
- `bswpf\autosar\ComM`
- `bswpf\framework\pf_com\net_Nm\net_Mngmt.c`

BYD工程中 `CanNm_MainFunction()` 没有直接放在生成的 `OsTask_BSW_10ms.c`，而是通过项目通信平台调度：

- `OsTask_ASW_10ms`
- `RE_COM_SWC_func()`
- `ComPlatform_mainfunction()`
- `net_NM_schedule()`
- `CanNm_MainFunction()`

新项目需要明确：NeuSAR采用生成式调度，还是保留项目自定义通信调度。

#### 交付物

- CanNm/Nm/ComM/CanSM配置。
- NM状态机说明。
- 休眠唤醒测试报告。
- 通信保持策略说明。

#### 验收标准

- FullCom、SilentCom、NoCom切换正确。
- NM报文发送和接收正确。
- 网络休眠和唤醒符合OEM时序。
- 诊断请求期间不误休眠。
- 本地事件能请求FullCom。

### 8.4 WdgM/WdgIf/外部看门狗

#### 要做的事情

1. 确认外部看门狗芯片或SBC/PMIC。
2. 配置WdgIf。
3. 配置WdgM。
4. 定义Supervised Entity。
5. 定义Alive Counter和窗口。
6. 定义任务监控列表。
7. 定义失效动作：复位、降级、DTC。
8. 与ASW alive supervision集成。

#### 参考BYD工程

- `bswpf\autosar\WdgM`
- `bswpf\autosar\WdgIf`
- `asw\ASW_WDG`
- `bswpf\cdd\WDGDrv`
- `coem\BYD_UKE\components\VoltemCfg`

#### 交付物

- WdgM/WdgIf配置。
- 看门狗监视列表。
- 外部Wdg驱动或CDD接口说明。
- Wdg自测报告。

#### 验收标准

- 正常运行不误复位。
- 指定任务卡死后能检测。
- Alive监督计数正确。
- 故障路径和DTC符合设计。

### 8.5 XCP标定

#### 要做的事情

1. 配置XCP over CAN/CANFD。
2. 配置DAQ/STIM范围，若需要。
3. 生成A2L。
4. 定义可标定变量。
5. 定义RAM/Flash标定边界。
6. 验证连接、读写、测量。

#### 参考BYD工程

- `bswpf\autosar\Xcp`
- `bswpf\framework\rbXcp`
- `bswpf\autosar\Xcp\Xcp_A2L.a2l`
- `coem\BYD_UKE\tools\RTA_CAR\DBC\Xcp.dbc`

#### 交付物

- XCP配置。
- A2L。
- XCP连接说明。
- 标定变量清单。
- XCP自测报告。

#### 验收标准

- CANape或等效工具能连接。
- 指定RAM变量可读写。
- 测量周期满足要求。
- XCP报文ID和DBC一致。

### 8.6 RTE与ASW接口集成

#### 要做的事情

1. 导入我方ASW ARXML。
2. 生成RTE接口。
3. 生成SchM接口。
4. 生成OsTask调用代码。
5. 适配手写ASW接口。
6. 对直接调用BSW API的代码做边界确认。
7. 对mmWave手写任务胶水做集成。
8. 解决RTE符号、内存段、MemMap、链接问题。

#### 参考BYD工程

BYD工程中ASW既有RTE接口也有手写调用：

- `asw\ASW_COM\src\SWC_Com.c` 包含 `Rte_ASW_COM.h`
- `asw\ASW_NVM\src\ASW_NVM.c` 包含 `Rte_ASW_NVM.h`
- `asw\ASW_WDG\src\ASW_WDG.c` 包含 `Rte_ASW_WDG.h`
- `rte\OsTask_MMW.c` 为mmWave任务胶水。

#### 交付物

- RTE生成工程。
- RTE生成代码。
- ASW接口适配说明。
- RTE集成问题清单。

#### 验收标准

- ASW可与RTE生成代码链接。
- 主要Runnable按周期运行。
- ASW调用Com/NvM/Wdg/Diag接口无链接错误。
- 直接BSW API调用边界经双方确认。

### 8.7 T2交付物汇总

东软T2必须交付：

- 完整NeuSAR配置工程。
- 完整MCAL配置工程。
- BSW生成代码。
- RTE生成代码。
- 集成编译工程。
- BSW自测报告。
- 诊断自测报告。
- NM休眠唤醒测试报告。
- NvM存储测试报告。
- Wdg测试报告。
- XCP测试报告。
- 已知问题清单和限制说明。

### 8.8 T2验收标准

T2过关标准建议定义为：

1. BSW主要模块初始化无误。
2. CAN/CANFD通信、NM、诊断、NvM、Wdg、XCP均可板上验证。
3. ASW主链路能与RTE/BSW集成运行。
4. Boot跳转相关APP侧接口可用。
5. 工程能稳定编译并生成可烧录文件。
6. 自测报告覆盖模块级功能和系统级链路。

## 9. BT2 量产刷写闭环

### 9.1 要做的事情

1. 补齐HSM/Crypto集成。
2. 实现镜像签名或完整性校验。
3. 实现正式APP镜像打包。
4. 实现客户数据区、威孚数据区、标定数据区打包。
5. 支持量产烧录包结构。
6. 支持刷写失败恢复。
7. 支持版本读取和兼容性检查。
8. 输出量产刷写手顺。

### 9.2 交付物

- Bootloader完整源码工程。
- Bootloader完整配置工程。
- BootManager/PlatformBoot/CustomerBoot镜像。
- HSM固件或集成说明。
- APP正式打包脚本。
- 量产container输入结构。
- 刷写工具链说明。
- Bootloader完整测试报告。

### 9.3 验收标准

- 通过诊断刷写正式APP成功。
- Boot可校验APP有效性。
- HSM/签名/CRC策略按设计生效。
- 错误镜像无法启动。
- 断电恢复策略验证通过。
- 量产包结构清晰，可复现生成。

## 10. ASW并行开发与集成

ASW不是东软主责，但必须和东软计划并行，否则T2后会出现“BSW好了但雷达链路跑不起来”。

### 10.1 我方ASW主要范围

| 模块 | 工作内容 |
|---|---|
| RF移植 | AWR2944LC射频初始化、profile/chirp/frame配置、校准、监控。 |
| mmWave控制 | mmwavelink、BSS/MSS/DSS交互、mailbox、monitor。 |
| 数据采集 | ADC buffer、EDMA、DPM、数据路径。 |
| 信号处理 | FFT、点云、目标检测、跟踪前处理。 |
| 数据处理 | 感知输出、目标列表、状态管理、滤波。 |
| 通信输出 | 将目标/状态映射到Com信号或PDU。 |
| 诊断接口 | 将传感器故障、RF故障、算法故障映射到Dem事件。 |
| NvM接口 | 参数、标定、故障记录持久化。 |
| Wdg接口 | ASW alive supervision。 |
| 任务调度 | mmWave高优先级任务与AUTOSAR任务协同。 |

### 10.2 与东软接口

| 接口 | 我方提供 | 东软提供 |
|---|---|---|
| RTE接口 | ASW ARXML、Runnable需求、端口需求 | RTE生成、接口头文件、OsTask映射 |
| 通信 | 信号定义、DBC需求、发送周期 | Com/PduR/CanIf配置 |
| 诊断 | DID/DTC/Routine需求 | Dcm/Dem配置和接口 |
| 存储 | Block List、读写时机 | NvM/Fee/Fls配置 |
| Wdg | 监控对象、周期、超时策略 | WdgM/WdgIf配置 |
| Boot | APP跳Boot触发需求 | Dcm/EcuM/BswM/Boot接口 |
| mmWave任务 | 实时性要求、任务周期、优先级建议 | OS任务和中断配置支持 |

### 10.3 ASW验收标准

- mmWave初始化成功。
- RF配置下发成功。
- 数据路径启动成功。
- 主任务周期稳定。
- 感知输出可通过CAN/CANFD发送。
- 关键故障能上报Dem。
- 标定/配置参数可通过NvM保持。
- Wdg alive supervision正常。

## 11. 模块级验收清单

| 模块 | 最小验收 | 量产验收 |
|---|---|---|
| OS | 任务周期运行 | 周期抖动、栈、Hook、异常路径验证。 |
| RTE | 代码生成并链接 | ASW Runnable、服务调用、模式切换完整。 |
| MCAL-Mcu/Port/Dio | 上电初始化/GPIO | 所有IO Map配置确认。 |
| MCAL-Can | CAN收发 | BusOff、错误中断、CANFD参数验证。 |
| MCAL-Fls | Flash擦写 | 与Fee/NvM/Boot并发边界确认。 |
| Com/PduR/CanIf | 周期报文收发 | DBC全量信号、超时、Group控制。 |
| CanTp | 诊断单帧/多帧 | 刷写大数据稳定性。 |
| CanNm/Nm/ComM | FullCom/NoCom | 休眠唤醒、诊断保持、网络管理时序。 |
| Dcm | 基础UDS服务 | 会话、安全、DID、Routine、Reset、刷写。 |
| Dem | DTC设置读取清除 | Aging、Snapshot、扩展数据、故障恢复。 |
| NvM/Fee/MemIf | Block读写 | 掉电恢复、默认值、寿命策略。 |
| WdgM/WdgIf | 正常喂狗 | 故障复位、Alive监督、DTC联动。 |
| XCP | 连接读写 | A2L、测量、标定、权限。 |
| Bootloader | 能刷APP | 安全启动、回滚、HSM、量产包。 |
| HSM/Crypto | 固件集成 | 签名验签、密钥管理、故障路径。 |
| CDD | 驱动可调用 | 外设异常、诊断上报、接口文档。 |
| ASW/mmWave | 主链路空跑 | RF、数据、感知、输出、故障闭环。 |

## 12. 交付包建议结构

每个正式里程碑交付包建议统一结构：

```text
Release_xxx/
  01_Project/
    ReleaseNote.md
    DeliverNote.md
    KnownIssues.xlsx
  02_Source/
    BSW/
    MCAL/
    RTE/
    Integration/
    Bootloader/
  03_Config/
    NeuSAR_Project/
    MCAL_Config/
    ARXML/
    DBC/
  04_Build/
    build_script/
    compiler_version.txt
    linker_script/
  05_Output/
    elf/
    map/
    hex/
    bin/
  06_TestReport/
    OS_TestReport.pdf
    CAN_TestReport.pdf
    DCM_DEM_TestReport.pdf
    NVM_TestReport.pdf
    NM_TestReport.pdf
    Bootloader_TestReport.pdf
  07_Doc/
    IntegrationGuide.md
    FlashGuide.md
    DebugGuide.md
```

## 13. 风险与管控

| 风险 | 影响 | 管控动作 |
|---|---|---|
| NeuSAR对AWR2944LC支持不完整 | MCAL/OS/Boot延期 | T0要求东软提供支持矩阵和已验证案例。 |
| Bootloader后置 | 无法形成测试闭环 | BT0/BT1前置，和T1并行。 |
| 外部Flash/SBC/CANFD收发器TBD | Boot/NvM/Wdg/NM卡住 | T0冻结型号或给出替代验证方案。 |
| RTE接口和手写ASW不匹配 | 链接失败、接口返工 | 早期导入ASW ARXML，T1交付RTE Stub。 |
| NM调度方式不明确 | 休眠唤醒不稳定 | 明确生成式调度还是项目自定义调度。 |
| mmWave实时任务被BSW影响 | 雷达数据丢帧 | OS优先级和中断优先级专项评审。 |
| NvM写入策略不清 | Flash寿命或掉电丢数据 | T0/T1定义Block List和写策略。 |
| 诊断需求晚到 | T2返工 | T0锁定诊断基础矩阵，变更走流程。 |
| HSM/签名边界不清 | Boot量产风险 | BT0冻结安全需求。 |

## 14. 今天和东软可以直接确认的问题

1. NeuSAR cCore 4.0 是否已有 TI AWR2944LC / AM294x R5F 的量产或板级验证案例？
2. MCAL模块支持到哪些：Mcu、Port、Dio、Gpt、Can、Fls、Spi、Adc、eDMA、Ipc 是否都支持？
3. Bootloader是否东软全责？是否包含BootManager、PlatformBoot、CustomerBoot、UDS刷写、HSM、安全启动？
4. T1是否能交付板上可运行的基础工程，而不是只交配置文件？
5. CanNm/Nm/ComM/BswM/EcuM的休眠唤醒是否包含在T2？
6. RTE由谁生成？我方ASW ARXML什么时候导入？手写ASW直接调用BSW API是否接受？
7. NvM/Fee/Fls是否支持外部Flash？外部Flash驱动谁做？
8. Dcm/Dem是否包含JumpToBootloader、DID、DTC、Routine、Security？
9. XCP是否首版启用？A2L由谁生成？
10. 每个里程碑是否交源码、配置工程、生成代码、可编译工程、测试报告？

## 15. 推荐项目分工

| 角色 | 建议负责人 | 工作内容 |
|---|---|---|
| 技术架构/总控 | 我方 | 范围冻结、接口决策、风险闭环、里程碑验收。 |
| BSW/MCAL/RTE | 东软 | NeuSAR配置、MCAL适配、RTE生成、BSW集成。 |
| Bootloader | 东软主责，我方配合 | 刷写协议、Boot跳转、HSM、安全启动、量产包。 |
| ASW/mmWave | 我方 | RF、mmWave、信号处理、数据处理、算法、应用逻辑。 |
| 通信/诊断需求 | 我方主责，东软实现 | DBC、DID、DTC、Routine、NM规范、验收。 |
| 测试验证 | 双方 | 模块自测、板级联调、系统验收、问题闭环。 |

## 16. 一句话总结

这个项目的核心不是“买一套AUTOSAR BSW”，而是把 BYD 量产工程中已经验证过的系统形态，迁移成适配 TI AWR2944LC + NeuSAR 的新平台：东软负责把 AUTOSAR基础平台、BSW、MCAL、RTE、Bootloader做成可交付闭环；我方负责ASW、mmWave、RF、信号处理和业务链路；双方共同完成任务调度、诊断、存储、网络管理、刷写和量产验证。

