# 阶段1：需求清晰与架构设计详细展开

目标：把阶段1需要明确的架构内容，严格按 BYD 量产工程 `D:\Weifu\Project\CR\BYD_RL\xxx` 的实际结构拆开，形成可给东软评审、报价、计划和验收的输入。

## 1. 阶段1的核心结论

阶段1不是泛泛地写“软件架构设计”，而是要把以下问题全部定下来：

1. ASW有哪些模块，哪些我方主责，哪些需要东软提供RTE/BSW支撑。
2. BSW有哪些模块，哪些阶段2必须先交，哪些可以阶段3补齐。
3. MCAL有哪些模块，哪些是mmWave/RF主链路的前置条件。
4. CDD有哪些模块，哪些是板级外设，哪些是雷达链路强相关。
5. mmWave/RF链路如何接入AUTOSAR OS/RTE/BSW。
6. RTE生成接口与项目级手写接口如何共存。
7. 首版必须跑通什么，第三阶段再补什么。

BYD量产工程给我们的启发是：它不是纯BSW工程，也不是纯手写工程，而是“AUTOSAR生成平台 + 项目级适配层 + 雷达业务链路”的组合。

## 2. BYD量产工程的软件分层

按实际目录抽象，BYD工程可以分成以下层：

```text
ASW业务层
  asw/
  adas/
  mmwave/

项目级接口与调度适配层
  rte/OsTask_MMW.c
  coem/BYD_UKE/components/
  bswpf/framework/pf_com/

RTE与配置生成层
  coem/BYD_UKE/gen_rte/
  coem/BYD_UKE/gen_bsw/
  coem/BYD_UKE/tools/RTA_CAR/

AUTOSAR BSW层
  bswpf/autosar/

MCAL层
  bswpf/mcal/

CDD与板级外设层
  bswpf/cdd/

Boot与量产包层
  coem/BYD_UKE/tools/container_input/
```

新项目阶段1要输出的架构设计，必须覆盖上述每一层。

## 3. ASW有哪些模块

### 3.1 BYD工程实际ASW目录

BYD工程 `asw` 下有：

| 模块 | BYD路径 | 作用判断 | 新项目处理建议 |
|---|---|---|---|
| `ASW_BASE` | `asw\ASW_BASE\src\SWC_Base.c` | 基础状态、系统模式、部分通信控制/上下电相关逻辑。 | 保留架构角色，阶段2至少需要基础状态和启动控制Stub。 |
| `ASW_COM` | `asw\ASW_COM\src\SWC_Com.c` | ASW通信入口，调用通信平台主函数 `ComPlatform_mainfunction()`。 | 阶段2必须保留，用于CAN调试输出和通信主循环。 |
| `ASW_CORE0` | `asw\ASW_CORE0\src\ASW_CORE0.c` | 核心应用Runnable入口。 | 阶段2需要空跑/Stub，阶段3补完整业务接口。 |
| `ASW_IN` | `asw\ASW_IN` | 雷达输入、波形、计算输入、FIM降级等。含 `ASWIN_DivWave`、`ASWIN_InCalc`、`ASWIN_FIM`。 | 阶段2必须重点分析，和mmWave/RF主链路强相关。 |
| `ASW_NVM` | `asw\ASW_NVM\src\ASW_NVM.c` | 应用层NvM访问封装。 | 阶段2可做Stub/基础参数，阶段3接完整NvM。 |
| `ASW_WDG` | `asw\ASW_WDG\src\ASW_WDG.c` | 应用层看门狗Alive监督。 | 阶段2保留接口，阶段3接完整WdgM/WdgIf。 |
| `ASW_XCP` | `asw\ASW_XCP` | 标定/测量相关应用接口。 | 阶段3再完整启用。 |
| `ASW_CALIBRATION` | `asw\ASW_CALIBRATION` | 标定初始化、NvM写块、Routine到ASW接口。 | 阶段2只保留必要参数入口，阶段3完整接诊断/标定。 |
| `CDD_CORE0` | `asw\CDD_CORE0` | ASW侧CDD入口或项目CDD封装。 | 阶段2需要明确是否用于雷达主链路或板级支撑。 |
| `SGU_Inject` | `asw\SGU_Inject` | 注入/测试类功能。 | 量产或测试需要再决定，非阶段2主路径。 |

