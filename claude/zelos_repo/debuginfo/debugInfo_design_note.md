# debugInfo 设计说明 (Design Note) — schema v4

> 运行时调试报文 — 实车无调试器环境下的"飞行记录仪"
> 模块代码:`mss/wf_debug_info.c` / `mss/wf_debug_info.h` ｜ 解析:`tools/debuginfo_parser.py`
> 作者:Peter Zhu ｜ 状态:已在 AWR2x44P EVM 上实测迭代(本周期黑匣子 / CPU 负载 / 总线估算 / 注入自检均已验证);WDT 闭环仍为待办(§10)。

---

## 0. 快速入门(TL;DR)

**平时**:什么都不用做。雷达每 **66ms** 自动连发两帧 `0x200`(hot)+ `0x201`(detail),一张完整体检快照。

**做一次体检 / 录到了一段总线想看健不健康**:
1. 用 CANoe / Kvaser 录几秒,存成 `.asc`。
2. 在 `mmw_ddm/tools/` 下跑(日常首选 `--summary`):
   ```
   python debuginfo_parser.py 你的录制.asc --summary
   ```
3. **只看末行 `VERDICT`**:
   - `OK` → 收工。
   - `OK (firmware) - only bench/environment faults` → 固件正常,只有台架/环境事(CANoe 未 ACK、无同步主节点…),通常不动固件。
   - `NEEDS ATTENTION` → 看每条 `[!]` 行(已带"是什么 + 下一步")。
4. 要逐帧明细加 `--full`;录制开场有缓冲假象用 `--skip 0.05s` 滤掉。

**主动自检(确认监控真的在工作)**:先把 `mss/wf_debug_inject.h` 的 `WF_DEBUG_FAULT_INJECT` 置 `1`(默认 `0`=关)并重编;然后往 **CAN-A 标准帧 id `0xC2`**(`WF_DBG_INJECT_CAN_ID`)发一帧,`data[0]`:
- `1`=软 assert(写黑匣子)、`2`=挂起 RspTask(任务失活+丢帧)、`3`=真延迟一帧 80ms(超时)、`4`=强制过温。
- 期望报告见 §12。

**量产出货前**:`mss/wf_debug_info.h` → `WF_DEBUG_INFO_ENABLE=0`(整模块编译消失);注入开关 `mss/wf_debug_inject.h` 的 `WF_DEBUG_FAULT_INJECT` 保持 `0`(留监控、只关 0xC2 注入)。

---

## 0.5 设计原理(核心思想)

**要解决的问题**:实车整机只有一条 CAN 总线,**接不了调试器** —— 看不到内存/栈,打不了断点,释放版 `assert` 命中即静默死循环。出问题时几乎没有观测手段(详见 §1)。

**核心思想(一句话)**:把散落在算法流水线 / 任务 / 资源 / 故障各处的运行时状态,用极轻量的单行埋点聚成一张全局快照;由一个**独立、最少依赖的发送任务**每 66ms 把它打成两条 CAN-FD 播出;离线用 `debuginfo_parser.py` 解析并**自动判读出一句话结论**。它回答"**现在健不健康、慢在哪、谁死了**",与 systemInfo("**上次为什么挂了**")互补。

```
  算法/任务/资源各处          独立发送任务(66ms)         离线
  ┌──────────────┐          ┌────────────────┐        ┌─────────────────┐
  │ 单行埋点      │  写全局   │ 评估存活/健康   │  CAN   │ parser --summary │
  │ mark_stage    │ ───────► │ 发 0x200 + 0x201│ ─────► │ → VERDICT 一句话  │
  │ task_alive 等 │  gWfDbg  │ rollingCounter++│        │   + 逐项告警      │
  └──────────────┘          └────────────────┘        └─────────────────┘
```

**为什么它是"可靠日志"而不是普通 printf**:靠五条设计原则(**粘滞位 / 峰值锁存读后清 / 滚动计数+CRC / 公共头每帧带 / 采集发送解耦**)—— 这是方法论核心,详见 **§3**。其中"采集/发送解耦 + 独立任务"最关键:报告器必须依赖最少、隔离最高,才能在被监控的任务崩溃时**自己还活着把它报出来**。

---

## 1. 出发点:一个硬约束

实车上整机只有一条 CAN 总线,**接不了调试器**:看不到内存、看不到栈、打不了断点、释放版 `assert` 命中即静默死循环。出问题时几乎没有观测手段。

因此引入一组专用 CAN 报文,固定 66ms 周期播出固件的"体检报告",在总线上用 CANoe/CANalyzer 接收、由 Python 脚本解析。**这组报文是实车上唯一的运行时观测窗口**,其设计质量直接决定故障可定位性。

---

## 2. 容量与结构:两条消息,一周期拿全快照

CAN FD 单帧最大 64 字节(DLC=15),装不下要监测的几十项信号。本设计用**两条 CAN-FD 消息**承载一张完整快照:

| 消息 | CAN ID | 内容 | msgIndex |
|---|---|---|---|
| hot | `0x200` | 时序 / 检测 / 存活(变化最快、最该实时盯的) | 0 |
| detail | `0x201` | TimeSync / CAN / 黑匣子 / 资源(慢变量) | 1 |

两帧每 66ms **背靠背连发**,合计 128B,去掉 2×(6B 头 + 2B CRC)= **112B 有效载荷**。经过去冗余(见附录 A 说明)把数据压到 112B 后,**一个周期即拿到完整快照,无需分页轮播**。DBC 只做透传(两条 64B 不透明消息),解析全在 Python 脚本。

> 早期 v1 是单帧 0x200 + 4 页轮播(264ms 一圈);v2 改双消息后取消轮播,`schemaVer` 升到 2,旧解析不会误读新帧。

---

## 3. 五条设计原则(方法论核心)

把"实时状态"变成"可靠日志"的关键,也是它区别于普通打印 log 的本质:

| # | 原则 | 动机 | 代码体现 |
|---|---|---|---|
| ① | **粘滞位 (sticky)** | 两帧间隔 66ms,期间的瞬态故障若只报"此刻"会漏。故障位"或累加",本上电周期内**只置不清** | `faultSummary \|= bit`,`wf_dbg_set_fault()` |
| ② | **峰值锁存 + 读后清零 (max-hold)** | 算法超时是偶发尖峰,平均值会抹平。各阶段耗时报窗口最大值,发出后清零 | `tMax[i]`;`wf_dbg_build_hot` 读后清 |
| ③ | **滚动计数器 + CRC** | rolling counter 每帧 +1,丢帧/阻塞可见;帧尾 CRC16 防误码 | `rollingCounter`、`wf_dbg_crc16()` |
| ④ | **公共头每帧都带** | "一眼定生死"信息每帧都带,丢一条也不瞎 | 两帧各带 Byte0–5 头 |
| ⑤ | **采集 / 发送解耦** | 采集点绝不阻塞发送;**独立发送任务**。即使 canoutput 挂死/栈溢出,本报文仍能发出并报告其失活 | 独立 `wf_debug_info_task` |

