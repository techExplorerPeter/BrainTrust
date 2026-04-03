# FreeRTOS 精通指南

> 从硬件脉搏到任务协作的深度原理 — 结合设计哲学的全景知识图谱
> 基于 FreeRTOS V10.x 内核源码 · Cortex-M 架构

---

## 一、设计哲学：道法自然

FreeRTOS 的设计哲学可以用老子的"**道生一，一生二，二生三，三生万物**"来理解。整个系统从硬件的一个时钟脉冲出发，层层抽象，最终支撑起无穷的应用可能。它的核心信条是：**最小化内核，最大化确定性**。

### 1.1 四层架构

```
┌─────────────────────────────────────────────────────────┐
│  应用层 (Application)                                    │
│  你的任务代码 / 业务逻辑                                  │
│                                                          │
│  "三生万物"：应用层是'无限可能'的世界。                     │
│  内核给你确定性，你用它创造复杂系统。                       │
│  正如老子所言：'道常无为而无不为'                           │
│  ——内核不做业务，但让一切业务成为可能。                     │
├─────────────────────────────────────────────────────────┤
│  内核层 (Kernel)                                         │
│  tasks.c / queue.c / list.c / timers.c                  │
│                                                          │
│  "二生三"：内核是FreeRTOS的'心智'。                        │
│  它只做三件事——决定谁运行（调度）、如何通信（IPC）、         │
│  如何共享（同步）。简洁即力量，少即是多（Less is More）。    │
├─────────────────────────────────────────────────────────┤
│  移植层 (Port)                                           │
│  port.c / portmacro.h / portASM.s                       │
│                                                          │
│  "一生二"：移植层是FreeRTOS的'翻译官'，                    │
│  将抽象的OS概念翻译成具体芯片能理解的指令。                 │
│  它遵循'依赖倒置原则'                                     │
│  ——内核不依赖硬件，硬件适配内核。                          │
├─────────────────────────────────────────────────────────┤
│  硬件层 (Hardware)                                       │
│  SysTick / PendSV / NVIC / MSP·PSP                      │
│                                                          │
│  "道生一"：硬件提供最原始的时间脉搏（SysTick）              │
│  和切换机制（PendSV），如同心跳之于生命。                   │
│  没有这一层，一切调度都是空谈。                             │
└─────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

**确定性优先 (Determinism)**

RTOS 的存在意义不是"快"，而是"准时"。一个 100μs 完成但时间不确定的系统，不如一个始终 200μs 完成的系统。正如孔子说"不患寡而患不均"——不怕慢，怕的是不可预测。

**最小内核 (Minimalism)**

FreeRTOS 整个内核只有 5 个 `.c` 文件（tasks.c, queue.c, list.c, timers.c, event_groups.c）。这不是偷懒，而是刻意为之——每多一行代码就多一个 bug 的可能。"大道至简"是它的灵魂。

**零成本抽象 (Zero-cost Abstraction)**

宏替代函数调用，编译期配置替代运行时判断。你不用的功能不会产生任何开销——"你不为你不用的东西付费"（C++ 哲学的嵌入式版本）。

**可移植性 (Portability)**

内核与硬件通过 Port 层解耦。这是"依赖倒置原则"的完美实践：高层模块不依赖低层模块，两者都依赖抽象。

---

## 二、调度器：FreeRTOS 的"裁判官"

调度器的哲学是"**能者上，庸者下**"——永远让优先级最高的就绪任务运行。这是一种"贤能政治"（Meritocracy），不是民主轮流。

### 2.1 就绪链表数组

```c
// 核心数据结构：每个优先级一个链表
List_t pxReadyTasksLists[configMAX_PRIORITIES];

// 调度逻辑：取最高优先级非空链表的头部任务
// 同优先级的多个任务通过链表实现 Round-Robin 轮转
```

可视化：

```
pxReadyTasksLists[4] ──→ [Safety]           ← 最高优先级（最先被调度）
pxReadyTasksLists[3] ──→ [Motor]
pxReadyTasksLists[2] ──→ [Sensor]
pxReadyTasksLists[1] ──→ [Logger]
pxReadyTasksLists[0] ──→ [Idle]             ← 最低优先级（系统空闲时运行）
```

### 2.2 调度算法的本质——O(1) 复杂度

```c
// ═══ 方法一：通用版 —— 从最高优先级向下遍历 ═══
UBaseType_t uxTopPriority = uxTopReadyPriority;
while (listLIST_IS_EMPTY(&pxReadyTasksLists[uxTopPriority])) {
    --uxTopPriority;  // 找到第一个非空链表
}
// 取该优先级链表的下一个节点（Round-Robin 轮转）
listGET_OWNER_OF_NEXT_ENTRY(pxCurrentTCB, &pxReadyTasksLists[uxTopPriority]);

// ═══ 方法二：硬件优化版 —— CLZ 指令（Cortex-M）═══
// 用一个 32 位位图记录哪些优先级有就绪任务
// __clz() 前导零计数 → O(1) 找到最高优先级
// 这就是 configUSE_PORT_OPTIMISED_TASK_SELECTION = 1 的秘密
```

> **哲学洞察：** 调度器使用"位图 + CLZ"实现 O(1) 查找——这是"空间换时间"的经典案例。32 位位图只需 4 字节，却让调度速度从 O(n) 降到了单条汇编指令。正如庄子所言"无用之用，方为大用"——那 4 字节的'额外空间'让整个系统获得了确定性。

### 2.3 SysTick 与延迟切换

```
SysTick_Handler() → xTaskIncrementTick()
├── 递增 xTickCount
├── 检查延时链表：有任务到期？→ 移到就绪链表
├── 同优先级有多个任务？→ 切换到下一个（Round-Robin）
└── 需要切换？→ 设置 PendSV 标志位
    （portYIELD() 实质是 SCB->ICSR |= (1<<28)）
