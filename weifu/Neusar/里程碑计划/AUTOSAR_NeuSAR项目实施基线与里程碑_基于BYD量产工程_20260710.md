# 毫米波雷达控制器 AUTOSAR/NeuSAR 项目实施基线与里程碑

版本：V1.0  
日期：2026-07-10  
目标芯片：TI 2944LC（最终料号、SDK、编译器、MCAL支持范围以阶段0冻结结果为准）  
量产参考工程：`D:\Weifu\Project\CR\BYD_RL\xxx`  
适用对象：威孚项目组、东软/NeuSAR项目组、测试与量产发布团队

## 目录

1. 文档目的与执行原则
2. 项目目标与范围
3. BYD量产工程基线
4. 项目组织与人员配置
5. 总体计划与里程碑
6. 阶段0：启动、输入冻结与架构设计
7. 阶段1：快速跑通mmWave/RF主链路
8. 阶段2：完成OEM强相关功能
9. 阶段3：达到量产交付能力
10. 统一交付包结构
11. 项目管控机制
12. 主要风险与措施
13. 仍需新项目冻结的TBD
14. 最终执行口径
15. 附录A至F：OS/ISR、诊断、NvM、通信/NM/Wdg/XCP和工程依据

## 1. 文档目的与执行原则

本文档将 `D:\Weifu\Docs\BrainTrust\weifu\Neusar` 目录下已有计划、阶段架构、Bootloader、QA、诊断、NvM、Wdg、XCP等材料统一收敛为一份项目实施基线，可用于：

1. 对东软发出正式需求输入。
2. 双方拆解WBS、人员、里程碑、交付物和验收标准。
3. 指导NeuSAR、MCAL、CDD、RTE、Bootloader和系统集成实施。
4. 作为范围变更、问题澄清和阶段验收的共同依据。

本项目必须遵守以下原则：

- 以BYD量产工程的实际生成配置和运行代码为参考基线，不以通用AUTOSAR模块清单代替雷达项目实际主链路。
- 架构、模块边界和运行机制参考BYD；芯片PinMux、外设型号、Flash地址、CAN ID、OEM诊断矩阵等必须根据新项目输入重新冻结，不能机械复制。
- 先交付可供我方移植mmWave/RF、信号处理和ASW的可运行底座，再补齐OEM功能，最后形成量产候选版本。
- Bootloader从项目启动即并行推进：阶段1必须有APP刷写/启动最小闭环，阶段3完成完整Boot/HSM/Secure Boot和量产包。
- 每阶段必须同时交付源码、配置工程、生成代码、构建脚本、说明、测试报告、ReleaseNote和KnownIssues，不能只交二进制或只在供应商环境可编译的工程。

## 2. 项目目标与范围

### 2.1 总体目标

基于BYD量产工程的软件形态，建立适配TI 2944LC的AUTOSAR/NeuSAR平台，使我方能够快速移植和开发：

- mmWave/RF配置与控制。
- mmWaveLink通信链路。
- Mailbox/IPC核间交互。
- eDMA/共享内存数据链路。
- 信号处理、数据处理、感知算法。
- ASW状态管理、通信、诊断适配、NVM、Wdg、XCP接口。

最终形成可重复生成、编译、打包、刷写、测试和发布的量产软件基线。

### 2.2 范围边界

| 工作域 | 我方主责 | 东软主责 | 共同工作 |
|---|---|---|---|
| 总体技术架构 | 目标架构、范围、优先级、接口决策、验收 | NeuSAR可实现方案与风险反馈 | 架构评审与冻结 |
| ASW | ASW_BASE/COM/CORE0/IN/NVM/WDG/XCP/CALIBRATION等业务 | 提供RTE、BSW服务和集成支持 | 接口联调 |
| mmWave/RF | Profile/Chirp/Frame、RF监控、Sensor Start/Stop业务 | OSI、IPC、CRC、锁/信号量、底层适配 | 主链路Bring-up |
| 信号/数据处理 | DSP/HWA/eDMA使用、算法、感知 | eDMA/中断/共享内存基础能力 | 性能与稳定性调优 |
| BSW/OS/RTE | 提供需求与ASW接口 | NeuSAR配置、生成、集成 | 配置评审 |
| MCAL | 提供硬件连接、PortList、外设资料 | Mcu/Port/Dio/Can/Gpt/Fls/Spi等配置集成 | 板级验证 |
| CDD | 提供功能需求和可复用BYD代码 | IPC/DMA及约定外设CDD适配集成 | 驱动联调 |
| 通信/诊断 | DBC、DID/DTC/Routine和OEM规则 | Com/PduR/CanIf/CanTp/Dcm/Dem配置 | CANoe/诊断仪验收 |
| Boot/HSM | 发布包、安全策略、密钥流程输入 | Bootloader、Crypto/HSM集成、合包工具 | 刷写与安全启动验收 |
| 测试发布 | 系统用例和整车场景 | BSW/MCAL/Boot自测与问题支持 | 集成、回归、Release |

## 3. BYD量产工程基线

### 3.1 软件分层

BYD工程是AUTOSAR生成代码、项目适配层、雷达SDK和ASW共存的混合架构，不是纯手写工程，也不是所有接口均RTE化。

```text
ASW / Algorithm
  asw/                基础、通信、NVM、Wdg、XCP、标定等
  adas/               RF配置、DSP/HWA、eDMA、感知
  mmwave/             mmWaveLink、Mailbox、监控和SDK抽象

RTE / Project Adapter
  coem/BYD_UKE/gen_rte/   Rte、SchM、周期OsTask生成物
  rte/OsTask_MMW.c        mmWave、DPM、Trigger任务和共享内存适配

AUTOSAR BSW
  BswM/CanIf/CanNm/CanSM/CanTp/CanTSyn/Com/ComM/Dcm/Dem/Det
  EcuM/Fee/MemIf/Nm/NvM/PduR/StbM/WdgIf/WdgM/Xcp等

MCAL / CDD
  Mcu/Port/Dio/Can/eDMA/Gpt/Ipc/Fls/Spi/Adc/Mpu
  LP87745/TCAN1043/WDGDrv/SaveErrLog/Trap等

Boot / Security / Package
  BootManager/PlatformBoot/CustomerBoot/App/HSM/WeifuData/CustData/ClibData
```

### 3.2 模块基线

| 分类 | BYD实际模块 | 本项目处理 |
|---|---|---|
| ASW | ASW_BASE、ASW_CALIBRATION、ASW_COM、ASW_CORE0、ASW_IN、ASW_NVM、ASW_WDG、ASW_XCP、CDD_CORE0、SGU_Inject | 我方移植/开发，阶段1提供可编译Stub和关键接口 |
| BSW通信 | CanIf、CanNm、CanSM、CanTp、CanTSyn、Com、ComM、Nm、PduR、StbM | 阶段1最小CAN；阶段2完整通信/NM/时间同步 |
| BSW诊断 | Dcm、Dem、Det | 阶段1仅保留最小调试/跳Boot依赖；阶段2完整OEM功能 |
| BSW存储 | NvM、MemIf、Fee、Rba_FeeFs1x | 阶段1最小参数/刷写支持；阶段2完整持久化 |
| 系统服务 | EcuM、BswM、Crc、Bfx、Mfl | 阶段1完成启动和主循环 |
| 看门狗 | WdgM、WdgIf、外部LP87745 watchdog | 阶段1保证开发板安全；阶段2完成量产复位闭环 |
| 标定 | Xcp | 阶段2完整交付A2L、DAQ、CAL/PAG |
| MCAL | Adc、Can、Can_Dma_Interface、Dio、eDMA、Fls、Gpt、Ipc、Mcu、MpuP_T、Port、Spi | 按新硬件裁剪；Ipc/eDMA/Can/Mcu/Port/Dio阶段1优先 |
| CDD | LP87745、TCAN1043、WDGDrv、SaveErrLog、RxIdCfg、Trap、测试CDD | IPC/DMA阶段1；外设和错误日志阶段2完整 |

### 3.3 必须保持的关键架构事实

