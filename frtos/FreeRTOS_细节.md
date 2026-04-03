# FreeRTOS 调度器与 ARM Cortex-M 底层切换机制深度解析

## 一、 FreeRTOS 调度器时间片轮转切换的时机和条件

在 FreeRTOS 中，时间片轮转（Time Slicing）的机制非常严谨，它并不是在所有任务之间无差别地分配时间。它的核心运作逻辑只针对**当前系统中最高优先级且优先级相同**的就绪任务。

### 1. 核心条件 (The "If")
要触发时间片轮转，必须**同时满足**以下三个条件：
1. **宏定义使能：** `FreeRTOSConfig.h` 中的 `configUSE_PREEMPTION` 必须设为 `1`（抢占式调度开启），且 `configUSE_TIME_SLICING` 必须设为 `1`（默认情况下，只要开启抢占，时间片轮转自动开启）。
2. **状态与优先级：** 系统中必须有**两个或以上**的任务处于就绪态（Ready）。
3. **优先级平等且最高：** 这几个就绪任务的**优先级必须完全相同**，并且必须是当前系统中**最高的**优先级。如果有更高优先级的任务就绪，会直接发生抢占（Preemption）；如果是较低优先级的任务，则根本得不到执行机会。

### 2. 触发时机 (The "When")
时间片轮转的判断和触发，严格绑定在**系统时钟节拍（SysTick Interrupt）**的生命周期内。在底层的 ARM Cortex-M 架构实现中，完整的流转过程如下：
1. **SysTick 中断触发：** 硬件定时器产生中断，进入 SysTick 中断服务函数。
2. **内核 Tick 递增：** 调用 FreeRTOS 内核 API `xTaskIncrementTick()`。
3. **就绪列表检查：** 在该函数内部，内核会检查当前正在运行的任务（`pxCurrentTCB`）所在的优先级就绪列表长度。如果长度大于 1，标志位置位，触发任务切换请求 (Yield)。
```
// FreeRTOS 源码逻辑简述
#if ( ( configUSE_PREEMPTION == 1 ) && ( configUSE_TIME_SLICING == 1 ) )
{
    // 如果当前优先级的就绪列表中，任务数量大于 1
    if( listCURRENT_LIST_LENGTH( &( pxReadyTasksLists[ pxCurrentTCB->uxPriority ] ) ) > ( UBaseType_t ) 1 )
    {
        // 触发任务切换请求 (Yield)
        xYieldPending = pdTRUE;
    }
}
#endif
```
4. **挂起上下文切换：** 触发一个**最低优先级的软中断（PendSV）**。
5. **执行切换：** 当 SysTick 中断退出，且没有更高优先级的硬件中断时，处理器会进入 `PendSV_Handler` 进行真正的上下文切换。

> **易错细节：** 如果关闭时间片 (`configUSE_TIME_SLICING = 0`) 但保持抢占开启(`configUSE_PREEMPTION` 仍为 `1`)会怎样？
>
> 这时，如果有两个同为优先级 3 的任务 A 和 B 都处于 Ready 状态。一旦 A 开始运行，即使 SysTick 不断产生，**只要 A 自己不主动调用阻塞 API（如 `vTaskDelay`, `xQueueReceive`）或调用 `taskYIELD()`，任务 B 就永远得不到执行**。高优先级抢占依然有效，但同级之间的“平分秋色”就被打破了。

---

## 二、 为什么 PendSV 是最低优先级，却能完成任务切换？

在 ARM Cortex-M 和 FreeRTOS 的设计中，将 PendSV（可悬起系统调用）设置为**最低优先级**，是为了**保护系统不崩溃**而做出的极其精妙的设计。

### 1. 为什么必须是最低优先级？（防雷机制）
在 Cortex-M 架构中，处理器分为两种执行模式：

- **Thread Mode (线程模式):** 运行普通的用户任务（Task），通常使用 PSP（进程堆栈指针）。
- **Handler Mode (处理者模式):** 运行中断服务函数（ISR），强制使用 MSP（主堆栈指针）。

**假设我们将 PendSV 设为高优先级（甚至高于某些硬件中断），会发生以下灾难：**