```

**关键设计：延迟切换（Deferred Context Switch）**

SysTick 只"标记"需要切换，不做切换本身。实际切换在 PendSV（最低优先级）中完成。这确保所有高优先级中断先处理完，才进行上下文切换。

> **为什么？** 如果 SysTick 中直接切换，而此时有更高优先级的中断 pending，切换过程会被打断——导致新任务的栈帧不完整。PendSV 的最低优先级保证了切换的原子性。

---

## 三、上下文切换：RTOS 的"灵魂摆渡"

上下文切换是 FreeRTOS 最精妙的操作——在纳秒级别将一个任务的"灵魂"（寄存器状态）保存，并注入另一个任务的"灵魂"。整个过程不到 **1 微秒**（Cortex-M4 @ 168MHz）。

### 3.1 完整 PendSV_Handler 汇编逐行解析

```asm
PendSV_Handler:
    ;; ══════ Step 1: 关中断（使用 BASEPRI，不是 PRIMASK！）══════
    mov r0, #configMAX_SYSCALL_INTERRUPT_PRIORITY
    msr basepri, r0             ; 屏蔽低优先级中断，高优先级中断仍可响应
    dsb                          ; 数据同步屏障：确保 BASEPRI 生效
    isb                          ; 指令同步屏障：清流水线

    ;; ══════ Step 2: 保存当前任务上下文 ══════
    ;; 注意：R0-R3, R12, LR, PC, xPSR 已由硬件自动入栈到 PSP
    mrs r0, psp                  ; 获取当前任务的进程栈指针
    isb

    ldr r3, =pxCurrentTCB        ; R3 = &pxCurrentTCB（TCB指针的地址）
    ldr r2, [r3]                 ; R2 = pxCurrentTCB（当前 TCB）

    ;; 保存 R4-R11（硬件不自动保存的寄存器）
    stmdb r0!, {r4-r11}          ; 将 R4-R11 压入任务栈，R0 自动递减
    ;; 如果有 FPU：tst r14, #0x10 → vstmdb r0!, {s16-s31}

    str r0, [r2]                 ; 保存新的栈顶 → TCB->pxTopOfStack
    ;;   ↑ 这就是为什么 pxTopOfStack 必须是 TCB 第一个字段！
    ;;     str r0, [r2] 等于 str r0, [r2, #0]，偏移量 = 0

    ;; ══════ Step 3: 选择下一个任务（调用 C 函数）══════
    stmdb sp!, {r3, r14}         ; 保存 R3(TCB地址) 和 LR(EXC_RETURN) 到内核栈(MSP)
    bl vTaskSwitchContext         ; 调用 C 函数：更新 pxCurrentTCB
    ldmia sp!, {r3, r14}         ; 恢复 R3 和 LR

    ;; ══════ Step 4: 恢复新任务上下文 ══════
    ldr r1, [r3]                 ; R1 = 新的 pxCurrentTCB
    ldr r0, [r1]                 ; R0 = 新任务的 pxTopOfStack

    ldmia r0!, {r4-r11}          ; 从新任务栈恢复 R4-R11，R0 自动递增
    msr psp, r0                  ; 更新 PSP 指向新任务的栈
    isb

    ;; ══════ Step 5: 开中断并返回 ══════
    mov r0, #0
    msr basepri, r0              ; 恢复中断（BASEPRI = 0 = 不屏蔽）

    bx r14                       ; 使用 EXC_RETURN 返回
    ;; 硬件自动从 PSP 恢复 R0-R3, R12, LR, PC, xPSR
    ;; 新任务从上次被中断的地方继续运行！
```

### 3.2 设计哲学逐步解读

| 步骤 | 操作 | 哲学 |
|------|------|------|
| 触发 PendSV | `SCB->ICSR \|= (1<<28)` | **让路哲学**：SysTick 中断可能嵌套在其他中断中，此时切换会破坏原子性。PendSV 等所有人忙完再行动，像谦让的智者。 |
| 硬件自动入栈 | R0-R3,R12,LR,PC,xPSR → PSP | **各司其职**：硬件做它擅长的（固定模式保存），软件做灵活的（调度决策）。ARM 架构设计者深谙此道。 |
| 软件保存 R4-R11 | `STMDB R0!, {R4-R11}` | **懒加载**：R4-R11 是"被调用者保存"寄存器，只有确实用到才保存。ARM 不自动保存它们是为了减少开销。 |
| 选择新任务 | `BL vTaskSwitchContext` | **正确的工具做正确的事**：汇编精确控制寄存器，C 遍历链表做决策。语言选择由任务特性决定。 |
| 恢复新上下文 | `LDMIA R0!, {R4-R11}` | **对称之美**：保存是 STMDB（先减后存），恢复是 LDMIA（先取后增），完美的逆操作。 |
| 异常返回 | `BX LR` (EXC_RETURN) | **信息密度的艺术**：EXC_RETURN（如 0xFFFFFFFD）用一个 32 位数编码了返回模式、栈选择、FPU 状态——一个数承载全部策略。 |

### 3.3 任务栈内存布局

```
高地址
┌───────────────────────────┐
│         xPSR              │  ← 硬件自动保存（进入异常时）
│         PC (返回地址)      │     从 PSP 自动入栈
│         LR                │     8 个寄存器 × 4 字节 = 32 字节
│         R12               │
│         R3                │
│         R2                │
│         R1                │
│         R0                │
├───────────────────────────┤
│         R11               │  ← 软件手动保存（PendSV_Handler 中）
│         R10               │     STMDB R0!, {R4-R11}
│         R9                │     8 个寄存器 × 4 字节 = 32 字节
│         R8                │
│         R7                │
│         R6                │
│         R5                │
│         R4                │  ← pxTopOfStack 指向这里
├───────────────────────────┤
│      （剩余栈空间）        │
│          ...              │
├───────────────────────────┤
│      （栈底标记）          │  ← pxStack（溢出检测基准）
└───────────────────────────┘
低地址
```

### 3.4 MSP 与 PSP 的双栈设计

```
MSP（主栈指针）                     PSP（进程栈指针）
┌──────────────────┐              ┌──────────────────┐
│  异常/中断处理    │              │  任务 A 的栈     │
│  内核代码执行     │              ├──────────────────┤
│  启动阶段        │              │  任务 B 的栈     │
└──────────────────┘              ├──────────────────┤
   ↑ Handler 模式使用               │  任务 C 的栈     │
                                  └──────────────────┘
                                     ↑ Thread 模式使用（每个任务独立栈）
```

> **为什么双栈？** 如果所有中断和任务共用一个栈，中断嵌套时需要在每个任务栈上预留中断用的空间——浪费且不可预测。双栈让中断固定用 MSP，任务固定用 PSP，互不干扰。这是"关注点分离"（Separation of Concerns）的硬件级实现。

---

## 四、内存管理：五种 Heap 的哲学

FreeRTOS 提供 5 种内存管理方案，它们不是"进化关系"，而是**不同哲学的体现**。选择哪个 heap，反映了你对系统的理解深度。

### 4.1 五种 Heap 对比总览

```
┌─────────┬───────────────────┬──────────┬──────────┬─────────────────────────────┐
│ 方案     │ 算法              │ 碎片化   │ 安全性   │ 适用场景                      │
├─────────┼───────────────────┼──────────┼──────────┼─────────────────────────────┤
│ heap_1  │ 顺序分配（不释放） │ 无       │ ★★★★★  │ 任务数固定的简单系统           │
│ heap_2  │ Best Fit（不合并） │ 严重     │ ★★☆☆☆  │ 已废弃，仅供理解               │
│ heap_3  │ 封装 malloc/free  │ 依赖库   │ ★★☆☆☆  │ 需兼容标准库代码               │
│ heap_4  │ First Fit + 合并  │ 低       │ ★★★★☆  │ 推荐方案（绝大多数项目）        │
│ heap_5  │ 同 heap_4 + 多区域 │ 低       │ ★★★★☆  │ 多块不连续 RAM（SRAM+SDRAM）   │
└─────────┴───────────────────┴──────────┴──────────┴─────────────────────────────┘
```

### 4.2 heap_1：只分配不释放

```c
// 极致简单：维护一个指针，每次分配向后移动
static uint8_t ucHeap[configTOTAL_HEAP_SIZE];
static size_t xNextFreeByte = 0;

void *pvPortMalloc(size_t xWantedSize) {
    void *pvReturn = &ucHeap[xNextFreeByte];
    xNextFreeByte += xWantedSize;  // 对齐处理省略
    return pvReturn;
}

void vPortFree(void *pv) {
    // 什么都不做。是的，真的什么都不做。
    (void)pv;
}
```

> **哲学（奥卡姆剃刀）：** "如无必要，勿增实体"。如果你的系统从不需要释放内存（所有任务在启动时创建，永不删除），那么释放逻辑就是 100% 的 bug 隐患。heap_1 消除了碎片化、双重释放、野指针一切问题——通过不提供释放功能。

### 4.3 heap_2：最佳匹配（反面教材）

```c
// 空闲块链表按大小排序，分配时找最接近的块
// 释放不合并相邻块 → 碎片化不可逆

// 场景：
// 分配 100 个 8 字节块
// 释放所有 100 个块
// 尝试分配 800 字节 → 失败！
// 因为有 100 个 8 字节空闲块，但没有一个 800 字节的连续块
```

> **哲学（热力学第二定律）：** heap_2 告诉我们，释放内存而不合并空闲块，会让碎片化像熵增一样不可逆。系统的"有序度"只会递减——除非有合并机制来"做功"对抗熵增。

### 4.4 heap_3：封装标准库

```c
void *pvPortMalloc(size_t xSize) {
    void *pvReturn;
    vTaskSuspendAll();          // 暂停调度器（不是关中断！）
    pvReturn = malloc(xSize);   // 调用编译器的标准库
    xTaskResumeAll();
    return pvReturn;
}
```

> **哲学（组合优于继承）：** heap_3 承认标准库的 malloc 可能比自己写得更好（在通用场景下），但用调度器锁来补全线程安全。不重新发明轮子，而是给已有的轮子加个锁——这是务实主义。

### 4.5 heap_4：合并空闲块（推荐方案）

```c
// 核心数据结构：空闲块链表
typedef struct A_BLOCK_LINK {
    struct A_BLOCK_LINK *pxNextFreeBlock;  // 指向下一个空闲块
    size_t xBlockSize;                      // 本块大小
    // xBlockSize 最高位(bit31) = 1 表示已分配，0 表示空闲
} BlockLink_t;  // 大小 = 8 字节（32位系统）
```

内存布局：

```
┌──────────────┬────────────────────────┬──────────────┬─────────────────┐
│ BlockLink_t  │     用户可用空间        │ BlockLink_t  │  用户可用空间    │
│ (8 bytes)    │    (xWantedSize)       │ (8 bytes)    │                 │
│ pxNext=NULL  │                        │ pxNext=...   │                 │
│ size=48|0x80 │  ← 已分配（bit31=1）   │ size=64      │  ← 空闲          │
└──────────────┴────────────────────────┴──────────────┴─────────────────┘
```

释放时的合并逻辑：

```c
// 1. 将释放的块插入按地址排序的空闲链表
// 2. 检查前一个空闲块：
//    if (前一块的尾地址 == 当前块的首地址) → 合并
// 3. 检查后一个空闲块：
//    if (当前块的尾地址 == 后一块的首地址) → 合并

// 效果：碎片化被持续修复
// 场景重放：
// 分配 100 个 8 字节块
// 释放所有 → 100 个相邻块被合并为 1 个大块
// 分配 800 字节 → 成功！
```

> **哲学（中庸之道）：** heap_4 既不像 heap_1 那样极端简单，也不像 heap_3 那样完全依赖外部。它在可控性与灵活性之间找到了最佳平衡。合并空闲块说明了一个道理：局部的"整理"可以对抗全局的"混乱"——这是反熵操作。

### 4.6 heap_5：多区域合并

```c
// 与 heap_4 算法完全相同，只是支持多块不连续内存
HeapRegion_t xHeapRegions[] = {
    { (uint8_t *)0x20000000, 64 * 1024 },          // SRAM1 (64KB)
    { (uint8_t *)0x20010000, 32 * 1024 },          // SRAM2 (32KB)
    { (uint8_t *)0xC0000000,  8 * 1024 * 1024 },   // 外部 SDRAM (8MB)
    { NULL, 0 }                                      // 结束标记
};
vPortDefineHeapRegions(xHeapRegions);
```

> **哲学（开放-封闭原则）：** heap_5 不改变核心算法，只扩展数据源。对扩展开放（支持新的内存区域），对修改封闭（算法不变）。这是"适配器模式"的完美实践。

---

## 五、IPC 通信：任务间的四种武器

任务是独立的个体，但系统需要协作。IPC 就是任务之间的"语言"——不同的 IPC 适合不同的"对话方式"。

### 5.1 队列 (Queue) —— 万物之基

Queue 是 FreeRTOS 所有 IPC 的基石——Semaphore、Mutex、EventGroup 底层都基于 Queue 实现。

```c
typedef struct QueueDefinition {
    int8_t *pcHead;                     // 环形缓冲区头指针
    int8_t *pcWriteTo;                  // 下一次写入位置
    int8_t *pcReadFrom;                 // 上一次读取位置

    List_t xTasksWaitingToSend;         // 等待发送的任务链表
    List_t xTasksWaitingToReceive;      // 等待接收的任务链表

    volatile UBaseType_t uxMessagesWaiting;  // 当前消息数
    UBaseType_t uxLength;               // 最大消息数
    UBaseType_t uxItemSize;             // 每条消息字节数
    // ...
} Queue_t;
```

关键行为：

```
发送时队列满 → 任务进入 xTasksWaitingToSend 链表（阻塞）
接收时队列空 → 任务进入 xTasksWaitingToReceive 链表（阻塞）

数据通过 memcpy 拷贝（值传递，非指针！）
→ 发送后原始数据可以安全修改
→ 代价：大数据应传指针，小数据直接拷贝

环形缓冲区：
  pcWriteTo 写到末尾后回到 pcHead（取模）
  pcReadFrom 读到末尾后回到 pcHead
  → 无需移动数据，O(1) 读写
```

> **哲学（生产者-消费者）：** Queue 体现了人类社会最古老的协作模式。卖包子的（生产者）不需要认识吃包子的（消费者），他们通过"蒸笼"（Queue）解耦。这就是"中间人模式"——降低耦合，提高灵活性。

### 5.2 信号量 (Semaphore) —— 计数的艺术

信号量本质上是一个特殊的 Queue：`uxItemSize = 0`，`uxMessagesWaiting` 就是计数值。

```c
// 底层实现揭秘：
xSemaphoreCreateBinary() →
    xQueueGenericCreate(1, 0, queueQUEUE_TYPE_BINARY_SEMAPHORE)
// 长度=1，元素大小=0 的队列！
// Give = xQueueSend（写入一个 0 字节的"消息"）
// Take = xQueueReceive（读取那个"消息"）
```

**二值信号量 vs 计数信号量**

```
二值信号量（Binary Semaphore）：
├── 计数值只有 0 或 1
├── 典型用途：ISR → Task 同步（中断通知任务处理数据）
├── 创建：xSemaphoreCreateBinary() → 初始值 = 0
└── ⚠️ 无优先级继承！不要用来保护共享资源

计数信号量（Counting Semaphore）：
├── 计数值 0 ~ uxMaxCount
├── 典型用途：资源池管理（DMA通道、连接池、缓冲区）
└── 创建：xSemaphoreCreateCounting(maxCount, initialCount)
```

> **哲学（Dijkstra 的 P/V 操作）：** 信号量源自荷兰计算机科学家 Dijkstra。P(proberen=尝试) 减计数，V(verhogen=增加) 加计数。哲学是"数量控制"——就像停车场的计数器：有空位才能进，出来一辆才能再进一辆。

### 5.3 互斥锁 (Mutex) —— 所有权的哲学

```
Mutex vs Binary Semaphore 的本质区别：

┌──────────────────┬────────────────────┬────────────────────┐
│                  │ Binary Semaphore   │ Mutex              │
├──────────────────┼────────────────────┼────────────────────┤
│ 谁能释放         │ 任何任务/ISR       │ 只有持有者          │
│ 优先级继承       │ 无                 │ 有                  │
│ 递归锁           │ 不支持             │ 支持                │
│ ISR 中使用       │ 可以（FromISR）    │ 不可以              │
│ 典型用途         │ 同步/通知          │ 互斥/保护共享资源   │
└──────────────────┴────────────────────┴────────────────────┘
```

优先级继承机制：

```
场景：任务 H(高优先级) 需要获取 L(低优先级) 持有的 Mutex

WITHOUT 优先级继承：
t0: L 持有 Mutex，运行
t1: H 就绪，抢占 L → H 尝试获取 Mutex → 阻塞
t2: M(中优先级) 就绪 → 抢占 L（M > L）
    H 被 M 间接阻塞了！H 比 M 优先级高却无法运行！→ 优先级反转！

WITH 优先级继承（FreeRTOS Mutex）：
t0: L 持有 Mutex，运行
t1: H 就绪 → 尝试获取 Mutex → 发现 L 持有
    → FreeRTOS 自动提升 L 的优先级 = H 的优先级
t2: M 就绪 → 无法抢占 L（因为 L 此时优先级 = H）
t3: L 释放 Mutex → 优先级恢复 → H 获得 Mutex 运行
```

递归互斥锁：

```c
// 防止同一任务对自己死锁
SemaphoreHandle_t xMutex = xSemaphoreCreateRecursiveMutex();

void funcA(void) {
    xSemaphoreTakeRecursive(xMutex, portMAX_DELAY);
    funcB();  // funcB 内部也会获取同一个 Mutex → 不会死锁！
    xSemaphoreGiveRecursive(xMutex);
}

void funcB(void) {
    xSemaphoreTakeRecursive(xMutex, portMAX_DELAY);
    // 同一任务第二次获取，计数器 +1，不阻塞
    xSemaphoreGiveRecursive(xMutex);  // 计数器 -1
}
// 全部释放后（计数器归零），其他任务才能获取
```

> **哲学（产权）：** Mutex 体现了"产权"哲学——只有锁的持有者才能释放它。如果任何人都能释放锁，就像任何人都能卖你的房子一样危险。产权清晰是秩序的基础。

### 5.4 任务通知 (Task Notification) —— 极速之道

每个任务内置一个 32 位通知值 + pending 标志，比 Queue 快 45%，零动态分配。

```c
// ═══ 用法1：轻量信号量 ═══
// ISR 端
void ISR_Handler(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    vTaskNotifyGiveFromISR(data_task_handle, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}
// 任务端
void data_task(void *p) {
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);  // 阻塞等待
        process_data();
    }
}