> 关于 ⑤:发送是**独立 FreeRTOS 任务**而非寄生在 `mss_canoutput_task`,是刻意的 —— 报告器要有最少依赖、最高隔离,才能在最复杂的任务崩溃时还活着报告它(栈溢出/任务挂死正是本模块要抓的目标)。

---

## 4. 架构与数据流

```
   算法流水线 (RspTask / DPM reportFxn)          独立发送任务 (66ms)
   ┌─────────────────────────────┐            ┌──────────────────────┐
   │ 单行"采集 API":             │            │ 1. eval 存活/健康     │
   │  wf_debug_mark_stage()      │  写全局     │ 2. 发 0x200(hot)      │
   │  wf_debug_frame_snapshot()  │ ─────────► │ 3. 发 0x201(det)      │
   │  wf_debug_task_alive() 等   │  gWfDbg    │ 4. rollingCounter++   │
   └─────────────────────────────┘            └──────────────────────┘
        (短临界区,不阻塞)                       (HwiP 临界区读快照)
```

- **采集端**:散落各处的单行埋点,只更新全局结构 `gWfDbg`,极轻量。
- **发送端**:独立任务(优先级 2,栈在 TCMB),66ms 醒一次,连发 0x200/0x201 两帧,共用本周期 `rollingCounter`,发完 +1。
- **并发**:采集与发送间用 `HwiP_disable/restore` 保证读写一致;所有 RMW(faultSummary)与"读后清零"(framePeriodMaxDev 等)均在临界区内对称保护。

---

## 5. 帧格式

### 公共头(两帧 Byte 0–5 各带 + 帧尾)

| 偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| 0 | u8 | `schemaVer`(bit7:4) \| `msgIndex`(bit3:0) | ver=4;msgIndex 0=hot/1=det |
| 1 | u8 | `rollingCounter` | 每周期 +1;**两帧相同**,解析端据此配对 |
| 2 | u16 | `faultSummary` | 12 粘滞位 |
| 4 | u8 | `sensorState`(bit3:0) \| `timeSyncState`(bit7:4) | |
| 5 | u8 | `taskAliveBitmap` | bit0 RSP,1 CANOUT,2 CANREC,3 TIMESYNC,4 CTRL |
| 62 | u16 | `CRC16-CCITT-FALSE` | poly 0x1021,init 0xFFFF,覆盖本帧 Byte 0–61 |

**`faultSummary` 位**:0 OVERRUN｜1 FRAME_DROP｜2 SYNC_LOST｜3 CAN_ERR｜4 OVER_TEMP｜5 DTC_ACTIVE｜6 TASK_DEAD｜7 STACK_LOW｜8 BLACKBOX｜9 VEHICLE_TIMEOUT｜10 ASSERT｜11 CAN_TX_STALL

> 收报文第一眼只看公共头的 `faultSummary` + `aliveBitmap`,哪位亮了再看对应字段。这两项在**两帧里都带**,丢一条也保得住。

---

## 6. 关键检测手法

1. **死字段改派生**:TI 自带 `interFrameProcessingMargin` 全工程无人填(死字段)。改为 `margin = 660 − tMax_total`(0.1ms,66ms=660),**由解析脚本派生,不占总线字节**。
2. **`lastStage` 指认卡点**:每个流水阶段写枚举值,卡死时冻结在最后到达的阶段。
3. **CAN 健康主动轮询**:bus-off 时收不到报文,故在 66ms 任务里主动读 `MCAN_getErrCounters` + `getProtocolStatus`(`wf_dbg_read_cana`)。
4. **任务存活位图**:各任务主循环 `wf_debug_task_alive()` 自增 tick,发送任务看"是否在涨"。周期任务(canout/timesync)才判死,事件驱动的 canrec 只进位图。
5. **栈水位扫描**:静态栈从栈底数连续 `0x00/0xA5A5A5A5` 字算剩余(`wf_dbg_scan_stacks`),传 6 个任务的水位。
6. **CPU 负载用 run-time stats(免抢占)+ 抗回绕累加**:`cpuR5Avg/Peak`、`cpuRsp`、`cpuCanout` 取自 FreeRTOS 每任务 run-time 计数(`vTaskGetInfo`/`ulTaskGetIdleRunTimeCounter`),是**CPU 时间**不是墙钟,免受抢占污染(这也是 `canout≈0%` 正确、而 timing 阶段是墙钟会被抢占抬高的原因)。
   - **抗 71min 回绕**:计数器源是 32 位微秒计数器,`2^32µs≈71.6min` 回绕。直接用"当前 total 作分母"在首次回绕后会失真(分母回绕、分子不同步)。`wf_dbg_eval_cpuload` 每 66ms 跑一次(≪71min),把**无符号回绕安全的逐次差值**累加进 **64 位累加器**(`accTotal/accIdle/accRsp/accCan`)再求比 → **累计均值整个 uptime(含 18h)都准**。
   - **窗口峰值**(`cpuR5Peak`)单独用 0.5s 窗口的差值算最坏尖峰(如 flash 写),与累计均值互补:均值看常态、峰值看挤帧风险。

---

## 7. 黑匣子(本上电周期实时定位)

**作用**:命中 assert 时,**实时**把死点(文件名 hash + 行号 + 计数)经 0x201 播出来,你抓总线日志当场就能看到死在哪。

**手法**:
1. assert 钩子 `wf_debug_blackbox_assert(file, line)` 写普通 RAM 里的 `gWfDbgBlackBox`(行号 + 文件名 hash + 计数),并置 `ASSERT` 粘滞位。
2. Page det 上报 `bbRecValid`(本周期有记录)+ `bbLine`/`bbFileHash`(死在哪)+ `assertCountLive`(几次)。

**职责边界**:本黑匣子**只管本上电周期**(普通 RAM,每次上电清空)。"上次启动有没有崩"由**系统级 dumptrace / systeminfo** 负责 —— 二者互补:dumptrace 是跨复位事后回读,本黑匣子是本周期实时。

> 早期版本曾尝试用 noinit RAM 跨 warm reset 保留黑匣子,但本平台**没有可用的热复位**(只能 PMIC 冷复位 = POR,RAM 物理清空),且与系统 dumptrace 重复,故移除。若将来需要"跨任意复位(含 POR)的崩溃回读",正解是**写 flash**(软 assert 在正常上下文从容写,预擦扇区、崩溃时只写不擦),而非 noinit RAM。

---

## 8. 内存布局

MSS_L2 近满载且碎片化(见仓库 CLAUDE.md),`mss/mmw_mss_linker.cmd` 按对象文件路由出 MSS_L2:

| 段 | 去向 | 内容 |
|---|---|---|
| `.wfDbgCode` | TCMA_RAM | `wf_debug_info.oer5f` 的 `.text`/`.rodata` |
| `.wfDbgData` | TCMB_RAM | 其 `.data`/`.bss`(含黑匣子,普通 RAM) |
| `.bss.wfDbgStack` | TCMB_RAM | 发送任务栈 |