1. **中断中的上下文切换（致命错误）：** 假设一个外设中断（如 UART 接收中断，优先级较高）正在执行。在这个 ISR 内部，你调用了 `xQueueSendFromISR()`，释放了一个信号量，唤醒了一个更高优先级的任务。
2. **强制抢占 ISR：** 如果 PendSV 优先级高于当前外设中断，PendSV 会**立刻**抢占当前的 UART ISR。
3. **栈空间错乱：** PendSV 的职责是保存当前任务的上下文，并恢复下一个任务的上下文。但是，此时 CPU 处于 Handler Mode，正在使用 MSP 处理硬件中断！如果 PendSV 强行去切换 PSP，或者试图把中断的执行上下文当成任务的上下文保存起来，系统的栈指针会瞬间彻底错乱，直接导致 `UsageFault` 或 `HardFault`。

**结论：** 任务切换（上下文切换）**绝对不能**在任何硬件中断活跃的时候发生。必须等所有硬件中断都处理完毕，CPU 即将回到 Thread Mode 时，才能进行任务切换。因此，PendSV 必须是最低优先级的中断。

### 2. 优先级最低，为什么还能成功切换？
这得益于 NVIC 的“悬起（Pend）”特性：
* **悬起延迟执行：** SysTick 或其他中断决定需要切换任务时，不会自己执行切换，而是向 ICSR 寄存器写 `1` 悬起 PendSV。

* **绝对的权限：** 尽管 PendSV 在所有中断中优先级最低，但它依然是一个**异常（Exception）**，其优先级永远高于普通的任务代码（Thread Mode）。
  当所有高优先级硬件中断执行完毕后，NVIC 发现 PendSV 还在排队，就会立刻执行它，绝对不会让 CPU 去执行旧任务代码。
```
  你可能会疑惑：“既然优先级最低，那它会不会一直被抢占，导致任务切不过去？”

  实际上，PendSV 依然能完美完成任务切换，这是由 NVIC（嵌套向量中断控制器）的硬件机制和“悬起（Pend）”特性共同保证的：

  #### A. “悬起（Pend）”机制的延迟执行

  当 SysTick（系统滴答定时器）或任何其他中断决定需要切换任务时，它们**不会自己去执行上下文切换**。它们只做一件事：向 NVIC 的中断控制和状态寄存器（ICSR）的特定位写 `1`，将 PendSV 中断**悬起（Pending）**。

  #### B. NVIC 的智能调度 (Tail-Chaining)

  将 PendSV 悬起后，只要当前还有其他高于 PendSV 优先级的中断在执行，PendSV 就必须“乖乖排队”。 当所有其他中断服务函数都执行完毕（即没有嵌套中断了），CPU 准备返回普通的 Thread Mode（执行任务代码）之前，NVIC 会发现：“还有一个 PendSV 处于悬起状态等着呢！”

  此时，ARM 架构会利用**咬尾中断（Tail-Chaining）**技术： CPU 不会先恢复旧任务的上下文再进入 PendSV，而是直接在 Handler Mode 之间穿梭，立刻进入 PendSV_Handler。

  #### C. 对比 Thread Mode，它依然是“王”

  虽然 PendSV 在所有**异常/中断**中优先级最低，但它依然是一个**异常（Exception）**。任何异常的优先级都高于普通的 Thread Mode（任务代码）。 因此，只要硬件级的中断退出了，PendSV 就一定会立刻执行，绝对不会让 CPU 去执行旧的任务代码。在 PendSV 中完成 PSP 的切换后，执行 `BX LR`（异常返回指令），CPU 就会顺理成章地跳入新任务的代码中。

  ### 总结运作流

  1. **产生切换需求：** SysTick 或外设 ISR 判断需要切换任务。
  2. **打个标记：** 悬起 PendSV（设置 ICSR 寄存器），然后该 ISR 继续执行完毕。
  3. **硬件让路：** 所有高优先级硬件中断全部执行完毕。
  4. **安全执行：** 轮到最低优先级的 PendSV 执行，它安全地交换 PSP（因为此时没有其他 ISR 在捣乱了）。
  5. **切换成功：** PendSV 退出，CPU 切回 Thread Mode，新任务开始运行。
```
---

## 三、 深入理解 Tail-Chaining 与上下文切换全过程

