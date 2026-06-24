# 0x200 debugInfo 设计说明 (Design Note)

> 运行时调试报文 — 实车无调试器环境下的"飞行记录仪"
> 模块代码:`mss/wf_debug_info.c` / `mss/wf_debug_info.h`
> 作者:Peter Zhu ｜ 状态:设计/落地阶段(未上硬件验证)

---

## 1. 出发点:一个硬约束

实车上整机只有一条 CAN 总线,**接不了调试器**:看不到内存、看不到栈、打不了断点、释放版 `assert` 命中即静默死循环。出问题时几乎没有观测手段。

因此引入一条专用 CAN 报文(CAN ID `0x200`),固定 66ms 周期播出固件的"体检报告"。在总线上用 CANoe/CANalyzer 即可接收。**这条报文是实车上唯一的运行时观测窗口**,其设计质量直接决定故障可定位性。

---

## 2. 核心矛盾与解法:分页轮播

想监测的信号有几十项,而 CAN FD 单帧最大 64 字节(DLC=15),装不下。

**解法 = multiplexed 分页轮播**:帧首字节低 4 位作页号(`pageId`),每 66ms 发一页,4 页一轮。

```
t=0     Page0 (时序/超时)
t=66ms  Page1 (数据通路/RF)
t=132ms Page2 (TimeSync/CAN)
t=198ms Page3 (黑匣子/栈/复位)
t=264ms 回到 Page0 …
```

264ms 得到一张完整快照,而总线上只占一条周期报文,负载不变。

---

## 3. 五条设计原则(本设计的方法论核心)

把"实时状态"变成"可靠日志"的关键,也是它区别于普通打印 log 的本质:

| # | 原则 | 动机 | 代码体现 |
|---|---|---|---|
| ① | **粘滞位 (sticky)** | 两帧间隔 66ms,期间的瞬态故障若只报"此刻"会漏。故障位用"或累加",本上电周期内**只置不清** | `faultSummary \|= bit`,`wf_dbg_set_fault()` |
| ② | **峰值锁存 + 读后清零 (max-hold)** | 算法超时是偶发尖峰,平均值会抹平。各阶段耗时报窗口最大值,发出后清零 | `tMax[i]`;Page0 发完置 0 |
| ③ | **滚动计数器 + CRC** | rolling counter 每帧 +1,丢帧/阻塞可见;帧尾 CRC16 防误码 | `rollingCounter`、`wf_dbg_crc16()` |
| ④ | **公共头每页都带** | "一眼定生死"的信息每页都带,某页丢了也不瞎 | 每帧 Byte0–5 固定头 |
| ⑤ | **采集 / 发送解耦** | 采集点绝不阻塞发送;发送独立任务。即使 canoutput 挂死,本报文仍能发出并报告其失活 | 独立 `wf_debug_info_task` |

---

## 4. 架构与数据流

```
   算法流水线 (RspTask / DPM reportFxn)          独立发送任务 (66ms)
   ┌─────────────────────────────┐            ┌──────────────────────┐
   │ 单行"采集 API":             │            │ 1. eval 存活/健康     │
   │  wf_debug_mark_stage()      │  写全局     │ 2. 填公共头           │
   │  wf_debug_frame_snapshot()  │ ─────────► │ 3. 填当前页载荷        │
   │  wf_debug_task_alive()      │  gWfDbg    │ 4. 算 CRC             │
   │  wf_debug_mark_vehicle_rx() │            │ 5. 发 0x200,翻页      │
   └─────────────────────────────┘            └──────────────────────┘
        (短临界区,不阻塞)                       (HwiP 临界区读快照)
```

- **采集端**:散落各处的单行埋点,只更新全局结构 `gWfDbg`,极轻量。
- **发送端**:独立 FreeRTOS 任务 `wf_debug_info_task`(优先级 2,栈在 TCMB),66ms 醒一次打包发送。
- **并发**:采集与发送之间用 `HwiP_disable/restore`(关中断临界区)保证读写一致。所有对 `faultSummary` 的读-改-写、`framePeriodMaxDev` 的"读后清零"等都在临界区内对称保护。

