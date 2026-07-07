# AUTOSAR实际导向里程碑优化方案

基于用户最新判断重新整理。核心思想是：不要照搬东软Excel里的线性BSW交付节奏，而是围绕“尽快跑通毫米波雷达主链路”来规划。

参考工程：`D:\Weifu\Project\CR\BYD_RL\xxx`

## 1. 对当前思路的判断

你的思路是对的，而且比东软Excel里的里程碑更符合实际项目推进。

东软Excel原计划偏“标准AUTOSAR模块堆叠式交付”：T1先OS/CAN/系统服务，T2再诊断、存储、NM、RTE、Wdg、XCP，Bootloader单独放一个节点。这个计划的问题是：它不一定能最快支撑我们把 mmWave/RF 主链路跑起来。

我们这个项目的真实目标应该是：

1. 第一阶段先把需求、边界、架构和接口设计清楚。
2. 第二阶段优先交付 mmWave/RF/ASW 主链路需要的基础平台能力，让我方可以同步移植和开发。
3. 第三阶段再把 OEM 强相关和量产完整功能补齐，比如UDS、完整诊断、完整NM、NvM策略、Boot量产安全、XCP、标定、HSM等。

需要优化的一点是：Bootloader不能完全后置。建议拆成：

- 第二阶段：最小Boot刷写闭环，用于开发测试。
- 第三阶段：完整量产Bootloader，包含安全、HSM、签名、回滚、正式刷写流程。

## 2. 基于BYD量产工程抽象出来的目标架构

### 2.1 总体分层

BYD量产工程可以抽象成以下架构：

```text
应用与算法层
  ASW_CORE / ASW_COM / ASW_NVM / ASW_WDG / ASW_XCP
  ADAS感知算法 / RF配置 / 信号处理 / 数据处理
  mmWave控制与数据链路

应用接口与调度层
  RTE生成接口
  项目级任务适配层（手写调度/集成代码）
  AswIf / AswIfSchedule / AswPerception
  通信平台调度 net_Scheduler / net_Mngmt

AUTOSAR服务层
  Com / PduR / CanIf / CanTp
  Dcm / Dem / NvM / Fee / MemIf
  EcuM / BswM / ComM / CanSM / CanNm / Nm
  WdgM / WdgIf / Xcp / StbM / CanTSyn

MCAL与CDD层
  Mcu / Port / Dio / Gpt / Can / Fls / Spi / Adc / eDMA / Ipc
  PMIC / SBC / TCAN1043 / Watchdog / ErrorLog / Trap等CDD

Boot与安全层
  BootManager / PlatformBoot / CustomerBoot
  HSM / Crypto / Secure Boot / 镜像校验

硬件层
  TI AWR2944LC / AM294x R5F
  mmWave RF / DSS-RSS-M4等协处理核 / CAN-CANFD / 外部Flash / SBC / PMIC
```

### 2.2 BYD工程里的几个关键事实

1. RTE存在，但不是所有逻辑都通过纯AUTOSAR SWC模型完成。
2. `asw`、`adas`、`mmwave` 是雷达业务主链路。
3. `bswpf\autosar` 提供BSW模块。
4. `bswpf\mcal` 提供MCAL模块。
5. `rte\OsTask_MMW.c` 是mmWave相关项目级任务适配代码，用于把雷达控制、IPC/Mailbox、DPM等非标准SWC链路接入OS任务。
6. `coem\BYD_UKE\gen_rte` 是RTE和OsTask生成代码。
7. `coem\BYD_UKE\tools\container_input` 已经有BootManager、PlatformBoot、CustBoot、HSM、APP、数据区量产包结构。
8. NM网络管理不是摆设，CanNm/Nm/ComM存在，但CanNm主函数通过项目通信平台调度。

### 2.3 新项目推荐架构

新项目不要按“BSW全量先做完，ASW后接入”的方式推进。推荐按“主链路优先”的架构组织：

```text
第一优先级：主链路启动
  OS任务
  中断
  eDMA/DMA
  IPC/Mailbox/协处理核交互
  mmWave控制
  RF/MMIC控制所需底层支撑
  CAN基础收发
  ASW主循环

第二优先级：主链路可观测、可调试、可刷写
  最小Boot刷写
  基础Dcm或调试命令
  日志/错误码
  基础NvM参数
  基础Wdg

第三优先级：OEM和量产完整功能
  完整UDS
  完整Dem/DTC
  完整NvM策略
  完整NM休眠唤醒
  XCP/A2L
  HSM/Secure Boot
  量产刷写包
```