1. BYD工程有完整生成RTE：`Rte.c/h`、`Rte_ASW_*.h`、`SchM_*.h`、`Rte_BSWMD.arxml`、`osNeeds.arxml`和周期OsTask生成代码均存在。
2. RTE与项目适配接口共存：普通SWC/Runnable走RTE，mmWave/IPC/eDMA等实时或平台相关链路通过项目适配层/CDD接入。
3. mmWave/RF主控制链路为 `mmWaveLink + Mailbox/IPC`。`mmwave_link_mailbox.c` 将 `MMWave_mboxOpen/Read/Write/Close` 注册给mmWaveLink，并在此后调用 `rlDevicePowerOn()`。
4. `mmwave_link_spi_22xx.c` 在BYD工程中为空文件，RF主链路不依赖AUTOSAR SPI。
5. SPI在BYD中用于LP87745 PMIC/外部Watchdog寄存器访问；外部NOR Flash走QSPI/Fls/Fee链路。两者不能与RF控制SPI混淆。
6. BYD存在CanNm/Nm/ComM/CanSM/BswM网络管理，并通过项目侧 `net_NM_schedule()` 调用 `CanNm_MainFunction()`。
7. BYD存在完整Boot容器结构和APP/Boot跳转接口，Boot不是后期附加项。

## 4. 项目组织与人员配置

### 4.1 我方五人建议分工

| 角色 | 人数 | 主责 | 阶段验收责任 |
|---|---:|---|---|
| 技术架构/项目技术负责人 | 1 | 总体架构、任务/中断/接口/Memory Map/Boot决策，东软技术接口，范围和风险管理 | 所有里程碑最终技术签字 |
| 平台与mmWave负责人 | 1 | mmWaveLink、RF配置、Mailbox/IPC、TI SDK、RF监控 | 阶段1 RF控制链路 |
| 算法与数据链负责人 | 1 | DSP/HWA、DPM、eDMA、共享内存、信号/数据处理、性能 | 阶段1数据链和实时性 |
| ASW/RTE接口负责人 | 1 | ASW模块、Runnable、RTE/手写适配、NVM/Wdg/XCP应用接口 | 阶段1接口、阶段2应用集成 |
| 通信诊断与测试负责人 | 1 | DBC、CANoe、UDS、DTC、NvM、XCP、Boot刷写、测试和发布 | 阶段2 OEM功能、阶段3发布 |

技术架构负责人负责决策和验收，但每个模块必须有唯一执行Owner，避免所有问题集中到架构负责人。

### 4.2 东软最低角色要求

东软至少需要覆盖：项目经理、AUTOSAR架构/集成、OS/RTE、BSW配置、MCAL/CDD五类职责；阶段2开始建议单独投入通信诊断和测试发布人员。若一人兼任多角色，必须在计划中明确其投入比例和备份人员。

## 5. 总体计划与里程碑

### 5.1 建议周期

| 阶段 | 建议时间 | 里程碑 | 业务结果 |
|---|---|---|---|
| 阶段0：启动与输入/架构冻结 | T0至T0+2周，可与阶段1并行 | M0 | 范围、工具、架构、Memory Map和Boot边界清晰 |
| 阶段1：快速跑通主链路 | T0至T0+6周 | M1 | 我方可开始RF、信号处理、数据处理和ASW并行开发 |
| 阶段2：完成OEM强相关功能 | M1后5周 | M2 | 诊断、存储、NM、Wdg、XCP达到OEM集成测试条件 |
| 阶段3：达到量产交付能力 | M2后6至8周 | M3 | 完整Boot/HSM、量产包、系统回归和可复现交付完成 |

总周期建议17至19周。时间为计划基线，最终日期由双方根据NeuSAR对目标芯片的成熟度、硬件到位时间和OEM输入冻结情况确认。

### 5.2 里程碑准入/准出

| 里程碑 | 准入条件 | 准出条件 |
|---|---|---|
| M0 | 合同/范围确认，双方Owner到位 | 支持矩阵、输入清单、架构、接口、Memory Map初版、Boot方案和风险清单评审通过 |
| M1 | 硬件、编译器、调试器、基础MCAL/SDK可用 | 可编译上板；OS任务、IPC、mmWaveLink、eDMA、最小CAN、APP刷写/启动闭环通过 |
| M2 | OEM诊断/通信/存储需求初版冻结 | Dcm/Dem/NvM/NM/Wdg/XCP按矩阵测试通过，ASW和BSW并行稳定运行 |
| M3 | Boot/HSM/量产规则冻结，M2问题关闭 | 完整刷写、安全启动、系统回归、可复现构建和正式Release包验收通过 |

### 5.3 按东软原计划分类的阶段范围

| 原表分类 | 阶段1：快速主链路 | 阶段2：OEM功能 | 阶段3：量产能力 |
|---|---|---|---|
| NeuSAR配置 | OS、EcuM/BswM、RTE骨架、最小Com/PduR/CanIf/Det | Dcm/Dem、NvM、NM/ComM/CanSM/BswM、WdgM/WdgIf、XCP、CanTSyn/StbM按需 | 配置冻结、Release开关、生成代码冻结 |
| MCAL配置 | Mcu/Port/Dio/Can/Gpt/Ipc/eDMA，Fls最小能力 | Fls/Spi/Adc及完整Can配置，按外设和OEM需求补齐 | 全量MCAL冻结、性能/资源/安全配置确认 |
| CDD/平台适配 | Cdd_Ipc、Cdd_Dma、Mailbox、共享内存、mmWaveLink OSI | LP87745/Watchdog、TCAN1043、错误日志、外设测试CDD | CDD冻结、异常恢复和量产诊断完善 |
| 系统集成 | 上电、任务、RF控制、数据链、最小CAN、APP刷写 | ASW与诊断/存储/NM/Wdg/XCP集成 | ASW/RF/BSW/Boot/HSM全系统回归 |
| Boot/HSM | Memory Map、APP镜像、最小刷写/启动 | UDS跳Boot接口和量产需求冻结 | 完整Bootloader、HSM/Crypto/Secure Boot、量产包 |
| 我方ASW | Stub、RF/信号/数据主枝干移植 | OEM业务回调、DTC、NvM、功能抑制、标定接入 | 功能冻结、性能优化、量产版本 |

## 6. 阶段0：启动、输入冻结与架构设计

### 6.1 目标

把项目从“通用AUTOSAR需求”收敛为可实施的雷达软件架构，冻结阶段1所需的全部输入和关键技术边界。

### 6.2 详细工作

| 工作项 | 设计/实施要求 | 我方输入 | 东软输出 | 验收 |
|---|---|---|---|---|
| 目标平台支持性 | 明确NeuSAR cCore、AUTOSAR版本、TI 2944LC料号、SDK、编译器、OS和MCAL/CDD支持状态 | 芯片料号、板卡版本、SDK目标版本 | 支持矩阵、限制、替代方案、已验证案例 | 所有“不支持/部分支持”项有Owner和关闭计划 |
| 软件分层 | 映射ASW/RTE/适配层/BSW/MCAL/CDD/Boot，不得把项目适配层遗漏 | BYD目录与模块说明 | 总体架构图、模块清单、阶段归属 | 能逐项映射BYD模块和新项目Owner |
| 运行时架构 | 定义Task、周期、优先级、Activation、Counter/ScheduleTable、ISR、资源、栈测量方法 | BYD OS基线、我方实时链路需求 | OS Task/ISR/Resource表、启动时序 | 可指导OS配置；StackSize不得凭空填写 |
| 接口架构 | RTE用于SWC/周期Runnable，CDD/适配层用于IPC、DMA、mmWave等平台链路 | ASW接口初版、BYD RTE基线 | RTE接口、直接BSW API、CDD/适配接口矩阵 | 每个接口有提供方、使用方、上下文、同步方式、错误码 |
| Memory Map | 覆盖Boot、APP、HSM、Fee/Fls、共享内存、IPC vring、eDMA buffer、L2/L3、标定和日志 | 镜像规模、数据规模、硬件内存资源 | 地址/大小/对齐/cache/访问方/linker section表 | 无重叠；DMA/IPC双方地址和cache属性一致 |
| Boot架构 | 明确BootManager/PlatformBoot/CustomerBoot、APP-Boot跳转、镜像校验、异常恢复 | 刷写通道、量产包和安全策略 | Boot方案、分区、镜像格式、最小刷写计划 | 阶段1最小刷写闭环和阶段3完整范围明确 |
| 输入资料分级 | 可不提供完整原理图，但必须提供足够的脱敏硬件接口资料 | PortList、IO Map、外设BOM、电源/复位/片选/中断映射 | 缺口清单及影响评估 | MCAL/CDD可配置；需现场调试的测试点资料按阶段提供 |

### 6.3 阶段0必须冻结的输入

