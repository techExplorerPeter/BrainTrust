# 毫米波雷达控制器 AUTOSAR/NeuSAR 项目需求输入完整版

本文档用于我方与东软进行项目计划、技术范围、阶段交付物和验收标准沟通。目标是把我方基于 BYD 量产工程已经验证过的软件形态，转化为本项目对东软的完整需求输入，减少双方信息差。

参考工程：

- BYD量产工程：`D:\Weifu\Project\CR\BYD_RL\xxx`
- 目标项目芯片：TI AWR2944LC / AM294x R5F 系列，最终以双方确认的芯片料号、SDK、MCAL支持矩阵为准。
- 东软输入计划表：`D:\Weifu\Docs\BrainTrust\weifu\Neusar\毫米波雷达控制器开发计划.xlsx`

## 1. 项目目标

本项目不是从零开发一套普通 AUTOSAR BSW，而是希望基于 BYD 量产工程的软件架构和功能范围，快速建立适配 TI AWR2944LC 的 AUTOSAR/NeuSAR 基础平台，并支撑我方尽快完成 mmWave/RF、信号处理、数据处理和 ASW 主链路移植，最终达到可量产状态。

项目目标分为三个层次：

1. 快速跑通主链路。
   - 上电启动。
   - OS任务调度。
   - mmWave/RF初始化。
   - mmWaveLink控制链路打通。
   - Mailbox/IPC与协处理核交互打通。
   - eDMA/共享内存数据链路可用。
   - CAN/CANFD最小调试输出可用。
   - APP可刷写、可启动。

2. 完成OEM强相关功能。
   - UDS诊断。
   - DTC/Dem/FiM。
   - NvM/Fee/Fls存储。
   - NM/ComM/CanSM/BswM网络管理。
   - WdgM/WdgIf/外部看门狗。
   - XCP/A2L。

3. 达到量产交付能力。
   - 完整Bootloader。
   - HSM/Crypto/Secure Boot。
   - 正式量产刷写包。
   - 可复现编译、生成、打包、刷写。
   - 测试报告、ReleaseNote、KnownIssues齐套。

## 2. BYD量产工程关键事实

以下内容是本项目需求输入的核心依据。东软需要按这些事实理解我方目标系统形态。

### 2.1 工程目录形态

BYD量产工程顶层包含：

| 目录 | 含义 |
|---|---|
| `asw` | 应用层软件，包含基础、通信、核心算法入口、NVM、Wdg、XCP等模块 |
| `adas` | 雷达算法、信号处理、感知、RF配置、eDMA接口 |
| `mmwave` | TI mmWave SDK/Link/Mailbox/ADC/HW抽象等相关代码 |
| `bswpf` | AUTOSAR BSW、MCAL、CDD、平台适配 |
| `coem\BYD_UKE` | BYD项目配置、生成代码、RTE、OS、Boot容器输入 |
| `rte` | 项目侧手写/适配任务与mmWave调度代码 |
| `integration` | 集成相关代码 |

### 2.2 BYD工程中的AUTOSAR/OS基础

BYD工程使用 ETAS RTA-OS/AUTOSAR 配置作为量产参考，关键事实如下：

| 项目 | BYD工程事实 |
|---|---|
| OS目标 | `AWR2E44` / R5目标 |
| AUTOSAR相关版本 | 工程中存在 `AUTOSAR_431` 宏，OS配置摘要中 ARVersion 为 `4.8.0` |
| 任务模型 | 存在 ASW周期任务、BSW周期任务、ECU启动任务、mmWave控制任务、DPM任务、触发任务 |
| RTE | `coem\BYD_UKE\gen_rte` 下存在 `Rte.c/h`、`Rte_ASW_*.h`、`SchM_*.h`、`OsTask_ASW_*.c` 等生成物 |

BYD工程OS任务参考：

| 任务 | 参考用途 |
|---|---|
| `OsTask_ECU_Startup` | ECU启动初始化 |
| `OsTask_BSW_10ms` | BSW周期调度 |
| `OsTask_BSW_SwcRequest` | BSW请求处理 |
| `OsTask_ASW_10ms` | ASW 10ms周期任务 |
| `OsTask_ASW_20ms` | ASW 20ms周期任务 |
| `OsTask_ASW_100ms` | ASW 100ms周期任务 |
| `OsTask_MmWaveCtrl` | mmWave控制任务 |
| `OsTask_DPM` | 数据处理/DPM任务 |
| `OsTask_TriggerWave` | 波形/采集触发相关任务 |
| `OsTask_Trigger66ms` | 66ms触发/数据处理相关任务 |

### 2.3 BYD工程中的ASW模块参考

BYD工程 `asw` 目录下主要模块包括：

| 模块 | 说明 |
|---|---|
| `ASW_BASE` | 基础应用功能、状态管理等 |
| `ASW_COM` | 应用通信入口 |
| `ASW_CORE0` | 核心应用调度入口 |
| `ASW_IN` | 输入、波形/计算/功能输入处理 |
| `ASW_NVM` | 应用NVM相关逻辑 |
| `ASW_WDG` | 应用看门狗相关逻辑 |
| `ASW_XCP` | XCP相关应用接口 |
| `ASW_CALIBRATION` | 标定、Routine、NVM写入等 |
| `CDD_CORE0` | 项目相关CDD接口 |

本项目中 ASW、mmWave/RF、信号处理和数据处理由我方主责，东软负责提供其运行所需的 AUTOSAR/NeuSAR 平台、RTE/BSW/MCAL/CDD支撑。

### 2.4 BYD工程中的BSW范围参考

BYD工程 `bswpf\autosar` 包含以下模块：

| 类别 | 模块 |
|---|---|
| 通信 | `CanIf`、`CanNm`、`CanSM`、`CanTp`、`CanTSyn`、`Com`、`ComM`、`PduR`、`Nm` |
| 诊断 | `Dcm`、`Dem`、`Det` |
| 存储 | `NvM`、`MemIf`、`Fee` |
| 系统服务 | `EcuM`、`BswM`、`Crc`、`StbM`、`Bfx`、`Mfl` |
| 看门狗 | `WdgIf`、`WdgM` |
| 标定 | `Xcp` |
| Bosch/平台库 | `Rba_BswSrv`、`Rba_DiagLib`、`Rba_FeeFs1x`、`Rba_MemLib` |

