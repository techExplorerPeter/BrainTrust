# systemInfo / dumptrace 设计笔记 (schema v1, R5F) — 最终版

> 跨复位的 **R5F 崩溃黑匣子**:CPU 异常(未定义指令 / 预取中止 / 数据中止=越界·野指针)发生时,把现场抓进 flash,**下次上电**经 CAN-FD systemInfo ID 播出上次崩溃:FL=`0x100`(head)+`0x104`(regs),FR=`0x101`(head)+`0x105`(regs)。用 `tools/sysinfo_parser.py` 反查到**函数·源码行·变量**。
>
> **状态:已在 AWR2x44P EVM 上多次实测通过**(三种故障注入 C3 01/02/03 全部:捕获→落 flash→自动冷复位→R5 systemInfo 播报→脚本定位)。

与 `0x200/0x201 debugInfo`(本上电周期实时遥测)互补:debugInfo 看"现在健不健康",systemInfo 回答"**上次为什么挂了、挂在哪**"。

---

## 0. 快速入门(TL;DR)

**平时**:什么都不用做。雷达开机后短时间 burst 播几对 R5 systemInfo(FL=`0x100/0x104`,FR=`0x101/0x105`);`valid=0` 表示历史干净,`valid=1` 表示上次有崩溃记录。

**怀疑崩溃过 / 要读上次崩溃**:
1. 用 CANoe / Kvaser 录几秒总线,存成 `.asc`。
2. 在 `mmw_ddm/tools/` 下跑:
   ```
   python sysinfo_parser.py 你的录制.asc
   ```
   (需 `R5F_CLANG_INSTALL_PATH` 指向 ti-arm-clang;脚本默认用 `mmw_ddm/awr2x44P_mmw_demo_mssDDM.xer5f` 反查符号。)
3. 看输出:`FAULT:` 哪类故障、`faulting PC` 哪个函数/源码行、`DFAR/IFAR` 哪个地址/变量、`aging:` 还差几个周期自动清除。

**主动自检(确认功能在工作)**:往 **CAN-A 标准帧 id `0xC3`**(`WF_SYS_INJECT_CAN_ID`,落在 MCAN 接受窗 0xC0–0xC4 内)发一帧,`data[0]`:
- `0x01` = data abort、`0x02` = prefetch abort、`0x03` = undefined instruction。
- 雷达会**故意崩溃 → 自动冷复位**,重启后 R5 systemInfo 播报该次记录。

**修好后清除**(像 UDS Clear DTC):同一个 `0xC3` 发 `data[0]=0xCC` → 记录立即擦除,R5 systemInfo 回到 `valid=0`。
> 不手动清也行:连续 `WF_SYSINFO_RETENTION_CYCLES`(默认 3)个无新故障的上电周期后自动擦。

**量产出货前**:`mss/wf_sysinfo.h` 把 `WF_SYSINFO_FAULT_INJECT` 改成 `0`(关闭 0xC3 注入,防误触发;清除 0xCC 不受影响)。

---

## 0.5 设计原理(核心思想)

**要解决的问题三连**(都是这颗芯片 + 实车的硬约束):
1. 实车**没有调试器**——崩溃了没人能接 J-Link 看,唯一出口是 CAN。
2. 这颗芯片**只有冷复位(POR,RAM 物理清零)**——崩溃现场不能"存 RAM 等下次上电再看",一掉电就没了。
3. SDK 默认的异常处理器是 **`while(1)` 死循环**——崩了就卡死,什么都不留,连"崩过"都不知道。

**核心思想(一句话)**:在异常发生的那一瞬间,把 CPU 寄存器现场抓进 RAM;再由一个**仍然存活的任务**把现场持久化到 **flash** 并触发**冷复位**自愈;**下次上电**把记录经 **CAN** 播出,离线用 **ELF 符号表**反查到源码行/变量。

```
崩溃瞬间          →   下次上电           →   离线
[异常向量抓现场]      [CAN systemInfo 播报]  [脚本 + .xer5f 反查]
   ↓(RAM)              ↑(flash 读)            函数/行/变量
[任务落 flash+复位] → [boot 读 flash] ──────────┘
```

