# AUTOSAR阶段2/阶段3调整Review

基于 BYD 量产工程 `D:\Weifu\Project\CR\BYD_RL\xxx` 的最新确认结果，需要对阶段2和阶段3做一次收敛调整。核心结论是：

- BYD 工程的 mmWave/RF 主控制链路走 `mmWaveLink + Mailbox/IPC`，不是 SPI。
- `mmwave\mmwave\src\mmwave_link_mailbox.c` 中 `rlDevicePowerOn()` 前注册的是 `MMWave_mboxOpen/Read/Write/Close`。
- `mmwave\mmwave\src\mmwave_link_spi_22xx.c` 文件存在，但长度为 0，不构成实际 SPI 控制链路。
- 因此阶段2不能写成“SPI/mmWaveLink/其他接口都要做”，而应明确为“优先交付 mmWaveLink over Mailbox/IPC 主链路基础平台”。

## 1. 对阶段2的Review结论

原阶段2方向是对的：不要等完整 AUTOSAR 功能全部完成后才开始 RF/ASW 移植，而是先让东软交付我方能开发 mmWave/RF 主链路的基础平台。

但阶段2需要调整三点：

1. `5.2.4 mmWave RF/MMIC控制支撑基础` 需要改写。
   - 不能再把 SPI 写成并列主通道。
   - 应明确 BYD 参考工程中 RF 控制主通道是 `mmWaveLink + Mailbox/IPC`。
   - SPI 只作为“若新硬件存在外部器件需要 SPI 时再纳入”的确认项，不作为 RF 首版跑通前置条件。

2. 阶段2交付物要从“通用 BSW Bring-up”改成“主链路可开发底座”。
   - 阶段2验收不看 Dcm/Dem/NvM/NM/XCP 是否完整。
   - 阶段2验收看 OS 任务、Mailbox/IPC、eDMA、共享内存、中断、RTE骨架、CAN调试、最小Boot 是否足以让我方开始 RF/ASW 移植。

3. CDD 要拆分优先级。
   - 阶段2必须交付：`Cdd_Ipc`/Mailbox、eDMA/DMA CDD、mmWave任务调度相关适配。
   - 阶段3再交付或完善：外部 Watchdog、PMIC、SBC/Transceiver、完整故障日志、OEM诊断相关 CDD。

## 2. 阶段2建议调整后的定义

### 2.1 阶段2名称

建议名称从：

`阶段2：mmWave/RF主链路基础平台交付`

调整为：

`阶段2：mmWaveLink + Mailbox/IPC 主链路基础平台交付`

这个名字更准确，也能防止东软把精力放到 SPI RF 通道上。

### 2.2 阶段2目标

东软在阶段2需要交付一个可编译、可上板、可调度、可通信的 NeuSAR 基础平台，使我方可以把 BYD 量产工程里的 mmWave/RF、信号处理、数据处理、ASW 主枝干移植进来并开始联调。

阶段2不是完整量产版本，目标是支撑以下最小闭环：

```text
上电启动
  -> OS启动
  -> mmWave控制任务运行
  -> Mailbox/IPC可用
  -> mmWaveLink可调用
  -> RF最小配置可下发
  -> eDMA/共享内存数据路径可验证
  -> CAN/CANFD可输出状态
  -> 最小Boot可刷APP
```

## 3. 阶段2东软需要交付什么

### 3.1 工程与环境

东软需要交付：

- NeuSAR 可编译工程。
- MCAL/BSW/RTE 配置工程。
- 生成代码。
- 链接脚本/Memory Map。
- 编译脚本。
- 上板烧录说明。
- Debug说明。
- 已知问题清单。

验收：

- 我方能在本地复现编译。
- 生成物路径、配置工具版本、编译器版本明确。
- 工程不是只在东软电脑上能编译。

### 3.2 OS与任务调度

东软需要交付：