东软最终交付范围应覆盖与 BYD量产工程同等级的 BSW能力。若首版不启用某些模块，必须在范围表中明确“阶段2不启用、阶段3启用”或“不适用”。

### 2.5 BYD工程中的MCAL范围参考

BYD工程 `bswpf\mcal` 包含以下模块：

| 模块 | 本项目用途 |
|---|---|
| `Mcu` | 时钟、复位、基础芯片初始化 |
| `Port` | 引脚复用配置 |
| `Dio` | GPIO控制 |
| `Can` | CAN/CANFD控制器 |
| `Can_Dma_Interface` | CAN相关DMA接口 |
| `eDMA` | 数据搬运、信号处理主链路依赖 |
| `Gpt` | 周期触发、时间基准 |
| `Ipc` | 多核/协处理核通信基础 |
| `Fls` | Flash访问 |
| `Adc` | 电压/温度等采样相关 |
| `Spi` | 平台SPI能力，是否用于新项目外设需单独确认 |
| `MpuP_T` | MPU/保护相关 |

### 2.6 BYD工程中的CDD范围参考

BYD工程 `bswpf\cdd` 包含：

| CDD | 说明 |
|---|---|
| `LP87745` | PMIC相关 |
| `TCAN1043` | CAN收发器相关 |
| `WDGDrv` | 外部看门狗相关 |
| `SaveErrLog` | 错误日志保存 |
| `RxIdCfg` | 接收ID配置 |
| `Trap` | 异常/Trap处理 |
| `ADCtest`、`PMICtest`、`VOL_Tem_Test` | 测试/电压温度相关 |

此外，雷达主链路中还存在项目侧 CDD/适配代码：

- `rte\OsTask_MMW.c` 直接包含 `Cdd_Ipc.h`，并通过 Mailbox回调、共享内存和任务激活完成 mmWave相关调度。
- `adas\symmetry\eDMAinterface\cdd_doa_dma.c`、`adas\beamform\eDMAinterface\cdd_doa_dma.c` 直接依赖 `Cdd_Dma`。

### 2.7 mmWave/RF控制链路参考

这是本项目阶段2最关键的事实。

BYD量产工程中，mmWave/RF 主链路不是通过 AUTOSAR `Spi_*` 接口直接控制。实际工程中：

- `mmwave\mmwave\src\mmwave_link_mailbox.c` 注册了 `MMWave_mboxOpen`、`MMWave_mboxRead`、`MMWave_mboxWrite`、`MMWave_mboxClose` 给 mmWaveLink 的 `rlComIf*` 回调。
- `rlDevicePowerOn()` 前使用的是 Mailbox通信回调。
- `mmwave\mmwave\src\mmwave_link_spi_22xx.c` 文件存在，但长度为 0。
- 在 `adas`、`mmwave`、`rte` 主路径中未发现 RF业务流程直接调用 AUTOSAR `Spi_*` API。

因此本项目应明确：

| 项目 | 结论 |
|---|---|
| RF主控制链路 | 以 `mmWaveLink + Mailbox/IPC` 为阶段2主线 |
| SPI | 不是 BYD参考工程 RF主链路前置依赖 |
| SPI在本项目中的定位 | 仅作为平台能力或外部器件需求确认项 |
| 阶段2不可阻塞项 | 不应因 SPI未完整量产化而阻塞 mmWave/RF 主链路 |

如果新硬件存在外部 MMIC、PMIC、SBC、外部Flash、外部Watchdog 等确实需要 SPI 的器件，应将 SPI作为对应外设驱动需求单独列入，而不是作为 RF主链路默认前置项。

### 2.8 BYD工程中的NM网络管理参考

BYD量产工程存在 NM 网络管理：

- `CanNm`、`Nm`、`ComM`、`CanSM`、`BswM` 均在 BSW范围内。
- `BswM_Cfg_AC.c` 中存在 `CanNm_Init(NULL_PTR)`、`Nm_Init(NULL_PTR)`、`ComM_Init(NULL_PTR)` 等初始化调用。
- `Nm_Cfg.c` 将 `Nm_NetworkRequest`、`Nm_NetworkRelease`、`Nm_GetState` 等映射到 `CanNm`。
- `CanNm_MainFunction()` 在生成的 `OsTask_BSW_10ms.c` 中被注释，但项目侧通过 `net_NM_schedule()` 调用。
- ASW侧存在读取 `CanNm_GetState()` 的使用。

因此新项目阶段3应包含完整 NM/ComM/CanSM/BswM 的量产功能。阶段2只需要保留最小通信管理能力，不应让完整 NM 逻辑阻塞 RF主链路开发。

### 2.9 BYD工程中的Boot参考

BYD量产工程存在完整Boot/镜像容器结构：

| 目录 | 含义 |
|---|---|
| `01_BootManager` | Boot管理 |
| `02_PlatformBoot` | 平台Boot |
| `03_CustBoot` | 客户Boot |
| `04_CustApp` / `04_CustApp_1M` | 客户APP |
| `04_ProductionApp` / `04_ProductionApp_1M` | 量产APP |
| `06_Hsm` | HSM相关 |
| `07_WeifuData` | 我方数据区 |
| `08_CustData` | 客户数据区 |
| `09_ClibData` | 库/公共数据区 |

因此本项目中 Bootloader 不能后置到很晚。建议拆成：

- 阶段1：Boot架构和Memory Map冻结。
- 阶段2：最小Boot刷写闭环，支撑开发测试。
- 阶段3：完整Bootloader/HSM/Secure Boot/量产刷写包。

## 3. 总体分工建议

