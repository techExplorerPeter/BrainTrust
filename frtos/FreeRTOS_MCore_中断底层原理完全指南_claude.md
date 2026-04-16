# FreeRTOS × Cortex-M 中断底层原理完全指南

> 基于第一性原理，从物理硬件到操作系统，完整建立认知体系 版本：已勘误版（修正 PSP/MSP 错误描述 & xSemaphoreTakeFromISR 误判）

------

## 目录

1. [第零层：物理约束——为什么需要这一切](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#第零层)
2. [第一层：硬件机制——Cortex-M 如何处理中断](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#第一层)
3. [第二层：FreeRTOS 的额外保存——完整上下文切换](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#第二层)
4. [第三层：临界区——MAX_SYSCALL 存在的根本原因](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#第三层)
5. [第四层：ISR API 设计哲学——FromISR 系列的本质](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#第四层)
6. [专家级问题：ISR 里能调用哪些 API？](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#专家级问题一)
7. [专家级问题：在 ISR 里直接调用 taskYIELD() 为何危险？（已勘误）](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#专家级问题二)
8. [全景总结：四层金字塔认知图](https://claude.ai/chat/477298d0-320a-4b56-a03d-e899a0a57589#全景总结)

------

<a name="第零层"></a>

## 第零层：物理约束——为什么需要这一切

CPU 是一台**严格顺序执行**的机器。它在同一时刻只能做一件事。
 "并发"和"中断"本质上是对这个顺序执行约束的破坏。

一旦破坏，所有跨越"破坏边界"的数据结构都可能处于**不一致的中间态**。
 这是一切问题的物理根源。

链表的插入/删除在汇编层面需要 3～5 条指令：

```
读指针（LDR）→ 改指针（运算）→ 写指针（STR）
```

在这几条指令执行的微秒间隙里，如果有中断打入并同样操作该链表：

```
T1: 内核读取链表头指针（存在寄存器里）
T2: [中断来了，中断也改了头指针，写回内存]
T3: 内核把 T1 时读到的旧指针写回内存 → 覆盖了中断的修改
结果: 链表损坏，内核崩溃
```

**操作系统的任何 ISR 限制，根本上都是为了解决这一个问题。**

------

<a name="第一层"></a>

## 第一层：硬件机制——Cortex-M 如何处理中断

### 1.1 两个栈指针：MSP 与 PSP

Cortex-M 提供两个栈指针：

| 栈指针 | 全称                  | 使用场景                                           |
| ------ | --------------------- | -------------------------------------------------- |
| MSP    | Main Stack Pointer    | 启动阶段、Handler Mode（所有 ISR）、无 RTOS 的裸机 |
| PSP    | Process Stack Pointer | FreeRTOS 任务运行时的 Thread Mode                  |

FreeRTOS 启动后，每个任务在 Thread Mode 下使用 PSP；
 一旦进入中断（Handler Mode），CPU 自动切换使用 MSP。

### 1.2 【核心】异常帧压入哪个栈？

这是最容易被误解的地方，必须清楚：

> **硬件将异常帧压入的是"被中断时正在使用的那个栈"，而不是永远压入 MSP。**

| 被中断时的状态                     | 使用中的栈 | 异常帧压入哪里    |
| ---------------------------------- | ---------- | ----------------- |
| Thread Mode + PSP（FreeRTOS 任务） | PSP        | **PSP（任务栈）** |
| Thread Mode + MSP（裸机/启动阶段） | MSP        | MSP               |
| Handler Mode（ISR 嵌套）           | MSP        | MSP               |

**FreeRTOS 任务被中断时的正确流程：**

```
任务运行 (Thread Mode, 使用 PSP)
         │
         │ ← 外部中断触发
         ▼
硬件自动动作：
  1. 将 {xPSR, PC, LR, R12, R3, R2, R1, R0} 压入 PSP（任务栈）
  2. CPU 切换到 Handler Mode，改用 MSP
  3. LR = EXC_RETURN = 0xFFFFFFFD
     （含义："我从 Thread Mode + PSP 来的，退出时请恢复 PSP"）
         │
         ▼
ISR 执行 (Handler Mode, 使用 MSP)
         │
         │ ISR 退出，执行 BX LR（LR = 0xFFFFFFFD）
         ▼
硬件自动动作：
  从 PSP 弹出 {xPSR, PC, LR, R12, R3, R2, R1, R0}
         │
         ▼
任务继续运行 (Thread Mode, PSP)
```

**结论：** PSP（任务栈）全程保管着任务的上下文，MSP 只是 ISR 执行时的临时"工作台"。
 异常帧从不会"孤零零地躺在 MSP 里"——这个说法是错误的。

### 1.3 EXC_RETURN：硬件知道如何回家

LR 在异常入口被设置为特殊的 EXC_RETURN 值，告诉 CPU 退出时去哪里：

| EXC_RETURN 值 | 含义                                                  |
| ------------- | ----------------------------------------------------- |
| `0xFFFFFFF1`  | 返回 Handler Mode，使用 MSP（ISR 嵌套）               |
| `0xFFFFFFF9`  | 返回 Thread Mode，使用 MSP                            |
| `0xFFFFFFFD`  | 返回 Thread Mode，使用 PSP（FreeRTOS 任务的正常路径） |

### 1.4 BASEPRI：FreeRTOS 临界区的硬件基础

Cortex-M 提供 BASEPRI 寄存器，用于选择性屏蔽中断：

```
BASEPRI = N → 屏蔽 数值 ≥ N 的中断（即紧迫度低于 N 的中断）
BASEPRI = 0 → 不屏蔽任何中断（关闭屏蔽）
```

**注意方向：** 在 ARM Cortex-M 中，优先级数值越小，紧迫度越高（0 是最高优先级）。
 所以 BASEPRI = 0x50，屏蔽的是数值 ≥ 0x50 的中断（即"不那么紧急"的中断），
 而数值 < 0x50 的高优先级中断（更紧急）不受影响，依然可以打断。

------

<a name="第二层"></a>

## 第二层：FreeRTOS 的额外保存——完整上下文切换

### 2.1 为什么硬件保存的 8 个寄存器不够？

硬件自动保存的是"调用者保存寄存器"（Caller-saved），共 8 个：
 `{R0, R1, R2, R3, R12, LR, PC, xPSR}`

但 C 函数还会使用"被调用者保存寄存器"（Callee-saved）：
 `{R4, R5, R6, R7, R8, R9, R10, R11}`

FreeRTOS 的 PendSV Handler 负责手动保存这 8 个，合并到 PSP（任务栈）中。

### 2.2 PendSV 上下文切换汇编全流程

```asm
PendSV_Handler:
    ; ── 第一步：屏蔽中断，进入临界区 ──
    mov  r0, #configMAX_SYSCALL_INTERRUPT_PRIORITY
    msr  basepri, r0
    dsb
    isb

    ; ── 第二步：保存当前任务上下文（R4-R11）到 PSP ──
    mrs  r0, psp              ; 读取当前任务的 PSP（硬件已把 R0-R3/R12/LR/PC/xPSR 压好了）
    isb
    ldr  r3, =pxCurrentTCB   ; 取当前任务 TCB 指针
    ldr  r2, [r3]

    stmdb r0!, {r4-r11}      ; 将 R4-R11 也压入 PSP（任务栈）
    str   r0, [r2]           ; 将更新后的 PSP 保存到 TCB->pxTopOfStack

    ; ── 第三步：调用调度器，决定下一个任务 ──
    stmdb sp!, {r3, r14}     ; 保存 TCB 指针和 EXC_RETURN 到 MSP（内核栈）
    bl    vTaskSwitchContext  ; 更新 pxCurrentTCB 指向下一个任务
    ldmia sp!, {r3, r14}     ; 从 MSP 恢复

    ; ── 第四步：恢复新任务上下文（R4-R11）从 PSP ──
    ldr  r1, [r3]            ; 新任务的 TCB
    ldr  r0, [r1]            ; 新任务的 pxTopOfStack（即新任务的 PSP）
    ldmia r0!, {r4-r11}      ; 从新任务栈恢复 R4-R11
    msr  psp, r0             ; 更新 PSP 指向新任务栈（剩余 8 个寄存器由硬件弹出）
    isb

    ; ── 第五步：开中断，退出 ──
    mov  r0, #0
    msr  basepri, r0
    bx   r14                 ; 使用 EXC_RETURN(0xFFFFFFFD)退出
                              ; 硬件自动从 PSP 弹出 {R0-R3,R12,LR,PC,xPSR}，新任务开始运行
```

### 2.3 完整的任务栈布局（切换时）

```
PSP 高地址
  ┌─────────────────┐
  │    xPSR         │  ← 硬件自动压入（异常进入时）
  │    PC           │
  │    LR (R14)     │
  │    R12          │
  │    R3           │
  │    R2           │
  │    R1           │
  │    R0           │
  ├─────────────────┤
  │    R11          │  ← FreeRTOS PendSV 手动压入
  │    R10          │
  │    R9           │
  │    R8           │
  │    R7           │
  │    R6           │
  │    R5           │
  │    R4           │
  └─────────────────┘  ← TCB->pxTopOfStack 指向这里
PSP 低地址（栈向下增长）
```

**完整的任务上下文 = 硬件自动的 8 个 + FreeRTOS 手动的 8 个 = 16 个寄存器，全部在 PSP（任务栈）里。**

------

<a name="第三层"></a>

## 第三层：临界区——MAX_SYSCALL 存在的根本原因

### 3.1 configMAX_SYSCALL_INTERRUPT_PRIORITY 是什么

这个宏定义了 FreeRTOS 可管辖的最高中断优先级（数值最小的那个）。
 它划定了一条"防火墙"：

```
优先级 0（最高/最紧急）  ──┐
优先级 1                   │  【禁区】：高于 MAX_SYSCALL
优先级 2                   │  FreeRTOS 无法屏蔽这些中断
优先级 3                   │  只能在这里做极简的硬件操作
优先级 4（= MAX_SYSCALL）  ─┤  ← 防火墙
────────────────────────────┤
优先级 5                   │  【可管辖区】：低于 MAX_SYSCALL
优先级 6                   │  FreeRTOS 可屏蔽这些中断（临界区有效）
...                        │  可以安全调用 FromISR 系列 API
优先级 15（最低）          ──┘
```

### 3.2 BASEPRI 如何实现这道防火墙

```c
// FreeRTOS 进入临界区时：
__set_BASEPRI(configMAX_SYSCALL_INTERRUPT_PRIORITY);
// → 数值 ≥ MAX_SYSCALL 的中断被屏蔽（较低优先级）
// → 数值 < MAX_SYSCALL 的中断（极高优先级）依然可以打断！

// FreeRTOS 退出临界区时：
__set_BASEPRI(0);
// → 恢复所有中断
```

### 3.3 为什么高于 MAX_SYSCALL 的中断不能调用 FreeRTOS API？

因为这类中断不受临界区保护：

```
内核正在修改就绪链表（以为中断已屏蔽）
         │
         │  ← 高于 MAX_SYSCALL 的中断来了！临界区无法拦截它
         ▼
该中断的 ISR 也去操作链表
         │
         ▼
链表指针被二次修改 → 内核数据结构损坏 → HardFault
```

### 3.4 configASSERT 的防护层

FreeRTOS 内部的 `FromISR` API 通常有这样的断言：

```c
// 伪代码，实际源码位于 port.c
configASSERT( ucCurrentPriority >= ucMaxSysCallPriority );
//           ↑ 当前中断优先级（数值）≥ MAX_SYSCALL（数值）
//           即：当前中断的紧迫度 ≤ MAX_SYSCALL（处于可管辖区），才能调用 API
```

如果你的中断优先级高于 MAX_SYSCALL（数值更小）而强行调用 API：

- 调试构建（configASSERT 开启）→ 断言失败 → HardFault
- 发布构建（configASSERT 关闭）→ 临界区失效 → 链表损坏 → 随机崩溃

------

<a name="第四层"></a>

## 第四层：ISR API 设计哲学——FromISR 系列的本质

### 4.1 ISR 为什么不能"等待"

ISR 是"无主体"的执行流：

- 它不属于任何任务
- 没有任务控制块（TCB）
- 没有"等待队列"可以把它挂起

如果代码试图让 ISR"阻塞等待"，就等于在问："请把一个不存在的任务挂起"——系统崩溃。

### 4.2 FromISR API 的三个核心原则

1. **绝不阻塞**：操作成功立即返回，操作失败也立即返回错误码（如 `errQUEUE_FULL`）
2. **不触发直接调度**：不会在 ISR 内部直接切换任务，只标记意图
3. **通过 pxHigherPriorityTaskWoken 延迟切换**：把调度决定交给 ISR 退出之后

### 4.3 pxHigherPriorityTaskWoken 的机制（第一性原理）

```c
void EXTI0_IRQHandler(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    // 发送数据到队列
    xQueueSendFromISR(xQueue, &data, &xHigherPriorityTaskWoken);
    // API 内部检查：唤醒的任务优先级 > 当前被中断任务的优先级？
    // 如果是：xHigherPriorityTaskWoken = pdTRUE

    // ISR 退出前：如果需要切换，挂起 PendSV
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
    // 等价于：if (xHigherPriorityTaskWoken) 设置 PendSV Pending 位
}
```

**为什么必须这样做，不能在 ISR 内直接切换？**

因为 ISR 进入时，硬件把任务的异常帧压到了 PSP 上，任务的现场还"挂在栈里"没有完整恢复。
 必须等 ISR 完整退出（硬件从 PSP 弹出寄存器，恢复任务现场）之后，
 PendSV 才能安全地操作 PSP，做完整的上下文切换。

```
ISR 设置 PendSV Pending 位
         │
         ▼
ISR 退出（BX LR）
         │
         ▼ 硬件从 PSP 弹出 {R0-R3, R12, LR, PC, xPSR}（任务现场完整恢复）
         │
         ▼
PendSV 触发（尾链 Tail-Chain 或正常触发）
         │
         ▼ PendSV 保存 R4-R11 → 选下一个任务 → 恢复新任务
         │
         ▼
高优先级任务开始运行 ✅
```

------

<a name="专家级问题一"></a>

## 专家级问题一：ISR 里能调用哪些 API？

### 🚫 绝对禁止（会死机）

| API                                  | 原因                                                         |
| ------------------------------------ | ------------------------------------------------------------ |
| `vTaskDelay()` / `vTaskDelayUntil()` | 试图让不存在的"ISR 任务"休眠，直接崩溃                       |
| `xQueueSend()` / `xQueueReceive()`   | 队列满/空时会阻塞，ISR 无法阻塞                              |
| `xSemaphoreTake()`                   | 获取失败会阻塞                                               |
| `xEventGroupWaitBits()`              | 涉及等待，必然阻塞                                           |
| `pvPortMalloc()` / `vPortFree()`     | heap_4/heap_5 使用临界区保护，在高优先级 ISR 里调用可能导致临界区失效，内存链表损坏 |

### ✅ 安全可用（专为 ISR 设计）

| API                        | 用途                                                      |
| -------------------------- | --------------------------------------------------------- |
| `xQueueSendFromISR()`      | 向队列发送，失败立即返回                                  |
| `xQueueReceiveFromISR()`   | 从队列接收（适合生产者在任务侧的场景）                    |
| `xSemaphoreGiveFromISR()`  | 给出信号量（最常用，通知任务"事件发生了"）                |
| `xSemaphoreTakeFromISR()`  | 获取信号量（非阻塞，失败立即返回，FreeRTOS 有提供此 API） |
| `vTaskNotifyGiveFromISR()` | 最快的中断通知方式，直接操作任务 TCB，比队列快            |
| `xTaskNotifyFromISR()`     | 带数值的任务通知（可携带 32-bit 数据）                    |
| `xTimerStartFromISR()`     | 向定时器服务任务的命令队列发指令                          |

> **【勘误说明】**
>  网络上部分资料（包括本文勘误前的版本）称 FreeRTOS "不提供 `xSemaphoreTakeFromISR()`"，
>  这是不正确的。FreeRTOS 的 `semphr.h` 中确实定义了此函数，
>  适用于需要在 ISR 中非阻塞地检查并获取 binary/counting semaphore 的场景。

### ⚡ 性能对比：三种中断通知方式

```
性能（快→慢）：任务通知 > 信号量 > 队列

任务通知（xTaskNotifyFromISR）：
  → 直接操作目标任务的 TCB 内置字段
  → 无需额外内核对象，无动态分配
  → 限制：只能一对一通知（一个目标任务）

信号量（xSemaphoreGiveFromISR）：
  → 操作信号量内部的计数/队列结构
  → 可以多个 ISR 都去 Give 同一个信号量
  → 适合多生产者场景

队列（xQueueSendFromISR）：
  → 可携带数据（信号量只是有/无，不带数据）
  → 开销最大，但功能最完整
```

------

<a name="专家级问题二"></a>

## 专家级问题二：在 ISR 里直接调用 taskYIELD() 为何危险？（已勘误）

### ❌ 错误的解释（网络常见误区）

> "在中断里调用 taskYIELD() 会炸，是因为硬件把异常帧压到了 MSP，
>  而 PendSV 只操作 PSP，导致 PSP/MSP 错位，旧任务的 R0-R3 和 PC 遗弃在 MSP 中……"

**这个解释是错的。** 前提就错了：
 FreeRTOS 任务使用 PSP，被中断时硬件把异常帧压到 **PSP**，不是 MSP。
 "遗弃在 MSP 中"的情况根本不会发生。

### ✅ 正确的分析

**在 Cortex-M 标准 FreeRTOS 移植中，`taskYIELD()` 的实现是：**

```c
#define portYIELD() {
    SCB->ICSR = portNVIC_PENDSVSET_BIT;  // 设置 PendSV Pending 位
    __dsb(portSY_FULL_READ_WRITE);
    __isb(portSY_FULL_READ_WRITE);
}
#define taskYIELD() portYIELD()
```

**PendSV 的优先级是所有异常中最低的。**
 因此，在 ISR 中调用 `taskYIELD()` 设置 PendSV Pending 后：

1. PendSV 不会打断当前 ISR（因为 ISR 优先级更高）
2. 等 ISR 正常退出后，硬件从 PSP 弹出异常帧（任务现场完整恢复）
3. PendSV 触发（尾链或正常触发）
4. PendSV 的 PSP 是完整的，上下文切换正常进行

**在纯硬件层面，这实际上不会立刻炸机。**

**那为什么还说"不能在 ISR 里调 taskYIELD()"？真正的危险是：**

#### 危险一：configASSERT 断言失败（调试构建必炸）

FreeRTOS 内部在很多关键路径有 `configASSERT` 检查：

```c
// 通过读取 IPSR 寄存器判断当前是否在 ISR 上下文
configASSERT( ( portNVIC_INT_CTRL_REG & 0xFF ) == 0 );
// 如果 IPSR != 0（即在 ISR 里），断言失败 → HardFault
```

在调试构建下，一旦从 ISR 调用不允许的函数，会立刻 HardFault。
 这保护了你在开发阶段就发现问题。

#### 危险二：丢失 pxHigherPriorityTaskWoken 机制（逻辑错误）

`taskYIELD()` 不接受 `pxHigherPriorityTaskWoken` 参数，
 它无法区分"是否真的有更高优先级的任务需要运行"，
 要么多余切换（浪费时间），要么在某些移植下不触发需要的切换。

#### 危险三：移植性与规范问题

`portYIELD_FROM_ISR()` 在某些非 Cortex-M 移植（如 Xtensa / RISC-V 端口）上
 实现方式与 `portYIELD()` 完全不同。在这些平台上，从 ISR 调用 `taskYIELD()` 可能真的炸机。

### 正确做法

```c
void My_IRQHandler(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    // 做你的 ISR 逻辑，使用 FromISR API
    xSemaphoreGiveFromISR(xSemaphore, &xHigherPriorityTaskWoken);

    // ISR 退出前，根据是否需要切换决定是否挂起 PendSV
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
    // 等价于：if (xHigherPriorityTaskWoken == pdTRUE) portYIELD();
}
```

**口诀：** 在中断里，只要看到函数名不带 `FromISR`，就千万别调；
 只要涉及"等"（Delay / Take / Wait），就千万别做。

------

<a name="全景总结"></a>

## 全景总结：四层金字塔认知图

```
┌─────────────────────────────────────────────────────────┐
│  L1：现象层                                              │
│  HardFault / 死锁 / 随机崩溃                             │
│  → 中断优先级高于 MAX_SYSCALL 强行调 API                  │
│  → 或 configASSERT 在调试构建中拦截错误调用               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  L2：架构层（Cortex-M 硬件）                              │
│  • BASEPRI 寄存器：选择性屏蔽"数值 ≥ N"的中断            │
│  • PSP / MSP 双栈：任务用 PSP，ISR 用 MSP               │
│  • 异常帧压入 PSP（不是 MSP），硬件自动保存 8 个寄存器     │
│  • EXC_RETURN (0xFFFFFFFD)：硬件知道如何回到 PSP         │
│  • PendSV 最低优先级：保证 ISR 退出后才做上下文切换        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  L3：系统层（FreeRTOS 设计）                              │
│  • MAX_SYSCALL 防火墙：划定可管辖的中断优先级边界          │
│  • PendSV Handler：手动保存 R4-R11 到 PSP，完成切换       │
│  • FromISR API：不阻塞 + 延迟调度 + pxHigherPriorityTaskWoken │
│  • configASSERT：运行时检查 IPSR，防止错误调用            │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  L4：理论层（并发理论 + 数字电路）                         │
│  • 临界区必须原子化：任何多指令操作在并发下必须加保护        │
│  • 屏蔽中断是最高级别的"锁"                               │
│  • "数字越小优先级越高"：ARM 硬件比较器设计选择             │
│  • 权衡（Trade-off）：数据一致性 vs 硬实时响应             │
└─────────────────────────────────────────────────────────┘
```

### 一句话终极总结

> FreeRTOS 的 ISR 限制，本质上是操作系统为了在"非原子性的物理硬件"上实现"并发安全"，
>  以 `configMAX_SYSCALL_INTERRUPT_PRIORITY` 为防火墙，
>  以 BASEPRI 为武器，以 PSP/MSP 双栈为载体，以 PendSV 为延迟切换机制，
>  在"数据一致性"与"硬实时响应"之间精确划定的工程边界。

------

## 附录：常见配置检查清单

```
□ configMAX_SYSCALL_INTERRUPT_PRIORITY 已设置（不为 0）
□ 所有调用 FromISR API 的中断，其优先级 ≤ MAX_SYSCALL（数值上 ≥）
□ 极高优先级中断（< MAX_SYSCALL 数值）的 ISR 不调用任何 FreeRTOS API
□ 所有 FromISR 调用结束后，检查 xHigherPriorityTaskWoken 并调用 portYIELD_FROM_ISR
□ 调试构建下 configASSERT 已启用（用于开发阶段捕捉错误）
□ 未在 ISR 中调用 pvPortMalloc / vPortFree（尤其是 heap_4/heap_5 配置下）
□ 使用 configCHECK_FOR_STACK_OVERFLOW = 2 开启运行时栈溢出检查
```