// ═══ 用法2：事件标志组（32位，每位一个事件）═══
#define EVT_SENSOR_READY  (1 << 0)
#define EVT_TIMEOUT       (1 << 1)
#define EVT_CMD_RECEIVED  (1 << 2)

// 发送方
xTaskNotifyFromISR(main_task, EVT_SENSOR_READY, eSetBits, &woken);

// 接收方
uint32_t events;
xTaskNotifyWait(0, 0xFFFFFFFF, &events, portMAX_DELAY);
if (events & EVT_SENSOR_READY) { /* ... */ }
if (events & EVT_CMD_RECEIVED) { /* ... */ }

// ═══ 用法3：邮箱模式（传递一个32位值）═══
xTaskNotify(handle, sensor_value, eSetValueWithOverwrite);
```

性能对比（STM32F4 @ 168MHz）：

```
┌──────────────────────┬──────────┬─────────────┐
│ 操作                 │ Queue    │ Notification │
├──────────────────────┼──────────┼─────────────┤
│ ISR→Task 唤醒        │ ~2.1 μs  │ ~1.2 μs     │
│ Task→Task 发送       │ ~1.8 μs  │ ~1.0 μs     │
│ RAM 占用             │ 76+ bytes│ 0 bytes     │
└──────────────────────┴──────────┴─────────────┘