- 目标芯片完整料号、板卡版本、晶振/时钟、电源和复位条件。
- PortList/IO Map：Pin、Mux、方向、初值、上下拉、电平、外设实例、片选、中断、使能/待机脚。
- CAN/CANFD通道、收发器型号、标称/数据波特率、DBC或通信矩阵。
- 外部PMIC/SBC、Watchdog、Flash、EEPROM、ETH Switch等器件型号和接口。
- mmWave核分配、Mailbox endpoint、共享数据对象、eDMA通道和数据规模初版。
- ASW模块与Runnable清单；若无完整ASW ARXML，允许阶段1采用Stub + 接口表。
- 诊断、DTC、NvM、XCP、NM、Boot和安全需求初版及TBD关闭时间。

### 6.4 阶段0交付物

1. 《项目范围和责任矩阵》。
2. 《NeuSAR/MCAL/CDD/Boot/HSM支持矩阵》。
3. 《软件总体架构设计》。
4. 《运行时架构设计》。
5. 《接口架构与RTE/适配层边界》。
6. 《Memory Map和Linker Section初版》。
7. 《Bootloader架构和刷写方案》。
8. 《阶段1详细计划、风险和TBD清单》。

## 7. 阶段1：快速跑通mmWave/RF主链路

### 7.1 阶段目标

交付一个可生成、可编译、可上板、可调度、可通信、可刷写的NeuSAR基础平台，让我方能够同步移植RF、信号处理、数据处理和ASW主枝干。

最小闭环：

```text
上电 -> Mcu/Port初始化 -> OS启动 -> EcuM/BswM最小初始化
     -> mmWave控制Task -> Mailbox/IPC -> mmWaveLink -> RF初始化/启动
     -> eDMA/共享内存 -> 数据处理Task -> CAN/CANFD状态输出
     -> APP可通过约定方式更新并重新启动
```

### 7.2 NeuSAR/系统服务

| 模块 | 详细要求 | 输入 | 设计要点 | 交付与验收 |
|---|---|---|---|---|
| EcuM/BswM | 实现最小启动流和BSW初始化顺序，进入稳定主循环 | 硬件启动时序、BYD EcuM/BswM参考 | Mcu/Port/Can/IPC/DMA/RTE启动先后可追踪；异常进入可诊断状态 | 启动流程、配置、trace；连续冷/热启动无异常 |
| OS | 建立BYD对应的10个Basic Task/BCC2模型或经评审的等价裁剪 | 附录A任务/ISR基线 | 数字优先级沿用BYD语义；mmWave实时任务高于普通周期Task；无Extended Task/Event | OS配置、Summary、优先级表、栈测量报告；周期与触发可观测 |
| RTE/SchM | 生成RTE骨架、周期Runnable、SchM和BSWMD；允许ASW Stub | ASW接口清单、BYD gen_rte | 普通Runnable走RTE；IPC/DMA/mmWave走CDD/适配层；接口Owner唯一 | 我方ASW可编译接入，Runnable可被OS调用 |
| Det/Trap/日志 | 保留Bring-up错误检测、HardFault/Trap和关键启动日志 | 错误码/日志接口 | ISR中不阻塞；日志不能破坏实时性 | 可定位启动、IPC、DMA、CAN失败原因 |

### 7.3 MCAL与CDD基础平台

| 模块 | 东软必须完成 | 我方输入 | 验收 |
|---|---|---|---|
| Mcu/Port/Dio | 时钟、复位、PinMux、GPIO方向/初值、电源/收发器控制 | PortList、晶振、外设控制表 | 关键时钟和引脚测量正确；上电无冲突 |
| Can/CanIf/PduR/Com最小链路 | 至少一组Tx/Rx和调试状态PDU，支持目标CAN/CANFD波特率 | 最小DBC、状态/错误报文 | CANoe可收发；ASW可发送状态；BusOff可定位 |
| Cdd_Ipc/Mailbox | 初始化、endpoint、中断、收发、回调、超时、错误码、共享内存协议 | 核间消息表、数据结构、目标核资源 | 双向收发稳定；中断触发回调；断链/超时可检测 |
| Cdd_Dma/eDMA | 通道、PaRAM/链式传输、中断/回调、错误处理、资源表 | 搬运源/目的、长度、周期、并发需求 | 真实数据搬运正确；无通道冲突；错误可恢复 |
| Gpt | 系统周期和阶段1必要定时能力 | 周期与精度 | 周期误差满足要求；不与OS Tick/Watchdog冲突 |
| Fls最小能力 | 支持阶段1约定的APP镜像写入/启动，不要求此时完成全部NvM | Flash型号/布局、刷写方法 | 镜像可重复写入、校验、启动 |

### 7.4 mmWaveLink与RF支撑

东软负责底层平台适配，我方负责RF业务配置。

东软必须交付：

- `rlComIfOpen/Close/Read/Write` 到Mailbox/IPC的适配。
- `rlRegisterInterruptHandler` 对应的异步事件/中断通知机制。
- Mutex、Semaphore、Queue、Delay、CRC等mmWaveLink OSI适配。
- `rlDevicePowerOn()` 前后的初始化顺序、超时和错误码传播。
- 可观测日志：区分IPC错误、BSS/RSS返回错误、CRC错误、超时和业务配置错误。

我方负责：

- Profile/Chirp/Frame配置及RF标定参数。
- `rlSetProfileConfig`、`rlSetChirpConfig`、`rlSensorStart/Stop`等业务链路。
- RF监控、信号处理和感知算法接入。

验收至少包括：mmWaveLink通信初始化、`rlDevicePowerOn()`、最小RF配置下发、Sensor Start/Stop、异步事件接收和错误注入定位。

### 7.5 DMA、共享内存与Memory Map

BYD基线中：

- `gIpcSharedMem_r5f[1152]` 放在 `.bss.ipc_vring_mem`，128字节对齐。
- `gSharedDataStr` 放在 `.shared_mem`。
- `gDotResArr[350]`、DCM 4096字节请求响应Buffer和XCP DAQ RAM放在 `.r5f_L3data`。
- DOA L2工作区需求为90 KiB，项目临时区使用 `.rbSecBootTemp`。

新项目必须重新输出每个共享区的地址、大小、对齐、cache属性、读写核、生命周期和所有权。DMA Buffer必须采用适合目标R5F cache line的对齐和cache维护策略；不得仅验证一次内存拷贝，需覆盖连续帧和并发中断。

### 7.6 最小Boot/APP刷写闭环

阶段1必须完成：

1. APP目标地址、链接布局和镜像格式初版。
2. Boot启动APP或等价启动链路。
3. APP进入Boot/下载模式的最小路径，可先采用经双方确认的Stub或标志位。
4. 至少一种不依赖单步调试的APP更新方式。
5. 镜像CRC/完整性基础检查和失败保护。
6. 烧录、回读、启动和版本确认手顺。

完整UDS刷写、安全启动和HSM可在阶段3完成，但阶段1不能长期只依赖JTAG更新APP。

### 7.7 阶段1交付物与验收

交付物：NeuSAR/MCAL/RTE配置工程、生成代码、集成源码、linker/Memory Map、编译脚本、IPC/DMA示例、最小CAN配置、APP镜像与刷写手顺、测试报告、ReleaseNote、KnownIssues。

M1验收必须同时通过：

- 我方电脑可复现生成和编译。
- 板端可稳定启动，10个任务或经评审裁剪后的等价任务可观测。
- Mailbox/IPC双向收发和异常检测通过。
- mmWaveLink最小控制链路通过。
- eDMA/共享内存连续数据验证通过。
- CAN/CANFD状态输出通过。
- APP可更新、可启动、坏镜像不被当作正常APP运行。

## 8. 阶段2：完成OEM强相关功能

### 8.1 目标

在主链路可运行的基础上，补齐OEM通信、诊断、故障、存储、网络管理、看门狗和标定功能，使系统达到OEM台架和整车集成测试条件。

### 8.2 Dcm/CanTp/诊断

| 项目 | BYD基线 | 东软实施要求 | 输入/验收 |
|---|---|---|---|
| DoCAN链路 | CanIf->CanTp->PduR->Dcm，BSW 10ms调度 | 配置物理/功能寻址、Buffer、CanTp参数、主函数调度 | 以附录C为基线；新OEM变更形成差异表 |
| 会话 | 0x01/0x02/0x03/0x06/0x60 | 配置P2/P2*、Boot跳转和会话Mode | 会话切换、S3、NRC和跳Boot测试 |
| 安全访问 | L1、L31、L32 | 配置Seed/Key、失败计数、延时和NvM保持 | 算法/密钥由我方或OEM提供；错误尝试测试 |
| 服务 | 0x10/11/14/19/22/27/28/2E/31/3E/85；0x2F不支持 | 仅开启需求矩阵中明确支持项 | 服务/子功能/会话/安全/寻址/NRC全矩阵测试 |
| DID/Routine | 见附录C | 生成回调、长度、读写属性、Session/Security、NvM映射 | 诊断仪逐项自动化测试 |