### 3.2 ADAS/mmWave相关ASW模块

BYD工程还有 `adas` 和 `mmwave`，它们虽然不在 `asw` 目录下，但对雷达功能来说属于主业务链路：

| 模块 | BYD路径 | 作用判断 | 新项目处理建议 |
|---|---|---|---|
| 感知算法 | `adas\symmetry\perception`、`adas\beamform\perception` | 目标/感知处理。 | 我方主责，阶段2开始移植。 |
| DSP/信号处理 | `adas\symmetry\dsp`、`adas\beamform\dsp` | 信号处理核心。 | 我方主责，依赖eDMA/HWA/任务调度。 |
| eDMA接口 | `adas\symmetry\eDMAinterface`、`adas\beamform\eDMAinterface` | 算法数据搬运。 | 阶段2必须要求东软提供eDMA底层支撑。 |
| RF配置 | `adas\symmetry\rfconfig`、`adas\beamform\rfconfig` | profile/chirp/frame/RF参数。 | 我方主责，东软提供运行支撑。 |
| M4输出 | `adas\symmetry\output_M4Core` | 与M4/协处理核输出相关。 | 阶段1需确认新项目是否保留。 |
| mmWaveLink | `mmwave\mmwavelink` | TI mmWave链路控制。 | 阶段2必须支撑。 |
| mailbox | `mmwave\mailbox` | MSS/RSS/DSS/HSM等核间通信。 | 阶段2必须支撑。 |
| monitor | `mmwave\monitor` | RF/BSS监控。 | 阶段2可最小化，阶段3完整故障上报。 |
| mmw_adc | `mmwave\mmw_adc` | ADC相关。 | 阶段2需确认是否参与数据链路。 |

### 3.3 阶段1 ASW架构要明确的问题

阶段1必须把ASW拆成三类：

| 类别 | 模块 | 阶段安排 |
|---|---|---|
| 主链路必需 | `ASW_COM`、`ASW_IN`、`ASW_CORE0`、`adas/*/rfconfig`、`adas/*/eDMAinterface`、`mmwave/mmwavelink`、`mmwave/mailbox` | 阶段2必须有可编译、可运行、可调试的接口。 |
| 基础支撑 | `ASW_BASE`、`ASW_NVM`、`ASW_WDG`、`CDD_CORE0` | 阶段2保留Stub/基础能力，阶段3补完整功能。 |
| OEM/量产增强 | `ASW_CALIBRATION`、`ASW_XCP`、完整Dem/Dcm/NvM映射 | 阶段3完整实现。 |

阶段1架构输出中要明确：

- ASW是否继续按 `ASW_BASE/COM/CORE0/IN/NVM/WDG/XCP/CALIBRATION` 组织。
- 哪些ASW做成ARXML SWC。
- 哪些ASW保持项目级C接口。
- 哪些接口通过RTE调用BSW。
- 哪些接口允许直接调用BSW API。
- mmWave/RF链路是否纳入RTE Runnable，还是继续用项目级任务适配代码调度。

## 4. BSW有哪些模块

### 4.1 BYD工程实际BSW模块

BYD工程 `bswpf\autosar` 下有：