---

## 5. 帧格式 (64 字节)

### 公共头 (Byte 0–5,每页相同)

```
[0]   schemaVer(高4位) | pageId(低4位)
[1]   rollingCounter            每帧 +1
[2-3] faultSummary              12 个粘滞故障位
[4]   sensorState(低4) | timeSyncState(高4)
[5]   taskAliveBitmap           各任务存活位
```

### 故障摘要位 `faultSummary`(`WF_DBG_FAULT_*`)

| bit | 含义 | bit | 含义 |
|---|---|---|---|
| 0 | 帧处理超 66ms 预算 | 6 | 周期任务失活 |
| 1 | 丢帧(trigger-result 差增大) | 7 | 某任务栈底剩余 < 阈值 |
| 2 | TimeSync SYNC_LOST | 8 | 黑匣子有上次死机记录 |
| 3 | CAN-A error passive / bus-off | 9 | 车身信息报文超时 |
| 4 | 前端过温 | 10 | 本周期 assert 命中过 |
| 5 | TimeSync DTC 锁存 | 11 | CAN-A TX FIFO 满等待 |

> **使用方式**:收报文第一眼只看这 2 字节,哪位亮了再去翻对应那一页看细节。

### 帧尾

```
[62-63] CRC-16/CCITT-FALSE (poly=0x1021, init=0xFFFF, 覆盖 Byte0..61)
```
与 TimeSync 0x040 帧同参数,可复用解析逻辑。

### 4 页载荷 (Byte 6–61)

| 页 | 主题 | 关键字段 | 回答的问题 |
|---|---|---|---|
| **Page0** | 时序/超时 | 各阶段耗时 max-hold ×6、tTotal、派生 margin、overrun 计数、`lastStage`、帧周期最大偏差 | 慢不慢?卡哪一段? |
| **Page1** | 数据通路/RF | frameTriggerReady、result 计数、cfar min/cur/max、航迹数、干扰数、waveId、温度 ×4、failedTimingReports、车身报文 age | 断流没?致盲没? |
| **Page2** | TimeSync/CAN | offsetUs、crc/invalid/jump 计数、DTC reason、CAN TEC/REC、bus-off 计数、TX 阻塞计数 | 同步/总线健康? |
| **Page3** | 黑匣子/资源 | 复位原因、warm 复位原因、bootCount、uptime、黑匣子(line+fileHash+count)、栈水位 ×8、lastErrorCode、sensorStart/Stop 计数 | 死过没?死在哪? |

---

## 6. 关键检测手法

1. **死字段改派生计算**
   TI 自带 `interFrameProcessingMargin` / CPU load 全工程无人填充(死字段)。改为派生:
   `margin = 660 − mssTimeRecord[5]`(单位 0.1ms,66ms = 660)。
   **教训:用一个字段前先确认它真被运行时填充。**

2. **`lastStage` 指认卡点**
   每个流水阶段(`wf_debug_mark_stage`)写一个枚举值。卡死时该字节冻结在最后到达的阶段,直接指认卡在 CM4 / DOA / 后处理哪一段。

3. **CAN 健康主动轮询**
   `MCAN_getErrCounters` 原本只在收到报文时读 —— bus-off 时根本收不到报文。改为在 66ms 任务里主动读 + `MCAN_getProtocolStatus()` 取 bus-off 标志(`wf_dbg_read_cana`)。

4. **任务存活位图**
   每个任务在主循环里 `wf_debug_task_alive()` 自增 tick,发送任务检查"tick 是否在涨"。某任务挂死但系统未崩时,这是唯一可观测手段。区分:周期性任务(canout/timesync,sensor 运行时含 rsp)才判死,事件驱动的 canrec 只进位图不判死。

5. **栈水位扫描**
   静态栈数组从栈底(数组首)向上数连续的 `0x00000000` / `0xA5A5A5A5` 字,首个非空字即用过的最深处,据此算剩余余量(`wf_dbg_scan_stacks`)。

---