---

## 9. 实战:如何用它定位问题

```
收齐同一 rolling 的 0x200+0x201 → 看 faultSummary 哪位亮
  ├ bit0  超时     → 0x200: 哪段 tMax 爆、marginMin(派生) 走负
  ├ bit1  丢帧     → 0x200: frameTrigger 涨但 result 停 = DSP/DPM 挂
  ├ bit6  任务失活 → aliveBitmap 哪个任务位灭
  ├ bit10 assert   → 0x201: bbLine + bbFileHash = 本周期死在哪行
  ├ bit11 TX 阻塞  → CAN 背压/带宽不足
  └ rollingCounter 不连续 → 丢帧或总线阻塞
```

`tools/debuginfo_parser.py` 自动:双 ID 收 → 按 rolling 配对成快照 → CRC 校验 → 派生 marginMin → rolling 连续性 / 丢半帧 / trigger-result 趋势告警。

---

## 10. 待办与硬件验证项

1. **MSS WDT 使能(自动恢复)**:改 syscfg,在 66ms 任务里喂狗,使"挂死→复位→自救"闭环。前提先确认本平台 WDT 复位路径(本芯片 MSS 热复位有问题,复位只能走 PMIC)。
2. **跨复位崩溃回读(可选)**:若需要,走 flash 持久化(见 §7),非 noinit RAM。当前跨复位由系统 dumptrace 负责。
3. **基本收发**:CANoe 收 0x200/0x201 成对,rollingCounter 连续、CRC 对、数值与 CCS 观测一致。

---

## 11. 故障速查(看 `--summary` 报告定位)

核心心法:`python tools/debuginfo_parser.py <capture>.asc --summary` 末尾的 **`VERDICT` 块已替你分好类,先只看它**,30 秒定位。

### 30 秒三步走

1. **只看最后一行 `VERDICT`**
   - `OK` → 无事。
   - `OK (firmware) - only bench/environment faults` → 固件正常,下面 `[bench]` 行是台架/环境事(CANoe 未 ACK、无同步主节点等),通常不用动固件。
   - `NEEDS ATTENTION` → 有真问题,每条 `[!]` 带了是什么 + 提示。
2. **看方括号标签**:`[!]` = 固件/系统要排查;`[bench]` = 环境。
3. **真有 `[!]` 才按下表往下挖。**

记忆口诀:**死没死 → 慢没慢 → 断没断 → 漏没漏**。

### 速查表:报告里看到 X → 去哪查

| 报告字段/标志 | 说明 | 下一步 |
|---|---|---|
| `blackbox record: YES` | 上次崩溃过(最高优先级) | `--full` 看 `bbLine`+`bbFileHash` = 死在哪文件哪行 |
| `warmResetCause=...(MSS_WDT/HSM_WDT)` | 被看门狗复位 = 挂死过 | 配合 blackbox 看死点;`boot` 是否 >1 |
| `overrun max>0` | 帧处理爆 66ms 预算 | 看 `timing max-hold` 哪段最大(CM4/DOA/postproc) |
| `lastStage` 卡某阶段(`--full`) | 流水卡死点 | 该阶段即卡点 |
| `FRAME_DROP` / `frameTrigger 涨 result 停` | DSP/DPM 挂了 | trigger 涨 result 不动 = 信号处理链断 |
| `TASK_DEAD` | 某周期任务停跳 | 逐帧看 `alive=` 少了哪个任务 |
| `stack free min` 某项 < ~256B | 栈快溢出 | 看哪个任务,加栈 / 查递归 / 大局部变量 |
| `CRC err>0` / `schema err>0` | 解码对不上 | 固件与脚本 schema 没同步,或总线误码 |
| `rolling gaps`/`missing` **中段反复** | 真丢帧 | 查总线拥塞 / 复位(`uptime` 归零、`boot` +1) |
| `rolling gaps`/`missing` **只在 t≈0** | 录制开场缓冲假象 | `--skip 0.05s` 滤掉,忽略 |
| `ASSERT` / `lastErrorCode≠0` | 命中断言 / 有错误码 | `--full` 看 `assertLive`、错误码值 |

### `--summary` 字段逐行含义(自查用)

| 字段 | 含义 | 正常 | 该警觉 |
|---|---|---|---|
| `frames`/`cycles`/`duration` | 解出帧数/周期数(=帧/2)/时长 | cycles≈时长÷0.066 | 纯信息 |
| `sensorState` | 传感器状态 | 运行时 `STARTED` | 该跑却 `OPENED`=没启动 |
| `timeSyncState` | 时间同步状态 | 有主节点时 `SYNCED` | `SYNC_LOST`=同步丢;`SILENT_WAIT`=无主节点(台架正常) |
| `boot` | 启动计数 | 稳定 | 突增=复位过 |
| `uptime` | 开机秒数 | 持续增长 | 中途突然变小=重启了 |
| `resetCause`/`warmResetCause` | 上次复位原因 | `POWER_ON` | `MSS_WDT`/`HSM_WDT`=看门狗触发(挂过) |
| **`frameStart→`/`resultCount→`** | 起始帧/完成帧(整段 首→尾) | **一起涨、数值接近** | start 涨 result 停=**处理挂**(FRAME_DROP);都不涨(STARTED下)=BSS 没触发 |
| **`timing` total** | 总耗时峰值(0.1ms) | **< 660**(66ms) | 接近/超 660=超时风险 |
| `timing` CM4/DOA/postproc | 各阶段耗时峰值(墙钟,含抢占,当趋势看) | 稳定 | 某阶段持续上抬=该算法变慢 |
| **`CPU load` R5 avg/peak** | R5 总负载:累计均值 / 窗口峰值(run-time stats,免抢占;均值 64 位累加抗 71min 回绕,18h 也准) | avg 有余量;peak 不长期触顶 | peak 频繁趋近 100%=有尖峰挤帧风险 |
| `CPU load` rsp/canout | 算法 CPU% / CAN发送 CPU% | rsp 稳定;canout≈0(发送是 FIFO 硬件,几乎不吃 R5) | rsp 飙升=算法变重 |
| `overrun max` | 总耗时超 66ms 累计次数 | 0 | >0=有帧超时 |
| `framePeriodMaxDev` | 帧周期最大抖动(0.1ms) | 个位数 | 变大=帧节奏不稳 |
| `tec`/`rec` | CAN-A 发/收错误计数 | 0 | tec 爬升=没ACK/总线问题;>127=error-passive |
| `busOffEver`/`txStall`/`CEL` | bus-off次数/TX满次数/硬件错误日志 | 全0 | 非0=总线断过/背压/有错 |
| `CAN-A TX rate` frames/s, KB/s | **优先用 ASC 实测**:脚本按 DBC 中 FL/FR TX CAN ID + 点云 ID(`FL=0x110`,`FR=0x111`)扫描录制报文;无 ASC/DBC 匹配时回退到 debugInfo det@28/@53 的固件上报峰值 | 与对象数相符、稳定 | 暴涨=发送异常;配合 `txStall` 判总线吃不吃得下 |
| `est. bus load (this radar)` | 由脚本按 `frames/s` + `KB/s` 和 500K/2M CAN-FD 时序估算;summary 行会标明 `ASC measured` 或 `debugInfo peak` 来源 | 与网络设计预算相符 | ASC 实测只统计 DBC/点云命中的 TX ID;本网络仅 FR+FL 时两台相加≈全总线占用;判总线满仍以 `txStall`/`tec` 为准 |
| `TimeSync crcErr/invalid/jump` | 同步帧 CRC错/非法/时间跳变 | 全0 | 非0=同步帧损坏或时间不连续 |
| `blackbox record` | 上次启动有无崩溃记录 | `no` | `YES`=上次崩过 |
| `assertLive max` | 本次运行 assert 命中数 | 0 | >0=命中过(看 `--full` det 页 `bbLine` 定位行号) |
| `lastErrorCode` | 最近模块错误码 | 0 | ≠0=某模块返回错误 |
| `stack free min` | 各任务栈底剩余最小值(B) | 千字节级 | 某项 < ~256B=快溢出 |
| `integrity CRC err`/`schema err` | 误码/版本不匹配 | 0/0 | CRC>0=误码;schema>0=固件↔脚本版本没对上 |
| `integrity rolling gaps`/`missing` | 丢周期/丢半帧 | 0/0(或仅 t≈0) | 中段反复=真丢帧(`--skip` 滤开场) |
| `VERDICT` | 一句话结论 | `OK` | `NEEDS ATTENTION`=看 `[!]` 行 |