新项目不能把诊断调查表空白项默认当作支持；只有冻结矩阵中标Y并完成回调/数据源的DID、DTC、Routine才进入配置。

### 8.3 Dem/DTC与FiM

BYD实际配置：217个Dem Event、59个DTC Class，Dem标准Indicator关闭；“报警提示”由ASW侧 `ASWIN_FIM` 的ErrorLamp、BlindnessLamp和功能降级输出实现，不等同于Dem WarningIndicator。

实施要求：

- 配置Event/DTC映射、Debounce、OperationCycle、Confirmation、Aging、Clear、FreezeFrame和ExtendedData。
- `0x19`支持子功能按BYD基线为0x01、0x02、0x04、0x06、0x0A；新OEM变更必须显式列出。
- 若延续BYD架构，东软保证Dem Event状态接口和20ms调度可供ASWIN_FIM使用，不凭空配置标准FiM矩阵。
- 若项目决定迁移到标准AUTOSAR FiM，必须把BYD `g_ASWIN_FIM_DTCFctDegrdTable_ast` 转换为FID/InhibitionMask矩阵，并作为范围变更评审。
- 标准Dem Indicator默认不配置；若OEM明确要求，需新增灯类型、Event映射、亮灭阈值、OperationCycle和清故障策略。

验收：故障注入、去抖、确认、存储、0x19读取、0x14清除、恢复/老化、功能抑制和重启保持全部可追踪。

### 8.4 NvM/MemIf/Fee/Fls

BYD基线：NvM Block ID 0至104，共105个；0为MultiBlock、1为ConfigId，用户Block为2至104。Fee为单设备、103项物理Block属性，两个物理扇区为 `0x00350000-0x0038FFFF` 和 `0x00390000-0x003CFFFF`；仅 `NvMBlockDescriptor_ECUConfiguration` 使用冗余策略。外部Flash基线为W25Q32JV、容量0x400000，经QSPI/Fls访问。

存储策略：

- 启动执行ReadAll，使DID、DEM、标定、EDR、复位原因等RAM镜像恢复。
- 不把关机WriteAll作为唯一保存路径；BYD基线全局WriteAll并未作为主要保存策略。
- DID、标定、EDR、故障、安全计数、刷写标志等按业务事件显式WriteBlock/SetRamBlockStatus。
- 每个Block必须明确RAM地址、ROM默认值、NV长度、管理类型、CRC、写触发、写频率、掉电策略和诊断关系。
- 新项目Flash/Boot/HSM分区变化时必须重算Fee地址，不能直接复制BYD绝对地址。

验收：ReadAll、显式写入、复位/掉电恢复、默认值、冗余块、Fee换扇区、重复写入、异常掉电、寿命评估和数据损坏恢复。

### 8.5 NM/ComM/CanSM/BswM

BYD存在完整CanNm/Nm/ComM/CanSM/BswM。新项目需完成：

- CanNm PDU、状态机和主函数周期。
- Generic Nm映射。
- ComM User/Channel和FullCom/SilentCom/NoCom切换。
- CanSM启动、BusOff恢复和控制器模式管理。
- BswM网络、诊断、启动/休眠规则。
- 诊断保持通信、唤醒源、休眠条件和超时。

验收覆盖冷启动、网络请求/释放、休眠、总线唤醒、本地唤醒、诊断保持、BusOff恢复和反复电源循环。

### 8.6 WdgM/WdgIf与外部Watchdog

必须严格区分“WdgM生成配置”和“真实硬件复位闭环”：

- BYD生成配置有1个Supervised Entity和1个Checkpoint，采用Alive Supervision；没有Deadline Supervision。
- Mode0：Min=0、Max=2、Expected=10、ReferenceCycle=10、Tolerance=2。
- Mode1：Min=1、Max=1、Expected=9、ReferenceCycle=10、Tolerance=0。
- `WdgM_MainFunction()` 在BSW 10ms中调度。
- 但BYD `ASW_WDG.c` 中CheckpointReached业务体被 `#if 0` 关闭，因此不能宣称WdgM Alive当前已形成运行复位闭环。
- BYD真实硬件复位链路是：被监控链路调用 `FUSA_WDGDrv_SetTriggerCondition()` 刷新计数200；GPT回调递减计数并调用 `LP87745_Wdg_Trigger()`；计数到0后停止喂LP87745，最终由外部PMIC watchdog复位。
- LP87745通过 `Spi_SetupEB/Spi_SyncTransmit` 访问，SPI不是RF主链路。

新项目默认沿用Alive、不配置Deadline。若要让WdgM Alive真正生效，必须明确启用Checkpoint调用、监督周期、容差、Local/Global状态反应，并与外部Watchdog触发策略连接。验收需分别覆盖WdgM状态监督和LP87745真实复位链路。

### 8.7 XCP/A2L

BYD实际基线：XCP over CAN开启、Ethernet关闭；CAL/PAG/DAQ开启；STIM和PGM关闭；Timestamp开启；DAQ RAM 1024字节；MAX_CTO/MAX_DTO为64；Rx ID 0x332、Tx ID 0x778，位于CANNODE_1；Xcp_MainFunction在BSW 10ms，ASW XCP Runnable在100ms。

东软需交付：

- XCP on CAN/CANFD传输和CanIf/PDU映射。
- A2L生成流程及与ELF/MAP地址的一致性检查。
- 测量变量、标定变量、类型、地址、大小、访问权限和量产开关清单。
- DAQ Event、周期、优先级、时间戳和带宽预算。
- CAL/PAG内存段和页切换策略。
- Seed&Key或连接权限策略，若OEM/量产模式要求。
- 禁止默认开启STIM和XCP Flash Programming。

验收使用CANape/INCA或双方约定工具完成连接、Upload/Download、DAQ、页切换、A2L一致性、错误访问和实时性影响测试。

### 8.8 阶段2交付与验收

交付：完整OEM BSW配置、生成代码、诊断矩阵、DTC/Event矩阵、NvM BlockList和Fee/Fls布局、NM状态机与测试、Wdg/PMIC测试、XCP/A2L、ASW接口说明、测试报告、ReleaseNote、KnownIssues。

M2准出要求：

- OEM通信和诊断自动化用例通过。
- DTC上报、读取、清除、老化和功能抑制通过。
- NvM掉电保持和Fee异常恢复通过。
- NM休眠唤醒、诊断保持和BusOff恢复通过。
- 外部Watchdog卡死复位和复位原因记录通过。
- XCP测量/标定和A2L一致性通过。
- 上述功能与mmWave/RF主链路并行运行无不可接受的实时性退化。

## 9. 阶段3：达到量产交付能力

### 9.1 完整Bootloader

按BYD `BootManager + PlatformBoot + CustomerBoot + APP + HSM + Data` 思路设计，具体实现由目标芯片和OEM规则冻结。必须完成：

- Boot启动链、APP有效性检查和Boot->APP跳转。
- APP通过Dcm/EcuM/BswM或冻结的等价机制进入Boot。
- UDS下载、擦除、写入、校验、依赖检查、复位和版本管理。
- 编程失败、断电、错误镜像、版本不兼容的保护和恢复。
- APP有效标志、刷写请求、Fingerprint、ResetReason等NvM数据闭环。
- 镜像格式、分区、链接地址、版本规则和兼容矩阵。

### 9.2 HSM/Crypto/Secure Boot

明确HSM固件提供方、Crypto Driver、密钥/证书Owner、签名工具、生产密钥注入和调试密钥退出机制。验收至少覆盖正确签名启动、篡改拒绝、错误密钥、版本回退策略、密钥数据保护和审计日志。

AUTOSAR模块和HSM/Crypto能力只能提供安全机制；信息安全合规、TARA、密钥流程和证据仍需单独管理。功能安全同理，AUTOSAR/OS/Wdg/MPU等不是ISO 26262合规本身，若项目有ASIL目标，需要额外的安全计划、需求、分析、验证和工作产品。

### 9.3 量产包与可复现交付

正式包应包含：BootManager、PlatformBoot、CustomerBoot、APP、协处理核/RSS镜像、HSM、WeifuData、CustData、ClibData或新项目等价数据区。