## 7. 黑匣子(noinit 段技巧)

**问题**:release 下 `assert` 命中 = 死循环 → 雷达静默消失,无任何痕迹。

**手法**:
1. 链接脚本开一块 `.bss.wfNoInit (NOLOAD)` —— warm reset 不清零的 RAM。
2. 自定义 assert 钩子 `wf_debug_blackbox_assert(file, line)` 写入 **magic + 行号 + 文件名 hash + 计数**。
3. 复位重启后 `wf_debug_info_init()` 检查 magic 有效 → 判定上次为崩溃复位 → 通过 Page3 把"上次死在哪行"发出。

配合 **MSS 看门狗(WDT,待做)**:挂死 → WDT 复位 → 重启后 Page3 报 `SOC_WarmResetCause_MSS_WDT`,形成闭环。届时**不存在"永久静默且无痕"的故障模式**(唯一物理无解的是 bus-off 进行中的窗口,靠恢复后的粘滞计数补侦)。

> ⚠️ 前提:noinit RAM 真不被启动清零、SBL 不对 TCM 做 ECC 清零。**这是头号硬件验证项。**

---

## 8. 内存布局

MSS_L2 近满载且碎片化(详见仓库 CLAUDE.md),新增代码易触发 `GROUP_6` 链接错误。本模块按对象文件路由出 MSS_L2(`mss/mmw_mss_linker.cmd`):

| 段 | 去向 | 内容 |
|---|---|---|
| `.wfDbgCode` | TCMA_RAM | `wf_debug_info.oer5f` 的 `.text` / `.rodata` |
| `.wfDbgData` | TCMB_RAM | 其 `.data` / `.bss` |
| `.bss.wfNoInit (NOLOAD)` | TCMB_RAM | 黑匣子(跨 warm reset 保留) |
| `.bss.wfDbgStack` | TCMB_RAM | 发送任务栈 |

> `.bss.wfNoInit` / `.bss.wfDbgStack` 用 `wf_debug_info.oer5f(.bss.<name>)` 对象+精确段名限定,严格比 `.wfDbgData` 的 `.bss.*` 通配更具体,无论列序都优先认领,防止黑匣子被并入普通 bss 清零。
> 代码置 TCMA 距 MSS_L2 调用点 >32MB,链接器自动生成小 veneer(无害)。

---

## 9. 实战:如何用它定位问题

```
收到 0x200 → 看 faultSummary 哪位亮
  ├ bit0  超时     → 等 Page0,看哪段 max-hold 爆、margin 走低
  ├ bit1  丢帧     → 等 Page1,trigger 涨但 result 停 = DSP/DPM 挂
  ├ bit6  任务失活 → 看 aliveBitmap 哪个任务位灭
  ├ bit8  黑匣子   → 等 Page3,line + fileHash = 上次死在哪行
  ├ bit11 TX 阻塞  → CAN 背压/带宽不足
  └ rollingCounter 不连续 → 丢帧或总线阻塞
```

故障场景覆盖(设计推演):

| 场景 | 能否定位 | 路径 |
|---|---|---|
| DOA/后处理偶发超时尖峰 | ✅ | Page0 各阶段 max-hold |
| 持续过载帧堆积 | ✅ | margin 走低 + 超时计数涨 |
| DSP/DPM 挂死 | ✅ | trigger 涨 result 停 + RspTask alive 停 |
| CM4 卡某流水段 | ✅ | `lastStage` 冻结在卡点 |
| BSS 停止触发帧 | ✅ | trigger 停 + sensorState 仍 STARTED |
| 偶发整机重启 | ✅(补 WDT 后) | uptime 归零 + warm 复位原因 |
| CAN bus-off | ⚠️ 物理极限 | 期间发不出,恢复后粘滞 busOffEverCount 补侦 |
| 车身报文丢失 | ✅ | Page1 报文 age + 同步失败 |
| 时间同步异常 | ✅ | Page2 全套 |
| 致盲/检测异常 | ✅ | cfarNum/trcNum/intfNum 趋势 + 温度 |
| 栈溢出 | ✅ | Page3 栈水位 + 粘滞位 |
| assert 命中 | ✅(noinit 验证后) | Page3 黑匣子 |