| 模块 | 作用 | 阶段2/阶段3建议 |
|---|---|---|
| `EcuM` | ECU启动、运行、关机管理。 | 阶段2必须。 |
| `BswM` | BSW模式管理，初始化动作、通信/诊断模式动作。 | 阶段2必须有基础动作，阶段3完整策略。 |
| `ComM` | 通信模式管理。 | 阶段2基础FullCom，阶段3完整休眠唤醒。 |
| `CanSM` | CAN网络状态管理。 | 阶段2基础FullCom/BusOff，阶段3完整网络状态。 |
| `Com` | 信号层通信。 | 阶段2最小DBC，阶段3完整DBC。 |
| `PduR` | PDU路由。 | 阶段2必须。 |
| `CanIf` | CAN接口层。 | 阶段2必须。 |
| `CanTp` | ISO-TP，多帧诊断和刷写。 | 阶段2若做最小Boot刷写则需要基础能力；阶段3完整。 |
| `CanNm` | CAN网络管理。 | 阶段3完整，阶段2可先不做完整休眠。 |
| `Nm` | Generic NM。 | 阶段3完整。 |
| `Dcm` | UDS诊断。 | 阶段2只需最小Boot跳转/刷写支撑，阶段3完整。 |
| `Dem` | 故障事件和DTC。 | 阶段2可Stub/基础错误，阶段3完整。 |
| `Det` | 开发错误检测。 | 阶段2建议启用。 |
| `NvM` | 非易失存储管理。 | 阶段2基础参数，阶段3完整Block List。 |
| `MemIf` | 存储抽象。 | 阶段2/3依赖Fls/Fee安排。 |
| `Fee` | Flash EEPROM Emulation。 | 阶段3完整；阶段2如需参数持久化则做最小。 |
| `WdgM` | 看门狗监督。 | 阶段2接口/基础，阶段3完整。 |
| `WdgIf` | 看门狗接口。 | 阶段2/3随外部Wdg驱动。 |
| `Xcp` | 标定测量。 | 阶段3。 |
| `CanTSyn` | CAN时间同步。 | 若项目有时间同步要求则阶段3，否则后置。 |
| `StbM` | 时间基准管理。 | 视时间同步需求决定。 |
| `Crc`、`Bfx`、`Mfl` | 基础库。 | 随依赖启用。 |
| `Rba_*` | ETAS/RTA相关服务库。 | NeuSAR下不照搬，只参考功能等价物。 |

### 4.2 阶段1 BSW架构要明确的问题

阶段1需要把BSW分成三档：

**阶段2必须交付的最小BSW：**

- `EcuM`
- `BswM`
- `ComM`
- `CanSM`
- `Com`
- `PduR`
- `CanIf`
- `CanTp`基础能力，若用于最小刷写
- `Det`
- 最小 `Dcm` 或Boot跳转服务

**阶段2建议具备基础接口但可不完整的BSW：**

- `NvM/MemIf/Fee`
- `Dem`
- `WdgM/WdgIf`
- `CanNm/Nm`

**阶段3完整实现的BSW：**

- 完整 `Dcm`
- 完整 `Dem/DTC`
- 完整 `NvM/Fee/Fls`
- 完整 `CanNm/Nm/ComM` 休眠唤醒
- `Xcp/A2L`
- `CanTSyn/StbM`，如果OEM需要

### 4.3 和BYD工程的差异

BYD工程是ETAS/RTA体系，新项目是NeuSAR。阶段1不能要求东软“复刻文件”，而是要求东软提供功能等价架构：

| BYD形态 | 新项目要求 |
|---|---|
| `bswpf\autosar\Com/CanIf/PduR/...` | NeuSAR等价BSW模块配置和源码/库。 |
| `coem\BYD_UKE\gen_bsw` | NeuSAR生成BSW配置代码。 |
| `Rba_*`库 | NeuSAR对应基础服务或替代方案。 |
| `BswM_Cfg_AC.c`动作列表 | NeuSAR BswM初始化/模式动作设计。 |

## 5. MCAL有哪些模块

### 5.1 BYD工程实际MCAL模块

BYD工程 `bswpf\mcal` 下有：

| 模块 | 作用 | 新项目阶段建议 |
|---|---|---|
| `Mcu` | 时钟、复位、平台初始化。 | 阶段2必须。 |
| `Port` | 引脚复用。 | 阶段2必须。 |
| `Dio` | GPIO。 | 阶段2必须。 |
| `Gpt` | 定时器、OS Tick或周期。 | 阶段2必须。 |
| `Can` | CAN/CANFD控制器。 | 阶段2必须。 |
| `Can_Dma_Interface` | CAN DMA接口。 | 若CAN DMA启用，阶段2确认。 |
| `eDMA` | 数据搬运。 | 阶段2必须重点交付。 |
| `Ipc` | 核间通信CDD/MCAL形式。 | 阶段2必须重点交付。 |
| `Spi` | SPI外设。 | 若SBC/PMIC/外部Flash/RF控制依赖，阶段2。 |
| `Fls` | Flash驱动。 | 阶段2最小Boot/NvM需要，阶段3完整。 |
| `Adc` | ADC采样。 | 若温压监控或硬件诊断需要，阶段2/3。 |
| `MpuP_T` | MPU/保护。 | 阶段2基础配置，阶段3安全强化。 |
| `integration` | MCAL集成。 | 阶段2必须。 |