- 启动任务。
- BSW周期任务。
- ASW周期任务骨架。
- mmWave控制任务，参考 BYD 的 `OsTask_MmWaveCtrl`。
- DPM/数据处理任务，参考 BYD 的 `OsTask_DPM`。
- 触发任务，参考 BYD 的 `OsTask_TriggerWave`、`OsTask_Trigger66ms`。
- Alarm/Counter配置。
- 关键 ISR 配置。
- 任务优先级说明。
- 栈大小说明。

验收：

- 所有任务可运行，周期可测。
- mmWave相关任务优先级高于普通 ASW/BSW 周期任务。
- 任务调度不会导致 BSW 或 ASW 饿死。
- 能输出任务运行心跳或 trace。

### 3.3 Mailbox/IPC主链路

这是阶段2最关键的交付项。

东软需要交付：

- `Cdd_Ipc` 或等效 NeuSAR CDD。
- Mailbox 初始化。
- Mailbox 中断配置。
- RSS/DSS/M4/R5 之间的通信对象配置，具体核心命名按 AWR2944LC 项目实际资源确认。
- 共享内存区配置。
- IPC消息收发接口。
- IPC回调注册机制。
- 异常检测机制，例如超时、无响应、错误返回。
- 与 mmWaveLink 通信接口的适配说明。

验收：

- 双核/多核 IPC 消息能收发。
- Mailbox 中断能触发回调。
- 共享内存地址双方一致。
- 异常断链能被检测。
- 我方可以基于该接口接入 `MMWave_mboxOpen/Read/Write/Close` 等价适配。

### 3.4 mmWaveLink适配支撑

东软需要交付的是“支撑 mmWaveLink 运行的底层适配”，不是 RF profile/chirp/frame 业务配置本身。

东软需要交付：

- mmWaveLink 通信回调适配方案。
- `rlComIfOpen`、`rlComIfClose`、`rlComIfRead`、`rlComIfWrite` 的 Mailbox/IPC 适配接口。
- `rlRegisterInterruptHandler` 对应的中断注册/触发机制。
- `rlDevicePowerOn()` 前后的初始化顺序说明。
- CRC、延时、锁、信号量、队列等 OSI 适配接口。
- 错误码传递和日志接口。

我方负责：

- RF profile/chirp/frame 配置移植。
- `rlSetProfileConfig`、`rlSetChirpConfig`、`rlSensorStart` 等业务调用链路移植。
- RF标定参数解释和配置策略。
- 雷达主链路调试。

验收：

- 我方能调用一组最小 `rl*` API。
- `rlDevicePowerOn()` 到 RF 最小初始化链路能执行到可定位结果。
- 失败时能区分是 IPC、Mailbox、中断、配置参数还是 RF 侧返回错误。

### 3.5 SPI在阶段2的定位

阶段2不建议把 SPI 作为 RF 首版跑通硬依赖。

建议对东软写成：

- BYD量产参考工程中，mmWave/RF 主链路不走 SPI。
- 阶段2 RF主链路以 `mmWaveLink + Mailbox/IPC` 为准。
- SPI MCAL 可以保留为平台能力确认项。
- 如果新硬件上存在外部 PMIC、SBC、外部Flash、外部Watchdog、外部MMIC 等确实需要 SPI 的器件，则单独列入对应外设驱动范围。
- 不允许因 SPI 未完整量产化而阻塞阶段2 RF主链路 bring-up，除非双方确认新项目 RF 控制确实必须走 SPI。

### 3.6 eDMA/DMA与共享内存

东软需要交付：

- eDMA初始化。
- DMA通道配置。
- DMA中断配置。
- DMA传输示例。
- Buffer对齐要求。
- Cache一致性策略。
- 共享内存 Memory Map。
- DMA完成回调接口。

验收：

- 能完成一次真实 DMA 搬运。
- 中断或回调正常。
- 数据无 cache 污染。
- 我方信号处理代码可接入该接口。

### 3.7 CAN/CANFD最小通信

东软需要交付：

- `Mcu/Port/Dio/Can` 基础配置。
- `CanIf`。
- `PduR/Com` 最小链路。
- 最小 DBC 导入。
- Tx/Rx 示例。
- 调试状态报文。