### 核心概念澄清
1. **PendSV 绝对不是任务，而是异常：** 它是 Cortex-M 向量表中的第 14 号异常，运行在 Handler Mode 下。
2. **栈指针的使用：** 当触发 Tail-Chaining 进入 `PendSV_Handler` 时，CPU 处于 Handler Mode，使用的是 **MSP**。但 PendSV 的核心使命是操作和修改 **PSP**。

### 动作拆解：从 SysTick 到 PendSV 的“偷天换日”

假设时间片到达，SysTick 打断任务 A，并准备切换到任务 B：

**第一步：打断前夜**
CPU 处于 **Thread Mode**，执行任务 A，堆栈指针使用 **PSP**。

**第二步：SysTick 触发与自动压栈**
SysTick 定时器产生硬件打断。ARM 硬件自动将任务 A 的 8 个核心寄存器（`R0-R3`, `R12`, `LR`, `PC`, `xPSR`）压入当前的 **PSP**（任务 A 的栈）。随后 CPU 切换到 **Handler Mode**，堆栈指针切换为 **MSP**，开始执行 `SysTick_Handler`。

**第三步：悬起 PendSV 与 Tail-Chaining 发生**
`SysTick_Handler` 判断需要切换任务，悬起 PendSV，然后准备 `BX LR` 退出。
此时，**咬尾中断 (Tail-Chaining)** 介入：
NVIC 发现后面紧跟着 PendSV。为了优化性能，CPU **直接跳过出栈和再次入栈的过程**。任务 A 的 8 个寄存器依然留在任务 A 的 PSP 里，CPU 保持在 **Handler Mode** 和 **MSP** 下，直接将 PC 指针跳入 `PendSV_Handler`。

**第四步：PendSV_Handler 执行（偷天换日）**
虽然 CPU 用着 MSP，但汇编编写的 PendSV 纯粹在操作 PSP：
1. **读取 PSP：** `MRS R0, PSP` 拿到任务 A 刚压入 8 个寄存器后的栈顶地址。
2. **手动存剩余寄存器：** 将 `R4-R11` 手动推入这个地址（任务 A 的栈）。
3. **冻结 TCB：** 将最终地址存入任务 A 的 TCB（任务控制块）。
4. **获取新任务：** 从任务 B 的 TCB 中读出它之前保存的 PSP 地址。
5. **手动恢复：** 从任务 B 的栈中手动弹出 `R4-R11`。
6. **更新物理 PSP：** `MSR PSP, R0`，将硬件 PSP 寄存器强行修改为**任务 B 的 PSP**。