| 工作项 | 主责方 | 说明 |
|---|---|---|
| 技术架构统筹 | 我方 | 负责目标架构、范围冻结、关键技术决策、里程碑验收 |
| ASW应用层 | 我方 | 基于量产工程移植/开发 |
| mmWave/RF配置 | 我方 | Profile/Chirp/Frame/RF标定策略由我方主责 |
| 信号处理/数据处理 | 我方 | 包含RF数据处理、目标输出、算法链路 |
| BSW/MCAL/RTE/OS | 东软 | NeuSAR配置、生成、适配、集成 |
| Mailbox/IPC/eDMA基础平台 | 东软主责，我方配合 | 阶段2核心，需满足我方mmWave/RF移植 |
| Bootloader | 东软主责，我方配合 | 需确认是否包含BootManager、PlatformBoot、CustomerBoot、HSM |
| UDS/诊断实现 | 东软主责，我方提供需求 | 我方提供DID/DTC/Routine/OEM需求 |
| CAN/CANFD通信 | 东软主责BSW，我方提供DBC/信号需求 | 阶段2最小通信，阶段3完整OEM通信 |
| NvM/标定数据存储 | 东软主责BSW，我方提供Block/数据定义 | 阶段2最小Stub，阶段3完整持久化 |
| 集成测试 | 双方 | 阶段2主链路，阶段3量产完整功能 |

## 4. 软件架构需求

### 4.1 分层架构

本项目目标软件分层如下：

```text
ASW / Algorithm
  - Base / COM / Core / NVM / WDG / XCP
  - mmWave RF配置
  - Signal Processing
  - Data Processing / Perception

RTE / Hand-written Adapter
  - RTE生成接口
  - SchM/ExclusiveArea
  - 手写接口适配
  - mmWave任务适配

BSW
  - Com / PduR / CanIf / CanTp / CanNm / Nm / ComM / CanSM
  - Dcm / Dem / Det / FiM
  - NvM / MemIf / Fee / Fls
  - EcuM / BswM / WdgM / WdgIf / Xcp / Crc

CDD / Platform Adapter
  - Cdd_Ipc / Mailbox
  - Cdd_Dma / eDMA封装
  - Transceiver / PMIC / Watchdog / ErrorLog

MCAL
  - Mcu / Port / Dio / Can / eDMA / Gpt / Ipc / Fls / Spi / Adc / Mpu

Hardware
  - TI AWR2944LC
  - R5F / RSS / DSS / M4等实际核心资源
  - CAN/CANFD / Flash / PMIC / Transceiver / WDG
```

### 4.2 运行时架构

运行时架构必须优先满足雷达主链路实时性。

东软需在阶段1输出并在阶段2实现：

- ECU启动顺序。
- BSW初始化顺序。
- mmWaveLink初始化顺序。
- Mailbox/IPC初始化顺序。
- eDMA初始化顺序。
- ASW Runnable调度关系。
- mmWave控制任务优先级。
- DPM/数据处理任务优先级。
- CAN/CANFD调试输出周期。
- 看门狗喂狗窗口和监控任务清单。

参考 BYD 量产工程，mmWave相关任务优先级应高于普通ASW/BSW周期任务，避免雷达主链路被普通周期任务阻塞。

### 4.3 接口架构

本项目不要求所有接口首版都完全RTE化。参考 BYD量产工程，RTE与项目侧手写适配接口可以共存。

接口分层建议：

| 接口类型 | 阶段2要求 | 阶段3要求 |
|---|---|---|
| ASW周期Runnable | RTE骨架可用 | 完整RTE配置 |
| CAN发送/接收 | 最小接口可用 | 完整OEM通信接口 |
| mmWaveLink控制 | 手写适配/封装优先 | 根据稳定性决定是否RTE化 |
| Mailbox/IPC | CDD/平台接口可用 | 完整异常处理 |
| eDMA | CDD封装可用 | 完整资源管理和错误处理 |
| NvM | Stub或固定数据接口 | 完整NvM Block |
| Dcm/Dem | 可先不完整 | 完整OEM诊断 |

### 4.4 Memory Map架构

东软需在阶段1输出 Memory Map 设计，阶段2实现主链路所需部分，阶段3完成量产完整设计。

Memory Map 必须包含：

- Boot保留区。
- APP代码区。
- APP数据区。
- HSM区。
- 客户数据区。
- 我方数据区。
- NVM/Fee/Fls区域。
- 多核共享内存区域。
- IPC vring/共享buffer区域。
- eDMA buffer区域。
- 标定数据区域。
- 错误日志区域。

参考 BYD工程，`rte\OsTask_MMW.c` 中存在对 `.bss.ipc_vring_mem` 的共享内存放置，并要求对齐。新项目必须明确共享内存地址、大小、对齐、cache属性和访问方。

### 4.5 Boot架构

Boot架构应参考 BYD量产工程容器结构，至少明确：

- BootManager。
- PlatformBoot。
- CustomerBoot。
- CustomerApp。
- ProductionApp。
- HSM。
- WeifuData。
- CustData。
- ClibData。
- APP跳Boot机制。
- Boot跳APP机制。
- 刷写失败保护。
- 镜像CRC/签名校验。
- 回滚策略。
- 量产包生成流程。

## 5. 里程碑总体建议

建议不完全照搬东软Excel中 T1/T2线性BSW交付方式，而是改成围绕“主链路先跑通，量产功能再补齐”的实际项目节奏。

| 阶段 | 名称 | 主目标 | 核心验收 |
|---|---|---|---|
| 阶段0 | 项目启动与输入冻结 | 冻结范围、输入物、责任边界 | 输入物清单、责任矩阵、风险清单确认 |
| 阶段1 | 需求清晰与架构设计 | 按BYD工程抽象目标架构 | 架构、接口、Memory Map、Boot、计划冻结 |
| 阶段2 | mmWaveLink + Mailbox/IPC主链路基础平台交付 | 支撑我方RF/ASW主链路移植 | OS、IPC、eDMA、RTE骨架、CAN、最小Boot可用 |
| 阶段3 | OEM强相关功能与量产完整功能 | 补齐完整AUTOSAR/OEM/Boot/HSM | 诊断、存储、NM、Wdg、XCP、量产Boot通过 |
| 阶段4 | 系统集成、验证与发布 | 完成稳定性、回归、交付包 | 可复现编译、刷写、测试、发布 |

## 6. 阶段0：项目启动与输入冻结

### 6.1 阶段目标

保证双方在项目一开始就明确范围、输入物、版本、责任和风险，避免后期因为边界不清导致延期。