**三个用踩坑换来的关键设计决策**(细节见 §3):
- **A. 异常里只"抓 + 置标志",持久化交给真任务**:flash 写和 PMIC 复位都依赖调度器在跑,不能在 abort 上下文做。
- **B. 向量表/处理器必须是纯 ARM 汇编**:C 的 `naked` 函数符号会带 Thumb 位,导致 CPU 用错指令态进入 → 长期写不进记录的真凶。
- **C. 擦/写分离 + 每页一 tick + 单槽**:迁就 NOR flash"擦慢、只能 1→0、同页不能重复 program"的物理特性。

---

## 1. 出发点与硬约束

- 本芯片**只有 PMIC 冷复位(=POR,RAM 物理清零)**,没有保 RAM 的热复位 → 崩溃记录**必须在故障当下落 flash**,不能靠"存 RAM、下次上电再写"。
- 量产实车**无调试器**;唯一通道是 CAN 报文。
- SDK 默认的 R5 异常处理器(undef/prefetch/data-abort)只是 `while(1)` **死循环**,什么都不留。

## 2. 总体数据流(最终)

```
①【故障·异常向量】我们自己的 _vectors(纯 ARM 汇编)→ wf_sys_<type>_handler
     置 gWfSysFtype、按类型修正异常 LR → wf_sys_capture_common
     抓 R0-R12 / 任务态 SP·LR(stm ^)/ 故障 PC / SPSR 进 gWfSysFaultRegs
②【故障·仍在 abort 模式】切到专用栈 → bl wf_sys_write_crash()
     读 CP15 DFSR/IFSR/DFAR/IFAR,在 RAM 里组好整条记录 gWfSysPendingRec(+CRC16)
     —— 注意:这一步【绝不碰 flash、不复位】
③【故障·返回】capture_common 置 gWfSysCrashPending=1,改写异常返回到
     wf_sys_crash_park(用原 SPSR → SYS 模式、开中断、空转),让调度器继续跑
④【flush 任务(prio 5,开机常驻)】轮询到 gWfSysCrashPending:
     Flash_eraseBlk(整块) → Flash_write(slot0, gWfSysPendingRec) → vTaskDelay(50ms)
     → BSW_SocRest()(实测可用的 PMIC 冷复位,不返回)
⑤【下次上电·boot】wf_sysinfo_init():读 slot0 → 追加一条 boot-tick → 老化判断 → 建发送任务
⑥【下次上电·发送任务(prio 2)】把记录打成 R5 systemInfo 两帧(head+regs),**上电初期 burst 发送**
⑦【离线】sysinfo_parser.py 解析 + 用 .xer5f 反查函数/行/变量
```

## 3. 关键修复:为什么是"置标志 + flush 任务",而不是在异常里直接写

这是整个功能的**核心教训**,踩过两个大坑:

**坑 1 —— 不能在 abort 模式 / 被劫持的任务上下文里写 flash 或复位。**
`Flash_eraseBlk` / `Flash_write` 内部用**计数忙等**轮询 NOR 的 WIP(写完成),这个忙等**只有调度器在跑时才会正常结束**;在 abort 模式(无抢占)里它会提前超时,把芯片留在"擦了一半 / 写了一半"的状态 → 记录损坏。`BSW_SocRest`(PMIC 复位)是一长串 `ClockP_usleep`/MIBSPI/`DebugP_log`,每一步都 yield,**只有真正的 FreeRTOS 任务能跑完**;在 abort 模式里调它直接挂死。
→ **方案**:异常处理器只在 RAM 里组记录 + 置 `gWfSysCrashPending`,改写返回到 `wf_sys_crash_park`(SYS 态、开中断、空转)让调度器活着;一个 prio 5 的 **flush 任务**在干净的任务上下文里完成擦+写+复位。