### 5.2 阶段1 MCAL架构要明确的问题

阶段1要让东软回答：

1. NeuSAR是否支持AWR2944LC上这些MCAL模块。
2. 哪些是东软现成支持，哪些需要适配开发。
3. eDMA和Ipc是标准MCAL、CDD，还是项目专用驱动。
4. Fls是否支持项目Flash和Boot刷写要求。
5. Can/CANFD是否支持目标波特率、Filter、BusOff恢复、DMA。
6. Spi是否覆盖SBC/PMIC/外部Flash/RF控制所需通道。
7. 中断优先级、DMA通道、共享内存、Cache一致性由谁设计和验证。

### 5.3 阶段2必须优先的MCAL

为了支撑mmWave/RF主链路，阶段2 MCAL优先级应该是：

1. `Mcu/Port/Dio/Gpt/Can`
2. `eDMA`
3. `Ipc`
4. `Spi`
5. `Fls`
6. `MpuP_T`
7. `Adc`

其中 `eDMA`、`Ipc`、`Spi`、`Fls` 是容易被标准AUTOSAR计划低估的部分，但对雷达主链路和Boot非常关键。

## 6. CDD有哪些模块

### 6.1 BYD工程实际CDD模块

BYD工程 `bswpf\cdd` 下有：

| 模块 | 作用判断 | 新项目建议 |
|---|---|---|
| `TCAN1043` | CAN收发器控制。 | 阶段2必须，尤其唤醒/Standby/Normal模式。 |
| `LP87745` | PMIC/电源芯片。 | 若新硬件使用同类PMIC，阶段2必须。 |
| `WDGDrv` | 外部看门狗驱动。 | 阶段2保留接口，阶段3完整Wdg集成。 |
| `SaveErrLog` | 错误日志保存。 | 阶段3完整，阶段2可先做基础日志。 |
| `Trap` | Trap/异常处理。 | 阶段2建议保留，用于调试HardFault/异常。 |
| `RxIdCfg` | 接收ID配置。 | 阶段2/3视通信需求。 |
| `VOL_Tem_Test` | 电压温度测试。 | 阶段3完整诊断，阶段2可用于硬件验证。 |
| `ADCtest`、`PMICtest` | 测试类模块。 | 板级Bring-up使用，不一定进量产主路径。 |

BYD工程 `coem\BYD_UKE\components` 下还有项目级组件：

| 组件 | 作用判断 | 新项目建议 |
|---|---|---|
| `AswIf` | ASW接口封装。 | 阶段2建议保留思想。 |
| `AswIfSchedule` | ASW调度接口。 | 阶段2重点。 |
| `AswPerception` | 感知输出接口。 | 阶段2/3随算法链路。 |
| `com` | 项目通信封装。 | 阶段2必须，用于主链路调试输出。 |
| `diag` | 项目诊断封装。 | 阶段3完整。 |
| `fm` | 故障管理。 | 阶段3完整，阶段2可基础错误状态。 |
| `NvmBlockDefine` | NvM Block定义。 | 阶段3完整，阶段2基础参数。 |
| `Sec`、`rbSec` | 安全相关。 | 阶段3配合Boot/HSM。 |
| `VoltemCfg` | 电压温度配置。 | 阶段3完整诊断。 |
| `rbBlock`、`rbVhm`、`CustMPR`、`EDR_interface` | 项目定制功能。 | 阶段1评估是否新项目需要。 |

### 6.2 阶段1 CDD架构要明确的问题