### 6.2 东软需要确认

- NeuSAR cCore版本。
- AUTOSAR版本。
- TI AWR2944LC / AM294x R5F支持状态。
- MCAL支持矩阵。
- Bootloader支持范围。
- HSM/Crypto支持范围。
- 工具链、编译器、调试器版本。
- 是否有已验证的同平台项目案例。
- 是否提供源码、配置工程、生成代码、编译工程和测试报告。

### 6.3 我方需要提供

- BYD量产工程作为参考。
- 芯片资料、SDK、硬件原理图、硬件接口说明。
- DBC/CAN通信需求。
- 诊断需求/DID/DTC/Routine初版。
- Boot刷写流程初版。
- ASW初版ARXML或接口清单。
- mmWave/RF启动时序和业务接口说明。
- 标定数据和NVM Block初版需求。

### 6.4 阶段0交付物

- 项目范围说明。
- 输入物清单。
- 责任矩阵。
- 工具链版本清单。
- 项目风险清单。
- 总体里程碑计划。

### 6.5 阶段0验收标准

- 东软确认目标芯片支持状态。
- Bootloader责任范围明确。
- ASW由我方主责、BSW/MCAL/RTE/OS由东软主责明确。
- 阶段2和阶段3交付边界明确。
- 所有关键TBD项有关闭责任人和关闭时间。

## 7. 阶段1：需求清晰与架构设计

### 7.1 阶段目标

阶段1是第一个正式技术里程碑。目标是把 BYD量产工程中的成熟架构抽象出来，形成新项目的目标架构和详细实施计划。

### 7.2 东软需要输出的架构内容

#### 7.2.1 软件分层架构

东软需输出：

- ASW模块清单。
- BSW模块清单。
- MCAL模块清单。
- CDD模块清单。
- RTE与手写接口共存边界。
- mmWave/RF链路接入 AUTOSAR/NeuSAR 的方式。
- 首版必须做的功能和第三阶段再做的功能。

#### 7.2.2 运行时架构

东软需输出：

- OS任务表。
- 任务周期。
- 任务优先级。
- 栈大小。
- Alarm/Counter配置。
- ISR表。
- mmWave控制任务调度。
- DPM/数据处理任务调度。
- ASW/BSW调度关系。
- 启动时序图。

#### 7.2.3 接口架构

东软需输出：

- RTE接口清单。
- 手写接口清单。
- ASW调用BSW接口清单。
- mmWaveLink适配接口。
- Mailbox/IPC接口。
- eDMA接口。
- CAN/CANFD接口。
- NvM接口。
- Dcm/Dem接口。

#### 7.2.4 Memory Map架构

东软需输出：

- Flash分区。
- RAM分区。
- 共享内存。
- IPC vring。
- eDMA buffer。
- Boot保留区。
- APP区。
- HSM区。
- 数据区。
- 标定区。
- 错误日志区。
- 对齐和cache策略。

#### 7.2.5 Boot架构

东软需输出：

- BootManager/PlatformBoot/CustomerBoot边界。
- APP跳Boot流程。
- Boot跳APP流程。
- UDS刷写流程。
- HSM/Crypto边界。
- Secure Boot方案。
- 镜像格式。
- 签名/CRC校验。
- 回滚策略。
- 量产包组成。

### 7.3 阶段1东软交付物

- 软件架构设计说明。
- 运行时架构设计说明。
- 接口架构说明。
- Memory Map说明。
- Boot架构说明。
- MCAL支持矩阵。
- CDD边界说明。
- RTE/手写接口共存说明。
- 阶段2详细开发计划。
- 阶段3详细开发计划。
- 风险清单和TBD关闭计划。

### 7.4 阶段1验收标准

- 架构能映射到 BYD量产工程实际形态。
- mmWave/RF主链路明确为 `mmWaveLink + Mailbox/IPC`。
- SPI不作为RF首版跑通前置条件，除非新硬件确认必须使用。
- Boot最小刷写闭环被前置到阶段2。
- RTE骨架被前置到阶段2。
- 完整UDS/NM/NvM/Wdg/XCP被放到阶段3。

## 8. 阶段2：mmWaveLink + Mailbox/IPC 主链路基础平台交付

### 8.1 阶段目标

阶段2是整个项目最关键的开发阶段。目标不是交付完整量产AUTOSAR，而是交付一个可编译、可上板、可调度、可通信、可刷写的基础平台，使我方可以开始移植 mmWave/RF、信号处理、数据处理和ASW主枝干。

阶段2最小闭环：

```text
上电启动
  -> OS启动
  -> BSW最小初始化
  -> mmWave控制任务运行
  -> Mailbox/IPC可用
  -> mmWaveLink可调用
  -> RF最小配置可下发
  -> eDMA/共享内存数据路径可验证
  -> CAN/CANFD可输出状态
  -> Boot可刷APP
```

### 8.2 阶段2东软必须交付的能力

#### 8.2.1 工程与环境

东软需交付：

- NeuSAR可编译工程。
- MCAL配置工程。
- BSW配置工程。
- RTE生成工程。
- 生成代码。
- 编译脚本。
- 链接脚本。
- 烧录和调试说明。
- 自测报告。

验收：

- 我方能在本地复现编译。
- 工程可上板运行。
- 编译器、工具链、配置工具版本明确。

#### 8.2.2 OS与任务配置

东软需交付：

- 启动任务。
- BSW周期任务。
- ASW周期任务骨架。
- mmWave控制任务。
- DPM/数据处理任务。
- 触发任务。
- Alarm/Counter。
- 关键ISR。
- 任务优先级和栈配置说明。

验收：

- 所有任务可运行。
- 周期可测。
- mmWave相关任务优先级高于普通ASW/BSW任务。
- 任务不会互相饿死。

#### 8.2.3 Mailbox/IPC

东软需交付：

- `Cdd_Ipc` 或等效NeuSAR CDD。
- Mailbox初始化。
- Mailbox中断。
- IPC消息收发接口。
- 回调注册机制。
- 共享内存配置。
- 超时和错误返回机制。
- 与 mmWaveLink 的适配说明。

