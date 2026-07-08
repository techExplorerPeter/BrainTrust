# AI XDS110 Radar Debug Workflow

本文档用于指导 Codex、Claude Code 或其他 AI agent 通过 TI XDS110 获取 AWR2E44LC 雷达现场状态。

目标是：attach 正在运行的雷达固件，只加载 ELF/OUT 符号，不重新下载程序，不 reset，不 restart，并按需读取 R5 或 M4 的寄存器、RAM、全局变量和 memory-mapped register。

## 1. 总体架构

AI agent 不直接控制 XDS110。正确调用链如下：

```text
Codex / Claude Code
  -> PowerShell wrapper: tools/ti_debug.ps1
  -> TI DSS JavaScript: tools/ti_debug_dss.js
  -> D:\ti\ccs1281\ccs\ccs_base\scripting\bin\dss.bat
  -> CCS Debug Server
  -> XDS110
  -> AWR2E44LC R5 / M4
```

PowerShell 只负责提供稳定 CLI、参数校验和 JSON 输出。

DSS JavaScript 负责真正的 JTAG debug 操作。

Python 不是必须的。Windows 环境下推荐使用 PowerShell wrapper 调用 DSS。若后续需要跨平台或更复杂的编排，可以再用 Python 包装 PowerShell/DSS，但不要绕过 TI DSS 直接访问 XDS110。

## 2. 必备文件

需要准备以下文件：

```text
target/awr2e44lc_xds110.ccxml
out/r5_app.out
out/m4_app.out
tools/ti_debug.ps1
tools/ti_debug_dss.js
```

说明：

- `awr2e44lc_xds110.ccxml` 是 CCS Target Configuration，必须配置为 XDS110 + AWR2E44LC 对应 target。
- `r5_app.out` 是当前雷达实际运行的 R5 固件对应 ELF/OUT，版本必须匹配现场固件。
- `m4_app.out` 是当前雷达实际运行的 M4 固件对应 ELF/OUT，版本必须匹配现场固件。
- `ti_debug.ps1` 是 AI agent 调用入口。
- `ti_debug_dss.js` 是 DSS 实现，不建议 AI agent 直接调用。

本机 CCS DSS 路径：

```powershell
D:\ti\ccs1281\ccs\ccs_base\scripting\bin\dss.bat
```

## 3. 安全边界

AI agent 必须遵守以下规则：

允许：

- `target.connect(true)`
- `symbol.load(outFile)`
- `memory.readData(...)`
- `memory.readRegister(...)`
- `symbol.getAddress(...)`
- `target.halt()`，但只能在用户显式要求 `-Halt` 或 `snapshot` 时使用
- `target.disconnect()`

禁止：

- `memory.loadProgram(...)`
- `target.reset()`
- `target.restart()`
- flash erase/program
- 默认 halt 所有 core
- 默认 attach 所有 core
- 默认写寄存器或写内存
- 未经用户明确同意设置 breakpoint

默认策略：

- 只 attach 用户指定的 core。
- 默认不 halt。
- 默认只读。
- 默认只加载 symbols，不加载程序到目标内存。
- 每个命令结束后 disconnect。

## 4. 推荐 CLI 设计

AI agent 只调用 `tools/ti_debug.ps1`。

### 4.1 列出 CPU path

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 list-cpus `
  -Ccxml .\target\awr2e44lc_xds110.ccxml
```

用途：

- 第一次接入硬件时运行。
- 输出 `.ccxml` 里可 attach 的 CPU path。
- 用于确认 R5 和 M4 的真实 session 名称。

### 4.2 读取 core 寄存器

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 read-regs `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Regs PC,SP,LR,R0,R1,R2,R3 `
  -Halt
```

注意：

- 读取 `PC/SP/LR` 等核心寄存器通常需要 halt 才可靠。
- 如果用户要求完全不暂停现场，不要加 `-Halt`，但读取结果可能失败或不可靠。

### 4.3 读取 RAM 地址

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 read-mem `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Address 0x10200000 `
  -Width 32 `
  -Count 16
```

说明：

- `-Width` 可为 `8`、`16`、`32`。
- `-Count` 是读取 word 数，不一定是 byte 数。
- 默认 no-halt，适合低侵入读取 RAM、共享内存、状态结构体、memory-mapped register。

### 4.4 读取符号地址对应的数据

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 read-symbol `
  -Core M4 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\m4_app.out `
  -Symbol gRadarState `
  -Width 32 `
  -Count 8
```

内部行为：

```text
attach M4
symbol.load(m4_app.out)
symbol.getAddress("gRadarState")
memory.readData(DATA, address, 32, 8, false)
disconnect
```

### 4.5 现场快照

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 snapshot `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Halt
```

用途：

- 需要看当前 PC、SP、LR、关键寄存器、关键全局变量时使用。
- 该命令会暂停指定 core。
- 只暂停指定 core，不要默认暂停 R5 和 M4 两个 core。

## 5. JSON 输出规范

所有命令必须输出 JSON 到 stdout。AI agent 只解析 JSON。

成功示例：

```json
{
  "ok": true,
  "operation": "read-mem",
  "core": "R5",
  "cpuPath": "Texas Instruments XDS110 USB Debug Probe/Cortex_R5_0",
  "halted": false,
  "address": "0x10200000",
  "width": 32,
  "count": 4,
  "data": [
    "0x00000001",
    "0x00000002",
    "0x00000003",
    "0x00000004"
  ]
}
```

失败示例：