验收：

- CAN/CANFD 可收发。
- ASW可调用发送接口。
- CANoe/CANalyzer可看到状态报文。
- 不要求阶段2完成完整 NM、完整诊断报文和完整OEM通信矩阵。

### 3.8 RTE/ASW接口骨架

东软需要交付：

- ASW初版 ARXML 导入方案。
- RTE头文件。
- Runnable调度。
- SchM/ExclusiveArea 最小支持。
- ASW Stub。
- 手写接口与 RTE 接口共存边界。

验收：

- 我方 ASW 能编译进东软工程。
- Runnable 能被 OS 周期调用。
- ASW 能调用 CAN状态、基础服务、mmWave底层封装接口。

### 3.9 最小Boot刷写闭环

阶段2必须保留最小 Boot，因为开发测试会大量依赖刷写。

东软需要交付：

- Boot能启动APP。
- APP能跳Boot。
- CAN/CANFD能刷写APP。
- 基础CRC校验。
- 刷写失败保护。
- 烧录手顺。

验收：

- 不依赖 JTAG 即可更新 APP。
- 刷写后 APP 能运行。
- 中断刷写或错误镜像不会启动坏 APP。

## 4. 对阶段3的Review结论

阶段3方向基本正确：在主链路已能运行后，补齐 OEM 和量产完整功能。

但阶段3也需要做两个调整：

1. NvM/Fls 要拆成“阶段2最小支撑”和“阶段3完整量产”。
   - 阶段2可以先提供 RF 标定参数读取的最小 Stub 或固定数据接口。
   - 阶段3再做完整 NvM Block、DID写入持久化、故障记录和Flash寿命策略。

2. SPI 不应写进 RF 完整功能，而应写进“平台外设完整性”。
   - 如果 SPI 用于外部 Flash、PMIC、SBC、Watchdog 或其他外设，阶段3补齐。
   - 如果没有外部SPI器件，则 SPI 只作为 MCAL配置能力保留，不作为RF验收项。

## 5. 阶段3建议调整后的交付范围

### 5.1 UDS/Dcm

东软需要交付：

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
- APP可通过 UDS 进入 Boot。
- 编程会话、安全访问、复位流程符合规范。

### 5.2 Dem/DTC/FiM

东软需要交付：

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

### 5.3 NvM/Fee/Fls完整存储

东软需要交付：

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
- RF标定数据读取链路与我方 ASW/RF 对接成功。

### 5.4 NM/ComM/CanSM/BswM

东软需要交付：

- CanNm。
- Generic Nm。
- ComM用户和通道。
- CanSM状态机。
- BswM规则。
- 休眠唤醒策略。
- 诊断保持通信策略。

验收：

- FullCom/NoCom切换正确。
- 网络休眠唤醒满足 OEM 时序。
- 诊断期间不误休眠。
- 和 BYD 工程中 `CanNm/Nm/ComM/BswM` 的功能范围保持同等级覆盖。

### 5.5 WdgM/WdgIf/外部看门狗

东软需要交付：

- 监控任务清单。
- Alive Supervision。
- Deadline Supervision，如需要。
- 外部 Watchdog 驱动。
- 复位策略。
- 故障记录接口。

验收：

- 正常运行不误复位。
- 指定任务卡死能触发复位。
- 复位原因可记录、可诊断读取。

### 5.6 XCP/A2L

东软需要交付：

- XCP over CAN/CANFD。
- A2L生成。
- 测量变量映射。
- 标定变量映射。
- 访问权限和开关策略。

验收：

- CANape或等效工具可连接。
- 指定变量可测量、可标定。
- 不影响实时主链路。

### 5.7 完整Bootloader/HSM/量产包

东软需要交付：

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

### 5.8 SPI/外设完整性

阶段3可补齐 SPI 相关内容，但范围要和 RF 解耦。

东软需要确认：

- 新项目是否有外部 SPI 器件。
- SPI 用于哪个器件。
- 是否需要 AUTOSAR `Spi` MCAL。
- 是否需要 DMA 模式。
- 是否需要独立 CDD 封装。
- 是否涉及 Boot、NvM、PMIC、SBC、外部 Watchdog 或外部 Flash。