## 3. 重新建议的里程碑

### 阶段0：项目启动与需求冻结

#### 目标

把需求、范围、责任、输入物、工具链、硬件条件全部明确。

#### 要做的事情

1. 确认芯片和平台：
   - TI AWR2944LC / AM294x R5F。
   - 是否有DSS/RSS/M4等协处理核或算法核交互需求。
   - mmWave RF/MMIC控制路径。

2. 确认工具链：
   - NeuSAR cCore版本。
   - AUTOSAR版本。
   - 编译器版本。
   - 调试器和烧录器。

3. 确认责任边界：
   - 东软建议负责：BSW、MCAL、RTE、OS、基础CDD适配、Bootloader方案和刷写闭环。完整量产Bootloader/HSM边界需在合同和技术方案中确认。
   - 我方负责：ASW、RF移植、mmWave业务链路、信号处理、数据处理、算法集成。
   - 双方共同：任务调度、接口定义、诊断需求、存储策略、刷写流程。

4. 确认输入物：
   - BYD量产工程参考。
   - 硬件原理图/IO Map。
   - DBC/CAN矩阵。
   - 诊断需求初版。
   - Memory Map初版。
   - Boot需求初版。
   - ASW接口初版。

#### 交付物

- 项目范围说明。
- 输入物清单。
- 责任矩阵。
- 风险清单。
- 初版项目计划。

#### 验收标准

- 每个模块谁负责已经明确。
- 每个输入物缺失项有补齐日期。
- 东软确认AWR2944LC支持状态。
- Bootloader是否东软主责已明确。

## 4. 阶段1：需求清晰与架构设计

这是你说的第一个真正里程碑。这个阶段非常关键，建议单独作为正式交付节点，而不是藏在T1里。

### 4.1 阶段目标

基于BYD量产工程，设计新项目的软件架构、任务架构、接口架构和交付架构。

### 4.2 架构设计要输出什么

#### 4.2.1 软件分层架构

要明确：

- ASW有哪些模块。
- BSW有哪些模块。
- MCAL有哪些模块。
- CDD有哪些模块。
- mmWave/RF链路怎么接入AUTOSAR。
- RTE接口和手写接口怎么共存。
- 哪些功能首版必须做，哪些放第三阶段。

#### 4.2.2 运行时架构

要明确：

- 有哪些OS Task。
- 每个Task周期是多少。
- 每个Task优先级如何设计。
- mmWave高实时任务如何保证。
- eDMA/DMA中断优先级如何设计。
- CAN/CANFD中断优先级如何设计。
- DSS/RSS/M4等协处理核交互中断如何设计。
- BSW周期主函数放在哪些Task里。
- ASW主链路放在哪些Task里。

参考BYD：

- `OsTask_MmWaveCtrl`
- `OsTask_DPM`
- `OsTask_TriggerWave`
- `OsTask_ASW_10ms`
- `OsTask_ASW_20ms`
- `OsTask_ASW_100ms`
- `OsTask_BSW_10ms`
- `OsTask_BSW_SwcRequest`

新项目需要重新评估优先级，但可以沿用这个结构。

#### 4.2.3 接口架构

要明确：

- ASW如何调用BSW服务。
- RTE接口有哪些。
- 哪些地方允许直接调用BSW API。
- mmWave/RF控制接口由谁提供。
- eDMA/DMA接口由谁提供。
- 协处理核交互接口由谁提供。
- CAN发送/接收接口怎么抽象。
- 诊断/Dem/NvM/Wdg接口怎么给ASW使用。

#### 4.2.4 Memory Map架构

要明确：

- Boot区域。
- APP区域。
- HSM区域。
- NvM区域。
- 标定区域。
- 客户数据区。
- 威孚数据区。
- 日志/错误记录区域。

#### 4.2.5 Boot架构

要明确：

- BootManager。
- PlatformBoot。
- CustomerBoot。
- APP跳Boot。
- Boot跳APP。
- 镜像校验。
- 安全启动。
- 刷写协议。

### 4.3 阶段1东软需要做什么