1. 哪些外设由东软开发CDD，哪些我方提供。
2. TCAN1043或新CAN收发器是否由CDD控制。
3. SBC/PMIC型号是否已定。
4. 外部Flash驱动是MCAL Fls、CDD，还是Bootloader私有驱动。
5. Watchdog是外部芯片还是MCU内部Wdg。
6. Trap/ErrorLog是否阶段2纳入调试闭环。
7. 电压温度监控是否阶段2就需要。

## 7. mmWave/RF链路怎么接入AUTOSAR

### 7.1 BYD工程实际接入方式

BYD工程中mmWave/RF不是一个普通的AUTOSAR SWC，它通过项目级任务适配层接入OS：

```text
AUTOSAR OS Task
  OsTask_MmWaveCtrl
  OsTask_DPM
  OsTask_TriggerWave
  OsTask_Trigger66ms
  OsTask_ASW_20ms

项目级任务适配代码
  rte/OsTask_MMW.c

调用链
  Cdd_Ipc / Mailbox
  gIpcSharedMem_r5f
  RE_ASWIN_InCalc_Copy
  RE_ASWIN_InCalc_Capture
  signal_process_initial
  perception_initial
  RE_ASWIN_DivWave_SetWaveGenNormal
  RE_ASWOUT_OutCalc_RadarWarnSignal
```

这说明 BYD架构是：

- OS由AUTOSAR管理。
- RTE管理部分ASW Runnable。
- mmWave关键任务通过项目级适配代码接入。
- RF配置和算法链路在 `adas` 和 `mmwave` 中实现。
- IPC/Mailbox/eDMA/共享内存是雷达主链路关键基础。

### 7.2 新项目建议接入架构

新项目阶段1建议明确以下接入方式：

```text
NeuSAR OS
  启动任务
  BSW 10ms任务
  ASW 10ms/20ms/100ms任务
  mmWave控制任务
  DPM/数据处理任务
  触发/同步任务

RTE生成层
  标准ASW Runnable
  服务接口：Com/NvM/Wdg/Dem/Dcm等

项目级任务适配层
  mmWave控制入口
  IPC/Mailbox回调
  eDMA完成回调
  数据处理触发
  感知输出触发

雷达业务层
  RF配置
  ADC/数据采集
  eDMA/HWA/DSP处理
  感知算法
  CAN输出
```

### 7.3 阶段1必须明确的接口

| 接口 | BYD参考 | 新项目阶段1要明确 |
|---|---|---|
| mmWave控制任务 | `OsTask_MmWaveCtrl` | 任务周期、优先级、触发方式。 |
| DPM任务 | `OsTask_DPM` | 数据路径控制和调度方式。 |
| 触发任务 | `OsTask_TriggerWave`、`OsTask_Trigger66ms` | 是否保留，触发源是什么。 |
| IPC/Mailbox | `Cdd_Ipc`、`Mailbox_readCallback` | 核间通信对象、消息格式、共享内存。 |
| 共享内存 | `gIpcSharedMem_r5f` | 地址、大小、对齐、Cache策略。 |
| eDMA | `adas/*/eDMAinterface` | 通道、优先级、回调、错误处理。 |
| RF配置 | `adas/*/rfconfig` | 我方移植内容，东软支撑接口。 |
| 感知输出 | `AswPerception`、`RE_ASWOUT_*` | 输出数据结构、CAN映射。 |

## 8. RTE接口和项目级接口怎么共存

### 8.1 BYD工程实际情况

BYD工程中RTE是真实存在的：

- `coem\BYD_UKE\gen_rte\Rte.c`
- `coem\BYD_UKE\gen_rte\Rte.h`
- `coem\BYD_UKE\gen_rte\Rte_ASW_COM.h`
- `coem\BYD_UKE\gen_rte\Rte_ASW_NVM.h`
- `coem\BYD_UKE\gen_rte\Rte_ASW_WDG.h`
- `coem\BYD_UKE\gen_rte\OsTask_ASW_10ms.c`
- `coem\BYD_UKE\gen_rte\OsTask_BSW_10ms.c`

同时也存在项目级接口：