验收：

- 如果项目有外部 SPI 器件，则对应驱动和集成测试通过。
- 如果项目无外部 SPI 器件，则 SPI 不作为量产功能验收项。

## 6. 和东软Excel原计划的差异

根据东软《毫米波雷达控制器开发计划》原 T1/T2/BT 节奏，建议差异如下：

| 项目 | 东软Excel原计划倾向 | 建议调整 |
|---|---|---|
| 阶段目标 | T1偏通用 BSW Bring-up，T2偏完整 BSW 功能 | 改为阶段2先交付 mmWave/RF 主链路基础平台，阶段3再补完整 AUTOSAR/OEM |
| RF控制通道 | 表格未明确，容易被理解成 SPI/MCAL 外设驱动之一 | 明确 BYD参考工程 RF主链路是 `mmWaveLink + Mailbox/IPC`，SPI不是RF首版前置 |
| CDD范围 | 原计划可能把 CDD 放在 T2 集成 | 拆分：`Cdd_Ipc`/Mailbox、eDMA 必须提前到阶段2；外设类 CDD 放阶段3 |
| RTE | 原计划 T2 做 RTE/完整接口 | RTE骨架、Runnable调度、ASW Stub 必须提前到阶段2，完整接口阶段3完善 |
| DMA/共享内存 | 原计划里通常不突出 | 阶段2必须作为核心交付，否则雷达数据链路跑不起来 |
| CAN/CANFD | T1做基础通信 | 保留在阶段2，但只要求最小Tx/Rx和调试报文，完整OEM通信放阶段3 |
| Dcm/Dem | T2完整功能 | 放阶段3，不阻塞阶段2 RF主链路 |
| NvM/Fee/Fls | T2完整存储 | 阶段2提供RF标定最小Stub/固定数据接口，阶段3完整NvM/Fee/Fls |
| NM/ComM/CanSM/BswM | T2完整网络管理 | 阶段2只保留最小通信管理，阶段3完整休眠唤醒/NM |
| Wdg/XCP | T2完整集成 | 阶段3做完整量产功能，阶段2只保留必要开发调试和复位安全 |
| Bootloader | 原计划通常单独 BT1/BT2，容易后置 | 拆成阶段2最小刷写闭环，阶段3完整 Boot/HSM/量产包 |
| 验收方式 | 以模块完成度为主 | 阶段2按“我方能否开始 RF/ASW 主链路开发”验收，阶段3按 OEM/量产测试验收 |

## 7. 推荐对东软的表达

建议会议上直接这样说：

我们希望阶段2不要按通用 AUTOSAR BSW 模块清单推进，而是按 BYD 量产工程的实际主链路推进。BYD 工程中 mmWave/RF 控制是通过 mmWaveLink 走 Mailbox/IPC，不是 SPI。因此阶段2请优先交付 OS任务、Mailbox/IPC、eDMA、共享内存、中断、RTE骨架、CAN最小调试和最小Boot刷写闭环。SPI可以作为平台能力确认，但不作为RF主链路首版跑通的前置条件。完整 DCM/DEM/NvM/NM/Wdg/XCP/Boot/HSM 等 OEM 和量产功能放到阶段3完成。

## 8. 最终建议

阶段2应该锁定为“主链路可开发”，交付物以 `mmWaveLink + Mailbox/IPC + eDMA + OS Task + RTE骨架 + 最小CAN + 最小Boot` 为核心。

阶段3应该锁定为“量产完整”，交付物以 `UDS/Dcm + Dem/DTC + NvM/Fee/Fls + NM/ComM/CanSM/BswM + Wdg + XCP + 完整Boot/HSM + 外设完整性` 为核心。

这样调整后，项目节奏更贴近 BYD 量产工程，也能避免东软先做一堆标准 AUTOSAR 功能，但我方迟迟无法开始 RF/ASW 主链路移植的问题。