限制：
• 只能一对一（一个发送方 → 一个接收方）
• 无法广播（用 EventGroup 解决）
• 无法缓冲多条消息
```

> **哲学（YAGNI — You Ain't Gonna Need It）：** 大多数 IPC 场景其实很简单——"有活了，来处理"。为此创建 Queue 对象是杀鸡用牛刀。Task Notification 直接嵌入 TCB，无需分配内存、无需遍历链表。够用就好。

---

## 六、软件定时器：时间的委托者

### 6.1 架构

```
  用户任务/ISR                    Timer Service Task
  ┌──────────┐                   (守护任务，优先级: configTIMER_TASK_PRIORITY)
  │ 启动定时器 │    命令队列        ┌──────────────────────────┐
  │ 停止定时器 ├──→ xTimerQueue ─→│ 解析命令：                │
  │ 重置定时器 │    (长度=          │ • 启动/停止/重置/改周期  │
  │ 改变周期   │     configTIMER_   │ 管理到期列表：            │
  └──────────┘     QUEUE_LENGTH)  │ • 检查哪些定时器到期      │
                                  │ • 执行对应回调函数        │
                                  └──────────────────────────┘
```

### 6.2 溢出处理——双链表交换

```
时间管理核心问题：xTickCount 是 32 位无符号整数，会溢出