**30 秒自查**:看 `VERDICT` → 若 `OK` 收工。再扫 4 点:① `frameStart`/`resultCount` 一起涨且接近;② `total`<660;③ `stack free min` 无 <256B;④ `integrity` 全0、`blackbox`=no、`tec`=0。四项都正常即健康。

### CAN 总线负载估算公式(parser 端,可改)

脚本现在有两种 TX 速率来源,总线占用都用同一套 CAN-FD 时序公式估算,常量在 `debuginfo_parser.py` 顶部 `CAN_*`:

1. **ASC measured(首选)**:`.asc` 输入时,脚本读取 TX DBC,按 FL/FR 的 TX CAN ID + 点云 ID(`FL=0x110`,`FR=0x111`)逐帧统计录制报文的帧数和 payload 字节数。
2. **debugInfo peak(回退)**:没有 ASC/DBC 匹配时,使用固件在 `0x201/0x203` det 半帧里上报的 `txFramesPerSec`/`txKBytesPerSec` 峰值。

```
本节点占用 ≈ frames/s × 每帧固定开销 + bytes/s × 每字节
         = frames × 78µs        + bytes × 4µs
```
- **每帧固定 78µs** = ~30 仲裁段位 ×2µs(500K)+ ~36 数据段控制/CRC 位 ×0.5µs(2M)。与 payload 无关:SOF/ID/控制/ACK/EOF/IFS + ESI/DLC/stuff-count/CRC。
- **每字节 4µs** = 8 位 ÷ 2Mbps。
- 当前总线 **500K / 2M**;改波特率只改 `CAN_NOM_BITS_US`/`CAN_DAT_BITS_US` 两个常量。**采样点(80%)不进公式**——它只决定位内采样点位置,不改位时长。
- 误差 ±~1–1.5%(未计位填充动态位、DLC 量化补齐),**只作量级/趋势用**;判总线满仍以 `txStall`/`tec`/`busOff`(实测背压)为准。
- 本网络仅 **FR + FL** 两节点同固件 → **两台 `est. bus load` 相加 ≈ 全总线占用**(无别的 ECU 漏算)。

### CAN 故障:台架假象 vs 真问题

`CAN_ERR`/`CAN_TX_STALL` 被标 `[bench]` 只是启发式,真假看在哪条总线录:

- **台架(雷达 + CANoe)**:几乎一定是 CANoe **listen-only 未 ACK**。改成正常模式(主动 ACK)再录,标志应消失。
- **整车总线(多 ECU)**:仍出 `CAN_ERR` 即**真问题** → 查 120Ω 终端(两端各一)、波特率、线束/收发器。
- 辅助判据:`tec max` 爬到 128(error-passive)或 `busOffEver>0`,且总线上有别的活动节点 → 偏真故障。

---

## 12. 自检测试(故障注入 → 期望报告)

"测试你的烟雾报警器":每个监控都主动制造一次对应故障,确认①故障位会亮、②报告能指到位置。做一遍建立信心。

### A. 台架/总线即可造(无需改固件)

| 故障 | 怎么造 | 报告应出现 |
|---|---|---|
| `CAN_ERR` | CANoe 设 listen-only(不 ACK)/ 拔 CANH-CANL / 设错波特率 | `CAN_ERR`,`tec` 爬到 128,`busOffEver++` |
| `CAN_TX_STALL` | 调低波特率 / 加大对象输出频率 / 阻塞总线 | `CAN_TX_STALL`,`txStall max` 飙升 |
| `SYNC_LOST` | SYNCED 后停发 TimeSync 主帧(0x40) | `SYNC_LOST`,`sync=SYNC_LOST` |
| `VEHICLE_TIMEOUT` | 停发车身信息 20ms 报文 | `VEHICLE_TIMEOUT`,`vehAgeMs`>200 |
| TimeSync `crcErr`/`invalid` | 发一帧 0x40 但 CRC/载荷故意错 | `crcErrorCount++` / `invalidFrameCount++` |

### B. 用注入工具造(`wf_debug_inject.*`,CAN 触发)

**触发方式**:从 CANoe 在 **CAN-A(发 0x200 那条总线)** 发一帧到 `WF_DBG_INJECT_CAN_ID = 0xC2`,`data[0]` = 故障码(或 CCS 里写 `gWfDbgInjectCmd`)。生产编译把 `WF_DEBUG_FAULT_INJECT` 置 0 即全部剔除。

> ⚠️ 注入 ID 必须在 MCAN 接收白名单里。本工程是 buffer 模式白名单(`0xC0–0xC4` + 车身/标定/tsync + 0x74C/0x78C),`0xC2` 已被收下且 CAN-A 无人处理,故选它,零过滤器改动。**不要用 `0x2FF`** —— 不在白名单(硬件直接丢)且与 OTA tx id 撞。