1. 基于NeuSAR给出新项目软件架构方案。
2. 基于BYD工程给出可复用/不可复用分析。
3. 给出OS任务设计。
4. 给出MCAL模块支持清单。
5. 给出BSW模块分阶段实现清单。
6. 给出RTE集成方案。
7. 给出Bootloader总体方案。
8. 给出第二阶段可交付的“mmWave/RF基础平台包”范围。

### 4.4 我方需要做什么

1. 提供BYD工程参考和关键说明。
2. 提供硬件资料。
3. 提供mmWave/RF主链路需求。
4. 提供DSS/RSS/M4等协处理核交互需求。
5. 提供CAN基础需求。
6. 提供ASW接口需求。
7. 确认哪些OEM功能可以第三阶段再做。

### 4.5 阶段1交付物

- 软件架构设计文档。
- 任务与中断设计文档。
- 接口设计文档。
- Memory Map初版。
- Bootloader架构设计。
- 模块分阶段交付清单。
- 风险清单。
- 阶段2详细开发计划。

### 4.6 阶段1验收标准

- 架构图能解释清楚ASW、RTE、BSW、MCAL、CDD、Boot、HSM的关系。
- 任务设计能支撑mmWave实时性。
- 第二阶段要交付的基础平台能力清楚。
- 我方ASW团队能基于接口设计开始开发。
- 东软和我方对“哪些功能先做、哪些功能后做”没有歧义。

## 5. 阶段2：mmWave/RF主链路基础平台交付

这是整个项目最重要的阶段。目标不是全量AUTOSAR，而是先把“我方开发mmWave/RF/ASW所需要的底座”交出来。

### 5.1 阶段目标

东软提供可移植、可编译、可运行的基础平台，使我方可以开始移植RF、跑mmWave主链路、熟悉NeuSAR环境。

### 5.2 阶段2必须包含的能力

#### 5.2.1 OS与任务配置

要做：

- 配置启动任务。
- 配置BSW周期任务。
- 配置ASW周期任务。
- 配置mmWave控制任务。
- 配置DPM/数据处理任务。
- 配置触发任务。
- 配置Alarm和Counter。
- 配置关键ISR。
- 配置任务栈。
- 配置任务优先级。

验收：

- 所有任务能运行。
- 任务周期可测量。
- 任务不会互相饿死。
- mmWave相关任务优先级高于普通ASW/BSW任务。

#### 5.2.2 eDMA/DMA能力

要做：

- eDMA初始化。
- DMA通道配置。
- DMA中断配置。
- DMA buffer对齐要求说明。
- Cache一致性策略说明。
- 和协处理核交互相关DMA路径打通。
- 提供DMA传输示例或接口。

验收：

- DMA能完成一次真实传输。
- 中断/完成回调正常。
- Buffer没有Cache污染问题。
- ASW能调用封装接口。

#### 5.2.3 协处理核交互

要做：

- 明确MSS/R5与DSS/RSS/M4等协处理核之间的数据通道，具体命名以AWR2944LC实际资源和项目配置为准。
- 配置IPC/Mailbox。
- 配置共享内存。
- 配置中断。
- 定义消息格式。
- 定义启动顺序。
- 定义异常恢复策略。

验收：

- 双核/多核消息能收发。
- DMA或共享内存数据可读写。
- 异常断链能检测。
- 接口文档足够我方ASW使用。

#### 5.2.4 mmWave RF/MMIC控制支撑基础

要做：

- 明确控制通道：SPI、mmWaveLink或其他接口。
- 配置所需MCAL/CDD。
- 提供RF配置下发所需的底层支撑接口。
- 提供初始化顺序。
- 提供错误返回和状态查询。
- 支持我方移植profile/chirp/frame配置。RF业务配置本身由我方主责，东软负责支撑其运行所需的OS/MCAL/CDD/IPC/中断/存储等基础能力。

验收：

- RF控制依赖的底层通道可用。
- 我方能基于该支撑下发一组最小RF配置。
- 能返回配置成功/失败。
- 错误路径可定位。

#### 5.2.5 CAN/CANFD基础通信

要做：

- 配置Mcu/Port/Dio/Can。
- 配置CanIf。
- 配置PduR和Com最小链路。
- 导入最小DBC。
- 支持基础Tx/Rx。
- 支持调试报文。

验收：

- CAN/CANFD能发报文。
- 能接收指定报文。
- ASW能调用发送接口。
- CANoe/CANalyzer能看到报文。

#### 5.2.6 RTE/ASW接口骨架