---

## 10. 待办与硬件验证项

1. **黑匣子跨复位存活**(头号验证项):触发 assert → 复位 → 看 Page3 的 `line`/`fileHash` 是否保留。若被清零,改放 DSS_L3 共享 RAM 再试。
2. **MSS WDT 使能**(第④步):需改 syscfg,在 66ms 任务里喂狗,使"挂死→WDT 复位→Page3 报 MSS_WDT"闭环。建议黑匣子验证通过后单独做。
3. **基本收发验证**:CANoe 收四页轮播,rollingCounter 连续、CRC 对、各页数值与 CCS 调试观测一致。
4. **(可选)堆余量字段**:设计文档原列 Page3 含 `minEverFreeHeap`,当前实现未放;如关心堆耗尽可补 `xPortGetMinimumEverFreeHeapSize()/64B`。

---

## 附录 A:字节偏移表(解析权威 spec)

> 所有偏移为**帧内绝对字节**(0–63),小端。固件真相源是 `wf_debug_info.c` 的 `wf_dbg_build_pageN()`;**改固件 schema 时先改本表,解析脚本(`tools/debuginfo_parser.py`)照本表实现**。`schemaVer` 当前 = 1,字段变更需 +1。

### 公共头(每页 Byte 0–5 + 帧尾)

| 偏移 | 类型 | 字段 | 说明 |
|---|---|---|---|
| 0 | u8 | `schemaVer`(bit7:4) \| `pageId`(bit3:0) | ver=1 |
| 1 | u8 | `rollingCounter` | 每帧 +1,断续=丢帧 |
| 2 | u16 | `faultSummary` | 12 粘滞位,见下 |
| 4 | u8 | `sensorState`(bit3:0) \| `timeSyncState`(bit7:4) | 枚举值见 `mmw_mss.h`/`wf_time_sync.h` |
| 5 | u8 | `taskAliveBitmap` | bit0 RSP,1 CANOUT,2 CANREC,3 TIMESYNC,4 CTRL |
| 62 | u16 | `CRC16-CCITT-FALSE` | poly 0x1021,init 0xFFFF,覆盖 Byte 0–61 |

**`faultSummary` 位**:0 OVERRUN｜1 FRAME_DROP｜2 SYNC_LOST｜3 CAN_ERR｜4 OVER_TEMP｜5 DTC_ACTIVE｜6 TASK_DEAD｜7 STACK_LOW｜8 BLACKBOX｜9 VEHICLE_TIMEOUT｜10 ASSERT｜11 CAN_TX_STALL

### Page0 — 时序/超时(`pageId`=0)

| 偏移 | 类型 | 字段 |
|---|---|---|
| 6 | u16 | `tMax0` CM4 解调 max-hold (0.1ms) |
| 8 | u16 | `tMax1` DOA/DSP |
| 10 | u16 | `tMax2` 后处理 |
| 12 | u16 | `tMax3` CAN-TX |
| 14 | u16 | `tMax4` Enet-TX |
| 16 | u16 | `tMax5` 总耗时 |
| 18 | u16 | `tTotalCur` 当前帧总耗时 |
| 20 | **i16** | `marginMin` 余量最小值(=660−总耗时,负即超时) |
| 22 | u16 | `overrunCount` 超时累计 |
| 24 | u32 | `lastOverrunFrame` 上次超时帧号 |
| 28 | u8 | `lastStage` 最后到达阶段(卡死指认) |
| 29 | u8 | (保留) |
| 30 | u16 | `framePeriodCur` 帧周期实测 |
| 32 | u16 | `framePeriodMaxDev` 帧周期最大偏差 |
| 34 | u32 | `resultCount` 处理完成帧数 |

`lastStage` 枚举:1 RANGE_START｜2 DOPPLER_START｜3 CFAR_START｜4 DPC_RESULT｜5 DOA_DONE｜6 POSTPROC_DONE