| `data[0]` | 宏 | 注入 | 报告应出现 |
|---|---|---|---|
| 1 | `WF_INJ_ASSERT` | 写黑匣子 + 置 ASSERT(软断言,系统照常) | 本周期 `ASSERT` + Page det `bbRecValid`/`bbLine`/`bbFileHash`/`assertLive`(实时,无需复位) |
| 2 | `WF_INJ_KILL_RSP` | 挂起 RspTask | `TASK_DEAD`(`alive=` 少 RSP)+ `FRAME_DROP`(frameStart 涨 result 停)+ 解析器 "DSP/DPM hang" 趋势告警 |
| 3 | `WF_INJ_OVERRUN` | RspTask 真实延迟一帧 80ms(经 rangeStartTs 环正确测量) | `OVERRUN`,`overrun max>0`,`marginMin` 转负,`total≈1160` |
| 4 | `WF_INJ_OVERTEMP` | 强制过温 | `OVER_TEMP` |

> 黑匣子是**本上电周期**实时定位(见 §7),不做跨复位。跨复位崩溃回读由系统 dumptrace 负责。

### C. 编译期阈值即可造

| 故障 | 怎么造 |
|---|---|
| `STACK_LOW` | 临时把 `WF_DEBUG_STACK_LOW_BYTES` 调到高于当前 `stack free min` → 立即亮(无需真撑爆栈) |
| `OVER_TEMP`(实测) | 临时把 `WF_DEBUG_OVER_TEMP_C` 调到低于室温 |

### 已修:FRAME_DROP 的哑源

`FRAME_DROP` 原先比较 `gMmwMssMCB.stats.frameTriggerReady` —— 那是 BSS `RL_RF_AE_FRAME_TRIGGER_RDY_SB` 事件,**整个 sensor 启动只发一次(恒=1)**,永远不会超过 `resultCount`,导致 FRAME_DROP 和解析器趋势告警都是哑的。现改用**每帧在 `RANGE_START` 自增的 `frameStartCount`**(同时占用 0x200 offset 30,取代原冻结字段),两条监控才真正接通。**这正是 §12 自检"揪出哑监控"的价值。**

### 已修(量产):`mcanA_transfer_FIFO` 并发竞态

调试任务每周期直接调 `mcanA_transfer_FIFO` 发 0x200/0x201,使该函数**第一次有了两个并发调用者**(原本只有 canoutput 任务)。函数体 `读 putIdx → 写该槽 → AddReq 该槽` 是 TOCTOU:高优先级的 canoutput 抢占调试任务时,两者会拿到**同一个 putIdx**,导致**对象帧被覆盖或同槽双请求**(丢真数据)。

修法:`mss_mcan.c` 加一把 **优先级继承互斥锁** `gMcanaTxFifoMutex`(`SemaphoreP_constructMutex`,在 `mcan_initialization` 构造),串行化整个取槽→写→请求序列。等待循环里有 `vTaskDelay`,故用 mutex 而非关中断;所有返回路径(含 FIFO 满超时丢帧)经单一 `out:` 释放,无死锁;`gMcanaTxFifoMutexValid` 门控避免 init 前 pend。

**整把锁用 `#if WF_CAN_TX_SERIALIZE` 门控**,其中 `WF_CAN_TX_SERIALIZE = (WF_DEBUG_INFO_ENABLE || WF_SYSINFO_ENABLE)`:只要存在第二个 TX 调用者(debugInfo 的 0x200/0x201 **或** systemInfo 的 0x100)就生效。**只有两者都关时**,声明/构造/pend/post/`out:` 才全部预处理消失,`mcanA_transfer_FIFO` 逐字节回到原始单调用者版本(超时走 `return`,无锁)。注意:量产 D sample 即便关掉 debugInfo,只要 **systemInfo 仍开**(崩溃黑匣子,通常保留),锁就**必须保留**——因为 systemInfo 的发送任务同样是 FIFO 的并发调用者。

---

## 13. 已知缺陷与权衡(必读)

这是**尽力而为(best-effort)**的运行时遥测,不是形式化保证。按重要度排:

1. **【结构性】只能报告"别人死了",报告不了"自己/内核彻底死了"。** 发送是独立 prio-2 任务,隔离度已做到最高,但仍依赖调度器/SysTick 在跑。若崩溃把内核或中断打死,66ms 报文会**停**——此时"报文消失 + `rollingCounter` 停 + `uptime` 不再涨"本身是信号,但**拿不到死时的快照**。"挂死那一刻发生了什么"要靠 systemInfo(异常向量直接抓)+ 硬件 WDT,不归本模块。

2. **覆盖面 = 埋点覆盖面。** debugInfo 只看到你**手动埋了点**的地方(`wf_debug_mark_*`)。新增流水阶段 / 新任务 / 新错误路径,必须同步加埋点,否则是盲区。它不是自动全覆盖的。

3. **黑匣子只管本上电周期(普通 RAM,POR 清空)。** assert 死点只在**本次上电**的后续帧里持续带出(粘滞位 + bbLine);一旦冷复位就清。跨复位崩溃回读不归它,归 systemInfo。

4. **各阶段 `tMax` 是墙钟(含抢占),只能当趋势,不是纯算法耗时。** 只有 `CPU load` 那几个 run-time-stats 百分比是真 CPU 时间(免抢占)。把 `tMax_DOA` 之类当"该算法绝对耗时"会被高优先级抢占抬高而误判 —— 这是最常见的使用陷阱。

5. **CAN 总线负载是 parser 端粗估(±1–1.5%),且只算本节点 TX。** 不是实测占用:没算 RX、别的 ECU、位填充动态位。判总线是否吃得下,**最终以 `txStall`/`tec`/`busOffEver` 实测背压为准**。"两台相加≈全总线"只在本网络仅 FR+FL 两节点时成立。

6. **112B 载荷零余量。** 两帧各 56B 已占满,**加任何新监测字段必须先腾位**(去冗余或砍字段)并 `schemaVer+1`。扩展性受限,这是双帧不分页换来的取舍。

7. **粘滞位本上电周期"只置不清"。** 好处是不漏瞬态故障;代价是某位一旦亮过就一直亮,**分不清"还在发生"还是"发生过一次"**——要区分得配合对应计数器的趋势(是否还在涨)。

8. **`schemaVer` 手动维护,漏改会静默误读。** 固件改了字段布局却忘了 +schemaVer 且同步改 parser,会被悄悄错解。`integrity schema err` 只有在版本号**变了**才报得出,版本号没动的错位它发现不了。

9. **栈水位依赖填充图样(0xA5/0x00)。** 若栈未被初始化填充、或已被踩穿覆盖了图样,`stackFree16` 读数会失真。它是"快溢出预警",不是精确测量。

10. **黑匣子只传文件名 16 位 hash,不传文件名。** 省字节;parser 要有 `hash→文件名` 映射表才能反查到文件,且理论上有 hash 碰撞可能(行号 `bbLine` 仍是精确的)。

> 一句话:**它让"实时状态"变成"可靠、可离线判读的日志",覆盖绝大多数"慢了 / 断了 / 某任务死了 / 资源紧张"的场景;但它依赖系统整体还活着,且只看到你埋了点的地方。** 终极的"硬死机 + 自动复位自救"要靠 systemInfo + 硬件 WDT(§10 待办①)。