**第五步：完美交接**
PendSV 执行异常返回（`BX LR`）。硬件自动从**当前的堆栈指针（已经被修改为任务 B 的 PSP）**中弹出 8 个核心寄存器（包含任务 B 的 PC 和状态）。
随着 PC 被赋值，CPU 退出 Handler Mode 切换回 Thread Mode，任务 B 顺利接班并开始运行。
```
为了让你深刻理解这个过程，我们把整个“SysTick 打断任务 A，并切换到任务 B”的动作放慢 10 倍，一步步看硬件和软件（PendSV）是如何配合执行“咬尾中断（Tail-Chaining）”的。

------

### 第一步：任务 A 正常运行 (打断前夜)

此时，CPU 处于 **Thread Mode（线程模式）**，正在执行任务 A 的代码。 此时 CPU 使用的堆栈指针是 **PSP**。任务 A 的局部变量、函数调用都在 PSP 指向的内存空间（也就是任务 A 自己的堆栈栈底）里。

### 第二步：SysTick 中断触发 (硬件自动压栈)

时间片到了，SysTick 定时器触发中断。这是一个硬件级别的打断。 ARM 硬件会**自动且强制**做两件事：

1. **自动压栈（Push）：** 硬件会自动把当前任务 A 的 8 个核心寄存器（`R0-R3`, `R12`, `LR`, `PC`, `xPSR`）压入当前的堆栈中。**注意：因为被打断时使用的是 PSP，所以这 8 个寄存器被压入了任务 A 的 PSP 中！**
2. **模式切换：** CPU 从 Thread Mode 切换到 **Handler Mode**，并且硬件自动将使用的堆栈指针切换为 **MSP**。 此时，SysTick_Handler 开始执行（跑在 MSP 上）。

### 第三步：悬起 PendSV 与“咬尾 (Tail-Chaining)”发生

在 SysTick_Handler 中，FreeRTOS 内核检查发现需要切换到任务 B，于是向 ICSR 寄存器写 `1`，悬起（Pend）了 PendSV。 然后，SysTick_Handler 执行完毕，准备执行 `BX LR` 退出中断。

**见证奇迹的 Tail-Chaining 来了：**

- **如果不咬尾（普通流程）：** CPU 会执行“出栈（Pop）”，把刚才压入任务 A PSP 的 8 个寄存器弹出来，恢复任务 A 的状态，回到 Thread Mode。然后因为 PendSV 在排队，CPU 瞬间又发生一次异常入栈（把这 8 个寄存器再次压入 PSP），再次进入 Handler Mode 执行 PendSV。这会浪费几十个时钟周期。
- **利用咬尾技术：** NVIC（中断控制器）极其聪明。它发现 SysTick 结束后紧接着还要处理 PendSV。于是，CPU **直接跳过出栈和再次入栈的过程**！
- **状态保持：** 任务 A 的 8 个寄存器依然安安静静地躺在任务 A 的 PSP 里。CPU 保持在 **Handler Mode**，继续使用 **MSP**，直接将 PC 指针跳转到 `PendSV_Handler` 函数的入口。

### 第四步：PendSV_Handler 执行 (偷天换日)

现在，我们在 PendSV 的中断服务函数里了。虽然当前 CPU 用的是 MSP（如果在这里定义局部变量，会消耗主堆栈），但 FreeRTOS 的 PendSV_Handler 是纯汇编写的，根本不用局部变量。 它的所有操作，都是针对那个被挂起的 **PSP** 展开的。

PendSV 执行以下“偷天换日”的操作：

1. **读取当前 PSP：** 通过 `MRS R0, PSP` 指令，把当前的 PSP 读到 R0 寄存器里（此时它指向任务 A 剩下的那一半上下文的保存位置）。
2. **手动保存剩余寄存器：** 硬件刚才只自动存了 8 个寄存器，PendSV 需要把剩下的 `R4-R11` 手动推入当前的 PSP 所在的内存中（也就是任务 A 的堆栈）。
3. **保存 TCB：** 把目前更新后的 PSP 地址，存进任务 A 的 TCB（任务控制块）中。任务 A 的状态被彻底冰封。
4. **读取新 TCB：** 找到任务 B 的 TCB，把任务 B 之前保存的 PSP 地址读出来。
5. **手动恢复新寄存器：** 从任务 B 的 PSP 内存区中，手动把任务 B 的 `R4-R11` 弹出来。
6. **更新物理 PSP：** 通过 `MSR PSP, R0` 指令，把 CPU 硬件的 PSP 寄存器，强行修改为任务 B 的 PSP！

### 第五步：异常返回 (完美交接)

PendSV 汇编代码的最后一句是异常返回指令（通常是 `BX LR`，此时 LR 中是一个特殊的 EXC_RETURN 值）。

当 CPU 执行异常返回时，硬件又会**自动且强制**做一件事：

- **自动出栈（Pop）：** 硬件会从**当前的堆栈指针**中弹出 8 个寄存器（`R0-R3`, `R12`, `LR`, `PC`, `xPSR`）。
- **关键点来了：** 因为在第四步的最后，PendSV 已经把物理 PSP 修改成了**任务 B 的 PSP**。所以，硬件现在弹出的是任务 B 之前被冻结的 PC（程序计数器）和状态！

随着 PC 被赋值为任务 B 的断点地址，CPU 自动退出 Handler Mode 返回 Thread Mode。任务 B 就这样自然而然地开始（或恢复）执行了。

------

**总结：** Tail-Chaining 是一种硬件级的“优化捷径”，它免去了 SysTick 和 PendSV 之间不必要的“状态恢复再状态保存”动作。在这个短暂的切换期，CPU 踩在 MSP 这个“脚手架”上执行 PendSV 异常，但 PendSV 的双手却在疯狂地搬运和替换代表任务灵魂的 PSP。替换完成，脚手架撤走，新任务顺利接班。
```