解决方案：两个链表轮流使用
• pxCurrentTimerList     → 当前 tick 周期的定时器
• pxOverflowTimerList    → 下一个溢出周期的定时器

当 xTickCount 从 0xFFFFFFFF 溢出到 0 时：
  两个链表指针交换！

这和 xTaskIncrementTick() 中的延时链表管理完全一样
——同一个"双链表溢出处理"模式被复用了两次。
```

### 6.3 回调注意事项

```
回调函数注意事项：
├── 回调运行在 Timer Task 上下文（不是 ISR！）
├── 可以调用普通 API（不需要 FromISR 版本）
├── ⚠️ 不可调用阻塞 API：
│   ├── vTaskDelay()
│   ├── xQueueReceive() with timeout
│   └── xSemaphoreTake() with timeout
│   → 因为会阻塞整个 Timer Task，影响所有定时器
├── 回调应尽可能短：发送消息到队列，让工作任务处理
└── 精度：± 1 tick（configTICK_RATE_HZ=1000 → ±1ms）
```

> **哲学（命令模式 + 单一职责）：** 所有定时器操作被编码为"命令"发送到队列，由专门任务处理。ISR 中可以安全操作定时器（通过命令队列），而不需要在中断上下文做复杂链表操作。正如管理学中的"不要亲自做，而是下达命令"——异步解耦是复杂系统的救星。

---

## 七、临界区：BASEPRI 的精妙设计

FreeRTOS 不使用 `__disable_irq()`（PRIMASK）来进入临界区，而是使用 `BASEPRI` 寄存器——这是一个**天才级的设计决策**。

### 7.1 PRIMASK vs BASEPRI

```
PRIMASK（__disable_irq）：
├── 屏蔽 ALL 可配置中断
├── 包括时间关键的高优先级中断（电机控制、安全监控）
├── 临界区期间系统完全"失聪"
└── 可能错过紧急事件 → 危险！

BASEPRI（FreeRTOS 方式）：
├── 只屏蔽优先级 ≥ configMAX_SYSCALL_INTERRUPT_PRIORITY 的中断
├── 高优先级中断（数值 < BASEPRI）仍然可以响应
├── 系统保留"紧急通道"
└── 安全相关中断不受影响
```

### 7.2 交互理解：中断屏蔽示意

假设 `configMAX_SYSCALL_INTERRUPT_PRIORITY = 5`（ARM：数字越小 = 优先级越高）

```
优先级  中断名        临界区状态
──────  ──────────    ──────────────
 -1     NMI           永不屏蔽（硬件固定）
 -1     HardFault     永不屏蔽（硬件固定）
  2     SPI_DMA       ✅ 可响应（2 < 5，高于 BASEPRI 阈值）
  4     UART_RX       ✅ 可响应（4 < 5）
─────── BASEPRI = 5 分界线 ────────────────────────────
  5     SysTick       ❌ 已屏蔽（5 ≥ 5）
  6     I2C_EV        ❌ 已屏蔽（6 ≥ 5）
  7     PendSV        ❌ 已屏蔽（7 ≥ 5）
```

### 7.3 API 划分规则

```
configMAX_SYSCALL_INTERRUPT_PRIORITY 划定了"安全线"：

高于它（数值小于它）的中断：
├── 不会被临界区屏蔽
├── 不能调用任何 FreeRTOS API（包括 FromISR 版本！）
├── 适合：电机过流保护、安全监控、高速 ADC
└── 这些中断必须完全自给自足

低于/等于它（数值大于等于它）的中断：
├── 会被临界区屏蔽
├── 可以调用 FreeRTOS 的 FromISR API
├── 适合：UART接收、SPI传输完成、普通传感器
└── 这些中断可以与任务交互
```

```c
// 临界区实现
void vPortEnterCritical(void) {
    portDISABLE_INTERRUPTS();  // MSR BASEPRI, configMAX_SYSCALL_INTERRUPT_PRIORITY
    uxCriticalNesting++;        // 支持嵌套
}

void vPortExitCritical(void) {
    uxCriticalNesting--;
    if (uxCriticalNesting == 0) {
        portENABLE_INTERRUPTS(); // MSR BASEPRI, 0
    }
}

// taskENTER_CRITICAL() / taskEXIT_CRITICAL() 是对以上的宏封装
```

> **哲学（分层防御 + 自由与责任）：** BASEPRI 承认了一个现实：不是所有中断都同等重要。安全相关的中断不能因为"操作系统在忙"就被忽略。这就像医院的"急诊通道"——普通排队可以暂停，但急救通道永远畅通。这种设计需要程序员正确划分中断优先级——**自由伴随责任**。

---

## 八、优先级反转：RTOS 的"阿喀琉斯之踵"

### 8.1 历史教训

1997 年，NASA 的火星探路者号（Mars Pathfinder）因优先级反转导致系统反复重启。最终靠从地球远程发送指令，启用 VxWorks 的优先级继承机制才修复。这个 Bug 告诉我们：**调度器的"公平"可能是致命的**。

### 8.2 问题重现（无优先级继承）

```
时间线：三个任务 H(高)、M(中)、L(低) 共享一个 Binary Semaphore