必须固定：工具版本、许可证依赖、配置输入、代码生成命令、编译命令、链接脚本、镜像转换、签名、合包、刷写和版本命名。第三方在干净环境按说明应能复现生成、编译、打包和刷写。

### 9.4 系统验证

量产候选版本至少完成：

- 多轮冷/热启动、休眠唤醒和电源循环。
- RF初始化、连续运行、数据链吞吐和任务负载。
- IPC/DMA异常、CAN BusOff、诊断并发、NvM忙/掉电、Watchdog复位。
- Boot下载中断、错误镜像、安全启动和回滚/恢复。
- XCP开启/关闭、调试版/量产版配置差异。
- 长稳、边界电压/温度、内存/栈/CPU负载和错误日志。

### 9.5 阶段3交付与验收

交付物：量产源码和配置基线、完整Boot/HSM工程、正式镜像和合包脚本、编译/生成/刷写手顺、全量测试报告、追溯矩阵、ReleaseNote、KnownIssues、许可证/第三方组件清单、培训材料。

M3准出：正式刷写流程、安全启动、系统回归、可复现构建和文档齐套全部通过；高优先级问题关闭，中低优先级问题有接受人和计划。

## 10. 统一交付包结构

```text
Release_<Project>_<Version>
  01_Source
  02_Config
  03_Generated
  04_Build_and_Linker
  05_Boot_HSM_Package
  06_Document
  07_TestReport
  08_ReleaseNote
  09_KnownIssues
  10_ToolVersion_License
  11_UserGuide_Training
  12_Traceability
```

每次交付必须有版本号、Git提交或等价基线号、配置差异、生成工具版本、编译器版本、校验值和可复现步骤。

## 11. 项目管控机制

### 11.1 会议与问题管理

- 每周项目例会：计划、资源、交付、风险。
- 每周技术专题：OS/IPC/DMA、诊断/NvM、Boot/HSM按需要拆分。
- QAList必须包含Owner、严重度、计划日期、实际关闭日期、版本和证据。
- 阻塞问题24小时内升级；范围/架构/接口/Memory Map变更必须走CR。

### 11.2 配置和变更管理

以下内容一旦冻结，修改必须提供影响分析：芯片/SDK/编译器、OS Task/ISR、Memory Map、RTE接口、DBC/PDU、DID/DTC/Routine、NvM Block、Boot分区、HSM/密钥流程和发布包格式。

### 11.3 质量门禁

每个里程碑至少检查：可编译、静态检查、单元/模块测试、上板测试、配置一致性、文档、KnownIssues和复现性。模块“配置完成”不等于验收完成，必须有板端或工具端证据。

## 12. 主要风险与措施

| 风险 | 影响 | 管控措施 |
|---|---|---|
| NeuSAR/MCAL对2944LC支持不完整 | 阶段1延期 | M0提供支持矩阵、替代CDD和PoC |
| 把RF主链路误做成SPI | 资源跑偏 | 锁定mmWaveLink over Mailbox/IPC；SPI只服务实际外设 |
| IPC/DMA/cache/对齐设计不清 | 随机数据错误 | 阶段0冻结Memory Map；阶段1做连续帧和异常测试 |
| TaskStackSize沿用空值 | 栈溢出 | 初值由东软工具给出，阶段1用OS stack meter和最坏场景校准 |
| RTE接口后置 | ASW无法并行 | 阶段1交RTE骨架、Stub和适配层 |
| Boot后置 | 集成效率和量产风险 | 阶段1最小刷写；阶段3完整Boot/HSM |
| 原理图不提供导致硬件信息缺失 | MCAL/CDD错误 | 提供脱敏PortList、BOM、时钟、电源/复位/中断/片选表；板级调试阶段补必要测试点 |
| OEM需求晚变 | 阶段2返工 | M0/M1冻结初版，之后走差异表和CR |
| WdgM配置与真实喂狗混淆 | 卡死不能复位 | 独立验收WdgM监督和LP87745硬件链路 |
| Fee地址照搬BYD | 分区冲突/数据损坏 | 新Boot/HSM布局冻结后重新计算并做边界测试 |
| XCP/A2L地址不一致 | 标定不可用 | A2L由ELF/MAP自动校验，Release时固化 |

## 13. 仍需新项目冻结的TBD

以下内容不能仅凭BYD工程决定，必须由我方/OEM/硬件和东软共同关闭：

1. TI目标芯片完整料号、核资源、SDK、编译器和NeuSAR支持版本。
2. 新板PMIC/SBC、Watchdog、Flash、CAN收发器和其他外设型号。
3. 最终PinMux、时钟、电源时序和中断映射。
4. 最终CAN/CANFD通道、DBC、波特率、诊断/XCP ID。
5. OEM DID/DTC/Routine、会话、安全、NRC和诊断时序差异。
6. NvM Block裁剪/新增、Flash分区和寿命目标。
7. NM网络规范、时间同步主从角色和休眠唤醒时序。
8. Boot下载通道、镜像格式、HSM/密钥/签名和量产烧录流程。
9. 功能安全等级、网络安全目标及所需工作产品。

## 14. 最终执行口径

东软应按本文档拆解详细计划和配置输入。阶段1以“我方能否开始RF/ASW主链路开发”为验收中心；阶段2以“OEM诊断、通信、存储、网络管理、Wdg、XCP是否可测试”为中心；阶段3以“Boot/HSM/量产包、可复现性和系统稳定性”为中心。

BYD工程提供成熟架构和功能基线，但新项目最终Release必须形成独立的、经双方冻结的配置矩阵和差异表。任何未在本文档或经批准CR中明确的功能，不应通过默认开启模块、猜测空白项或复制BYD绝对地址的方式进入量产配置。

## 附录A：BYD OS任务配置基线

BYD为单核RTA-OS、SC1，任务均为Basic Task/BCC2，无Extended Task、无Event；每个任务Activation为10。RTA-OS该配置中数值更大的Task优先级更高。`TaskStackSize/Stack_budget` 在Configuration Summary中为空，`DefTaskStack`未定义，因此下表不能被解释为“无需配置栈”；新项目必须由东软给出初始值，并用目标编译器和最坏场景实测校准。

| Task | 类型 | 优先级 | 触发/周期 | 主要内容 | 新项目处理 |
|---|---|---:|---|---|---|
| OsTask_ASW_100ms | BCC2 | 5 | RTE ScheduleTable，每100ms | Base、CORE0 100ms、Wdg状态、XCP SWC、CDD_CORE0 | 阶段1保留Stub，阶段2接完整功能 |
| OsTask_Trigger66ms | BCC2 | 6 | Mailbox回调触发 | ProfileReload、信号/感知处理、RTE通信输出 | 按实际帧周期确认名称/触发 |
| OsTask_ASW_10ms | BCC2 | 10 | 每10ms | COM SWC、ASW WDG、ASW NvM、CORE0 10ms | 阶段1保留 |
| OsTask_BSW_SwcRequest | BCC2 | 15 | RTE/BSW请求触发 | 异步BSW请求、模式通知 | 随RTE生成 |
| OsTask_ASW_20ms | BCC2 | 20 | 每20ms | EDR、监控、PMIC测试、Rx映射、自研FiM、自检 | 阶段2按功能接入 |
| OsTask_BSW_10ms | BCC2 | 30 | 每10ms | EcuM、ComM、WdgM、BswM、Dem、Can、Com、CanTp、Dcm、CanSM、Xcp、CanTSyn、StbM | 阶段1最小，阶段2完整 |
| OsTask_MmWaveCtrl | BCC2 | 50 | mmWave控制触发 | BYD中MmwDemo_initTask调用被注释，需新项目确认实际入口 | 阶段1必须明确并启用等价链路 |
| OsTask_DPM | BCC2 | 55 | 手写任务 | `MmwDemo_mmWaveCtrlTask`等数据处理控制 | 阶段1必须 |
| OsTask_ECU_Startup | BCC2 | 60 | 启动一次 | FmScheduler init、EcuM_StartupTwo、BswM、DiaScheduler init、CUDA读取 | 阶段1必须 |
| OsTask_TriggerWave | BCC2 | 70 | 波形触发 | `RE_ASWIN_DivWave_TimeDivWave` | 最高Task优先级，按新项目触发策略确认 |

BYD OS资源/调度基线：