```json
{
  "ok": false,
  "operation": "read-symbol",
  "core": "M4",
  "error": "symbol not found: gRadarState",
  "availableCpus": [
    "Texas Instruments XDS110 USB Debug Probe/Cortex_R5_0",
    "Texas Instruments XDS110 USB Debug Probe/Cortex_M4_0"
  ]
}
```

## 6. DSS JavaScript 核心逻辑

DSS 侧必须使用 `symbol.load()`，不得使用 `memory.loadProgram()`。

正确：

```javascript
debugServer.setConfig(ccxml);
var session = debugServer.openSession(cpuPath);
session.target.connect(true);
session.symbol.load(elfPath);
```

错误：

```javascript
session.memory.loadProgram(elfPath);
```

读取 memory：

```javascript
var values = session.memory.readData(Memory.Page.DATA, address, width, count, false);
```

读取 register：

```javascript
var pc = session.memory.readRegister("PC");
var sp = session.memory.readRegister("SP");
var lr = session.memory.readRegister("LR");
```

读取 symbol：

```javascript
var address = session.symbol.getAddress(symbolName);
var values = session.memory.readData(Memory.Page.DATA, address, width, count, false);
```

列出 CPU path：

```javascript
debugServer.setConfig(ccxml);
var cpus = debugServer.getListOfCPUs();
```

## 7. Core 选择规则

AI agent 必须显式指定 core：

```powershell
-Core R5
```

或：

```powershell
-Core M4
```

不要使用：

```javascript
debugServer.openSession(".*")
```

推荐匹配逻辑：

```text
R5 -> /R5|R5F|Cortex_R5/i
M4 -> /M4|Cortex_M4/i
```

如果匹配到多个 CPU，命令必须失败并输出候选 CPU path，让用户指定更精确的名称。

## 8. Agent 决策规则

当用户说“看 R5 当前状态”：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 snapshot `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Halt
```

当用户说“不要暂停现场，只看某个全局变量”：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 read-symbol `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Symbol gRadarState `
  -Width 32 `
  -Count 8
```

当用户说“读某个地址”：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 read-mem `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Address 0x10200000 `
  -Width 32 `
  -Count 16
```

当用户说“先看看能连哪些核”：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 list-cpus `
  -Ccxml .\target\awr2e44lc_xds110.ccxml
```

## 9. AI Agent System Prompt 可直接使用

可把下面内容加入 Codex 或 Claude Code 的项目说明：

```text
You are allowed to inspect the running AWR2E44LC radar target through XDS110 only by invoking tools/ti_debug.ps1.

Do not invoke TI DSS directly unless modifying or debugging the wrapper itself.

Never use memory.loadProgram, target.reset, target.restart, flash erase, flash program, or broad openSession(".*") for live target inspection.

Default to no-halt reads. Use -Halt only when the user explicitly asks for a CPU snapshot, PC/SP/LR, call stack, current source line, or local variables.

Only attach the requested core. Use -Core R5 for R5 and -Core M4 for M4. Do not attach both unless the user explicitly asks for both.

All tool output is JSON. Parse stdout JSON and summarize the meaningful values for the user.

For low-intrusion inspection, prefer read-symbol or read-mem.
For core execution state, use snapshot -Halt on the requested core.
If CPU matching is ambiguous, run list-cpus and ask the user to select the exact CPU path.
```

## 10. 常见问题

### 10.1 能不能 attach 正在运行的雷达？

可以，前提是 JTAG 没有被锁，XDS110 连接正常，`.ccxml` 正确。

### 10.2 attach 会不会改变代码？

单纯 `target.connect(true)` 和 `symbol.load(outFile)` 不会把 ELF/OUT 写入目标 RAM/Flash。

### 10.3 为什么不能用 loadProgram？

`memory.loadProgram(outFile)` 会把程序装载到目标，可能覆盖现场。现场调试必须用 `symbol.load(outFile)`。

### 10.4 不 halt 能读什么？

通常可以读 RAM、全局变量地址、共享内存、memory-mapped register。运行中数据可能变化，因此结果是瞬时值，不一定一致。

### 10.5 什么时候必须 halt？

读取 PC/SP/LR、call stack、当前源代码位置、局部变量时，通常需要 halt。halt 会暂停指定 core，可能影响实时雷达流程。

### 10.6 读外设寄存器怎么做？

按 memory-mapped address 用 `read-mem` 读取：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ti_debug.ps1 read-mem `
  -Core R5 `
  -Ccxml .\target\awr2e44lc_xds110.ccxml `
  -Elf .\out\r5_app.out `
  -Address 0xFFFF0000 `
  -Width 32 `
  -Count 1
```

注意：部分外设寄存器读操作可能有副作用，读取前应确认 TRM/register description。

## 11. 最小可用实现计划

第一阶段：

1. 创建 `tools/ti_debug.ps1`。
2. 创建 `tools/ti_debug_dss.js`。
3. 实现 `list-cpus`。
4. 实现 `read-mem`。
5. 实现 `read-regs`。
6. 实现 `read-symbol`。
7. 所有命令输出 JSON。

第二阶段：

1. 增加 `snapshot`。
2. 增加可配置 symbol preset，例如 `radar_state`、`frame_stats`、`heap_stats`。
3. 增加读取 struct 的解析逻辑。
4. 增加日志保存，例如 `logs/debug_snapshot_YYYYMMDD_HHMMSS.json`。

第三阶段：

1. 做常驻 debug server，减少每次 attach 的开销。
2. 用 JSON-over-stdin/stdout 或 TCP 控制 DSS session。
3. 增加多步骤现场诊断流程。

MVP 建议使用一次命令一次 attach/read/disconnect。它速度慢一些，但状态简单、安全边界清楚，适合先交给 AI agent 使用。