验收：

- 多核消息能收发。
- Mailbox中断能触发回调。
- 共享内存地址、大小、对齐、cache属性明确。
- 我方能基于该接口接入 mmWaveLink 通信回调。

#### 8.2.4 mmWaveLink适配支撑

东软需交付：

- `rlComIfOpen` / `rlComIfClose` / `rlComIfRead` / `rlComIfWrite` 的 Mailbox/IPC适配方案。
- `rlRegisterInterruptHandler` 适配机制。
- OSI Mutex/Sem/Queue/Delay适配。
- CRC适配。
- `rlDevicePowerOn()` 前后初始化顺序。
- 错误码和日志接口。

我方负责：

- RF profile/chirp/frame配置。
- `rlSetProfileConfig`、`rlSetChirpConfig`、`rlSensorStart` 等业务调用链路。
- RF标定策略。
- 雷达主链路调试。

验收：

- 我方能调用最小 `rl*` API。
- RF最小初始化链路可执行到明确结果。
- 失败路径可定位到 IPC/Mailbox/中断/参数/RF返回错误。

#### 8.2.5 SPI定位

阶段2不将 SPI 作为 RF主链路前置交付项。

但需要避免另一个误解：BYD参考工程的 RF主链路不走 SPI，不代表 BYD工程完全不用 SPI。BYD工程中 AUTOSAR `Spi` 主要用于 LP87745 PMIC/外部watchdog寄存器访问，`LP87745.c` 通过 `Spi_SetupEB`、`Spi_SyncTransmit` 并配合 `Dio_WriteChannel(GPIOA_Ch3)` 控制片选。因此如果新硬件沿用 LP87745 或类似 PMIC/watchdog 器件，SPI/PMIC/watchdog 的最小可控能力需要在阶段2具备，至少要支持开发阶段的使能、关闭、喂狗和故障定位；完整诊断和量产验收可放到阶段3。

东软需确认：

- 新硬件是否有外部SPI器件。
- SPI是否用于 PMIC、SBC、外部Flash、外部Watchdog、外部MMIC 或其他器件。
- 如存在SPI器件，是否阶段2必须使用。

验收原则：

- BYD参考工程 RF主链路不走SPI。
- 阶段2 RF主链路以 `mmWaveLink + Mailbox/IPC` 为准。
- 不允许因SPI完整量产功能未完成而阻塞阶段2 RF主链路，除非双方确认新项目RF控制必须走SPI。
- 如果SPI用于 PMIC/外部watchdog，则不能完全后置；至少需要提供 bring-up 阶段可控策略，避免外部watchdog影响上板调试。
- BYD工程中的Flash存储主路径是 `Fls/Fee` 加 QSPI/Flash驱动链路，不应默认理解为通过 AUTOSAR `Spi` 访问外部SPI Flash。

#### 8.2.6 eDMA/DMA

东软需交付：

- eDMA初始化。
- DMA通道配置。
- DMA中断配置。
- DMA传输示例。
- Buffer对齐说明。
- Cache一致性策略。
- DMA完成回调。
- 与共享内存配套的Memory Map。

验收：

- 能完成一次真实DMA搬运。
- 中断/回调正常。
- 数据无cache污染。
- 我方信号处理代码可接入。

#### 8.2.7 CAN/CANFD最小通信

东软需交付：

- `Mcu/Port/Dio/Can` 最小配置。
- `CanIf`。
- `PduR/Com` 最小链路。
- 最小DBC导入。
- Tx/Rx示例。
- 调试状态报文。

验收：

- CAN/CANFD可收发。
- ASW可调用发送接口。
- CANoe/CANalyzer可看到状态报文。
- 阶段2不要求完整OEM通信矩阵。

#### 8.2.8 RTE/ASW接口骨架

东软需交付：

- ASW初版ARXML导入方案。
- RTE头文件。
- Runnable调度。
- SchM/ExclusiveArea最小支持。
- ASW Stub。
- RTE接口和手写接口共存边界说明。

验收：

- 我方ASW可编译进东软工程。
- Runnable可被OS周期调用。
- ASW能调用CAN、基础服务、mmWave底层封装接口。

#### 8.2.9 NvM/Fls最小支撑

阶段2不要求完整NvM/Fee/Fls，但必须为RF和ASW主链路提供最小支撑。

东软需交付：

- RF标定参数读取Stub或固定数据接口。
- 最小配置数据接口。
- 后续完整NvM Block映射方案。

验收：

- 我方RF代码能获取一组可用标定/配置数据。
- 不阻塞RF主链路开发。

#### 8.2.10 最小Boot刷写闭环

东软需交付：

- Boot能启动APP。
- APP能跳Boot。
- CAN/CANFD能刷写APP。
- 基础CRC校验。
- 刷写失败保护。
- 烧录手顺。

验收：

- 不依赖JTAG即可更新APP。
- 刷写后APP能运行。
- 中断刷写或错误镜像不会启动坏APP。

### 8.3 阶段2东软交付物汇总

- 可编译NeuSAR基础平台工程。
- OS任务配置。
- MCAL配置和生成代码。
- BSW最小配置。
- RTE骨架。
- `Cdd_Ipc`/Mailbox接口说明和示例。
- eDMA/DMA接口说明和示例。
- mmWaveLink适配说明。
- 共享内存/Memory Map说明。
- CAN/CANFD最小通信示例。
- NvM/Fls最小Stub。
- 最小Boot刷写工程。
- 阶段2自测报告。
- KnownIssues。

### 8.4 阶段2我方同步工作

我方在阶段2同步进行：

- 移植mmWave/RF配置。
- 移植信号处理主链路。
- 移植数据处理主链路。
- 接入eDMA数据路径。
- 接入Mailbox/IPC数据交互。
- 接入CAN调试输出。
- 熟悉NeuSAR工程生成、编译和调试流程。
- 跑通主枝干。

### 8.5 阶段2验收标准

阶段2验收不按“完整BSW模块完成度”验收，而按“我方是否能开始RF/ASW主链路开发”验收。

验收标准：