t0: L 获取信号量，开始访问共享资源
t1: H 就绪，抢占 L（H > L）
t2: H 尝试获取信号量 → 发现 L 持有 → H 阻塞等待
t3: M 就绪 → M > L → M 抢占 L 开始运行
    ┌──────────────────────────────────────────────────┐
    │ ★ 优先级反转发生！                                │
    │ H（最高优先级）被 M（中优先级）间接阻塞            │
    │ H 的响应时间被 M 无限延长（不确定性！）            │
    │ 如果 M 运行很久，H 可能超时 → 系统看门狗重启      │
    └──────────────────────────────────────────────────┘
t4: M 完成 → L 恢复运行
t5: L 释放信号量 → H 终于运行
```

### 8.3 解决方案：优先级继承（Mutex）

```
使用 xSemaphoreCreateMutex() 替代 xSemaphoreCreateBinary()：

t0: L 获得 Mutex，运行
t1: H 就绪，抢占 L
t2: H 尝试获取 Mutex → L 持有
    → FreeRTOS 自动将 L 的优先级提升为 H 的优先级 ★
t3: M 就绪 → 但 L 此时优先级 = H → M 无法抢占！★★
t4: L（以 H 的优先级运行）释放 Mutex
    → L 的优先级恢复原值
    → H 获得 Mutex，立即运行
```

### 8.4 三种解决方案对比

```
┌───────────────────────┬──────────────────────────────────────┐
│ 优先级继承 (PIP)       │ FreeRTOS Mutex 使用                   │
│                       │ 运行时动态提升                         │
│                       │ 简单但只支持单级继承                   │
│                       │ 链式反转（H→M→L）无法处理             │
├───────────────────────┼──────────────────────────────────────┤
│ 优先级天花板 (PCP)     │ AUTOSAR OSEK 使用                     │
│                       │ 资源在设计时分配一个"天花板优先级"     │
│                       │ 获取资源时直接提升到天花板             │
│                       │ 静态分析，无死锁保证，但开销更大       │
├───────────────────────┼──────────────────────────────────────┤
│ 禁止中断/调度          │ 最简单粗暴                            │
│                       │ taskENTER_CRITICAL()                  │
│                       │ 适合极短的临界区（<几微秒）            │
│                       │ 代价：所有调度停止                     │
└───────────────────────┴──────────────────────────────────────┘
```

> **工程铁律：** 永远用 `xSemaphoreCreateMutex()` 而非 `xSemaphoreCreateBinary()` 来保护共享资源。Binary Semaphore 用于"通知"（ISR→Task），Mutex 用于"互斥"（Task↔Task）。混用是优先级反转的根源。

---

## 九、TCB 深度解析：任务的"身份证"

### 9.1 完整 TCB 结构体

```c
typedef struct tskTaskControlBlock {

    // ═══════ 第一字段（汇编硬编码依赖！）═══════
    volatile StackType_t *pxTopOfStack;
    //   PendSV 中通过 LDR R0, [TCB] 直接取第一个字段（偏移=0）
    //   如果这不是第一个字段，上下文切换会崩溃

    // ═══════ 状态链表节点 ═══════
    ListItem_t xStateListItem;
    //   任务在就绪/阻塞/挂起链表中的位置
    //   xItemValue = 优先级（就绪态）或唤醒时间（阻塞态）

    ListItem_t xEventListItem;
    //   任务在事件等待链表中的位置
    //   等待 Queue/Semaphore/EventGroup 时使用

    // ═══════ 优先级 ═══════
    UBaseType_t uxPriority;
    //   当前优先级（可能因优先级继承而临时提升）
    UBaseType_t uxBasePriority;
    //   原始优先级（继承恢复时用）

    // ═══════ 栈信息 ═══════
    StackType_t *pxStack;
    //   栈底地址（溢出检测基准）
    //   栈从高地址向低地址增长
    //   pxTopOfStack 总是 ≥ pxStack（否则溢出）

    // ═══════ 任务名 ═══════
    char pcTaskName[configMAX_TASK_NAME_LEN];

    // ═══════ 可选字段（由 FreeRTOSConfig.h 宏控制）═══════
    #if (configUSE_MUTEXES == 1)
        UBaseType_t uxMutexesHeld;       // 持有的 mutex 数量
    #endif

    #if (configUSE_TASK_NOTIFICATIONS == 1)
        volatile uint32_t ulNotifiedValue;  // 通知值（32位）
        volatile uint8_t  ucNotifyState;    // NOT_WAITING / WAITING / NOTIFIED
    #endif

    #if (configGENERATE_RUN_TIME_STATS == 1)
        uint32_t ulRunTimeCounter;       // CPU 运行时间统计
    #endif

    #if (configCHECK_FOR_STACK_OVERFLOW > 0)
        StackType_t *pxEndOfStack;       // 栈顶边界（向下增长时）
    #endif

} TCB_t;
```

### 9.2 任务状态机

```
                     xTaskCreate()
                          │
                          ▼
                ┌──────────────────┐
                │     就绪 Ready   │◄──────────────────────┐
                └────────┬─────────┘                        │
                         │ 调度器选中                        │
                         │ （最高优先级就绪任务）              │
                         ▼                                   │
                ┌──────────────────┐                        │
                │   运行 Running   │                        │
                └────────┬─────────┘                        │
                         │                                   │
            ┌────────────┴────────────┐                     │
            ▼                          ▼                     │
   ┌─────────────────┐    ┌──────────────────┐              │
   │  阻塞 Blocked   │    │  挂起 Suspended  │              │
   │                 │    │                  │              │
   │ vTaskDelay()    │    │ vTaskSuspend()   │              │
   │ xQueueReceive() │    │                  │              │
   │ xSemaphoreTake()│    │                  │              │
   └────────┬────────┘    └────────┬─────────┘              │
            │ 超时/事件到达        │ vTaskResume()           │
            └──────────────────────┴────────────────────────┘