- `rte\OsTask_MMW.c`
- `bswpf\framework\pf_com\net_Scheduler\net_Scheduler.c`
- `bswpf\framework\pf_com\net_Nm\net_Mngmt.c`
- `coem\BYD_UKE\components\AswIf`
- `coem\BYD_UKE\components\AswIfSchedule`

典型例子：

- `OsTask_ASW_10ms` 通过RTE生成代码调用 `RE_COM_SWC_func()`。
- `SWC_Com.c` 内部再调用 `ComPlatform_mainfunction()`。
- `ComPlatform_mainfunction()` 再调通信平台、NM调度、用户通信主函数。

这就是“RTE生成入口 + 项目级适配层”的共存方式。

### 8.2 新项目建议规则

阶段1要把接口规则定成这样：

| 接口类型 | 走RTE | 走项目级接口 |
|---|---|---|
| 标准服务调用 | Com、NvM、WdgM、Dem、Dcm、ComM等 | 原则上走RTE或SchM，必要时直接调用BSW API需登记。 |
| 周期Runnable | ASW_COM、ASW_CORE、ASW_NVM、ASW_WDG | 由RTE/OS调度。 |
| 高实时雷达任务 | 不强行包装成标准SWC | 通过项目级任务适配层接入OS。 |
| IPC/Mailbox回调 | 不建议走RTE | 走CDD/项目接口，再通知ASW。 |
| eDMA完成回调 | 不建议走RTE | 走CDD/项目接口，注意中断上下文。 |
| RF配置下发 | ASW可通过接口触发 | 底层由mmWaveLink/项目接口执行。 |
| CAN信号发送 | 阶段2可直接封装调用，阶段3规范化RTE/Com接口 | 允许调试接口先行。 |

### 8.3 阶段1必须输出的接口清单

1. RTE接口清单：
   - Runnable名称。
   - 周期。
   - 输入端口。
   - 输出端口。
   - 服务端口。
   - 模式端口。

2. 项目级接口清单：
   - mmWave控制API。
   - IPC/Mailbox API。
   - eDMA API。
   - RF配置API。
   - 感知输出API。
   - CAN调试输出API。

3. 直接BSW API调用清单：
   - 哪些ASW允许直接调用 `NvM_*`。
   - 哪些ASW允许直接调用 `Dem_*`。
   - 哪些ASW允许直接调用 `Com_SendSignal`。
   - 哪些ASW允许直接调用 `ComM_RequestComMode`。
   - 这些直接调用后续是否要RTE化。

## 9. 哪些功能首版必须做，哪些放第三阶段

### 9.1 首版，也就是阶段2必须做

目标：支撑我方跑通mmWave/RF/ASW主枝干。

| 类别 | 必须做的内容 | 原因 |
|---|---|---|
| OS | 启动任务、BSW任务、ASW任务、mmWave任务、DPM任务、触发任务 | 主链路运行基础。 |
| MCAL | `Mcu/Port/Dio/Gpt/Can/eDMA/Ipc/Spi/Fls最小` | 时钟、通信、DMA、核间通信、RF/Flash前置。 |
| BSW通信 | `CanIf/PduR/Com/CanSM/ComM基础` | CAN调试和状态输出。 |
| RTE | ASW Runnable骨架、RTE头文件、OS任务映射 | 我方ASW能编译运行。 |
| CDD | IPC/Mailbox、TCAN1043、基础Wdg/Trap、必要PMIC/SBC | 板级和雷达链路前置。 |
| mmWave支撑 | mmWaveLink、Mailbox、共享内存、eDMA接口、RF配置支撑 | RF移植和数据链路前置。 |
| Boot | 最小Boot刷写闭环 | 开发测试效率和恢复能力。 |
| 诊断 | 最小跳Boot/版本读取/调试服务 | 支撑刷写和调试即可。 |
| NvM | 最小参数或Stub | 先不阻塞主链路。 |
| Dem/Wdg/NM | 接口或基础状态 | 阶段3完整。 |

阶段2验收应该看：