### Page1 — 数据通路/RF(`pageId`=1)

| 偏移 | 类型 | 字段 |
|---|---|---|
| 6 | u32 | `frameTriggerReady`(低 32) BSS 触发计数 |
| 10 | u32 | `resultCount` 处理完成计数 |
| 14 | u16 | `cfarNumCur` 当前检测点数 |
| 16 | u16 | `cfarNumMin` 窗口最小 |
| 18 | u16 | `cfarNumMax` 窗口最大 |
| 20 | u16 | `trcNum` 航迹数 |
| 22 | u16 | `intfNumCur` 干扰数 |
| 24 | u16 | `waveIdCur` 波形 ID |
| 26 | i8 | `tmpRx0` (°C) |
| 27 | i8 | `tmpTx0` |
| 28 | i8 | `tmpPm` |
| 29 | i8 | `tmpDig0` |
| 30 | u8 | `tempValid`(1=温度有效) |
| 31 | u8 | (保留) |
| 32 | u16 | `failedTimingReports` |
| 34 | u16 | `calibrationReports` |
| 36 | u16 | `vehAgeMs` 车身报文距上次接收(ms,0xFFFF=从未) |
| 38 | u32 | `vehicleRxCount` |

### Page2 — TimeSync/CAN(`pageId`=2)

| 偏移 | 类型 | 字段 |
|---|---|---|
| 6 | i32 | `offsetUs` 时钟偏移 |
| 10 | u32 | `validFrameCount` |
| 14 | u16 | `crcErrorCount` |
| 16 | u16 | `invalidFrameCount` |
| 18 | u16 | `offsetJumpCount` |
| 20 | u8 | `dtcActive` |
| 21 | u8 | `dtcReason` |
| 22 | u8 | `lastSequenceCounter` |
| 23 | u8 | `tec` CAN-A 发送错误计数 |
| 24 | u8 | `rec` CAN-A 接收错误计数 |
| 25 | u8 | `canFlags` bit0 busOff,1 errPassive,2 warning |
| 26 | u16 | `busOffEverCount` |
| 28 | u16 | `canTxStallCount` |
| 30 | u16 | `dtcReportCount` |
| 32 | u32 | `canErrLogCnt` |

### Page3 — 黑匣子/资源(`pageId`=3)

| 偏移 | 类型 | 字段 |
|---|---|---|
| 6 | u8 | `resetCause` (`SOC_rcmGetResetCause`) |
| 7 | u8 | `warmResetCause` (`SOC_getWarmResetCause`) |
| 8 | u16 | `bootCount` |
| 10 | u32 | `uptimeMs` |
| 14 | u8 | `bbRecValid`(1=黑匣子有记录) |
| 15 | u8 | `bbFromPrevBoot`(1=记录来自上一次启动) |
| 16 | u16 | `bbLine` 死机行号 |
| 18 | u16 | `bbFileHash` 文件名 djb2 hash |
| 20 | u16 | `bbAssertCount` |
| 22 | 8×u8 | `stackFree16[0..7]` 各任务栈底剩余/16B(0xFF=未注册) |
| 30 | i32 | `lastErrorCode` |
| 34 | u8 | `sensorStartCount` |
| 35 | u8 | `sensorStopCount` |
| 36 | u16 | `assertCountLive` 本次运行 assert 计数 |

`stackFree16` 注册顺序:0 ctrl,1 rsp,2 canout,3 canrec,4 tsync,5 wfdbg(见 `mss_main.c` 注册序)。

---

## 附录 B:对外开关

`wf_debug_info.h` 顶部 `WF_DEBUG_INFO_ENABLE`:置 0 时所有采集 API 编译为空宏,量产可一键关闭。

---

## 附录 C:解析脚本

`tools/debuginfo_parser.py` —— 按附录 A 实现:4 页重组、粘滞位/状态解名、rollingCounter 连续性检查、CRC 校验、trigger/result 趋势告警。输入支持 CANoe `.asc`(经典/CANFD)与十六进制行,详见脚本头注释。