- 我方ASW能在东软工程里编译运行。
- mmWave/RF初始化路径具备。
- mmWaveLink over Mailbox/IPC 路径具备。
- eDMA/共享内存路径具备。
- CAN/CANFD基础调试输出具备。
- OS任务调度具备。
- RTE骨架具备。
- 最小刷写闭环具备。
- 我方可以开始独立开发和调试主枝干。

## 9. 阶段3：OEM强相关功能与量产完整功能

### 9.1 阶段目标

在阶段2主链路可开发、可运行的基础上，阶段3补齐OEM和量产所需的完整功能。

### 9.2 阶段3东软需交付的模块

#### 9.2.1 UDS/Dcm

东软需交付：

- Default/Extended/Programming Session。
- SecurityAccess。
- DID读写。
- RoutineControl。
- CommunicationControl。
- ECUReset。
- TesterPresent。
- JumpToBootloader。
- 刷写相关服务。
- OEM诊断矩阵实现说明。

验收：

- OEM诊断测试通过。
- APP可通过UDS进入Boot。
- 编程会话、安全访问、复位流程符合规范。

#### 9.2.2 Dem/DTC/FiM

东软需交付：

- DTC事件清单。
- Event到DTC映射。
- Snapshot。
- Extended Data。
- ClearDTC。
- Aging策略。
- FiM抑制策略。
- ASW故障上报接口。

验收：

- ASW能上报故障。
- 诊断仪能读清DTC。
- 故障恢复、老化和抑制策略正确。

#### 9.2.3 NvM/Fee/Fls完整存储

东软需交付：

- NvM Block List。
- 默认值。
- Fee/Fls配置。
- DID写入持久化。
- 标定数据存储。
- 故障数据存储。
- 掉电保护。
- Flash寿命评估。

验收：

- 掉电保持正确。
- DID写入后重启仍有效。
- 写入策略不伤Flash寿命。
- RF标定数据读取链路与我方ASW/RF对接成功。

#### 9.2.4 NM/ComM/CanSM/BswM

东软需交付：

- CanNm。
- Generic Nm。
- ComM用户和通道。
- CanSM状态机。
- BswM规则。
- 休眠唤醒策略。
- 诊断保持通信策略。

验收：

- FullCom/NoCom切换正确。
- 网络休眠唤醒满足OEM时序。
- 诊断期间不误休眠。
- 与BYD工程中 `CanNm/Nm/ComM/BswM` 的功能范围保持同等级覆盖。

#### 9.2.5 WdgM/WdgIf/外部看门狗

东软需交付：

- 监控任务清单，需明确哪些周期任务/链路需要参与看门狗闭环，至少覆盖 BYD 工程当前用于刷新外部看门狗触发条件的 `CDD_CORE0_func` 链路。
- WdgM/WdgIf 配置需按 BYD 工程现状对齐：BYD 已配置 1 个 `WdgMSupervisedEntity_Alive_Supervision_Entity1` 和 1 个 `WdgMCheckpoint_Alive_Supervision_Entity1`，`WdgM_MainFunction()` 在 `OsTask_BSW_10ms` 中周期调用。
- Alive Supervision 作为配置项保留，但东软需注意 BYD 当前 `ASW_WDG.c` 中 `Rte_Call_RPort_Alive_Supervision_Entity1_CheckpointReached()` 的实际调用逻辑被 `#if 0` 关闭。因此新项目若要求 WdgM Alive 真正参与监督，需要明确打开/补齐 ASW checkpoint 调用，并给出 checkpoint 周期、容差和故障反应策略。
- Deadline Supervision 不作为 BYD 基线交付项。BYD 生成配置中明确为 `No WdgMDeadlineSupervision configured`，`WDGM_RB_DEADLINE_TIMER_SELECTION_NONE`。除非新项目或 OEM 明确要求，否则不要把 Deadline Supervision 写成默认必做项。
- WdgIf链路需特别说明：BYD生成的 `WdgIf_SetTriggerCondition(DeviceIndex, WdgTimeout)` 映射到 `Wdg_SetTriggerCondition(WdgTimeout)`，但 BYD工程 `bswpf\mcal\integration\Wdg.c` 中 `Wdg_SetTriggerCondition()` 是空stub。因此不能把 WdgM/WdgIf 误认为 BYD当前硬件喂狗闭环。
- 外部 Watchdog 驱动按 BYD 工程实际链路实现：`FUSA_WDGDrv` + `LP87745` PMIC watchdog。
- LP87745 PMIC 通信按 BYD 工程实际方式实现：通过 AUTOSAR `Spi_SetupEB`/`Spi_SyncTransmit` 访问 PMIC 寄存器，CS 由 `Dio_WriteChannel(GPIOA_Ch3)` 控制。
- GPT 周期喂狗链路按 BYD 工程实现：`GptChannel_1` -> `Wdg_Sbc_Cbk_GptNotificationTrigger()` -> `LP87745_Wdg_Trigger()`。
- 任务监控计数器按 BYD 工程实现：`FUSA_WDGDrv_SetTriggerCondition()` 将 `Wdg_SafetyWatchdog_TimeoutCounter` 刷新为 200；若被监控链路不再刷新，GPT 回调中计数器递减到 0 后停止触发 LP87745，最终由外部看门狗复位。
- 复位策略需区分两条链路：WdgM/WdgIf 的 AUTOSAR 管理链路，以及 LP87745 外部 PMIC watchdog 的真实硬件复位链路。
- 故障记录接口需覆盖 LP87745 watchdog 状态和复位状态读取，例如 `REG_WD_ERR_STATUS`、`REG_RECOV_CNT_REG_1` 等寄存器，并能进入 Dem/NvM/诊断读取链路。

验收：

- 正常运行时 LP87745 watchdog 能稳定喂狗，不误复位。
- `GptChannel_1` 周期回调、`LP87745_Wdg_Trigger()`、SPI 通信和 PMIC question/answer 喂狗过程可观测、可测试。
- 停止 `FUSA_WDGDrv_SetTriggerCondition()` 刷新后，`Wdg_SafetyWatchdog_TimeoutCounter` 能递减到 0，并停止喂外部 watchdog，最终触发 PMIC watchdog 复位。
- 如新项目启用 WdgM Alive，则停止 ASW checkpoint 后，WdgM local/global status 应进入异常状态，并按约定策略处理；如果沿用 BYD 当前关闭 checkpoint 调用的状态，则该项只作为配置存在性检查，不作为复位触发验收。
- 不要求 Deadline Supervision 验收，除非后续需求明确新增。
- LP87745 watchdog 复位原因、错误状态和恢复计数可记录，并可通过诊断或等效接口读取。