**坑 2(THE bug,记录长期写不进的真因)—— 向量里的 handler 地址带了 Thumb 位。**
最早 handler 用 C 的 `__attribute__((naked, target("arm")))` 写。即便代码是 ARM,**符号也会被标成 THUMB**,于是向量表里 `.word handler` 的最低位=1。CPU 取到奇地址 → 以 **Thumb 态**进入一段 **ARM 字节** → 执行垃圾 → 不停重故障,handler 实际**从没正确跑过**(表现为:flash 块被擦了却没有记录)。
→ **方案**:把向量表 + 所有 handler 写成**文件作用域的纯 ARM `__asm__` 块**,显式 `.arm` + `.type <sym>, %function`,符号被标成 ARM,向量字为偶 → 进入即 ARM 态。(用 `tiarmobjdump` 验证向量字为偶、handler 反汇编正常。)入口态必须 ARM,因为 `SCTLR.TE=0` 把异常入口态钉死为 ARM。

**坑 3 —— "读出即擦"会丢、且 NOR 不能重复 program 同一页。**
- 防丢失:崩溃后那次上电若没人录到 systemInfo 帧,擦了就永久丢 → 改为**每次上电初期 burst 重发**,并**靠上电计数老化**(见 §4),满 `RETENTION_CYCLES` 个无新故障的上电周期才擦。
- 上电计数 tick:NOR 一页(256B)**只有第一次 program 可靠**,重复 program 同一页的不同字不稳。所以**每次上电占一整页**(`WF_SYS_TICK_STRIDE=256`),tick 数才不会卡在 1、老化才会触发。

## 4. Flash 布局(`0x3F0000`,64KB,擦除粒度 64KB)— 单槽

| 区 | 偏移 | 内容 |
|---|---|---|
| 记录槽 | `0x0000`–`0x07FF` | **单槽实际只用 slot0**(512B,一条 `WFSysCrashRec_s`)。flush 任务每次崩溃**先擦整块再写 slot0**,所以"最新崩溃覆盖旧的"。`SLOT_COUNT=4` 仅作布局保留,slot1–3 永远空(boot 仍扫 4 槽,纯为健壮性 + slot0 诊断快照)。 |
| 上电计数 | `0x0800`–`0xFFFF` | append-only,**每次上电 program 一整页**(stride=256):把该页首字 `0xFFFFFFFF→0`;已 program 的页数 = 自上次擦除以来的上电次数(=当前 bootTick)。二分查找边界,无需每次擦。 |

**老化规则**(`wf_sysinfo_init` 第 3 步):
- `gWfSysTxValid && (bootTickNow − 最新记录.bootTick) ≥ RETENTION_CYCLES` → 擦(新故障刷新窗口)。
- 无有效记录且 tick 区将满 → 擦(housekeeping)。
- 无有效记录、recCount=0、但 slot0 magic 非 0xFF(残留垃圾)→ 擦。
- 注:记录是 flush 任务擦后才写的,所以记录里的 `bootTick=0`;擦动作把 tick 区也清零,老化窗口从复位后重新计。

## 5. 异常捕获(R5 / ARMv7-R)要点

- **自带 `_vectors`**(放 `.vectors`→`RESET_VECTORS` 0x0):undef/prefetch/data 指向我们的 `wf_sys_*_handler`,reset/svc/reserved/irq/fiq 仍指 SDK(`_c_int00`/`HwiP_*`)。`--undef_sym=_vectors` 由我们的表满足,SDK 那个纯 `_vectors` 对象不被拉入,无重定义冲突。不复用 SDK 的 `HwiP_*_abort` 名字(同归档冲突)。
- 进异常时 R0-R12 仍是故障现场;SP/LR 是 banked → `stm {sp,lr}^` 取任务态。**故障 PC 由异常 LR 按类型修正**:data `−8`、prefetch `−4`、undef ARM `−4` / Thumb `−2`(读 SPSR 的 T 位判定)。三种都已实测 PC 精确落在出错指令。
- **重入守卫** `gWfSysInFault`:写入途中再故障直接走复位,不死循环。
- 栈回溯只读 R5 数据 RAM(TCMB / MSS_L2)且字对齐(`wf_sys_readable64`),防野 SP 触发二次致命 abort。