链表归属：
• Ready     → pxReadyTasksLists[优先级]
• Blocked   → pxDelayedTaskList 或 pxOverflowDelayedTaskList
• Suspended → xSuspendedTaskList
• Running   → pxCurrentTCB 指针（不在任何链表中！）
```

> **哲学（一花一世界）：** TCB 的设计体现了"数据局部性"原则——所有与任务相关的状态都集中在一个结构体中。任务切换只需切换一个指针（pxCurrentTCB），就能"换一个世界"。每个 TCB 都是一个完整的独立宇宙。

---

## 十、启动流程：从裸机到 RTOS

理解 FreeRTOS 的启动流程，就是理解"混沌到秩序"的演变——从硬件复位的一片空白，到多任务并行的有序世界。

### 10.1 完整启动流程

```
═══════════════════════════════════════════════════════════
Step 1: 硬件复位
═══════════════════════════════════════════════════════════
CPU 上电 / 复位
  │ • 从 0x00000000 读取初始 MSP 值（主栈指针）
  │ • 从 0x00000004 读取 Reset_Handler 地址
  │ • 跳转到 Reset_Handler
  │ • 此时处于 Handler 模式，使用 MSP
  ▼
═══════════════════════════════════════════════════════════
Step 2: Reset_Handler（启动汇编代码）
═══════════════════════════════════════════════════════════
  │ • 复制 .data 段（Flash → RAM）
  │   → 已初始化的全局变量需要从 Flash 拷贝到 RAM
  │ • 清零 .bss 段
  │   → 未初始化的全局变量设为 0
  │ • 初始化 FPU（如果是 Cortex-M4F/M7）
  │   → CPACR 寄存器使能 CP10/CP11
  │ • 调用 SystemInit()
  │   → 基本时钟配置
  │ • 跳转到 main()
  ▼
═══════════════════════════════════════════════════════════
Step 3: main()（用户代码开始）
═══════════════════════════════════════════════════════════
  │ HAL_Init()
  │   → 配置 NVIC 优先级分组（通常 4 位抢占 / 0 位子优先级）
  │   → 配置 SysTick（此时还是裸机模式的 SysTick）
  │
  │ SystemClock_Config()
  │   → 配置 PLL、HSE/HSI
  │   → 设置 AHB/APB 总线分频
  │
  │ 外设初始化
  │   → GPIO、UART、SPI、I2C、DMA、ADC...
  │
  │ 创建 RTOS 对象（调度器还没启动！）
  │   → xTaskCreate() × N      → 分配 TCB + 栈 + 加入就绪链表
  │   → xQueueCreate()          → 分配队列结构 + 缓冲区
  │   → xSemaphoreCreateMutex() → 分配 mutex
  │
  │ ⚠️ 此时所有 xTaskCreate 只是"登记"，没有任何任务在运行
  ▼
═══════════════════════════════════════════════════════════
Step 4: vTaskStartScheduler() ← 关键转折点！
═══════════════════════════════════════════════════════════
  │ • 创建 Idle Task（优先级 0，系统空闲时运行）
  │ • 创建 Timer Task（如果 configUSE_TIMERS == 1）
  │ • 配置 SysTick 定时器
  │   → 重载值 = configCPU_CLOCK_HZ / configTICK_RATE_HZ - 1
  │   → 典型值：168MHz / 1000Hz - 1 = 167999
  │ • 设置 PendSV 优先级 = 最低（0xFF）
  │ • 设置 SysTick 优先级 = 最低（0xFF）
  │ • 调用 xPortStartScheduler()
  ▼
═══════════════════════════════════════════════════════════
Step 5: prvStartFirstTask()（质变时刻！）
═══════════════════════════════════════════════════════════
  │ • 找到最高优先级就绪任务
  │ • 从该任务的 TCB 取出 pxTopOfStack
  │ • 恢复 R4-R11
  │ • 设置 PSP = 任务栈顶
  │ • 切换到 Thread 模式 + PSP
  │   → MSR CONTROL, #2
  │ • BX LR → 跳转到第一个任务的入口函数
  │
  │ ═══════════════════════════════════════
  │   从此刻起：
  │   • Handler 模式 → Thread 模式
  │   • MSP → PSP
  │   • 裸机单线程 → RTOS 多任务
  │   • main() 永远不会返回
  │ ═══════════════════════════════════════
  ▼
═══════════════════════════════════════════════════════════
Step 6: 任务世界开始运转
═══════════════════════════════════════════════════════════
  • SysTick 每 1ms 触发
    → 递增 tick 计数
    → 检查延时链表
    → 时间片轮转
  • PendSV 在需要时触发
    → 上下文切换
  • 你的任务在各自的 while(1) 中运行
  • Idle Task 在没人运行时运行
    → 可以在这里进入低功耗模式（WFI/WFE）
```

> **哲学（单程票 + 宇宙大爆炸）：** `vTaskStartScheduler()` 是一个"单程票"——它永远不会返回。调用它的那一刻，程序的控制流从"线性执行"变为"事件驱动的并发"。这是一个质变——如同宇宙大爆炸，从单一到多元，从有序到混沌中的有序。main() 函数的最后一行之后，世界的运行方式彻底改变了。

### 10.2 关键配置项速查

```
┌──────────────────────────────────────┬──────────────────┬──────────────────────────┐
│ 配置项                               │ 含义             │ 说明                      │
├──────────────────────────────────────┼──────────────────┼──────────────────────────┤
│ configCPU_CLOCK_HZ                   │ CPU 主频         │ 用于 SysTick 重载值计算   │
│ configTICK_RATE_HZ                   │ Tick 频率        │ 通常 1000（1ms 一个 tick）│
│ configMAX_PRIORITIES                 │ 最大优先级数     │ 通常 5~56                │
│ configMINIMAL_STACK_SIZE             │ 最小栈大小       │ Idle Task 的栈大小（字）  │
│ configTOTAL_HEAP_SIZE                │ 堆总大小         │ heap_1/2/4/5 使用        │
│ configMAX_SYSCALL_INTERRUPT_PRIORITY │ API 安全线       │ BASEPRI 阈值             │
│ configUSE_PREEMPTION                 │ 抢占式调度       │ 1=抢占 0=协作            │
│ configUSE_TIME_SLICING               │ 时间片轮转       │ 同优先级是否轮流         │
│ configUSE_MUTEXES                    │ 启用互斥锁       │ 支持优先级继承           │
│ configUSE_TASK_NOTIFICATIONS         │ 启用任务通知     │ 轻量级 IPC              │
│ configCHECK_FOR_STACK_OVERFLOW       │ 栈溢出检测       │ 0=关闭 1=快速 2=完整    │
│ configUSE_IDLE_HOOK                  │ 空闲钩子         │ Idle Task 中调用         │
│ configUSE_TICK_HOOK                  │ Tick 钩子        │ 每个 SysTick 中调用      │
└──────────────────────────────────────┴──────────────────┴──────────────────────────┘
```

---

## 附录 A：FreeRTOS 链表机制（所有数据结构的基石）

FreeRTOS 的链表实现在 `list.c` / `list.h` 中，是一个极简的双向循环链表。所有的就绪链表、阻塞链表、事件等待链表都基于它。

```c
// 链表节点
struct xLIST_ITEM {
    TickType_t xItemValue;              // 排序值（优先级/唤醒时间）
    struct xLIST_ITEM *pxNext;          // 下一个节点
    struct xLIST_ITEM *pxPrevious;      // 上一个节点
    void *pvOwner;                      // 拥有者（TCB指针）
    struct xLIST *pxContainer;          // 所属链表
};