---

## 附录 A:字节偏移表(解析权威 spec)

> 偏移为**帧内绝对字节**(0–63),小端。固件真相源是 `wf_debug_info.c` 的 `wf_dbg_build_hot()` / `wf_dbg_build_det()`;**改 schema 时先改本表,`debuginfo_parser.py` 照本表实现**。`schemaVer` 当前 = 4,字段变更需 +1。两帧公共头同上表(§5)。**两条各 56B 载荷正好占满,零余量** —— 加新字段需先腾位。

### 0x200 hot(msgIndex=0)— 时序/检测/存活

| 偏移 | 类型 | 字段 | | 偏移 | 类型 | 字段 |
|---|---|---|---|---|---|---|
| 6 | u16 | `tMax_CM4`(0.1ms) | | 34 | u32 | `resultCount` |
| 8 | u16 | `tMax_DOA` | | 38 | u16 | `cfarNumCur` |
| 10 | u16 | `tMax_postproc` | | 40 | u16 | `cfarNumMin` |
| 12 | u8 | `cpuR5AvgPct`(R5总负载,累计均值) | | 42 | u16 | `cfarNumMax` |
| 13 | u8 | `cpuR5PeakPct`(R5负载,窗口峰值) | | | | |
| 14 | u8 | `cpuRspPct`(算法 DOA+perc) | | 44 | u16 | `trcNum` |
| 15 | u8 | `cpuCanoutPct`(CAN发送,真实CPU≈0) | | | | |
| 16 | u16 | `tMax_total` | | 46 | u16 | `intfNumCur` |
| 18 | u16 | `tTotalCur` | | 48 | u16 | `waveIdCur` |
| 20 | u16 | `overrunCount` | | 50 | u16 | `failedTimingReports` |
| 22 | u32 | `lastOverrunFrame` | | 52 | u16 | `calibrationReports` |
| 26 | u16 | `framePeriodCur` | | 54 | u16 | `vehAgeMs`(ms,0xFFFF=从未) |
| 28 | u16 | `framePeriodMaxDev` | | 56–59 | i8×4 | `tmpRx0/Tx0/Pm/Dig0`(°C) |
| 30 | u32 | `frameStartCount`(每帧++) | | 60 | u8 | `tempValid`(1=有效) |
| | | | | 61 | u8 | `lastStage` |

> `marginMin` 不传,解析端派生 `660 − tMax_total`(0.1ms,<0 即超时)。
> `lastStage` 枚举:1 RANGE_START｜2 DOPPLER_START｜3 CFAR_START｜4 DPC_RESULT｜5 DOA_DONE｜6 POSTPROC_DONE

### 0x201 detail(msgIndex=1)— TimeSync/CAN/黑匣子/资源

| 偏移 | 类型 | 字段 | | 偏移 | 类型 | 字段 |
|---|---|---|---|---|---|---|
| 6 | u16 | `vehicleRxCount`(回绕) | | 38 | u16 | `assertCountLive` |
| 8 | u16 | `validFrameCount`(回绕) | | 40 | i32 | `lastErrorCode` |
| 10 | u16 | `crcErrorCount` | | 44 | u8 | `dtcActive` |
| 12 | u16 | `invalidFrameCount` | | 45 | u8 | `dtcReason` |
| 14 | u16 | `offsetJumpCount` | | 46 | u8 | `lastSeqCounter` |
| 16 | i32 | `offsetUs` | | 47 | u8 | `tec` |
| 20 | u16 | `busOffEverCount` | | 48 | u8 | `rec` |
| 22 | u16 | `canTxStallCount` | | 49 | u8 | `canFlags`(bit0 busOff,1 errPassive,2 warning) |
| 24 | u16 | `dtcReportCount` | | 50 | u8 | `resetCause` |
| 26 | u16 | `canErrLogCnt`(HW CEL,≤255) | | 51 | u8 | `warmResetCause` |
| 28 | u16 | `txFramesPerSec`(雷达自身TX) | | 52 | u8 | `bbRecValid` |
| 30 | u16 | `uptimeSec`(秒,饱和,18h 上限) | | 53 | u8 | `txKBytesPerSec`(雷达自身TX,KB/s) |
| 32 | u16 | `bbLine` | | 54 | u8 | `sensorStartCount` |
| 34 | u16 | `bbFileHash` | | 55 | u8 | `sensorStopCount` |
| 36 | u16 | `bbAssertCount` | | 56–61 | u8×6 | `stackFree16[0..5]`(剩余/16B,0xFF=未注册) |

`stackFree16` 注册顺序:0 ctrl,1 rsp,2 canout,3 canrec,4 tsync,5 wfdbg。

**v1→v2 字段裁剪(无诊断信息损失)**:`resultCount` 去重(原 P0/P1 各一份)、删 2 个 padding、`marginMin` 改派生;`uptime` u32 ms→u16 秒、`canErrLogCnt`/`validFrameCount`/`vehicleRxCount` u32→u16、`stackFree16[8]→[6]`。

---

## 附录 B:对外开关

`wf_debug_info.h` 顶部 `WF_DEBUG_INFO_ENABLE`:置 0 时所有采集 API 编译为空宏,量产可一键关闭。

---

## 附录 C:解析脚本

`tools/debuginfo_parser.py` —— 按附录 A 实现:双 ID 收 + rolling 配对 + 派生 marginMin + 粘滞位/状态/复位原因解名 + 连续性/丢半帧/趋势告警。输入支持 CANoe `.asc`(经典/CANFD,按 asc 头 `base hex|dec` 解析 ID)与十六进制行。帧的 hot/det 归属取自帧头 `msgIndex`(不靠 CAN ID),hex dump 无 ID 也能解析。

脚本同时支持 **ASC 实测 CAN-A 负载**:`.asc` 输入时读取 `mss/dbc/MCR1+MFR1+objects_list CAN Matrix to Zelos_V3.0.2_07_TX.dbc`,按 DBC 中 FL/FR 的 TX CAN ID 统计录制报文,并额外纳入点云 ID `FL=0x110` / `FR=0x111`。summary 中 `CAN-A TX rate (ASC measured)` 与 `est. bus load` 使用这个实测口径;没有匹配数据时才回退到 debugInfo 内部上报的 `debugInfo peak`。纯 stdlib,Python 3.7+。

如果量产版本屏蔽 debugInfo,`.asc` 中没有 `0x200/0x201/0x202/0x203`,脚本不会直接失败;只要录制里有 DBC/点云匹配的 TX 报文,会输出 `no debugInfo frames found; showing ASC measured CAN-A bus load only` 并给出 CAN 负载统计。

### 多雷达(合并总线)自动分流

两台雷达电气合并到同一条 CAN 总线,固件按位置给 debugInfo ID 加偏移(`wf_debug_info.c`:FL 发 `CAN_ID`,FR 发 `CAN_ID+2`):