## 6. CAN systemInfo 帧格式(2×64B=128B,CRC16-CCITT-FALSE 覆盖 byte 0..61)

| 雷达 | head 前 64B | regs 后 64B |
|---|---|---|
| FL | `0x100` | `0x104` |
| FR | `0x101` | `0x105` |

每个 R5 发送周期包含两帧:head 64B + regs 64B,合计 128B payload。head 和 regs 使用不同 CAN ID。当前 `WF_SYSINFO_TX_BURST_PAIRS=5`,所以上电 burst 共 5 对 / 10 帧 / 640B payload;收到 clear 后也 burst 5 对 clean 帧用于确认。

公共头(两帧 byte0..5):`0` schemaVer|msgIndex、`1` rolling、`2` valid(1=有记录)、`3` faultType、`4` recCount、`5` core。
- **head(msg0,payload@byte6)**:`+0` seq、`+4` bootTickFault、`+8` bootTickNow、`+12` PC、`+16` LR、`+20` SP、`+24` CPSR、`+28` DFSR、`+32` IFSR、`+36` DFAR、`+40` IFAR、`+44` dbgMagic、`+48` dbgCrcStored、`+50` dbgCrcCalc、`+52` retentionCycles。
- **regs(msg1)**:R0–R12。
- 16 字栈回溯只存 flash(128B 放不下);需要时用 CCS/J-Link 读 slot0。

## 7. 解析脚本 `tools/sysinfo_parser.py`

- 解析 `.asc`(CANFD `Rx <id>` 格式)/hex,按 CAN ID 分流 FL/FR R5 记录,把同一雷达的 head/regs 两个 ID 合并后校验 CRC/schema,每路取**最新**一对 head+regs。hex dump 没有 CAN ID,按旧行为当作 FL/head stream。
- **符号化**:`PC/LR` 经 `llvm-symbolizer` + `.xer5f` → 函数+源码行;`DFAR` 经 `llvm-nm` → 变量(+偏移);`DFSR/IFSR` 解码原因(对齐/权限/越界/外部 abort + 读写)。
- **不可解析地址不再吐 `??:0:0`**:符号化失败时给清晰中文/英文提示。尤其:
  - **预取中止**的 PC/IFAR 是**坏跳转目标**(无符号)→ IFAR 行明确指引"看 caller LR(调用点)"。
  - **叶子函数崩溃**时 LR 指向"上上层"(叶子不更新 LR,ARM 固有特性);**PC 永远准确**,定位以 PC 为准。
- 还输出 `flash slot0:`(magic/CRC 诊断)和 `aging:`(第几周期、还差几个干净周期自动清除)两行。
- 默认 ELF=`mmw_ddm/awr2x44P_mmw_demo_mssDDM.xer5f`,工具链=`$R5F_CLANG_INSTALL_PATH/bin`;`--elf`/`--toolchain` 可覆盖。无工具链时退化为原始地址+故障解码。
- 可用 `tools/build_systeminfo_exe.bat` 打包成 `tools/dist/sysinfo_parser.exe`。exe 内置当前 `awr2x44P_mmw_demo_mssDDM.xer5f`,适合同事电脑无 Python 的场景。
- exe 使用方式:双击打开后,先把 `.xer5f` 文件或其所在目录拖进窗口并按 Enter;也可直接按 Enter 使用 exe 内置 ELF。随后把 `.asc` 文件拖进窗口并按 Enter。解析结束后窗口会停在 `Press Enter to exit...`。命令行直接传参方式仍支持 `--elf` / `--toolchain`,不受该交互流程影响。
- 若固件重新编译导致 `.xer5f` 更新,必须重新运行 `build_systeminfo_exe.bat`;否则 exe 内置 ELF 仍是旧版本。符号化仍需要目标电脑能找到 `llvm-symbolizer/llvm-nm`(`R5F_CLANG_INSTALL_PATH` 或 PATH),否则只输出原始地址和 fault 解码。