- 我方ASW能编译进东软工程。
- mmWave/RF初始化路径可跑。
- eDMA/IPC路径可跑。
- CAN可以输出调试状态。
- 最小Boot可以刷APP。
- 任务周期和优先级可测。

### 9.2 第三阶段完整做

目标：补齐OEM和量产功能。

| 类别 | 第三阶段内容 |
|---|---|
| 完整UDS | Session、Security、DID、Routine、CommunicationControl、ECUReset、刷写。 |
| 完整Dem/DTC | 事件、DTC、Snapshot、Extended Data、ClearDTC、老化。 |
| 完整NvM/Fee/Fls | Block List、默认值、掉电写、标定、故障记录、寿命策略。 |
| 完整NM | CanNm、Nm、ComM、CanSM、BswM休眠唤醒、诊断保持通信。 |
| 完整Wdg | WdgM、WdgIf、外部Wdg、Alive/Deadline监督、复位策略。 |
| XCP/A2L | 标定、测量、A2L、工具连接。 |
| Boot/HSM量产 | BootManager、PlatformBoot、CustomerBoot、HSM、安全启动、签名、回滚、量产包。 |
| 时间同步 | CanTSyn/StbM，如OEM需要。 |
| 量产测试 | 长稳、刷写、诊断、休眠唤醒、故障注入、交付包复现。 |

## 10. 阶段1东软必须交付的架构文档

建议阶段1让东软正式交付以下文档：

| 文档 | 必须包含 |
|---|---|
| 软件总体架构设计 | 分层架构、模块清单、责任边界、与BYD参考工程差异。 |
| ASW接口设计 | SWC清单、Runnable清单、RTE端口、项目级接口、直接BSW API清单。 |
| BSW分阶段配置方案 | 阶段2最小BSW、阶段3完整BSW、各模块启用原因。 |
| MCAL支持矩阵 | AWR2944LC支持状态、模块版本、适配风险、验证计划。 |
| CDD设计方案 | TCAN/SBC/PMIC/Flash/Wdg/IPC/Trap等边界。 |
| mmWave/RF接入设计 | OS任务、IPC、eDMA、共享内存、RF配置支撑、数据路径。 |
| RTE与任务设计 | OsTask、Runnable、SchM、RTE生成方式、手写适配代码边界。 |
| Bootloader架构设计 | 最小刷写、量产刷写、HSM、安全启动、APP-Boot跳转。 |
| Memory Map初版 | Boot、APP、HSM、NvM、数据区、标定区、日志区。 |
| 阶段2交付范围说明 | 明确什么必须可运行，什么只是Stub，什么放阶段3。 |

## 11. 阶段1评审时要问东软的问题

1. NeuSAR是否支持 BYD工程中等价的 `Mcu/Port/Dio/Gpt/Can/eDMA/Ipc/Spi/Fls`？
2. eDMA和IPC/Mailbox是标准模块、CDD，还是东软要定制？
3. mmWave/RF主链路相关任务是否允许使用项目级任务适配层？
4. RTE生成如何支持ASW_COM、ASW_CORE、ASW_NVM、ASW_WDG等Runnable？
5. 哪些接口东软要求必须RTE化，哪些允许阶段2先用C接口封装？
6. 阶段2是否能给出可编译、可运行、可刷写的基础平台工程？
7. 阶段2是否包括最小Boot刷写闭环？
8. 阶段3完整UDS、Dem、NvM、NM、Wdg、XCP是否独立报价/计划？
9. Bootloader和HSM是否东软全责，还是东软只做集成？
10. 新项目与BYD量产工程相比，哪些模块不能复用，替代方案是什么？

## 12. 可以直接放进阶段1计划的一句话

阶段1交付目标建议这样写：

> 基于BYD量产工程的软件架构、任务模型、RTE/项目级接口共存方式、BSW/MCAL/CDD模块范围和Boot量产包结构，完成AWR2944LC + NeuSAR平台的软件架构设计。阶段1必须输出ASW/BSW/MCAL/CDD模块清单、mmWave/RF接入方案、RTE与项目级接口边界、Memory Map、Bootloader架构，以及阶段2最小可运行平台和阶段3量产完整功能的明确划分。