#### 9.2.6 XCP/A2L

东软需交付：

- XCP over CAN/CANFD。
- A2L生成。
- 测量变量映射。
- 标定变量映射。
- 访问权限和开关策略。

验收：

- CANape或等效工具可连接。
- 指定变量可测量、可标定。
- 不影响实时主链路。

#### 9.2.7 完整Bootloader/HSM/量产包

东软需交付：

- BootManager。
- PlatformBoot。
- CustomerBoot。
- UDS刷写。
- HSM/Crypto集成。
- Secure Boot。
- 镜像签名/校验。
- 回滚策略。
- 正式量产刷写包。
- 数据区打包。
- ReleaseNote。

验收：

- 正式刷写流程通过。
- 错误镜像不能启动。
- HSM/签名策略生效。
- 量产包能复现生成。

#### 9.2.8 SPI/外设完整性

阶段3可补齐SPI相关内容，但范围要与RF主链路解耦。

按BYD量产工程校准后的基线理解：

- RF主链路不依赖 AUTOSAR `Spi`。
- LP87745 PMIC/外部watchdog依赖 AUTOSAR `Spi`。
- Flash/NvM/Fee 主路径不按“SPI外部Flash”理解，而应按 `Fls/Fee` 与底层QSPI/Flash驱动链路理解。

东软需确认：

- 新项目是否有外部SPI器件。
- SPI用于哪个器件。
- 是否需要 AUTOSAR `Spi` MCAL。
- 是否需要DMA模式。
- 是否需要独立CDD封装。
- 是否涉及Boot、NvM、PMIC、SBC、外部Watchdog或外部Flash。

验收：

- 如果项目有外部SPI器件，则对应驱动和集成测试通过。
- 如果项目无外部SPI器件，则SPI不作为量产功能验收项。

### 9.3 阶段3交付物汇总

- 完整BSW配置工程。
- 完整MCAL配置工程。
- 完整RTE生成代码。
- 完整Bootloader工程。
- Dcm/Dem诊断实现说明。
- DID/DTC/Routine实现矩阵。
- NvM Block List。
- NM测试报告。
- Wdg测试报告。
- XCP/A2L交付。
- Bootloader测试报告。
- 量产刷写手顺。
- ReleaseNote。
- KnownIssues。

### 9.4 阶段3验收标准

- OEM诊断功能通过。
- 存储和故障管理通过。
- 网络管理休眠唤醒通过。
- Boot量产刷写闭环通过。
- ASW主链路和BSW完整功能同时运行稳定。
- 交付包可复现编译、生成、刷写。

## 10. 阶段4：系统集成、验证与发布

### 10.1 阶段目标

完成集成稳定性、回归测试、量产包固化和交付验收。

### 10.2 东软需支持

- 问题定位和Patch。
- 配置变更说明。
- 编译/生成复现支持。
- Boot刷写问题支持。
- BSW/RTE/MCAL问题闭环。
- 量产交付包整理。

### 10.3 阶段4交付物

- 最终Release包。
- 编译说明。
- 配置生成说明。
- 刷写说明。
- 测试报告。
- ReleaseNote。
- KnownIssues。
- QAList关闭记录。
- 培训材料。

## 11. 和东软Excel原计划的差异

根据东软《毫米波雷达控制器开发计划》原 T1/T2/BT 节奏，建议做如下调整：

| 项目 | 东软Excel原计划倾向 | 建议调整 |
|---|---|---|
| 阶段目标 | T1偏通用BSW Bring-up，T2偏完整BSW功能 | 改为阶段2先交付mmWave/RF主链路基础平台，阶段3再补完整AUTOSAR/OEM |
| RF控制通道 | 表格未明确，容易被理解成SPI/MCAL外设驱动之一 | 明确BYD参考工程RF主链路是 `mmWaveLink + Mailbox/IPC`，SPI不是RF首版前置 |
| CDD范围 | 原计划可能把CDD放在T2集成 | 拆分：`Cdd_Ipc`/Mailbox、eDMA必须提前到阶段2；外设类CDD放阶段3 |
| RTE | 原计划T2做RTE/完整接口 | RTE骨架、Runnable调度、ASW Stub必须提前到阶段2，完整接口阶段3完善 |
| DMA/共享内存 | 原计划里通常不突出 | 阶段2必须作为核心交付，否则雷达数据链路跑不起来 |
| CAN/CANFD | T1做基础通信 | 保留在阶段2，但只要求最小Tx/Rx和调试报文，完整OEM通信放阶段3 |
| Dcm/Dem | T2完整功能 | 放阶段3，不阻塞阶段2 RF主链路 |
| NvM/Fee/Fls | T2完整存储 | 阶段2提供RF标定最小Stub/固定数据接口，阶段3完整NvM/Fee/Fls |
| NM/ComM/CanSM/BswM | T2完整网络管理 | 阶段2只保留最小通信管理，阶段3完整休眠唤醒/NM |
| Wdg/XCP | T2完整集成 | 阶段3做完整量产功能，阶段2只保留必要开发调试和复位安全 |
| Bootloader | 原计划通常单独BT1/BT2，容易后置 | 拆成阶段2最小刷写闭环，阶段3完整Boot/HSM/量产包 |
| 验收方式 | 以模块完成度为主 | 阶段2按“我方能否开始RF/ASW主链路开发”验收，阶段3按OEM/量产测试验收 |

## 12. 风险与管控