```
python tools/sysinfo_parser.py capture.asc
# FAULT: data-abort on R5F (seq=1, 1 power-cycle(s) ago)
# faulting PC : 0x...  myFunc (src/foo.c:123)
# DFAR (addr) : 0x...  -> gMyArray+0x40
# DFSR        : 0x0D   permission fault (MPU) [write]
# aging: this fault is 1 power-cycle(s) old; auto-clears at 3 -> 2 clean cycle(s) left
```

## 8. 清除(像 UDS Clear DTC)+ 老化计数

- **手动清除**:故障定位并修复后,往 `WF_SYS_INJECT_CAN_ID=0xC3` 发一帧 `data[0]=WF_SYS_CLEAR_CODE=0xCC`。发送任务下个周期擦掉 systemInfo 块 → R5 systemInfo 报 `valid=0`(clean),不再回放旧故障。**此功能不受 FAULT_INJECT 开关影响,量产保留。**
- **自动老化**:即使不手动清,满 `WF_SYSINFO_RETENTION_CYCLES`(默认 3)个无新故障的上电周期后自动擦。
- R5 head 里带 `retentionCycles` + `bootTickNow`,脚本据此显示"第 N 次上电无异常 / 还差 M 个周期自动清除"。

## 9. 开关 / 参数(`mss/wf_sysinfo.h`)

| 宏 | 值 | 说明 |
|---|---|---|
| `WF_SYSINFO_ENABLE` | 1 | 置 0 → 整功能编译消失 |
| `WF_SYSINFO_FLASH_OFF` | 0x3F0000 | 64KB 自由块 |
| `WF_SYSINFO_RETENTION_CYCLES` | 3 | 自动老化的无故障上电周期数 |
| `WF_SYSINFO_TX_FIRST_MS` / `_PERIOD_MS` | 300 / 1000 | 首发 / burst 对间隔 |
| `WF_SYSINFO_TX_BURST_PAIRS` | 5 | 上电或 clear 后发送的 head+regs 对数 |
| `WF_SYS_CLEAR_CODE` | 0xCC | 清除指令(0xC3 帧 data[0]) |
| **`WF_SYSINFO_FAULT_INJECT`** | **0** | **当前关闭;自检时临时置 1,量产必须保持 0** |

## 10. 自检方法(CAN 触发崩溃,不用改代码)

`WF_SYSINFO_FAULT_INJECT=1` 时,往 **CAN-A `0xC3`** 发一帧,`data[0]`:
- `1` = data abort(写 `0xDEAD0000`)、`2` = prefetch abort(调用 `0xDEAD0000`)、`3` = undefined(`udf #0`)。
- `0xCC` = 清除(见 §8,不受注入开关限制)。

发送任务下个周期消费标志 → 在任务上下文故意崩溃 → 捕获→落 flash→自动复位 → 重启后 R5 systemInfo ID 播报 → 脚本定位。三种已实测:
- C3 01 → PC=`wf_sys_do_inject`、`DFAR=0xDEAD0000`、`DFSR=0x0D`、R9=注入值。
- C3 02 → IFSR=0x0D、IFAR=0xDEAD0000,LR→调用点。
- C3 03 → PC=`wf_sys_do_inject` 的 `udf` 那行,精确。

## 11. 台架验证状态

1. ✅ `_vectors` 覆盖生效且正常启动(系统健康、R5 systemInfo 在发)。
2. ✅ 数据中止 / 预取中止 / 未定义指令三类捕获 + CAN 注入触发。
3. ✅ 置标志 + flush 任务方案:abort 处理器改写返回 → SYS 任务态 park → flush 任务擦+写+复位。
4. ✅ 自动重启 + 下次上电 R5 systemInfo `valid=1` + 脚本定位到函数/行/变量。
5. ✅ 手动清除(0xCC)+ 自动老化(RETENTION_CYCLES)。

## 12. 已知缺陷与权衡(必读)

这套黑匣子是**尽力而为(best-effort)**的诊断,不是形式化可证的。以下缺陷按严重度排:

1. **【结构性·最重要】依赖调度器还活着。** 现场是在异常里抓进 RAM 的,但真正落 flash + 复位靠一个 prio-5 的 FreeRTOS 任务。如果崩溃**把调度器本身搞死了**(关中断死锁、踩坏 SysTick/PendSV、在不可恢复的临界区里炸),flush 任务永远不被调度 → **这次记录写不进 flash → 丢失**。能抓的是"任务态里的崩溃"(绝大多数业务 bug),抓不了"内核/中断态的彻底死机"。
   - *缓解方向*:加独立硬件看门狗(WDT)兜底复位 + 在异常里直接写一个最小标志到某个保留寄存器/RTC 域(若有);本期未做。

2. **【取舍】单槽,只留最近一次崩溃。** flush 任务每次擦整块再写 slot0,新崩溃覆盖旧的。连环不同崩溃只看得到最后一次。这是为了写入可靠性(NOR 同页不能重复 program)换来的简化。

3. **【取舍】崩溃 / 复位死循环的风险。** 若故障是确定性的、一上电就触发(比如初始化里就有野指针),会形成"崩溃→落flash→复位→又崩溃"的环,雷达起不来,且反复擦同一 64KB 块**加速 flash 磨损**。`gWfSysInFault` 只能防单次上电内的二次故障,**防不了跨复位的环**。
   - *缓解方向*:boot 时若发现"上电计数飙升但一直有新故障",进入安全模式不再自动复位;本期未做。

4. **定位精度依赖符号。** 数据中止能给 `DFAR`,但只有当它落在**全局符号**上才反查得出变量名;越界到**栈/堆/外设**地址只能给裸地址。预取/未定义的 PC 跳到野地址时无符号,要靠 `LR`;而**叶子函数**崩溃时 LR 还偏一层(ARM 不更新叶子的 LR)。

5. **CAN 上只有两层(PC + LR),完整调用栈要现场读 flash。** 16 字栈回溯只存 flash(128B 帧放不下),要完整 backtrace 得用 CCS/J-Link 读 slot0。

6. **记录里 `bootTick=0`(丢了"崩在第几个上电周期")。** flush 擦块时把 tick 区也清了,所以记录内不保留崩溃发生的绝对周期;老化窗口是复位后重新计的。单槽设计的取舍。

7. **只覆盖 R5。** M4(CM4)、DSS(C66x)的崩溃这套看不到(M4 无 QSPI 所有权,Phase 2 经共享内存交 R5 落盘)。

8. **依赖自定义 `_vectors` 覆盖 SDK 向量。** 若 SDK 升级改了向量机制,或别的模块也要覆盖向量,会冲突,需要重新核对 §5 的覆盖方式。

9. **CRC16(非加密),16 位有极低碰撞概率;`50ms` settle、flush `prio 5` 等是经验值**,极端负载下复位前的落盘可能被抢占延迟(实测足够)。

> 一句话总结:**它能抓住绝大多数"任务里崩了"的场景并精确定位;抓不住"把内核/中断彻底搞死"的硬死机。** 对后者,长期方案是叠加硬件 WDT。

## 13. 移植到其他工程的接入清单

systemInfo 不是单个源文件就能独立工作的功能。移植到另一个工程时,按下面四类一起搬,并逐项核对工程差异。

### 13.1 核心实现文件

| 文件 | 作用 |
|---|---|
| `mss/wf_sysinfo.h` | 功能开关、CAN ID、flash 布局、记录格式、fault 类型、clear/inject 命令、`wf_sysinfo_init()` 声明。 |
| `mss/wf_sysinfo.c` | 核心实现:自定义 `_vectors`、undef/prefetch/data abort 捕获、寄存器现场保存、flash 落盘、上电读回、CAN burst 发送、clear/inject 处理。 |

移植时重点确认:
- `WF_SYSINFO_FLASH_OFF` 必须是新工程确认空闲的 64KB flash block。
- `WF_SYSINFO_CAN_ID_FL_HEAD/FR_HEAD/FL_REGS/FR_REGS` 要和新项目 CAN Matrix 一致。
- `WF_SYSINFO_FAULT_INJECT` 量产保持 `0U`;只在台架自检时临时置 `1U`。