要做：

- 导入ASW初版ARXML。
- 生成RTE头文件。
- 生成Runnable调度。
- 提供ASW Stub。
- 明确哪些接口先走RTE，哪些先用手写封装。

验收：

- 我方ASW能包含RTE头文件编译。
- Runnable能被OS周期调用。
- ASW能调用CAN发送、状态读取、基础服务接口。

#### 5.2.7 最小Boot刷写闭环

这个阶段不要求完整量产Boot，但要有开发测试闭环。

要做：

- Boot能启动APP。
- APP能通过诊断或标志跳Boot。
- CAN/CANFD能刷写APP。
- 基础CRC校验。
- 刷写失败不启动坏APP。

验收：

- 不依赖JTAG即可更新APP。
- 刷写后APP能运行。
- 中断刷写后设备能恢复到Boot。

### 5.3 阶段2东软交付物

- 可编译基础平台工程。
- OS任务配置。
- MCAL配置和生成代码。
- BSW最小配置。
- RTE骨架。
- DMA/eDMA接口说明和示例。
- 协处理核交互接口说明。
- mmWave RF/MMIC控制所需底层支撑接口。
- CAN基础通信示例。
- 最小Boot刷写工程。
- 阶段2自测报告。

### 5.4 阶段2我方同步工作

我方拿到阶段2交付物后，同步做：

1. 移植mmWave RF配置。
2. 移植信号处理主链路。
3. 接入DMA数据路径。
4. 接入协处理核数据交互。
5. 接入CAN调试输出。
6. 熟悉NeuSAR工程生成、编译、调试流程。
7. 跑通最小主枝干：
   - 上电。
   - RF初始化。
   - 启动采集。
   - 数据搬运。
   - 基础处理。
   - CAN输出状态或结果。

### 5.5 阶段2验收标准

阶段2的验收不能按“BSW模块是否全量完成”，而要按“主链路是否可开发”来验收：

- 我方ASW能在东软工程里编译运行。
- mmWave/RF初始化路径具备。
- DMA/协处理核交互路径具备。
- CAN基础调试输出具备。
- 任务调度具备。
- 最小刷写闭环具备。
- 我方可以开始独立开发和调试主枝干。

## 6. 阶段3：OEM强相关功能与量产完整功能

阶段3再补全东软Excel里那些标准AUTOSAR完整项，这样不会阻塞前面的主链路。

### 6.1 阶段目标

在主链路已经能跑的基础上，补齐OEM量产需要的诊断、存储、网络管理、看门狗、XCP、完整Boot和安全。

### 6.2 阶段3模块

#### 6.2.1 UDS / Dcm

要做：

- Default/Extended/Programming Session。
- SecurityAccess。
- DID读写。
- RoutineControl。
- CommunicationControl。
- ECUReset。
- JumpToBootloader。
- TesterPresent。
- DTC相关服务。

验收：

- OEM诊断测试通过。
- APP能通过UDS跳Boot。
- 编程会话和安全访问符合规范。

#### 6.2.2 Dem / DTC / FiM

要做：

- 故障事件定义。
- DTC映射。
- Snapshot。
- Extended Data。
- ClearDTC。
- 故障恢复策略。
- 与ASW故障上报接口。

验收：

- ASW能上报故障。
- 诊断仪能读清DTC。
- 故障状态和老化策略正确。

#### 6.2.3 NvM / Fee / Fls

要做：

- Block List。
- 默认值。
- 掉电写。
- 周期写。
- 立即写。
- 标定参数存储。
- 故障记录存储。

验收：

- 掉电保持。
- 写入策略不伤Flash寿命。
- DID写入后能持久化。

#### 6.2.4 NM / ComM / CanSM / BswM

要做：

- CanNm配置。
- Generic Nm配置。
- ComM用户和通道。
- CanSM网络状态。
- 休眠唤醒。
- 本地唤醒事件。
- 诊断保持通信。

验收：

- FullCom/NoCom切换正确。
- 网络休眠唤醒满足OEM时序。
- 诊断期间不误休眠。

#### 6.2.5 WdgM / WdgIf / 外部看门狗

要做：

- 监控任务清单。
- Alive supervision。
- Deadline supervision，如需要。
- 外部看门狗驱动。
- 复位策略。

验收：

- 正常运行不误复位。
- 指定任务卡死能触发看门狗。
- 故障可记录。