- Resource：`RTE_RESOURCE`、`RTE_RESOURCE_OS_APP_OsApplication_Core0`、`RES_SCHEDULER`。
- Counter：硬件 `OsCounter_0`，软件 `Rte_TickCounter`。
- Alarm：无。
- ScheduleTable：`Rte_ScheduleTable`，Duration=10、Repeat=true、Explicit synchronization；10个Expiry Point按10ms基准激活ASW 10/20/100ms和BSW 10ms任务。
- OS生成选项开启stack budget检查、stack meter和execution meter，但配置摘要没有给出每个Task的具体Stack预算。

新项目栈验收要求：启动、RF初始化、连续帧、CAN/诊断并发、NvM写入、XCP DAQ、错误处理和Boot跳转场景下分别采集high-water mark；每个Task保留经双方评审的安全裕量。

## 附录B：BYD ISR和资源基线

BYD OSIPL=16，HighestIPL/MaxIPL=17。Cat1异常ISR具有独立512字节预算；Cat2的Stack_budget在配置摘要中为空，必须在新项目补齐。

| 类别 | ISR | 优先级 | Vector/用途 | BYD Stack预算 |
|---|---|---:|---|---:|
| Cat1 | OsTrap_DataAbort | 17 | CPU Data abort | 512 |
| Cat1 | OsTrap_PrefetchAbort | 17 | CPU Prefetch abort | 512 |
| Cat1 | OsTrap_UndefInstruction | 17 | CPU Undefined instruction | 512 |
| Cat2 | Eth_MiscIrqHdlr_0 | 1 | MSS_CPSW_MISC_INT | 未定义 |
| Cat2 | Eth_RxIrqHdlr_0 | 1 | MSS_CPSW_TH_INT | 未定义 |
| Cat2 | Eth_RxThreshIrqHdlr_0 | 1 | MSS_CPSW_TH_TRSH_INT | 未定义 |
| Cat2 | Eth_TxIrqHdlr_0 | 1 | MSS_CPSW_FH_INT | 未定义 |
| Cat2 | Spi_IrqUnit0TxRx | 1 | MSS_SPIA_INT0，LP87745链路 | 未定义 |
| Cat2 | Gpt_Ch1Isr | 2 | MSS_RTIA_INT1 | 未定义 |
| Cat2 | Can_0_Int0ISR | 5 | MSS_MCANA_INT0 | 未定义 |
| Cat2 | Can_1_Int0ISR | 5 | MSS_MCANB_INT0 | 未定义 |
| Cat2 | Cdd_MailBox2FullIsr | 15 | MSS_CR5A_MBOX_READ_REQ，IPC | 未定义 |
| Cat2 | DSS_TPCC_B_func | 15 | DSS_TPCC_B_INTAGG，eDMA | 未定义 |
| Cat2 | MSS_TPCC_A_func | 15 | MSS_TPCC_A_INTAGG，eDMA | 未定义 |
| Cat2 | OsIsr_CR5A_FPU | 15 | MSS_CR5A_FPU_INT | 未定义 |
| Cat2 | RSS_TPCC_A_func | 15 | RCSS_TPCC_A_INTAGG，eDMA | 未定义 |
| Cat2 | Gpt_Ch0Isr | 16 | MSS_RTIA_INT0，系统时基相关 | 未定义 |

新项目中不用ETH时可裁剪4个ETH ISR；新芯片Vector、核归属和优先级必须按TI 2944LC资源重新配置。Mailbox/eDMA ISR保持短小，只做清标志、搬运必要状态和唤醒Task/回调；复杂处理放Task上下文。

## 附录C：BYD诊断通信与诊断功能基线

### C.1 诊断通信坐标

| 项目 | BYD生成配置 |
|---|---|
| 网络 | `Can_Network_CANNODE_0` |
| 协议 | UDS on CAN/CANFD，标准寻址 |
| 功能请求CAN ID | 0x7DF，Standard ID |
| 物理请求CAN ID | 0x7C2，Standard ID |
| 物理响应CAN ID | 0x7CA，Standard ID，Tx PDU长度8 |
| DCM Rx/Tx Buffer | 4096字节；最大响应4095字节 |
| Tester Source Address | 0x01 |
| ECU Target Address | 0x00 |
| Dcm MainFunction | BSW 10ms |
| CanTp MainFunction | BSW 10ms |

功能寻址负响应抑制集合在BYD中包含NRC 0x11、0x12、0x31、0x7E、0x7F。新项目需按OEM规范确认，不应仅按通用默认值配置。

### C.2 会话和P2时序

| Session | ID | P2 | P2* | Boot行为 |
|---|---:|---:|---:|---|
| Default | 0x01 | 50ms | 5000ms | No Boot |
| Programming | 0x02 | 50ms | 5000ms | OEM Boot |
| Extended | 0x03 | 50ms | 5000ms | No Boot |
| Weifu | 0x06 | 60ms | 6000ms | OEM Boot |
| Bosch | 0x60 | 60ms | 6000ms | No Boot |

DCM内部 `P2ServerTimeAdjust` 和 `P2StarServerTimeAdjust` 均为10ms。

### C.3 CanTp时序

| 连接 | 寻址 | N_As | N_Ar | N_Bs | N_Br | N_Cr | N_Cs | STmin | BS | Padding |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 物理请求Rx 0x7C2 | Physical/Standard | - | 70ms | - | 70ms | 180ms | - | 20ms | 8 | ON |
| 功能请求Rx 0x7DF | Functional/Standard | - | 70ms | - | 70ms | 180ms | - | 20ms | 8 | ON |
| 物理响应Tx 0x7CA | Physical/Standard | 70ms | - | 180ms | - | - | ARXML 70ms；当前生成C表为80ms | - | - | ON |

注意：BYD的CanTp ARXML中N_Cs=70ms，但当前生成 `CanTp_TimeOut[0]={7,18,8}` 且tick为10ms，对应编译行为为80ms。新项目配置必须消除此差异，并以最终生成代码和实测为验收依据。

### C.4 UDS服务

| SID | 服务 | BYD支持 | 备注 |
|---:|---|---|---|
| 0x10 | DiagnosticSessionControl | 是 | 5个会话 |
| 0x11 | ECUReset | 是 | 带Precondition和安全限制 |
| 0x14 | ClearDiagnosticInformation | 是 | 与Dem联动 |
| 0x19 | ReadDTCInformation | 是 | 子功能0x01/02/04/06/0A |
| 0x22 | ReadDataByIdentifier | 是 | DID见C.5 |
| 0x27 | SecurityAccess | 是 | L1、L31、L32 |
| 0x28 | CommunicationControl | 是 | 3个子服务 |
| 0x2E | WriteDataByIdentifier | 是 | 带Precondition和安全限制 |
| 0x2F | InputOutputControlByIdentifier | 否 | IOCBI配置OFF，DID数量0 |
| 0x31 | RoutineControl | 是 | Routine见C.6 |
| 0x3E | TesterPresent | 是 | 1个子服务 |
| 0x85 | ControlDTCSetting | 是 | 2个子服务 |

### C.5 DID基线

下列DID来自BYD `Dcm_Lcfg_DspUds.c`。新项目应以此建立初版差异表；DID长度、数据类型、默认值、Session/Security、NRC、NvM关联和业务回调必须在阶段0/M1前冻结。

| 访问 | DID |
|---|---|
| 只读0x22 | 0x0103、0x0285、0x028D、0x1011、0x3403、0x3404、0x3441、0x3442、0x3443、0x3444、0x3449、0xF180、0xF186、0xF18C、0xF193、0xF194、0xF195、0xF199、0xFA13、0xFA14、0xFD12、0xFD13、0xFD20、0xFD21、0xFD22、0xFD23、0xFD24、0xFD25、0xFD26、0xFD27、0xFD28、0xFD31、0xFDAA、0xFF94、0xFF95 |
| 读写0x22/0x2E | 0x2100、0x344A、0x6666、0xF190、0xF1C2、0xFD14、0xFD15、0xFD17、0xFD30 |
| 只写0x2E | 0xFD16、0xFD18、0xFD19、0xF1A1 |

关键命名示例：0x1011 VehicleSpeed、0x2100 VariantCoding、0x344A LifecycleSwitch、0xF180 FBLVersion、0xF186 CurrentSession、0xF190 VIN、0xF193 HWVersion、0xF194 ECUSoftwareCode、0xF195 SWVersion、0xF199 ProgramDate、0xFA13/0xFA14 EDR、0xFD14 FaultMask、0xFD17 RadarPosition、0xFD30 InjectFault。

### C.6 Routine基线