### 13.2 工程接入点

| 文件 | 必要改动 |
|---|---|
| `mss/mss_main.c` | `#include "wf_sysinfo.h"`;在 CAN-A 和 flash 初始化完成后调用 `wf_sysinfo_init()`。 |
| `mss/mss_mcan.c` | `#include "wf_sysinfo.h"`;`WF_CAN_TX_SERIALIZE` 要包含 `WF_SYSINFO_ENABLE`;在 CAN RX switch 里接入 `WF_SYS_INJECT_CAN_ID=0xC3` 的 clear/inject 命令。 |
| `mss/mmw_mss.mak` | 把 `wf_sysinfo.c` 加入 MSS 编译源文件列表。 |
| `mss/mmw_mss_linker.cmd` | 保留 `.wfSysCode` / `.wfSysData` 映射,让 `wf_sysinfo.oer5f` 的代码/数据/栈放到 R5 可用 RAM。 |

`wf_sysinfo.c` 还依赖这些外部符号/接口,新工程名字不一致时要适配:
- `mcanA_transfer_FIFO(uint32_t msgIdentifier, uint8_t *data, uint32_t size, uint32_t dlc)`。
- `BSW_SocRest()` 或等价的系统冷复位函数。
- `dir_flag` 以及 `FRONT_LEFT_RADAR` / `FRONT_RIGTH_RADAR` 等雷达位置宏。
- flash driver: `Flash_getHandle` / `Flash_read` / `Flash_write` / `Flash_eraseBlk` / `Flash_offsetToBlkPage`。
- FreeRTOS 静态任务接口: `xTaskCreateStatic`、`vTaskDelay`。

### 13.3 CAN 与离线解析

R5 systemInfo 的 CAN ID 映射:

| 雷达 | head 前 64B | regs 后 64B |
|---|---|---|
| FL | `0x100` | `0x104` |
| FR | `0x101` | `0x105` |

每次发送一对 head+regs,共 128B payload。当前上电 burst 为 `WF_SYSINFO_TX_BURST_PAIRS=5`,即 10 帧 / 640B payload;clear 后也 burst 5 对 clean 帧。

离线工具搬 `tools/sysinfo_parser.py`。如果新工程 ELF 名称或路径不同,运行时用:

```
python sysinfo_parser.py capture.asc --elf path/to/app.xer5f --toolchain path/to/ti-arm-clang
```

需要发给非开发同事时,同时搬 `tools/build_systeminfo_exe.bat`。在新工程确认 ELF 路径后运行该 bat,交付 `tools/dist/sysinfo_parser.exe`;同事可双击后先拖入 `.xer5f` 或其目录,再拖入 `.asc`,无需安装 Python。

### 13.4 移植后最小验证

1. 编译确认 `_vectors` 没有和 SDK 或其他模块重复定义。
2. 上电后抓 CAN,确认只 burst 出现 FL/FR 对应 ID,发完停止。
3. 发 `0xC3 data[0]=0xCC`,确认 flash 记录可清除,随后 burst clean 帧。
4. 台架自检时临时打开 `WF_SYSINFO_FAULT_INJECT=1`,分别测 `0xC3 01/02/03`,确认捕获→落 flash→冷复位→下次上电 CAN 播报→`sysinfo_parser.py` 定位。
5. 自检完成后把 `WF_SYSINFO_FAULT_INJECT` 恢复为 `0U`。

## 14. 后续 / 量产前

- **量产关闭注入**:`WF_SYSINFO_FAULT_INJECT=0`(本模块)。诊断字段(dbgMagic/dbgCrc)可保留(便于现场分析)或后续精简。
- M4(CM4)崩溃捕获:M4 无 QSPI 所有权 → 经共享内存交 R5 落 flash(Phase 2)。
- 可选:16 字栈回溯走第 3 帧或单独诊断会话传出。
- WDT→PMIC 自动恢复联动(与 debugInfo 待办合并)。