| 风险 | 影响 | 管控措施 |
|---|---|---|
| NeuSAR对AWR2944LC支持不完整 | MCAL/OS/Boot延期 | 阶段0要求东软提供支持矩阵和已验证案例 |
| mmWaveLink适配不清 | RF主链路无法启动 | 阶段1冻结 `mmWaveLink + Mailbox/IPC` 方案 |
| SPI边界误解 | 阶段2资源跑偏或PMIC/watchdog调试受阻 | 明确SPI不是BYD RF主链路前置项，但BYD的LP87745 PMIC/watchdog依赖SPI |
| WdgM/WdgIf理解偏差 | 误把WdgM配置当作硬件喂狗闭环，导致复位策略缺口 | 明确BYD无Deadline Supervision；WdgM Alive配置存在但checkpoint调用关闭；硬件复位闭环按LP87745外部watchdog实现 |
| eDMA/cache/共享内存问题 | 数据链路异常、随机错误 | 阶段2必须交付对齐、cache、DMA示例 |
| Boot后置 | 开发测试效率低 | 阶段2必须有最小刷写闭环 |
| RTE接口后置 | ASW无法并行移植 | 阶段2必须有RTE骨架和ASW Stub |
| OEM诊断需求晚到 | 阶段3延期 | 阶段0/1冻结DID/DTC/Routine初版 |
| HSM/Crypto边界不清 | 量产刷写阻塞 | 阶段1冻结Boot/HSM责任边界 |
| NM休眠唤醒复杂 | 量产测试失败 | 阶段3专项测试 |
| 工程不可复现 | 交付不可控 | 每阶段必须交源码、配置、生成代码、编译说明 |

## 13. 给东软的关键确认问题

1. NeuSAR cCore是否已经支持 TI AWR2944LC / AM294x R5F？支持到哪些MCAL模块？
2. 东软是否负责完整Bootloader？是否包含BootManager、PlatformBoot、CustomerBoot、UDS刷写、APP跳转、HSM和Secure Boot？
3. mmWaveLink over Mailbox/IPC 是否由东软负责完成底层适配？
4. 阶段2是否可以按 `mmWaveLink + Mailbox/IPC + eDMA + OS Task + RTE骨架` 优先交付？
5. SPI在新硬件中具体用于哪些器件？是否与RF主链路有关？
6. RTE生成由谁负责？东软是否能导入我方ASW ARXML并生成RTE/SchM/OsTask？
7. CDD边界如何划分？`Cdd_Ipc`、`Cdd_Dma`、TCAN1043、PMIC、Watchdog、错误日志分别由谁负责？
8. 阶段2最小Boot刷写闭环何时交付？是否能不依赖JTAG更新APP？
9. 每个里程碑是否提供源码、配置工程、生成代码、编译工程、自测报告和KnownIssues？
10. 阶段3完整UDS/NM/NvM/Wdg/XCP的验收标准是否可按OEM测试项拆分？

## 14. 阶段性交付包建议结构

每个阶段交付包建议统一包含：

```text
Deliverable_Package
  01_Source
  02_Config
  03_Generated
  04_Build
  05_Document
  06_TestReport
  07_ReleaseNote
  08_KnownIssues
  09_ToolVersion
  10_UserGuide
```

交付包必须满足：

- 可复现编译。
- 可复现生成。
- 可复现刷写。
- 配置变更可追溯。
- 问题清单可闭环。

## 15. 基于BYD工程的检查结论

本文档已按以下 BYD 量产工程事实进行校验：

| 检查项 | BYD工程事实 | 本文档处理 |
|---|---|---|
| 工程目录 | 存在 `asw`、`adas`、`mmwave`、`bswpf`、`coem`、`rte` | 已按此分层组织架构 |
| BSW范围 | 存在 CanIf/CanNm/CanSM/CanTp/Com/ComM/Dcm/Dem/NvM/Nm/WdgM/Xcp等 | 阶段3要求同等级覆盖 |
| MCAL范围 | 存在 Mcu/Port/Dio/Can/eDMA/Gpt/Ipc/Fls/Spi等 | 阶段2优先 Mcu/Port/Dio/Can/eDMA/Ipc/Gpt |
| CDD范围 | 存在 LP87745/TCAN1043/WDGDrv/SaveErrLog等 | 阶段3补齐外设类CDD |
| RTE | `coem\BYD_UKE\gen_rte` 存在RTE/SchM/OsTask生成物 | 阶段2要求RTE骨架提前 |
| OS任务 | 存在 `OsTask_MmWaveCtrl`、`OsTask_DPM`、`OsTask_Trigger66ms`等 | 阶段2要求mmWave相关任务 |
| mmWaveLink通道 | `mmwave_link_mailbox.c` 注册 `MMWave_mbox*` 回调 | 阶段2明确 `mmWaveLink + Mailbox/IPC` |
| SPI | `mmwave_link_spi_22xx.c` 文件长度为0 | SPI不作为RF首版前置 |
| DMA | ADAS信号处理依赖 `Cdd_Dma` / `cdd_doa_dma` | 阶段2要求eDMA/CDD DMA |
| IPC共享内存 | `OsTask_MMW.c` 使用 `Cdd_Ipc`、Mailbox和 `.bss.ipc_vring_mem` | 阶段2要求IPC/共享内存 |
| NM | 存在 CanNm/Nm/ComM，并由项目侧调度 | 阶段3要求完整NM |
| Boot | 存在 BootManager/PlatformBoot/CustBoot/App/HSM/Data容器 | Boot拆为阶段2最小闭环、阶段3完整量产 |

## 16. 结论

建议东软按本文档作为项目需求输入和里程碑调整依据。

本项目最关键的节奏是：

1. 阶段1先把基于 BYD量产工程的架构、接口、Memory Map、Boot边界设计清楚。
2. 阶段2优先交付 `mmWaveLink + Mailbox/IPC + eDMA + OS Task + RTE骨架 + 最小CAN + 最小Boot`，让我方能尽快开始 RF/ASW 主链路移植。
3. 阶段3再补齐 UDS、Dem、NvM、NM、Wdg、XCP、完整Boot/HSM 等OEM和量产完整功能。
4. SPI不作为 RF主链路首版跑通前置项，除非新硬件明确存在必须通过SPI控制的RF或外部器件。

这样规划更贴近 BYD量产工程的实际软件形态，也能最大限度降低双方因AUTOSAR通用计划与雷达项目实际主链路不一致造成的沟通成本和进度风险。