| RID | 子功能 | BYD业务 |
|---:|---|---|
| 0x0203 | Start | FBL前置条件检查，Start输出1字节 |
| 0x0302 | Start/Stop/RequestResult | SDA标定，RequestResult输出56bit |
| 0x54DF | Start/Stop/RequestResult | EOL静态标定，RequestResult输出40bit |
| 0xFD00 | Start | Bosch Security Routine |
| 0xFD01 | Start | Bosch Clear ITC Routine |

### C.7 DTC Class基线

BYD共有59个DTC Class和217个Event。下表为DTC Class与UDS DTC值；完整217 Event到DTC、Debounce、OperationCycle、FreezeFrame/ExtendedData映射必须从 `Dem_Cfg_EventId.h`、`Dem_Cfg_DtcId.h` 和 `Dem_Cfg_Events_DataStructures.*` 导出成东软配置表。

| DTC Class | UDS DTC | DTC Class | UDS DTC |
|---|---:|---|---:|
| DTC_IPB_SIGNAL_INVALID | 0x5C6286 | DTC_IPB_ALC | 0x5C6302 |
| DTC_IPB_CRC | 0x5C6462 | DTC_Left_BCM_SIGNAL_INVALID | 0x5C6586 |
| DTC_Left_BCM_ALC | 0x5C6602 | DTC_Left_BCM_CRC | 0x5C6762 |
| DTC_PRODUCTION_MODE_ACTIVE | 0xACD000 | DTC_ALIGNMENT_NEVER_DONE | 0xACD178 |
| DTC_ALIGNMENT_NOT_OK | 0xACD278 | DTC_BOSCH_DRIVETESTACTIVE | 0xACD304 |
| DTC_FACTORYDATA_FAILURE | 0xACD488 | DTC_HW_UC_PFLASH | 0xACD541 |
| DTC_INTERNAL_POWER_MANAGEMENT_SYS_FAILURE | 0xACD640 | DTC_INTERNAL_UC_SYS_FAILURE | 0xACD740 |
| DTC_INTERNAL_HW_FAILURE | 0xACD804 | DTC_POWER_MANAGEMENT_CHIP_VOLTAGE_HIGH | 0xACD917 |
| DTC_MMIC_VOLTAGE_HIGH | 0xACDA17 | DTC_POWER_MANAGEMENT_CHIP_VOLTAGE_LOW | 0xACDB16 |
| DTC_MMIC_VOLTAGE_LOW | 0xACDC16 | DTC_RADAR_MODULATION_CONFIGURE | 0xACDD00 |
| DTC_RADAR_MODULATION | 0xACDE00 | DTC_SW_FAILURE | 0xACDF52 |
| DTC_SW_RIF_FAILURE | 0xACE000 | DTC_SW_TEMP_FAILURE | 0xACE152 |
| DTC_UC_TEMPERATURE_OUTOFRANGE | 0xACE24B | DTC_MMIC_TEMPERATURE_OVER_MAXIMUM | 0xACE34B |
| DTC_MMIC_TEMPERATURE_OVER_OPERATION | 0xACE44B | DTC_ADC_SELF_TEST_FAILURE | 0xACE500 |
| DTC_NVM_EOL_NO_VAR | 0xACE655 | DTC_CUDA_Invalid | 0xACE791 |
| DTC_SYS_BLIND | 0xACE876 | DTC_SENSOR_BLIND | 0xACE976 |
| DTC_HORIZONTAL_MISALIGNED | 0xACEB94 | DTC_AntennaDiagram_INVALID | 0xACED00 |
| DTC_Time_SYNC_FAIL | 0xACEE00 | DTC_Modulation_OFF | 0xACEF00 |
| DTC_PCAN_BUSOFF | 0xC07388 | DTC_EPS_TIMEOUT | 0xC13187 |
| DTC_IPB_TIMEOUT | 0xC19780 | DTC_Left_BCM_TIMEOUT | 0xC1A887 |
| DTC_VCU_SIGNAL_INVALID | 0xC1D529 | DTC_SFCAN_BUSOFF | 0xC1D788 |
| DTC_CMRR_DACORE_OOS | 0xC1D829 | DTC_Private_Can_ALC | 0xC1EA82 |
| DTC_Private_Can_CRC | 0xC1EA83 | DTC_Private_Can_TIMEOUT | 0xC1EA87 |
| DTC_Media_TIMEOUT | 0xC24500 | DTC_Media_CRC | 0xC2ED83 |
| DTC_EPS_ALC | 0xC42082 | DTC_EPS_CRC | 0xC42083 |
| DTC_EPS_SIGNAL_INVALID | 0xD01786 | DTC_MRR_TIMEOUT | 0xD02E87 |
| DTC_MRR_ALC | 0xD0B818 | DTC_MRR_CRC | 0xD0B819 |
| DTC_VCU_TIMEOUT | 0xD0C286 | DTC_VBAT_HIGH | 0xD10017 |
| DTC_VBAT_LOW | 0xD10116 | DTC_VCU_ALC | 0xD27182 |
| DTC_VCU_CRC | 0xD27183 |  |  |

BYD `0x19`配置最多一次读取1个DTC、1个Record；FreezeFrame和ExtendedData相关能力开启。标准Dem Event Indicator关闭，不能把DTC表的“报警提示=Y”直接转换成Indicator配置。

## 附录D：BYD NvM Block与存储策略基线

### D.1 全局配置

| 项目 | BYD值 |
|---|---|
| `NVM_CFG_NR_BLOCKS` | 105 |
| Block ID范围 | 0至104 |
| 用户Block范围 | 2至104 |
| `NVM_DYNAMIC_CONFIGURATION` | STD_OFF |
| `NVM_JOB_PRIORITIZATION` | STD_OFF |
| `NVM_SET_RAM_BLOCK_STATUS_API` | STD_ON |
| MemIf设备数 | 1 |
| 启动行为 | BswM调用 `NvM_ReadAll()` |
| 关机WriteAll | `BswM_NvM_WriteAll()` 中实际 `NvM_WriteAll()` 调用被注释 |
| 主要写策略 | DID/EDR/Dem/标定/计数/刷写标志等按事件显式 `NvM_WriteBlock()` |

### D.2 Block 0至28

| ID | Block | 长度Byte | 用途 |
|---:|---|---:|---|
| 0 | NvM_MultiBlock | 1 | NvM系统保留 |
| 1 | NvM_ConfigId | 2 | NvM系统保留 |
| 2 | NvMBlock_LogisticData | 128 | 物流/系统数据 |
| 3 | NVM_OS_ErrorlogOsErrorHook | 370 | OS错误日志 |
| 4 | NVM_OS_ErrorlogOsShutdown | 44 | 关机错误日志 |
| 5 | NVM_OS_ErrorlogOsWdgReset | 6 | Watchdog复位日志 |
| 6 | NVM_OS_ErrorlogActiveReset | 5 | 主动复位日志 |
| 7 | NVM_PMIC_DTC_ERROR | 40 | PMIC DTC |
| 8 | CustDID_APPVersion | 6 | APP版本DID |
| 9 | CustDID_DisBetFrontandRear | 2 | 车辆配置DID |
| 10 | CustDID_DisBetLeftandRight_0x126A | 2 | 车辆配置DID |
| 11 | CustDID_ECUHWVersionNumber | 5 | 硬件版本DID |
| 12 | CustDID_ECUSoftwareCode | 9 | 软件代码DID |
| 13 | CustDID_FBLVersion | 9 | FBL版本DID |
| 14 | CustDID_ProductionMode | 1 | 生产模式DID |
| 15 | NvMBlockDescriptor_ECUConfiguration | 4 | ECU配置，Fee冗余Block |
| 16 | CustDID_TargetPosition_0x1266 | 4 | 目标位置DID |
| 17 | CustDID_VIN | 17 | VIN |
| 18 | CustDID_VariantCoding | 8 | Variant Coding |
| 19 | CustDID_WheelBase | 2 | 轴距DID |
| 20 | NvM_PowerOn_Counter | 4 | 上电计数 |
| 21 | NvM_RadarPosition_ETHOnly | 1 | 雷达位置 |
| 22 | Cust_SecurityAccesscounter | 1 | 客户安全访问计数 |
| 23 | Dia_SecurityAccesscounter | 1 | 诊断安全访问计数 |
| 24 | ECUM_CFG_NVM_BLOCK | 4 | EcuM启动/关机状态 |
| 25 | NVM_ADAS_HMISwitch | 11 | ADAS HMI开关 |
| 26 | NVM_Calibration_EffStatus | 1 | 标定有效状态 |
| 27 | NVM_Calibration_OnlineStatus | 30 | 在线标定状态 |
| 28 | NVM_Calibration_TriggerStatus | 30 | 标定触发状态 |