#### 6.2.6 XCP / A2L

要做：

- XCP over CAN/CANFD。
- A2L生成。
- RAM变量标定。
- 测量变量。
- 权限和开关策略。

验收：

- CANape或等效工具可连接。
- 指定变量可测量/标定。

#### 6.2.7 完整Bootloader / HSM / 量产包

要做：

- BootManager。
- PlatformBoot。
- CustomerBoot。
- HSM固件集成。
- Secure Boot。
- 镜像签名/校验。
- 回滚策略。
- 量产刷写包。
- 数据区打包。

验收：

- 正式刷写流程通过。
- 错误镜像不能启动。
- HSM/签名策略生效。
- 量产包能复现生成。

### 6.3 阶段3交付物

- 完整BSW配置工程。
- 完整MCAL配置工程。
- 完整RTE生成代码。
- 完整Bootloader工程。
- 诊断矩阵实现说明。
- NvM Block List。
- NM测试报告。
- DCM/DEM测试报告。
- Wdg测试报告。
- XCP/A2L交付。
- Bootloader测试报告。
- 量产刷写手顺。
- ReleaseNote和KnownIssues。

### 6.4 阶段3验收标准

- OEM诊断功能通过。
- 存储和故障管理通过。
- 网络管理休眠唤醒通过。
- Boot量产刷写闭环通过。
- ASW主链路和BSW完整功能同时运行稳定。
- 交付包可复现编译、生成、刷写。

## 7. 和东软Excel原计划的差异

| 东软Excel原计划 | 建议调整 |
|---|---|
| T1开始就按标准BSW Bring-up展开 | 改为先完成架构设计，再交付mmWave/RF主链路所需基础平台。 |
| T2才做RTE、诊断、存储、Wdg、XCP | RTE骨架和基础接口要提前到阶段2，完整诊断/存储/Wdg/XCP放阶段3。 |
| Bootloader单独BT1，时间较后 | 拆成阶段2最小刷写闭环、阶段3完整量产Boot。 |
| 以BSW模块为中心 | 改为以雷达主链路跑通为中心。 |
| OEM功能和基础平台混在一起 | 拆开，避免UDS/OEM需求拖慢mmWave主链路。 |

## 8. 推荐向东软表达的版本

可以这样和东软说：

> 我们不是反对按AUTOSAR模块交付，但这个项目的第一优先级是快速支撑毫米波雷达主链路跑通。我们希望第一阶段先完成需求和架构设计，架构参考BYD量产工程；第二阶段优先交付mmWave/RF/ASW开发所需的基础平台能力，包括OS任务、DMA/eDMA、协处理核交互、RF控制所需底层支撑、CAN基础通信、RTE骨架和最小Boot刷写闭环；第三阶段再补齐UDS、Dem、NvM、NM、Wdg、XCP、HSM、完整Bootloader等OEM和量产功能。

## 9. 最终推荐里程碑

| 阶段 | 名称 | 核心目标 | 验收口径 |
|---|---|---|---|
| 阶段0 | 项目启动与输入冻结 | 明确范围、输入物、责任、工具链 | 输入齐套、责任明确、风险清单建立。 |
| 阶段1 | 需求清晰与架构设计 | 基于BYD量产工程设计新架构 | 架构、任务、接口、Memory Map、Boot方案冻结。 |
| 阶段2 | mmWave/RF基础平台交付 | 给我方ASW/RF开发提供可运行底座 | OS、DMA/协处理核交互、RF底层支撑、CAN、RTE骨架、最小Boot可用。 |
| 阶段3 | OEM与量产完整功能 | 补齐完整AUTOSAR和OEM功能 | UDS、Dem、NvM、NM、Wdg、XCP、完整Boot、HSM通过验收。 |
| 阶段4 | 系统集成与量产验收 | 联调、稳定性、交付闭环 | 长稳、刷写、诊断、通信、算法主链路、交付包通过。 |

## 10. 结论

你的思路建议采纳。它更符合我们的实际节奏：先用BYD量产工程抽象出架构，再让东软优先交付mmWave/RF主链路所需的基础平台，这样我方能尽快开始ASW和RF移植，不会被UDS、OEM诊断、完整NM、XCP这些后置功能拖住。

唯一需要调整的是Bootloader：不要整体后置。第二阶段要有最小刷写闭环，第三阶段再做量产完整Boot和HSM安全闭环。