| 雷达 | hot / det |
|---|---|
| **FL**(FRONT_LEFT) | `0x200` / `0x201` |
| **FR**(FRONT_RIGHT) | `0x202` / `0x203` |

解析脚本**按 CAN ID 路由到各自的 monitor**(`msgIndex` 只在单台内区分 hot/det,分不出 FL/FR),所以一份 `.asc` 会输出:**每台雷达一份独立 summary + VERDICT**。对于 CAN 负载,summary 内部会优先显示 DBC/ASC 实测值,末尾追加 `ASC measured CAN-A bus load` 表,列出 FL/FR/TOTAL 的帧数、命中 ID 数、frames/s、KB/s 和估算负载。

> **免 Python 的独立 exe**:对外分发时不必给 `.py` 源码,用 `dist/debuginfo_parser.exe`(单文件,目标机器无需装 Python),把 `.asc` **拖到图标上**即出报告。打包方法见**附录 E**。

- ID↔位置的映射集中在脚本顶部 `RADARS` 列表;换偏移/加后雷达(RL/RR)改这一处即可。
- 只录到一台时只出一份 summary、不打合计行(向后兼容单雷达老 capture)。
- ⚠️ **旧版脚本 `want_ids` 只收 `0x200/0x201`,会静默丢掉 FR 的 `0x202/0x203`** —— 即只解析了 FL。务必用本版解析合并总线的录制。

### 用法

```bash
# 快速体检:跑完整段,出"体检报告 + 结论"(日常首选)
python debuginfo_parser.py capture.asc --summary

# 逐帧明细(查某一时刻);加 --full 在每个周期末打印完整快照
python debuginfo_parser.py capture.asc
python debuginfo_parser.py capture.asc --full

# 滤掉录制起始的缓冲假象(CANoe 开场会刷一批挤在一起的旧帧)
python debuginfo_parser.py capture.asc --summary --skip 0.05s   # 丢弃 t<0.05s 的帧
python debuginfo_parser.py capture.asc --summary --skip 16      # 或丢弃前 16 帧

# 串口转发/手动粘贴的十六进制(每行 64 字节)
python debuginfo_parser.py frames.hex --format hex --summary
```

### 怎么看 `--summary` 的结论

末行 `VERDICT`:
- **`OK`** —— 无故障、无完整性问题。
- **`OK (firmware) - only bench/environment faults`** —— 固件正常,只有台架/环境类故障(`CAN_ERR`/`CAN_TX_STALL`/`SYNC_LOST`/`VEHICLE_TIMEOUT`),通常是 CANoe 未 ACK、无同步主节点等,非固件问题。
- **`NEEDS ATTENTION`** —— 有需排查项(CRC 错、schema 不匹配、黑匣子有崩溃记录、overrun、任务失活、栈紧张、assert 命中等),逐条带提示。

完整性栏:`rolling gaps`/`missing hot/det` **只在 t≈0 出现一次** = 录制开场假象(用 `--skip` 滤掉);**录制中段反复出现** = 真丢帧(查总线拥塞或设备复位:看 `uptime` 是否归零、`resetCause`)。

---

## 附录 D:`--summary` 报告逐字段详解

> 这份解释报告**输出端的每一行**:数据来自哪条帧/哪个字节(对应附录 A)、脚本怎么算出来的、什么含义、正常 vs 该警觉。与附录 A(on-wire 字节真相)互为正反面:附录 A 是"帧里有什么",本附录是"报告里那行从哪来"。

### 解析总流程(从 .asc 到报告)

```
.asc 每行 → 取 CAN ID + payload 数据
   ├─ debugInfo 路径:只收 FL(0x200/1) / FR(0x202/3) 的 64B 帧
   │    → 解 6 字节公共头,用 msgIndex 选 hot/det 半张
   │    → CRC16 校验(覆盖 byte0–61)+ schema 版本校验
   │    → 按 rollingCounter 把 hot+det 配成"一个周期快照"
   │    → 全程聚合 → print_summary 打出聚合值 → VERDICT 判读
   └─ CAN 负载路径:按 TX DBC + 点云 ID 扫描 FL/FR 实际发送报文
        → 统计 frames、payload bytes、duration → frames/s、KB/s、bus load
```

**四种聚合方式**(报告里反复出现):

| 方式 | 含义 | 用在哪些字段 |
|---|---|---|
| **峰值锁存 max-hold** | 整段取最大 | 耗时/CPU负载/overrun/tec/busOff/TX rate… |
| **派生 derived** | 固件不发,脚本算 | `margin`、`est. bus load` |
| **并集/集合** | 故障位按位或;状态收集所有出现值 | `faultSummary`、`sensorState`、`timeSyncState` |
| **首→尾 / min** | 计数器记首末帧;栈取最小剩余 | `frameStart/resultCount`、`stack free min` |

### 逐字段(按报告自上而下)