### D.3 Dem事件存储Block 29至90

- ID 29至48：`NVM_ID_DEM_EXTRA_INFO_<suffix>`，每个32字节。ID递增对应suffix顺序为：`0, 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 2, 3, 4, 5, 6, 7, 8, 9`。
- ID 49：`NVM_ID_DEM_GENERIC_NV_DATA`，16字节。
- ID 50至89：`NVM_ID_EVMEM_LOC_<suffix>`，每个48字节。ID递增对应suffix顺序为：`0, 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 2, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 3, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 4, 5, 6, 7, 8, 9`。
- ID 90：`NVM_ID_EVT_STATUSBYTE`，218字节。

### D.4 Block 91至104

| ID | Block | 长度Byte | 用途 |
|---:|---|---:|---|
| 91 | NVM_NM_ForceHibernationLatestSts | 1 | NM强制休眠状态 |
| 92 | NvMBlockDescriptor_Application_Valid_Flag | 1 | APP有效标志 |
| 93 | NvMBlockDescriptor_Did_for_test_0x6666 | 3 | 测试DID |
| 94 | NvMBlockDescriptor_Fingerprint_Data | 9 | 刷写Fingerprint |
| 95 | NvMBlockDescriptor_Reprogramming_Request_Flag | 4 | 重编程请求标志 |
| 96 | NvMBlockDescriptor_ResetReason_Type | 1 | 复位原因 |
| 97 | NvM_BLDDetStatus | 1 | BLD检测状态 |
| 98 | NvM_Calibration_TargetPosition | 4 | 标定目标位置 |
| 99 | NvM_EDR_Data1 | 4900 | EDR数据区1 |
| 100 | NvM_EDR_Data2 | 4900 | EDR数据区2 |
| 101 | NvM_EDR_WRITE_FLAG | 2 | EDR写标志 |
| 102 | NvM_FaultMask_Info | 32 | Fault Mask |
| 103 | NvM_PFDem_ErrorInfo | 512 | PF Dem错误信息 |
| 104 | NvM_Security_Key | 32 | 安全密钥数据 |

### D.5 东软必须补充的Block配置字段

上表是BYD名称/ID/长度基线，不等于完整NeuSAR配置输入。东软需对每个新项目Block补充：Block管理类型、NV副本数、RAM地址、ROM默认值、CRC类型、ReadAll/WriteAll选择、写保护、显式同步、回调、Fee Block号、写触发源、最大写频率、掉电原子性和诊断/ASW引用关系，并输出相对BYD的新增/删除/长度变化差异表。

## 附录E：BYD通信、NM、Wdg和XCP关键基线

### E.1 CAN/PduR

- 2路MCAN：CANNODE_0、CANNODE_1，支持CAN FD。
- BYD配置存在500k/2M和1000k/5M波特率组合；新项目由硬件和DBC冻结。
- 诊断位于CANNODE_0，XCP位于CANNODE_1。
- PduR没有配置CAN Gateway路由；存在的是Com、Dcm/CanTp和XCP到CanIf的普通路由。新项目若需要网关，必须新增独立路由表和验收。

### E.2 NM

- BswM初始化 `CanNm_Init(NULL_PTR)`、`Nm_Init(NULL_PTR)`、`ComM_Init(NULL_PTR)`。
- Nm API映射到CanNm。
- 生成的BSW 10ms任务中 `CanNm_MainFunction()` 被注释，但项目补丁 `net_NM_schedule()` 实际调用它。
- ASW存在 `CanNm_GetState()` 使用。

东软必须在新项目中把CanNm MainFunction的唯一调度位置明确下来，禁止生成任务和项目调度重复调用，也不能两处都关闭。

### E.3 Wdg

| 项目 | BYD基线 |
|---|---|
| WdgM监督 | 1个SE/1个CP，Alive；无Deadline |
| WdgM周期 | BSW 10ms |
| Checkpoint运行状态 | ASW Runnable被调度，但内部调用整体处于`#if 0` |
| WdgIf硬件意义 | 不能单独视为真实喂狗闭环；项目MCAL `Wdg_SetTriggerCondition()`存在空Stub风险 |
| 真实硬件Wdg | FUSA_WDGDrv + LP87745，SPI访问，GPT回调喂狗 |
| 超时计数 | `Wdg_SafetyWatchdog_TimeoutCounter=200`，业务刷新，GPT递减 |

### E.4 XCP

| 项目 | BYD基线 |
|---|---|
| Transport | XCP on CAN ON；Ethernet OFF |
| Rx/Tx | 0x332 / 0x778，CANNODE_1 |
| 功能 | CAL ON、PAG ON、DAQ ON、STIM OFF、PGM OFF |
| Packet | MAX_CTO=64、MAX_DTO=64 |
| DAQ RAM | 1024字节，`.r5f_L3data` |
| Timestamp | ON |
| 调度 | Xcp MainFunction 10ms；ASW XCP Runnable 100ms |

BYD当前存在一项必须清理的XCP配置一致性问题：运行生成配置 `Xcp_Cfg.h/XcpOnCan_Cfg.c` 的MAX_CTO/MAX_DTO为64，而仓库中的 `bswpf/autosar/Xcp/Xcp_A2L.a2l` 仍写8，`tools/INCATest/Entry_A2L_Complete.a2l`中也存在8/255等模板值。新项目不得直接复用这些静态A2L模板；必须从最终XCP配置和ELF/MAP重新生成，并将Packet Size、地址、Event和内存段一致性纳入Release门禁。

## 附录F：基线依据与冲突处理

本文件关键结论直接依据以下BYD工程生成物/代码：

- OS：`bswpf\rtaos\gen\Configuration Summary.txt`。
- RTE：`coem\BYD_UKE\gen_rte`。
- mmWave：`mmwave\mmwave\src\mmwave_link_mailbox.c`、`rte\OsTask_MMW.c`。
- DCM：`gen_bsw\Dcm\Dcm_Lcfg_Dsl.c`、`Dcm_Lcfg_Dsd.c`、`Dcm_Lcfg_DspUds.c`。
- CanIf/CanTp：`gen_bsw\CanIf\CanIf_PBcfg.c`、`gen_bsw\CanTp_PC\CanTp_Cfg.c`和CanTp ARXML。
- Dem：`gen_bsw\Dem\Dem_Cfg_*`、`components\AswIf\ASW_IN\ASWIN_FIM_*`。
- NvM/Fee/Fls：`gen_bsw\NvM\NvM_Cfg.h`、`gen_bsw\Fee\rba_FeeFs1x_Prv_Cfg.*`、`gen_mcal\Fls*`。
- Wdg：`gen_bsw\WdgM\WdgM_Cfg.*`、`asw\ASW_WDG\src\ASW_WDG.c`、`bswpf\cdd\WDGDrv\FUSA_WDGDrv.c`、`bswpf\cdd\LP87745\LP87745.c`。
- XCP：`gen_bsw\Xcp\Xcp_Cfg.*`、`XcpOnCan_Cfg.*`、CanIf配置和RTE任务。
- NM：BswM生成配置、`gen_bsw\Nm\Nm_Cfg.c`、`buildscripts\patch\net_Mngmt.c`。
- Boot：`coem\BYD_UKE\tools\container_input`及RTE中的BootTarget/JUMPTOBOOTLOADER接口。

若早期讨论文档与上述实际代码冲突，以当前生成配置和运行代码为准。本次已明确修正的冲突包括：

1. WdgM不是Deadline Supervision；BYD仅配置Alive，且Checkpoint业务调用当前被`#if 0`关闭。
2. mmWave/RF主链路不走AUTOSAR SPI；SPI实际用于LP87745 PMIC/外部Watchdog。
3. NvM不是“104个Block”，而是ID 0至104共105个；Fee物理属性103项是另一概念。
4. BYD不是“无RTE的纯手写ASW”，而是生成RTE与项目适配接口共存。
5. 诊断SID 0x2F不支持；IOControl页不应默认配置。
6. Dem“报警提示”不等同于Dem Indicator；BYD标准Indicator关闭，报警/降级主要在ASWIN_FIM实现。
7. XCP运行配置MAX_CTO/MAX_DTO为64，但仓库静态A2L模板存在8/255等不一致值；新项目必须重新生成并校验A2L。