// 链表头
struct xLIST {
    UBaseType_t uxNumberOfItems;        // 节点数量
    ListItem_t *pxIndex;                // 遍历指针（Round-Robin 的关键）
    MiniListItem_t xListEnd;            // 哨兵节点（xItemValue = portMAX_DELAY）
};

// listGET_OWNER_OF_NEXT_ENTRY() 的核心操作：
// pxIndex = pxIndex->pxNext;
// if (pxIndex == &xListEnd) pxIndex = pxIndex->pxNext;  // 跳过哨兵
// return pxIndex->pvOwner;
// → 这就是 Round-Robin 轮转的实现：每次调用取下一个节点
```

> **哲学：** 链表是计算机科学中最朴素的数据结构，但 FreeRTOS 用它支撑了整个调度系统。`pxIndex` 指针的巧妙移动实现了时间片轮转——不需要计时器，不需要计数器，只需要"下一个"。简单到极致，就是优雅。

---

## 附录 B：Stream Buffer 与 Message Buffer

FreeRTOS V10+ 新增的轻量级 IPC，专为单生产者-单消费者场景优化。

```c
// ═══ Stream Buffer：字节流（如 UART）═══
StreamBufferHandle_t xStreamBuf = xStreamBufferCreate(
    1024,   // 缓冲区大小
    1       // 触发阈值：至少 N 字节时唤醒接收方
);

// ISR 发送
void UART_RX_ISR(void) {
    uint8_t byte = USART1->RDR;
    xStreamBufferSendFromISR(xStreamBuf, &byte, 1, &woken);
}

// 任务接收
size_t received = xStreamBufferReceive(xStreamBuf, buf, sizeof(buf),
                                        pdMS_TO_TICKS(100));

// ═══ Message Buffer：消息流（变长消息）═══
// 在 Stream Buffer 基础上，每条消息前加 4 字节长度头
// 保证消息完整性：要么读出完整消息，要么不读
MessageBufferHandle_t xMsgBuf = xMessageBufferCreate(1024);
xMessageBufferSend(xMsgBuf, &myStruct, sizeof(myStruct), portMAX_DELAY);
```

---

## 附录 C：静态分配（安全关键系统）

AUTOSAR 和安全关键系统要求：**禁止动态内存分配**（不确定性）。

```c
// configSUPPORT_STATIC_ALLOCATION = 1

// 静态任务
static StaticTask_t task_tcb;
static StackType_t  task_stack[512];
TaskHandle_t h = xTaskCreateStatic(task_func, "Task", 512, NULL, 5,
                                    task_stack, &task_tcb);

// 静态队列
static StaticQueue_t queue_struct;
static uint8_t       queue_storage[10 * sizeof(MyMsg_t)];
QueueHandle_t q = xQueueCreateStatic(10, sizeof(MyMsg_t),
                                      queue_storage, &queue_struct);

// 静态定时器
static StaticTimer_t timer_struct;
TimerHandle_t t = xTimerCreateStatic("Timer", pdMS_TO_TICKS(100), pdTRUE,
                                      NULL, callback, &timer_struct);

// 必须提供 Idle 和 Timer 任务的静态内存回调
void vApplicationGetIdleTaskMemory(StaticTask_t **ppTCB,
                                    StackType_t **ppStack,
                                    uint32_t *pSize) {
    static StaticTask_t idle_tcb;
    static StackType_t  idle_stack[configMINIMAL_STACK_SIZE];
    *ppTCB   = &idle_tcb;
    *ppStack = idle_stack;
    *pSize   = configMINIMAL_STACK_SIZE;
}
```

> **哲学（确定性 > 灵活性）：** 在安全关键领域，你宁可牺牲灵活性也要保证确定性。动态分配的问题不在于"可能失败"，而在于"你不知道什么时候会失败"。静态分配的系统，所有内存在编译时确定——如果能编译通过，就能运行一万年。

---

## 附录 D：调试技巧速查

```
栈溢出检测：
├── configCHECK_FOR_STACK_OVERFLOW = 1
│   → 快速检查：任务切换时检查 PSP 是否超出栈边界
│   → 只能检测切换瞬间的溢出
├── configCHECK_FOR_STACK_OVERFLOW = 2
│   → 完整检查：栈底填充 0xA5A5A5A5 魔数
│   → 任务切换时检查魔数是否被破坏
│   → 更安全但开销更大
└── 溢出时回调 vApplicationStackOverflowHook(TaskHandle_t, char *pcTaskName)

运行时统计：
├── configGENERATE_RUN_TIME_STATS = 1
├── 需要提供一个高精度计时器（比 SysTick 精度更高）
│   → portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()
│   → portGET_RUN_TIME_COUNTER_VALUE()
└── vTaskGetRunTimeStats(buffer) → 打印每个任务的 CPU 占用率

任务状态查询：
├── vTaskList(buffer)
│   → 打印所有任务的名称、状态、优先级、栈剩余
├── uxTaskGetStackHighWaterMark(taskHandle)
│   → 返回任务栈的历史最小剩余量（字）
│   → 如果返回值很小（<20），说明栈可能不够
└── xPortGetFreeHeapSize()
    → 返回当前可用的堆空间
    → 周期性调用可监控内存泄漏

HardFault 调试：
├── 读取 SCB->CFSR (Configurable Fault Status Register)
│   ├── MMFSR (MemManage Fault) → 地址: SCB->MMFAR
│   ├── BFSR (Bus Fault)        → 地址: SCB->BFAR
│   └── UFSR (Usage Fault)      → 原因：未对齐/未定义指令/除零
├── 读取 stacked PC → 反汇编定位出错指令
└── 检查 EXC_RETURN → 判断故障前是在任务还是中断中
```

---

*本文档基于 FreeRTOS V10.x 内核源码分析，适用于 ARM Cortex-M 系列（M0/M3/M4/M7）。*
*所有代码示例均可在 STM32 HAL + FreeRTOS 环境中直接使用或稍作修改。*