| 报告行/字段 | 来源(帧@偏移) | 聚合 | 含义 / 正常 · 该警觉 |
|---|---|---|---|
| 标题 `summary — FL (0x200/0x201)` | 按 CAN ID 分流 | — | FL=0x200/1,FR=0x202/3 |
| `frames` / `cycles` / `duration` | 计数 / 行首时间戳 | — | cycles≈frames/2≈duration÷0.066;差很多=中段断流 |
| `sensorState` | 头 byte4[3:0] | 集合 | 该跑应 `STARTED`;停在 `OPENED`=没启动信号链 |
| `timeSyncState` | 头 byte4[7:4] | 集合 | `SYNCED` 正常;`SILENT_WAIT`=无主节点(台架常见);`SYNC_LOST`=丢同步 |
| `uptime` | det@30 (u16 秒) | max | 持续涨;max≪duration=中途复位过 |
| `resetCause` | det@50 | 最后值 | `POWER_ON` 正常 |
| `warmResetCause` | det@51 | 最后值 | `MSS_WDT`/`HSM_WDT`=被看门狗复位(挂死过,重点查) |
| `frameStart A->B` | hot@30 (u32) | 首→尾 | 每帧 RANGE_START 自增 |
| `resultCount C->D` | hot@34 (u32) | 首→尾 | 与 frameStart **一起涨且接近**;start 涨 result 停=DSP/DPM 挂 |
| `timing CM4/DOA/postproc/total` | hot@6/8/10/16 (u16,0.1ms) | max | ⚠️ **墙钟含抢占,只当趋势**;`total`<660(66ms) |
| `overrun max` | hot@20 (u16) | max | 超 66ms 预算的累计次数,>0=有帧超时 |
| `framePeriodMaxDev max` | hot@28 (u16,0.1ms) | max | 帧周期抖动,个位数正常 |
| `CPU R5 avg/peak` | hot@12/13 (u8 %) | max | **真 CPU 时间**(run-time stats,免抢占);avg=累计均值(抗 71min 回绕),peak=0.5s 窗口尖峰 |
| `CPU rsp/canout` | hot@14/15 (u8 %) | max | rsp=算法(DOA+感知);canout≈0(发送走 FIFO 硬件,不吃 R5) |
| `tec` / `rec` | det@47 / @48 (u8) | max | CAN 发/收错误计数;tec 爬升=没ACK,>127=error-passive |
| `busOffEver` | det@20 (u16) | max | bus-off 次数 |
| `txStall` | det@22 (u16) | max | TX FIFO 满等待(背压) |
| `CEL` | det@26 (u16) | max | 硬件错误日志;以上全 0=总线健康 |
| `CAN-A TX rate (ASC measured)` | ASC + TX DBC + 点云 ID | 全段统计 | `.asc` 输入时的首选口径:按 FL/FR TX CAN ID 实测 frames/s、KB/s;若无匹配则显示 `debugInfo peak` 并回退到 det@28/@53 |
| `est. bus load (this radar)` | **派生** | — | `fps×78us + KB/s×1024×4us`→占空比;来源随上一行标注为 `DBC TX ids + point cloud` 或 `firmware-reported radar TX` |
| `TimeSync crcErr/invalid/jump` | det@10/12/14 (u16) | max | 同步帧 CRC错/非法/时间跳变;全 0 干净 |
| `blackbox record` | det@52 (bbRecValid) | 或 | `YES`=本上电周期命中过 assert(`--full` 看 `bbLine`+`bbFileHash`) |
| `assertLive max` | det@38 (u16) | max | 本次运行 assert 命中数 |
| `lastErrorCode` | det@40 (i32) | 最后非零 | ≠0=某模块返回过错误码 |
| `stack free min` | det@56–61 (u8×16B) | **min** | 各任务最坏剩余;某项 **<~256B=快溢出**;`0xFF`=未注册 |
| `integrity CRC err` | byte62 校验 | 计数 | >0=误码或固件↔脚本 schema 没同步 |
| `integrity schema err` | byte0[7:4]≠4 | 计数 | >0=固件/脚本版本没对上(偏移可能全错) |
| `integrity rolling gaps` | byte1 不连续 | 计数 | 丢周期;仅 t≈0 一次=开场假象(`--skip` 滤) |
| `integrity missing hot/det` | 周期内缺半张 | 计数 | 某周期只收到 0x200 或 0x201 |

### VERDICT 判读逻辑

故障位(头 byte2-3,整段**并集**)分两类后给结论:
- **`FAULT_BENCH`**(`CAN_ERR`/`CAN_TX_STALL`/`SYNC_LOST`/`VEHICLE_TIMEOUT`)→ 台架/环境事,标 `[bench]`。
- 其余故障位 + CRC错 + schema错 → 固件/系统问题,标 `[!]`。

| 情况 | 结论 |
|---|---|
| 无 `[!]` 无 `[bench]` | `OK` |
| 只有 `[bench]` | `OK (firmware) - only bench/environment faults` |
| 有任何 `[!]` | `NEEDS ATTENTION`(逐条列出 + 提示) |

> 多雷达录制时,每台各出一份本报告 + VERDICT。CAN 负载优先使用 ASC/DBC 实测口径,末尾追加 `ASC measured CAN-A bus load` 表和 TOTAL;若没有 debugInfo 帧,仍可只输出 CAN 负载表。

---

## 附录 E:打包成独立 exe(免 Python 分发)

**目的**:对外(客户/产线/同事)分发解析工具时,**不交付 `.py` 源码**,只给一个免安装的 `.exe`,把 `.asc` 拖进去就出报告。

**工具**:[PyInstaller](https://pyinstaller.org)(把解释器 + 脚本 + 依赖打进单个 exe)。本脚本是**纯标准库**,无第三方依赖,`--onefile` 可干净打包。

### 一键打包

仓库已带脚本 **`tools/build_debuginfo_exe.bat`**,改完 `debuginfo_parser.py` 后双击它即可重出 exe。它执行的核心命令是:

```bat
:: 一次性安装(只需一次)
python -m pip install pyinstaller

:: 打包(build_debuginfo_exe.bat 里就是这条)
python -m PyInstaller --onefile --console --name debuginfo_parser ^
    --distpath dist --workpath build_tmp --specpath build_tmp ^
    --add-data "%DBC_FILE%;mss\dbc" ^
    --noconfirm debuginfo_parser.py
```

| 选项 | 作用 |
|---|---|
| `--onefile` | 打成**单个** exe(而非一堆 dll + exe 的文件夹) |
| `--console` | 保留控制台窗口(报告要打印在窗口里) |
| `--name` | 输出名 `debuginfo_parser.exe` |
| `--distpath dist` | exe 输出到 `tools/dist/` |
| `--workpath/--specpath build_tmp` | 临时产物集中到 `build_tmp/`(脚本结尾 `rmdir` 删掉,保持 tools/ 干净) |
| `--add-data "%DBC_FILE%;mss\\dbc"` | 把 TX DBC 一起打进 onefile exe;否则 exe 解压到临时目录后找不到默认 DBC,只能统计内置点云 ID |

产物:`tools/dist/debuginfo_parser.exe`(约 9–10 MB,已内置 TX DBC)。连同 `dist/使用说明.txt` 一起发即可。

### exe 的"拖拽即用"是怎么做到的

`debuginfo_parser.py` 的 `main()` / `__main__` 里有**仅在打包后(`sys.frozen`)才生效**的三段逻辑(跑 `.py` 开发时完全不触发):

1. **拖拽 / 命令行带文件**:文件路径作为 `argv[1]` 进来,正常解析。
2. **双击(无参数)**:`input()` 提示"拖入 .asc 文件后回车,或输入路径",把路径补进 `argv`。
3. **默认出体检报告**:打包版若没显式加 `--full`,自动等价 `--summary`(终端用户要的就是结论)。
4. **跑完不闪退**:`__main__` 的 `finally` 里 `input("按回车键退出...")` 让控制台窗口停住。

### ⚠️ 注意事项(必读)

- **exe ≠ 加密源码**:PyInstaller 只是把字节码打包进去,**懂逆向的人能解出 `.pyc` 再反编译**回接近源码。它能挡住普通用户(不交付明文 `.py`),但**不是强 IP 保护**。需要更强防逆向请用 **Nuitka**(编译成 C 再生成 exe,逆向难度高得多)或商业混淆器(PyArmor 等)。
- **平台绑定**:打出来的是 **64 位 Windows** exe,Linux/Mac/32 位跑不了;在哪个平台打包就只能在哪个平台跑。
- **杀软误报**:单文件 exe 的引导器**偶尔被杀软误报**(打包器通病),加信任放行即可。
- **不建议提交进 git**:9–10 MB 二进制随源码每次变都变,体积大;建议 `tools/dist/` 加进 `.gitignore`,需要时用 `build_debuginfo_exe.bat` 现场重打。
- **Python 版本**:在 Python 3.14 + PyInstaller 6.21 上验证通过;换很新的 Python 时,PyInstaller 可能需同步升级才支持。
