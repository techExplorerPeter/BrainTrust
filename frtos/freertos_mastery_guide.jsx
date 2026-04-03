import { useState, useEffect, useRef } from "react";

const sections = [
  { id: "philosophy", title: "哲学总纲", icon: "∞" },
  { id: "scheduler", title: "调度器", icon: "⚙" },
  { id: "context", title: "上下文切换", icon: "↔" },
  { id: "memory", title: "内存管理", icon: "▦" },
  { id: "ipc", title: "IPC通信", icon: "⇌" },
  { id: "timer", title: "软件定时器", icon: "◷" },
  { id: "critical", title: "临界区", icon: "⊘" },
  { id: "priority", title: "优先级反转", icon: "⇅" },
  { id: "tcb", title: "TCB深度", icon: "◈" },
  { id: "startup", title: "启动流程", icon: "▶" },
];

// ─── Philosophy Section ───
function PhilosophySection() {
  const [activeLayer, setActiveLayer] = useState(null);
  const layers = [
    { id: "hw", label: "硬件层", color: "#854F0B", bg: "#FAEEDA", desc: "SysTick / PendSV / NVIC / MSP·PSP", philosophy: "道生一：硬件提供最原始的时间脉搏（SysTick）和切换机制（PendSV），如同心跳之于生命。没有这一层，一切调度都是空谈。" },
    { id: "port", label: "移植层 (Port)", color: "#993C1D", bg: "#FAECE7", desc: "port.c / portmacro.h / portASM.s", philosophy: "一生二：移植层是FreeRTOS的'翻译官'，将抽象的OS概念翻译成具体芯片能理解的指令。它遵循'依赖倒置原则'——内核不依赖硬件，硬件适配内核。" },
    { id: "kernel", label: "内核层", color: "#185FA5", bg: "#E6F1FB", desc: "tasks.c / queue.c / list.c / timers.c", philosophy: "二生三：内核是FreeRTOS的'心智'。它只做三件事——决定谁运行（调度）、如何通信（IPC）、如何共享（同步）。简洁即力量，少即是多（Less is More）。" },
    { id: "app", label: "应用层", color: "#0F6E56", bg: "#E1F5EE", desc: "你的任务代码 / 业务逻辑", philosophy: "三生万物：应用层是'无限可能'的世界。内核给你确定性（Determinism），你用它创造复杂系统。正如老子所言：'道常无为而无不为'——内核不做业务，但让一切业务成为可能。" },
  ];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px", color: "var(--color-text-primary)" }}>
        FreeRTOS 设计哲学：道法自然
      </h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 20px" }}>
        FreeRTOS 的设计哲学可以用老子的"道生一，一生二，二生三，三生万物"来理解。
        整个系统从硬件的一个时钟脉冲出发，层层抽象，最终支撑起无穷的应用可能。
        它的核心信条是：<strong style={{ color: "var(--color-text-primary)" }}>最小化内核，最大化确定性</strong>。
      </p>

      {/* Architecture Stack */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 24 }}>
        {[...layers].reverse().map((l, i) => (
          <div
            key={l.id}
            onClick={() => setActiveLayer(activeLayer === l.id ? null : l.id)}
            style={{
              background: activeLayer === l.id ? l.bg : "var(--color-background-secondary)",
              border: `0.5px solid ${activeLayer === l.id ? l.color : "var(--color-border-tertiary)"}`,
              borderRadius: 8,
              padding: "12px 16px",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontWeight: 500, fontSize: 14, color: activeLayer === l.id ? l.color : "var(--color-text-primary)" }}>
                {l.label}
              </span>
              <span style={{ fontSize: 12, color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)" }}>{l.desc}</span>
            </div>
            {activeLayer === l.id && (
              <p style={{ fontSize: 13, color: l.color, lineHeight: 1.7, margin: "10px 0 0", padding: "10px 0 0", borderTop: `0.5px solid ${l.color}33` }}>
                {l.philosophy}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Core Design Principles */}
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 12px" }}>核心设计原则（为什么这么设计？）</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {[
          { title: "确定性优先", desc: "RTOS的存在意义不是'快'，而是'准时'。一个100μs完成但时间不确定的系统，不如一个始终200μs完成的系统。正如孔子说'不患寡而患不均'。", tag: "Determinism" },
          { title: "最小内核", desc: "FreeRTOS整个内核只有5个.c文件。这不是偷懒，而是刻意为之——每多一行代码就多一个bug的可能。'大道至简'是它的灵魂。", tag: "Minimalism" },
          { title: "零成本抽象", desc: "宏替代函数调用，编译期配置替代运行时判断。你不用的功能不会产生任何开销——'你不为你不用的东西付费'（C++哲学的嵌入式版本）。", tag: "Zero-cost" },
          { title: "可移植性", desc: "内核与硬件通过Port层解耦。这是'依赖倒置原则'的完美实践：高层模块不依赖低层模块，两者都依赖抽象。", tag: "Portability" },
        ].map((p) => (
          <div key={p.tag} style={{
            background: "var(--color-background-secondary)",
            borderRadius: 8,
            padding: "12px 14px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-info)", background: "var(--color-background-info)", padding: "2px 6px", borderRadius: 4 }}>{p.tag}</span>
              <span style={{ fontSize: 14, fontWeight: 500 }}>{p.title}</span>
            </div>
            <p style={{ fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>{p.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Scheduler Section ───
function SchedulerSection() {
  const [selectedPri, setSelectedPri] = useState(3);
  const [tickCount, setTickCount] = useState(0);
  const [running, setRunning] = useState(false);
  const timerRef = useRef(null);

  const tasks = [
    { name: "Idle", pri: 0, color: "#B4B2A9", bg: "#F1EFE8" },
    { name: "Logger", pri: 1, color: "#0F6E56", bg: "#E1F5EE" },
    { name: "Sensor", pri: 2, color: "#185FA5", bg: "#E6F1FB" },
    { name: "Motor", pri: 3, color: "#993C1D", bg: "#FAECE7" },
    { name: "Safety", pri: 4, color: "#A32D2D", bg: "#FCEBEB" },
  ];

  useEffect(() => {
    if (running) {
      timerRef.current = setInterval(() => setTickCount(t => t + 1), 500);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [running]);

  const readyTasks = tasks.filter(t => t.pri <= selectedPri);
  const runningTask = readyTasks[readyTasks.length - 1];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>调度器：FreeRTOS 的"裁判官"</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        调度器的哲学是<strong style={{ color: "var(--color-text-primary)" }}>"能者上，庸者下"</strong>——永远让优先级最高的就绪任务运行。
        这是一种"贤能政治"（Meritocracy），不是民主轮流。
      </p>

      {/* Ready List Visualization */}
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>就绪链表数组 <code style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>pxReadyTasksLists[configMAX_PRIORITIES]</code></span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={() => { setRunning(!running); if (!running) setTickCount(0); }}
              style={{ fontSize: 12, padding: "4px 10px", borderRadius: 6, border: "0.5px solid var(--color-border-secondary)", background: running ? "var(--color-background-danger)" : "var(--color-background-primary)", color: running ? "var(--color-text-danger)" : "var(--color-text-primary)", cursor: "pointer" }}>
              {running ? "停止" : "模拟运行"}
            </button>
            {running && <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>Tick: {tickCount}</span>}
          </div>
        </div>

        {tasks.map((t, i) => {
          const isRunning = runningTask?.name === t.name;
          return (
            <div key={t.name} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ width: 28, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", textAlign: "right" }}>[{t.pri}]</span>
              <div style={{
                flex: 1, display: "flex", alignItems: "center", gap: 8,
                background: isRunning ? t.bg : "transparent",
                border: `0.5px solid ${isRunning ? t.color : "var(--color-border-tertiary)"}`,
                borderRadius: 6, padding: "6px 10px",
                transition: "all 0.3s",
              }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: t.pri <= selectedPri ? t.color : "var(--color-border-tertiary)", transition: "background 0.3s" }} />
                <span style={{ fontSize: 13, fontWeight: isRunning ? 500 : 400, color: isRunning ? t.color : "var(--color-text-primary)" }}>{t.name}</span>
                {isRunning && (
                  <span style={{ marginLeft: "auto", fontSize: 11, fontFamily: "var(--font-mono)", color: t.color, background: `${t.color}15`, padding: "1px 6px", borderRadius: 4 }}>
                    RUNNING
                  </span>
                )}
                {t.pri <= selectedPri && !isRunning && (
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--color-text-secondary)" }}>READY</span>
                )}
                {t.pri > selectedPri && (
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--color-text-tertiary)" }}>BLOCKED</span>
                )}
              </div>
            </div>
          );
        })}
        <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>最高就绪优先级</span>
          <input type="range" min={0} max={4} value={selectedPri} onChange={e => setSelectedPri(+e.target.value)}
            style={{ flex: 1 }} />
          <span style={{ fontSize: 13, fontWeight: 500, fontFamily: "var(--font-mono)", minWidth: 16 }}>{selectedPri}</span>
        </div>
      </div>

      {/* Scheduling Algorithm */}
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 10px" }}>调度算法的本质（O(1) 复杂度）</h3>
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "14px 16px", fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.8, color: "var(--color-text-secondary)", marginBottom: 16, overflowX: "auto", whiteSpace: "pre" }}>
{`// 核心调度逻辑（tasks.c 中 taskSELECT_HIGHEST_PRIORITY_TASK）
// 方法一：通用版 —— 从最高优先级向下遍历
UBaseType_t uxTopPriority = uxTopReadyPriority; // 记录的最高优先级
while(listLIST_IS_EMPTY(&pxReadyTasksLists[uxTopPriority])) {
    --uxTopPriority;  // 找到第一个非空链表
}
// 取该优先级链表的下一个节点（Round-Robin轮转）
listGET_OWNER_OF_NEXT_ENTRY(pxCurrentTCB, &pxReadyTasksLists[uxTopPriority]);

// 方法二：硬件优化版 —— CLZ指令（Cortex-M）
// 用一个32位位图记录哪些优先级有就绪任务
// __clz() 前导零计数 → O(1) 找到最高优先级
// 这就是 configUSE_PORT_OPTIMISED_TASK_SELECTION = 1 的秘密`}
      </div>

      <div style={{ padding: "12px 14px", background: "var(--color-background-info)", borderRadius: 8, marginBottom: 16 }}>
        <p style={{ fontSize: 13, color: "var(--color-text-info)", lineHeight: 1.6, margin: 0 }}>
          <strong>哲学洞察：</strong> 调度器使用"位图+CLZ"实现 O(1) 查找——这是"空间换时间"的经典案例。
          32位位图只需4字节，却让调度速度从 O(n) 降到了单条汇编指令。
          正如庄子所言"无用之用，方为大用"——那4字节的'额外空间'让整个系统获得了确定性。
        </p>
      </div>

      {/* Time Slice */}
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 10px" }}>时间片轮转（Round-Robin）</h3>
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 12px" }}>
        当多个任务优先级相同时，FreeRTOS 使用时间片轮转。每个 SysTick 中断（1ms 典型值）触发一次调度检查。
        链表中的 <code style={{ fontSize: 12 }}>listGET_OWNER_OF_NEXT_ENTRY</code> 会移动到下一个节点——这就是"公平"的实现。
      </p>
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "12px 16px", fontSize: 12, fontFamily: "var(--font-mono)", lineHeight: 1.8, color: "var(--color-text-secondary)", whiteSpace: "pre" }}>
{`SysTick_Handler() → xTaskIncrementTick()
├── 递增 xTickCount
├── 检查延时链表：有任务到期？→ 移到就绪链表
├── 同优先级有多个任务？→ 切换到下一个（Round-Robin）
└── 需要切换？→ 设置 PendSV 标志位
    （portYIELD() 实质是 SCB->ICSR |= (1<<28)）

设计智慧：SysTick只"标记"需要切换，不做切换本身。
实际切换在PendSV（最低优先级）中完成。
这就是"延迟切换"——确保所有高优先级中断先处理完。`}
      </div>
    </div>
  );
}

// ─── Context Switch Section ───
function ContextSection() {
  const [step, setStep] = useState(0);
  const steps = [
    { title: "1. 触发 PendSV", code: "SCB->ICSR |= (1 << 28)", desc: "调度器通过设置 ICSR 寄存器的 PENDSVSET 位来请求上下文切换。PendSV 被设为最低优先级（0xFF），所以它只在所有其他中断处理完后才执行。", philosophy: "为什么用PendSV而不是SysTick直接切换？这体现了'让路'的哲学——SysTick中断可能嵌套在其他中断之中，此时切换会破坏中断的原子性。PendSV等所有人忙完再行动，像谦让的智者。" },
    { title: "2. 硬件自动入栈", code: "自动保存: R0-R3, R12, LR, PC, xPSR → PSP", desc: "ARM Cortex-M 硬件在进入异常时自动将8个寄存器压入当前任务的进程栈（PSP）。这是硬件免费帮你做的——你无需写一行代码。", philosophy: "硬件与软件的分工：硬件做它擅长的（固定模式的寄存器保存），软件做它擅长的（灵活的调度决策）。这是'各司其职'的体现——ARM架构设计者深谙此道。" },
    { title: "3. 软件保存剩余寄存器", code: "MRS R0, PSP\nSTMDB R0!, {R4-R11}\nSTR R0, [R2] // → TCB.pxTopOfStack", desc: "R4-R11 不在硬件自动保存范围内，需要软件手动保存到任务栈。保存后，更新 TCB 中的栈顶指针。", philosophy: "为什么R4-R11不自动保存？因为ARM的AAPCS调用约定规定它们是'被调用者保存'寄存器——只有确实需要时才保存，避免浪费。这是'懒加载'思想的硬件级体现。" },
    { title: "4. 选择新任务", code: "BL vTaskSwitchContext\n// → 更新 pxCurrentTCB", desc: "调用 C 函数选择下一个要运行的任务。这个函数从就绪链表中取最高优先级任务，更新全局指针 pxCurrentTCB。", philosophy: "汇编与C的边界：上下文保存/恢复用汇编（因为需要精确控制寄存器），调度决策用C（因为需要遍历链表）。这是'用正确的工具做正确的事'的工程智慧。" },
    { title: "5. 恢复新任务上下文", code: "LDR R0, [R1] // 新任务栈顶\nLDMIA R0!, {R4-R11}\nMSR PSP, R0", desc: "从新任务的TCB中取出栈顶指针，恢复R4-R11，然后更新PSP指向新任务的栈。", philosophy: "对称之美：保存是STMDB（先减后存），恢复是LDMIA（先取后增），完美的逆操作。栈的LIFO特性在此展现了数学般的优雅。" },
    { title: "6. 异常返回", code: "BX LR // LR = EXC_RETURN\n// 硬件自动恢复 R0-R3,R12,LR,PC,xPSR", desc: "通过特殊的 EXC_RETURN 值返回，硬件自动从PSP恢复之前保存的8个寄存器。新任务从上次被中断的地方继续运行。", philosophy: "EXC_RETURN是一个'魔法数字'（如0xFFFFFFFD），它告诉硬件：返回线程模式、使用PSP、非FPU上下文。一个32位数编码了整个返回策略——这是信息密度的艺术。" },
  ];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>上下文切换：RTOS 的"灵魂摆渡"</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        上下文切换是FreeRTOS最精妙的操作——在纳秒级别将一个任务的"灵魂"（寄存器状态）保存，
        并注入另一个任务的"灵魂"。整个过程不到<strong style={{ color: "var(--color-text-primary)" }}>1微秒</strong>（Cortex-M4 @ 168MHz）。
      </p>

      {/* Step Navigator */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, flexWrap: "wrap" }}>
        {steps.map((s, i) => (
          <button key={i} onClick={() => setStep(i)} style={{
            flex: "1 1 auto", minWidth: 80, padding: "8px 6px", borderRadius: 6, fontSize: 11,
            border: `0.5px solid ${step === i ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
            background: step === i ? "var(--color-background-info)" : "var(--color-background-primary)",
            color: step === i ? "var(--color-text-info)" : "var(--color-text-secondary)",
            cursor: "pointer", fontWeight: step === i ? 500 : 400,
          }}>
            Step {i + 1}
          </button>
        ))}
      </div>

      {/* Current Step Detail */}
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 500, margin: "0 0 8px", color: "var(--color-text-primary)" }}>
          {steps[step].title}
        </h3>
        <div style={{ background: "var(--color-background-primary)", borderRadius: 8, padding: "10px 14px", fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.8, color: "var(--color-text-info)", marginBottom: 10, whiteSpace: "pre-wrap", border: "0.5px solid var(--color-border-tertiary)" }}>
          {steps[step].code}
        </div>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 12px" }}>
          {steps[step].desc}
        </p>
        <div style={{ padding: "10px 12px", background: "var(--color-background-warning)", borderRadius: 8 }}>
          <p style={{ fontSize: 12, color: "var(--color-text-warning)", lineHeight: 1.6, margin: 0 }}>
            {steps[step].philosophy}
          </p>
        </div>
      </div>

      {/* Stack Layout Diagram */}
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 10px" }}>任务栈内存布局</h3>
      <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 500, textAlign: "center", marginBottom: 6, color: "var(--color-text-info)" }}>硬件自动保存</div>
          {["xPSR", "PC (返回地址)", "LR", "R12", "R3", "R2", "R1", "R0"].map((r, i) => (
            <div key={r} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
              <span style={{ width: 20, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-tertiary)", textAlign: "right" }}>+{(7-i)*4}</span>
              <div style={{ flex: 1, textAlign: "center", padding: "4px 0", fontSize: 12, fontFamily: "var(--font-mono)", background: "var(--color-background-info)", color: "var(--color-text-info)", borderRadius: 4, border: "0.5px solid var(--color-border-info)" }}>{r}</div>
            </div>
          ))}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 500, textAlign: "center", marginBottom: 6, color: "var(--color-text-warning)" }}>软件手动保存</div>
          {["R11", "R10", "R9", "R8", "R7", "R6", "R5", "R4"].map((r, i) => (
            <div key={r} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
              <span style={{ width: 20, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-tertiary)", textAlign: "right" }}>-{(i+1)*4}</span>
              <div style={{ flex: 1, textAlign: "center", padding: "4px 0", fontSize: 12, fontFamily: "var(--font-mono)", background: "var(--color-background-warning)", color: "var(--color-text-warning)", borderRadius: 4, border: "0.5px solid var(--color-border-warning)" }}>{r}</div>
            </div>
          ))}
          <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 20 }}></span>
            <div style={{ flex: 1, textAlign: "center", padding: "3px 0", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-danger)", borderTop: "2px solid var(--color-border-danger)" }}>← pxTopOfStack 指向这里</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Memory Section ───
function MemorySection() {
  const [selectedHeap, setSelectedHeap] = useState(3);
  const heaps = [
    { id: 0, name: "heap_1", title: "只分配不释放", algo: "顺序分配", frag: "无", safe: "★★★★★", use: "任务数固定的简单系统", detail: "维护一个指针 pucAlignedHeap，每次分配向后移动。永远不释放。\n\n哲学：有时'不做某事'就是最好的设计。如果你的系统从不需要释放内存，那么释放逻辑就是100%的bug隐患。heap_1是'奥卡姆剃刀'原则的体现——如无必要，勿增实体。", code: "void *pvReturn = pucAlignedHeap + xNextFreeByte;\nxNextFreeByte += xWantedSize;\n// 就这么简单。没有链表，没有碎片，没有bug。" },
    { id: 1, name: "heap_2", title: "最佳匹配", algo: "Best Fit", frag: "严重", safe: "★★☆☆☆", use: "已废弃，仅供理解", detail: "空闲块链表按大小排序，分配时找最接近的块。释放不合并相邻块。\n\n哲学：heap_2是一个'反面教材'——它告诉我们，释放内存而不合并空闲块，会让碎片化像熵增一样不可逆。这是热力学第二定律在内存管理中的映射。", code: "// 遍历空闲链表，找到 size >= xWantedSize 的最小块\n// 问题：反复分配释放后，产生大量无法使用的小碎片\n// 比如：释放了100个8字节块，却无法分配一个800字节块" },
    { id: 2, name: "heap_3", title: "封装标准库", algo: "malloc/free", frag: "依赖库", safe: "★★☆☆☆", use: "需兼容标准库代码", detail: "直接调用编译器的 malloc/free，只是在外面加了 vTaskSuspendAll/xTaskResumeAll 保证线程安全。\n\n哲学：有时最好的代码是'不写代码'。heap_3承认标准库的malloc可能比自己写得更好（在通用场景下），但用调度器锁来补全线程安全——这是'组合优于继承'的体现。", code: "void *pvPortMalloc(size_t xSize) {\n    vTaskSuspendAll();  // 暂停调度器\n    pvReturn = malloc(xSize);  // 调用标准库\n    xTaskResumeAll();\n    return pvReturn;\n}" },
    { id: 3, name: "heap_4", title: "合并空闲块", algo: "First Fit + 合并", frag: "低", safe: "★★★★☆", use: "推荐方案（绝大多数项目）", detail: "在一个静态数组 ucHeap[configTOTAL_HEAP_SIZE] 上管理内存。空闲块链表按地址排序。释放时自动合并相邻空闲块。\n\n哲学：heap_4体现了'中庸之道'——它既不像heap_1那样极端简单，也不像heap_3那样完全依赖外部。它在可控性与灵活性之间找到了最佳平衡点。合并空闲块的设计说明了一个道理：局部的'整理'可以对抗全局的'混乱'（反熵）。", code: "// 释放时的合并逻辑：\n// 1. 将释放的块插入按地址排序的空闲链表\n// 2. 检查前一个空闲块：如果紧邻，合并\n// 3. 检查后一个空闲块：如果紧邻，合并\n// 效果：碎片化被持续修复，像GC一样但无暂停" },
    { id: 4, name: "heap_5", title: "多区域合并", algo: "同heap_4 + 多区域", frag: "低", safe: "★★★★☆", use: "多块不连续RAM", detail: "与heap_4算法相同，但可以跨多个不连续的内存区域工作（如SRAM1+SRAM2+外部SDRAM）。\n\n哲学：heap_5是'适配器模式'——它不改变核心算法，只是扩展了数据源。这体现了软件工程中的'开放-封闭原则'：对扩展开放（支持新的内存区域），对修改封闭（算法不变）。", code: "// 初始化时告诉heap_5有哪些内存区域：\nHeapRegion_t xHeapRegions[] = {\n    { (uint8_t *)0x20000000, 64 * 1024 }, // SRAM1\n    { (uint8_t *)0x20010000, 32 * 1024 }, // SRAM2\n    { (uint8_t *)0xC0000000,  8 * 1024 * 1024 }, // SDRAM\n    { NULL, 0 } // 结束标记\n};\nvPortDefineHeapRegions(xHeapRegions);" },
  ];

  const h = heaps[selectedHeap];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>内存管理：五种 Heap 的哲学</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        FreeRTOS 提供5种内存管理方案，它们不是"进化关系"，而是<strong style={{ color: "var(--color-text-primary)" }}>不同哲学的体现</strong>。
        选择哪个 heap，反映了你对系统的理解深度。
      </p>

      {/* Heap Selector */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {heaps.map((hp, i) => (
          <button key={i} onClick={() => setSelectedHeap(i)} style={{
            flex: 1, padding: "8px 4px", borderRadius: 8, fontSize: 12, fontWeight: selectedHeap === i ? 500 : 400,
            border: `0.5px solid ${selectedHeap === i ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
            background: selectedHeap === i ? "var(--color-background-info)" : "var(--color-background-primary)",
            color: selectedHeap === i ? "var(--color-text-info)" : "var(--color-text-secondary)",
            cursor: "pointer",
          }}>
            {hp.name}
          </button>
        ))}
      </div>

      {/* Heap Detail */}
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
          <h3 style={{ fontSize: 15, fontWeight: 500, margin: 0 }}>{h.name}: {h.title}</h3>
          <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>安全性 {h.safe}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
          {[{ l: "算法", v: h.algo }, { l: "碎片化", v: h.frag }, { l: "适用场景", v: h.use }].map(item => (
            <div key={item.l} style={{ background: "var(--color-background-primary)", borderRadius: 6, padding: "8px 10px" }}>
              <div style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>{item.l}</div>
              <div style={{ fontSize: 13, fontWeight: 500, marginTop: 2 }}>{item.v}</div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 12px", whiteSpace: "pre-wrap" }}>{h.detail}</p>
        <div style={{ background: "var(--color-background-primary)", borderRadius: 8, padding: "10px 14px", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.8, color: "var(--color-text-secondary)", whiteSpace: "pre-wrap", border: "0.5px solid var(--color-border-tertiary)" }}>
          {h.code}
        </div>
      </div>

      {/* BlockLink_t Structure */}
      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 10px" }}>空闲块链表结构（heap_4/5 核心）</h3>
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.8, whiteSpace: "pre", color: "var(--color-text-secondary)" }}>
{`typedef struct A_BLOCK_LINK {
    struct A_BLOCK_LINK *pxNextFreeBlock; // 指向下一个空闲块
    size_t xBlockSize;  // 本块大小（最高位=已分配标志）
} BlockLink_t;  // 大小 = 8 字节（32位系统）

内存布局：
┌─────────────┬───────────────────────┬─────────────┐
│ BlockLink_t │    用户可用空间        │ BlockLink_t │ ...
│ (8 bytes)   │   (xWantedSize)       │ (8 bytes)   │
└─────────────┴───────────────────────┴─────────────┘
│← 一个分配块 →│                       │← 下一个块  →│

关键细节：
• xBlockSize 最高位(bit31) = 1 表示已分配，0 表示空闲
• 所有块 8 字节对齐（portBYTE_ALIGNMENT = 8）
• 最小块 = sizeof(BlockLink_t) = 8 字节`}
      </div>
    </div>
  );
}

// ─── IPC Section ───
function IPCSection() {
  const [activeIPC, setActiveIPC] = useState("queue");
  const ipcs = {
    queue: {
      title: "队列 (Queue)",
      subtitle: "万物之基",
      desc: "Queue是FreeRTOS所有IPC的基石——Semaphore、Mutex、EventGroup底层都基于Queue实现。",
      philosophy: "Queue体现了'生产者-消费者'这一人类社会最古老的协作模式。卖包子的（生产者）不需要认识吃包子的（消费者），他们通过'蒸笼'（Queue）解耦。这就是'中间人模式'——降低耦合，提高灵活性。",
      detail: `Queue 数据结构 (queue.c)：
typedef struct QueueDefinition {
    int8_t *pcHead;        // 环形缓冲区头指针
    int8_t *pcWriteTo;     // 下一次写入位置
    int8_t *pcReadFrom;    // 上一次读取位置
    List_t xTasksWaitingToSend;    // 等待发送的任务链表
    List_t xTasksWaitingToReceive; // 等待接收的任务链表
    UBaseType_t uxMessagesWaiting; // 当前消息数
    UBaseType_t uxLength;          // 最大消息数
    UBaseType_t uxItemSize;        // 每条消息大小
    // ...
} Queue_t;

关键行为：
• 发送时队列满 → 任务进入 xTasksWaitingToSend 链表（阻塞）
• 接收时队列空 → 任务进入 xTasksWaitingToReceive 链表（阻塞）
• 数据通过 memcpy 拷贝（值传递，非指针！）
  → 这意味着发送后原始数据可以安全修改
  → 代价：大数据应传指针，小数据直接拷贝
• 环形缓冲区实现：写到末尾后回到开头（取模）`,
    },
    semaphore: {
      title: "信号量 (Semaphore)",
      subtitle: "计数的艺术",
      desc: "信号量本质上是一个特殊的Queue：uxItemSize=0，uxMessagesWaiting就是计数值。",
      philosophy: "信号量源自荷兰计算机科学家Dijkstra的P/V操作。P(proberen=尝试)减计数，V(verhogen=增加)加计数。它的哲学是'数量控制'——就像停车场的计数器：有空位才能进，出来一辆才能再进一辆。",
      detail: `二值信号量 vs 计数信号量：

二值信号量（Binary Semaphore）：
• 计数值只有 0 或 1
• 典型用途：ISR → Task 同步（中断发生→通知任务处理）
• 创建：xSemaphoreCreateBinary() → 初始值 = 0（空）
• Give = 设为1，Take = 等待变为1然后设为0
• ⚠️ 无优先级继承！高优先级任务等待时不会提升持有者

计数信号量（Counting Semaphore）：
• 计数值 0 ~ uxMaxCount
• 典型用途：资源池管理（如DMA通道数、连接池大小）
• 创建：xSemaphoreCreateCounting(maxCount, initialCount)

底层实现揭秘：
xSemaphoreCreateBinary() →
    xQueueGenericCreate(1, 0, queueQUEUE_TYPE_BINARY_SEMAPHORE)
// 长度=1，元素大小=0 的队列！
// Give = xQueueSend（写入一个0字节的"消息"）
// Take = xQueueReceive（读取那个"消息"）`,
    },
    mutex: {
      title: "互斥锁 (Mutex)",
      subtitle: "所有权的哲学",
      desc: "Mutex与Binary Semaphore的关键区别：Mutex有'所有者'概念，支持优先级继承。",
      philosophy: "Mutex体现了'产权'哲学——只有锁的持有者才能释放它。这不是技术限制，而是设计意图：如果任何人都能释放锁，就像任何人都能卖你的房子一样危险。产权清晰是秩序的基础。",
      detail: `Mutex vs Binary Semaphore 的本质区别：

Binary Semaphore：
• 谁都可以 Give（释放）→ 适合"通知"场景
• ISR → Task：ISR Give，Task Take
• 无所有者，无优先级继承

Mutex：
• 只有持有者才能释放 → 适合"互斥"场景
• 具有优先级继承（Priority Inheritance）
• 支持递归锁（Recursive Mutex）

优先级继承机制：
┌──────────────────────────────────────────────────┐
│ 任务H(高) 要获取 Mutex，但被 任务L(低) 持有       │
│ → FreeRTOS 临时提升 L 的优先级 = H 的优先级       │
│ → L 以高优先级运行，尽快释放 Mutex                │
│ → L 释放后，优先级恢复原值                        │
│ → H 获得 Mutex，继续运行                         │
└──────────────────────────────────────────────────┘

⚠️ FreeRTOS 的优先级继承是"一级"的：
如果 H 等待 M 持有的 Mutex，M 又等待 L 持有的 Mutex，
L 不会被提升。这叫"链式优先级反转"，FreeRTOS 不处理。
完整的优先级继承协议(PIP)需要AUTOSAR OSEK的Priority Ceiling。`,
    },
    notification: {
      title: "任务通知 (Task Notification)",
      subtitle: "极速之道",
      desc: "每个任务内置一个32位通知值+pending标志，比Queue快45%，零动态分配。",
      philosophy: "Task Notification是'够用就好'（YAGNI）哲学的极致体现。大多数IPC场景其实很简单——一个任务通知另一个任务'有活了'。为此创建Queue对象是杀鸡用牛刀。通知值直接嵌入TCB，无需分配内存、无需遍历链表、无需拷贝数据。",
      detail: `三种使用模式：

1. 轻量信号量模式：
   vTaskNotifyGive(taskHandle)     // +1
   ulTaskNotifyTake(pdTRUE, timeout) // 取并清零

2. 事件标志模式（32位，每位一个事件）：
   xTaskNotify(handle, EVT_BIT, eSetBits)    // 设位
   xTaskNotifyWait(0, 0xFFFF, &val, timeout) // 等待

3. 邮箱模式（传递一个32位值）：
   xTaskNotify(handle, value, eSetValueWithOverwrite)
   xTaskNotifyWait(0, 0, &val, timeout)

性能对比（STM32F4 @ 168MHz）：
┌──────────────────────┬──────────┬────────────┐
│ 操作                 │ Queue    │ Notification│
├──────────────────────┼──────────┼────────────┤
│ ISR→Task 唤醒        │ ~2.1 μs  │ ~1.2 μs    │
│ Task→Task 发送       │ ~1.8 μs  │ ~1.0 μs    │
│ RAM 占用             │ 76+ bytes│ 0 bytes    │
└──────────────────────┴──────────┴────────────┘

限制：
• 只能一对一（一个发送方→一个接收方）
• 无法广播（用 EventGroup 解决）
• 无法像 Queue 一样缓冲多条消息`,
    },
  };

  const ipc = ipcs[activeIPC];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>IPC：任务间通信的四种武器</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        任务是独立的个体，但系统需要协作。IPC就是任务之间的"语言"——不同的IPC适合不同的"对话方式"。
      </p>

      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {Object.entries(ipcs).map(([k, v]) => (
          <button key={k} onClick={() => setActiveIPC(k)} style={{
            flex: 1, padding: "10px 4px", borderRadius: 8, fontSize: 12,
            border: `0.5px solid ${activeIPC === k ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
            background: activeIPC === k ? "var(--color-background-info)" : "var(--color-background-primary)",
            color: activeIPC === k ? "var(--color-text-info)" : "var(--color-text-secondary)",
            cursor: "pointer", fontWeight: activeIPC === k ? 500 : 400,
          }}>
            <div>{v.title.split(" ")[0]}</div>
            <div style={{ fontSize: 10, marginTop: 2, opacity: 0.7 }}>{v.subtitle}</div>
          </button>
        ))}
      </div>

      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 500, margin: "0 0 4px" }}>{ipc.title}</h3>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 12px" }}>{ipc.desc}</p>
        <div style={{ padding: "10px 12px", background: "var(--color-background-warning)", borderRadius: 8, marginBottom: 12 }}>
          <p style={{ fontSize: 12, color: "var(--color-text-warning)", lineHeight: 1.6, margin: 0 }}>{ipc.philosophy}</p>
        </div>
        <div style={{ background: "var(--color-background-primary)", borderRadius: 8, padding: "10px 14px", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.7, color: "var(--color-text-secondary)", whiteSpace: "pre-wrap", border: "0.5px solid var(--color-border-tertiary)", maxHeight: 360, overflowY: "auto" }}>
          {ipc.detail}
        </div>
      </div>
    </div>
  );
}

// ─── Timer Section ───
function TimerSection() {
  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>软件定时器：时间的委托者</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        软件定时器不是硬件定时器——它由一个专门的<strong style={{ color: "var(--color-text-primary)" }}>守护任务</strong>（Timer Service Task）管理。
        这是"委托模式"（Delegation）的经典应用。
      </p>

      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.8, color: "var(--color-text-secondary)", whiteSpace: "pre" }}>
{`架构：
                                    Timer Service Task
  用户任务/ISR                     (优先级: configTIMER_TASK_PRIORITY)
  ┌──────────┐    命令队列           ┌──────────────────┐
  │ 启动定时器├──→ xTimerQueue ──→  │ 处理命令：        │
  │ 停止定时器│    (长度=             │ • 启动/停止/重置  │
  │ 重置定时器│     configTIMER_      │ • 检查到期列表    │
  │ 改变周期  │     QUEUE_LENGTH)     │ • 执行回调函数    │
  └──────────┘                      └──────────────────┘

时间管理（溢出处理）：
┌───────────────────────────────────────────────────────┐
│ 两个链表轮流使用：                                      │
│ • pxCurrentTimerList    → 当前 tick 周期的定时器       │
│ • pxOverflowTimerList   → 下一个溢出周期的定时器       │
│                                                        │
│ 当 xTickCount 溢出(从 0xFFFFFFFF → 0)时，              │
│ 两个链表指针交换！                                      │
│                                                        │
│ 这和 vTaskIncrementTick() 中的延时链表管理完全一样      │
│ ——同一个"双链表溢出处理"模式被复用了两次。              │
│ 这就是设计模式的力量：一个好的解决方案可以重复使用。      │
└───────────────────────────────────────────────────────┘

回调函数注意事项：
• 回调运行在 Timer Task 上下文（不是ISR！）
• 可以调用普通API（不需要 FromISR 版本）
• ⚠️ 不可调用阻塞API（vTaskDelay/xQueueReceive等）
  → 因为会阻塞整个 Timer Task，影响所有定时器
• 回调应尽可能短：发送消息到队列，让工作任务处理
• 精度：± 1 tick（configTICK_RATE_HZ=1000 → ±1ms）`}
        </div>
      </div>

      <div style={{ padding: "12px 14px", background: "var(--color-background-info)", borderRadius: 8 }}>
        <p style={{ fontSize: 13, color: "var(--color-text-info)", lineHeight: 1.6, margin: 0 }}>
          <strong>哲学洞察：</strong> Timer Service Task的设计体现了"单一职责"和"命令模式"。
          所有定时器操作都被编码为"命令"发送到队列，由单独的任务处理。这样的好处是：
          ISR中可以安全地操作定时器（通过命令队列），而不需要在中断上下文中做复杂的链表操作。
          正如管理学中的"不要亲自做，而是下达命令"——异步解耦是复杂系统的救星。
        </p>
      </div>
    </div>
  );
}

// ─── Critical Section ───
function CriticalSection() {
  const [basepri, setBasepri] = useState(5);
  const interrupts = [
    { name: "NMI", pri: -1, desc: "不可屏蔽" },
    { name: "HardFault", pri: -1, desc: "不可屏蔽" },
    { name: "SPI_DMA", pri: 2, desc: "高优先级外设" },
    { name: "UART_RX", pri: 4, desc: "串口接收" },
    { name: "SysTick", pri: 5, desc: "OS 节拍" },
    { name: "PendSV", pri: 7, desc: "上下文切换" },
    { name: "I2C_EV", pri: 6, desc: "I2C事件" },
  ];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>临界区：BASEPRI 的精妙设计</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        FreeRTOS 不使用 <code style={{ fontSize: 12 }}>__disable_irq()</code>（PRIMASK）来进入临界区，
        而是使用 <code style={{ fontSize: 12 }}>BASEPRI</code> 寄存器——这是一个<strong style={{ color: "var(--color-text-primary)" }}>天才级的设计决策</strong>。
      </p>

      {/* Interactive BASEPRI Demo */}
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>BASEPRI 值 (configMAX_SYSCALL_INTERRUPT_PRIORITY)</span>
          <input type="range" min={1} max={7} value={basepri} onChange={e => setBasepri(+e.target.value)} style={{ flex: 1 }} />
          <span style={{ fontSize: 14, fontWeight: 500, fontFamily: "var(--font-mono)", minWidth: 16 }}>{basepri}</span>
        </div>

        <div style={{ fontSize: 12, marginBottom: 8, color: "var(--color-text-secondary)" }}>
          优先级数值 ≥ {basepri} 的中断被屏蔽（ARM：数字越小 = 优先级越高）
        </div>

        {interrupts.map(irq => {
          const blocked = irq.pri >= basepri && irq.pri >= 0;
          const unblockable = irq.pri < 0;
          return (
            <div key={irq.name} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
              <span style={{ width: 30, textAlign: "right", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-tertiary)" }}>
                {irq.pri < 0 ? "fix" : irq.pri}
              </span>
              <div style={{
                flex: 1, display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "5px 10px", borderRadius: 6,
                background: unblockable ? "var(--color-background-danger)" : blocked ? "var(--color-background-secondary)" : "var(--color-background-success)",
                border: `0.5px solid ${unblockable ? "var(--color-border-danger)" : blocked ? "var(--color-border-tertiary)" : "var(--color-border-success)"}`,
                opacity: blocked && !unblockable ? 0.5 : 1,
                transition: "all 0.3s",
              }}>
                <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 500 }}>{irq.name}</span>
                <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
                  {unblockable ? "永不屏蔽" : blocked ? "已屏蔽" : "可响应"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.8, color: "var(--color-text-secondary)", whiteSpace: "pre", marginBottom: 16 }}>
{`为什么用 BASEPRI 而不是 PRIMASK？

PRIMASK（__disable_irq）：
• 屏蔽 ALL 可配置中断
• 包括时间关键的高优先级中断（如电机控制、安全监控）
• 临界区期间系统完全"失聪" → 可能错过紧急事件

BASEPRI（FreeRTOS 方式）：
• 只屏蔽优先级 ≥ configMAX_SYSCALL_INTERRUPT_PRIORITY 的中断
• 高优先级中断（数值 < BASEPRI）仍然可以响应
• 系统保留"紧急通道" → 安全相关中断不受影响

代价：
• 高优先级中断中 不能调用 FreeRTOS API
  （因为临界区没保护它们，API调用会导致数据竞争）
• 所以 FreeRTOS 有 FromISR 版本的 API
• configMAX_SYSCALL_INTERRUPT_PRIORITY 划定了"安全线"
  → 高于它：不用 FreeRTOS API，但永远不被屏蔽
  → 低于/等于它：可用 FreeRTOS API，但会被临界区屏蔽`}
      </div>

      <div style={{ padding: "12px 14px", background: "var(--color-background-warning)", borderRadius: 8 }}>
        <p style={{ fontSize: 12, color: "var(--color-text-warning)", lineHeight: 1.6, margin: 0 }}>
          <strong>哲学：</strong> BASEPRI的设计是"分层防御"思想的体现。它承认了一个现实：
          不是所有中断都同等重要。安全相关的中断（如电机过流保护）不能因为"操作系统在忙"就被忽略。
          这就像医院的"急诊通道"——普通排队可以暂停，但急救通道永远畅通。
          这种设计需要程序员理解并正确划分中断优先级——<strong>自由伴随责任</strong>。
        </p>
      </div>
    </div>
  );
}

// ─── Priority Inversion Section ───
function PrioritySection() {
  const [step, setStep] = useState(0);
  const timeline = [
    { time: "t0", h: "—", m: "—", l: "运行", mutex: "L持有", event: "L 获得 Mutex，开始访问共享资源", problem: "" },
    { time: "t1", h: "就绪", m: "—", l: "被抢占", mutex: "L持有", event: "H 就绪，抢占 L（因为 H 优先级更高）", problem: "" },
    { time: "t2", h: "阻塞", m: "—", l: "运行", mutex: "L持有", event: "H 尝试获取 Mutex → 发现 L 持有 → H 阻塞", problem: "L被提升至H的优先级（继承）" },
    { time: "t3", h: "阻塞", m: "就绪", l: "运行(提升)", mutex: "L持有", event: "M 就绪，但 L 此时优先级=H → M 无法抢占", problem: "继承保护：M 被正确阻挡" },
    { time: "t4", h: "运行", m: "就绪", l: "就绪(恢复)", mutex: "H持有", event: "L 释放 Mutex → 优先级恢复 → H 获得 Mutex 运行", problem: "问题解决！" },
  ];

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>优先级反转：RTOS 的"阿喀琉斯之踵"</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        1997年，NASA 的火星探路者号因优先级反转导致系统反复重启，最终靠远程启用优先级继承修复。
        这个Bug告诉我们：<strong style={{ color: "var(--color-text-primary)" }}>调度器的"公平"可能是致命的</strong>。
      </p>

      {/* Timeline */}
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
          {timeline.map((t, i) => (
            <button key={i} onClick={() => setStep(i)} style={{
              flex: 1, padding: "6px 4px", borderRadius: 6, fontSize: 12, fontFamily: "var(--font-mono)",
              border: `0.5px solid ${step === i ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
              background: step === i ? "var(--color-background-info)" : "var(--color-background-primary)",
              color: step === i ? "var(--color-text-info)" : "var(--color-text-secondary)",
              cursor: "pointer",
            }}>
              {t.time}
            </button>
          ))}
        </div>

        {/* Task States */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 12 }}>
          {[
            { label: "H (高优先级)", state: timeline[step].h, color: "#A32D2D", bg: "#FCEBEB" },
            { label: "M (中优先级)", state: timeline[step].m, color: "#854F0B", bg: "#FAEEDA" },
            { label: "L (低优先级)", state: timeline[step].l, color: "#185FA5", bg: "#E6F1FB" },
          ].map(t => (
            <div key={t.label} style={{
              padding: "8px 10px", borderRadius: 8,
              background: t.state.includes("运行") ? t.bg : "var(--color-background-primary)",
              border: `0.5px solid ${t.state.includes("运行") ? t.color : "var(--color-border-tertiary)"}`,
            }}>
              <div style={{ fontSize: 11, color: t.color, fontWeight: 500 }}>{t.label}</div>
              <div style={{ fontSize: 13, fontWeight: t.state.includes("运行") ? 500 : 400, marginTop: 2 }}>{t.state}</div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
          Mutex 状态: <code style={{ fontSize: 11 }}>{timeline[step].mutex}</code>
        </div>
        <div style={{ fontSize: 13, color: "var(--color-text-primary)", lineHeight: 1.6 }}>{timeline[step].event}</div>
        {timeline[step].problem && (
          <div style={{ marginTop: 8, padding: "6px 10px", background: "var(--color-background-success)", borderRadius: 6, fontSize: 12, color: "var(--color-text-success)" }}>
            {timeline[step].problem}
          </div>
        )}
      </div>

      <div style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.8, whiteSpace: "pre", color: "var(--color-text-secondary)" }}>
{`如果没有优先级继承（使用 Binary Semaphore）：

t0: L 获取信号量，运行
t1: H 就绪，抢占 L
t2: H 尝试获取信号量 → 阻塞（L持有）
t3: M 就绪，抢占 L（因为 M > L）
    ← H 被 M 间接阻塞了！H 比 M 优先级高却无法运行！
    ← 这就是"优先级反转"：高优先级反而等低优先级
t4: M 运行很久...
t5: M 完成，L 恢复运行
t6: L 释放信号量 → H 终于运行
    ← H 的响应时间被 M 无限拉长（不确定性！）

解决方案对比：
┌──────────────────┬─────────────────────────────────┐
│ 优先级继承(PIP)  │ Mutex使用。运行时动态提升。       │
│                  │ FreeRTOS实现（单级）             │
├──────────────────┼─────────────────────────────────┤
│ 优先级天花板(PCP)│ 资源预分配最高优先级。静态分析。  │
│                  │ AUTOSAR OSEK使用。无死锁保证。   │
├──────────────────┼─────────────────────────────────┤
│ 禁止中断         │ 简单粗暴。适合极短临界区。       │
└──────────────────┴─────────────────────────────────┘`}
      </div>

      <div style={{ marginTop: 12, padding: "12px 14px", background: "var(--color-background-danger)", borderRadius: 8 }}>
        <p style={{ fontSize: 12, color: "var(--color-text-danger)", lineHeight: 1.6, margin: 0 }}>
          <strong>工程警告：</strong> 永远用 <code style={{ fontSize: 11 }}>xSemaphoreCreateMutex()</code> 而非
          <code style={{ fontSize: 11 }}> xSemaphoreCreateBinary()</code> 来保护共享资源。
          Binary Semaphore 用于"通知"（ISR→Task），Mutex 用于"互斥"（Task↔Task）。混用是优先级反转的根源。
        </p>
      </div>
    </div>
  );
}

// ─── TCB Deep Dive ───
function TCBSection() {
  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>TCB 深度解析：任务的"身份证"</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        每个任务在内核中都有一个 TCB（Task Control Block）结构体。
        它就像任务的"身份证"——记录了任务的一切状态信息。
        <strong style={{ color: "var(--color-text-primary)" }}>pxTopOfStack 必须是第一个字段</strong>——这是对汇编代码的承诺。
      </p>

      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.8, color: "var(--color-text-secondary)", whiteSpace: "pre" }}>
{`typedef struct tskTaskControlBlock {
    // ═══════ 第一字段（汇编硬编码依赖）═══════
    volatile StackType_t *pxTopOfStack;
    //   ↑ PendSV 中通过 LDR R0, [TCB] 直接取第一个字段
    //   如果这不是第一个字段，上下文切换会崩溃

    // ═══════ 状态链表节点 ═══════
    ListItem_t xStateListItem;
    //   ↑ 任务在就绪/阻塞/挂起链表中的位置
    //   xItemValue = 优先级（就绪态）或唤醒时间（阻塞态）

    ListItem_t xEventListItem;
    //   ↑ 任务在事件等待链表中的位置
    //   如等待 Queue/Semaphore/EventGroup 时

    // ═══════ 优先级 ═══════
    UBaseType_t uxPriority;
    //   ↑ 当前优先级（可能因优先级继承而临时提升）
    UBaseType_t uxBasePriority;
    //   ↑ 原始优先级（继承恢复时用）

    // ═══════ 栈信息 ═══════
    StackType_t *pxStack;
    //   ↑ 栈底地址（检测溢出用）
    //   栈从高地址向低地址增长
    //   pxTopOfStack 总是 ≥ pxStack（否则溢出）

    // ═══════ 任务名 ═══════
    char pcTaskName[configMAX_TASK_NAME_LEN];
    //   ↑ 调试用。vTaskList() 打印时显示

    // ═══════ 可选字段（由配置宏控制）═══════
    #if (configUSE_MUTEXES == 1)
        UBaseType_t uxMutexesHeld;  // 持有的 mutex 数量
    #endif
    #if (configUSE_TASK_NOTIFICATIONS == 1)
        uint32_t ulNotifiedValue;   // 通知值（32位）
        uint8_t  ucNotifyState;     // taskNOT_WAITING / WAITING / NOTIFIED
    #endif
    #if (configGENERATE_RUN_TIME_STATS == 1)
        uint32_t ulRunTimeCounter;  // CPU 运行时间统计
    #endif
} TCB_t;`}
        </div>
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 10px" }}>任务状态机</h3>
      <div style={{ background: "var(--color-background-secondary)", borderRadius: 8, padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.8, whiteSpace: "pre", color: "var(--color-text-secondary)" }}>
{`                    xTaskCreate()
                         │
                         ▼
               ┌──────────────────┐
               │     就绪 Ready   │◄──────────────────────┐
               └────────┬─────────┘                        │
                        │ 调度器选中（最高优先级）             │
                        ▼                                   │
               ┌──────────────────┐  vTaskDelay() / 等待IPC │
               │   运行 Running   │─────────────────────────│
               └────────┬─────────┘                        │
                        │                                   │
           ┌────────────┴────────────┐                     │
           ▼                          ▼                     │
  ┌─────────────────┐    ┌──────────────────┐              │
  │  阻塞 Blocked   │    │  挂起 Suspended  │              │
  │ (等待事件/超时)  │    │ (vTaskSuspend)   │              │
  └────────┬────────┘    └────────┬─────────┘              │
           │ 超时/事件到达        │ vTaskResume()           │
           └──────────────────────┴────────────────────────┘

链表归属：
• Ready   → pxReadyTasksLists[优先级]
• Blocked → pxDelayedTaskList 或 pxOverflowDelayedTaskList
• Suspended → xSuspendedTaskList
• Running → pxCurrentTCB 指针（不在任何链表中）`}
      </div>

      <div style={{ marginTop: 12, padding: "12px 14px", background: "var(--color-background-info)", borderRadius: 8 }}>
        <p style={{ fontSize: 12, color: "var(--color-text-info)", lineHeight: 1.6, margin: 0 }}>
          <strong>哲学：</strong> TCB的设计体现了"数据局部性"原则——所有与任务相关的状态都集中在一个结构体中，
          而不是分散在全局变量里。这使得任务切换只需要切换一个指针（pxCurrentTCB），
          就能"换一个世界"。正如佛教的"一花一世界"——每个TCB都是一个完整的独立宇宙。
        </p>
      </div>
    </div>
  );
}

// ─── Startup Section ───
function StartupSection() {
  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 8px" }}>启动流程：从裸机到 RTOS</h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", lineHeight: 1.7, margin: "0 0 16px" }}>
        理解FreeRTOS的启动流程，就是理解"混沌到秩序"的演变——
        从硬件复位的一片空白，到多任务并行的有序世界。
      </p>

      <div style={{ background: "var(--color-background-secondary)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 2, color: "var(--color-text-secondary)", whiteSpace: "pre" }}>
{`═══════════════════════════════════════════════════════
                     启动全流程
═══════════════════════════════════════════════════════

1. 硬件复位
   │ • CPU 从 0x00000000 读取初始 MSP 值
   │ • 从 0x00000004 读取 Reset_Handler 地址
   │ • 跳转到 Reset_Handler（仍在 Handler 模式）
   ▼
2. Reset_Handler（启动汇编）
   │ • 复制 .data 段（Flash → RAM）
   │ • 清零 .bss 段
   │ • 初始化 FPU（如果有）
   │ • 跳转到 main()
   ▼
3. main()（用户代码开始）
   │ • HAL_Init()          → 配置中断分组、SysTick
   │ • SystemClock_Config() → PLL、总线时钟
   │ • 外设初始化           → GPIO、UART、SPI、DMA...
   │ • 创建任务             → xTaskCreate() × N
   │ • 创建IPC对象          → Queue、Semaphore、Mutex...
   │
   │  ⚠️ 此时调度器还没启动！所有 xTaskCreate 只是
   │     分配 TCB + 栈 + 加入就绪链表
   ▼
4. vTaskStartScheduler()  ← 关键转折点！
   │ • 创建 Idle Task（优先级 0）
   │ • 创建 Timer Task（如果启用软件定时器）
   │ • 配置 SysTick 定时器（1ms 中断）
   │ • 设置 PendSV 和 SysTick 为最低优先级（0xFF）
   │ • 调用 xPortStartScheduler()
   ▼
5. xPortStartScheduler() → prvStartFirstTask()
   │ • 找到最高优先级就绪任务
   │ • 设置 PSP = 该任务栈顶
   │ • 切换到 PSP（MSR CONTROL, #2）
   │ • 恢复任务上下文（POP {R4-R11}）
   │ • BX LR → 跳转到第一个任务的入口函数
   │
   │  从此，CPU 从 Handler 模式 → Thread 模式
   │  从 MSP → PSP
   │  从"裸机单线程" → "RTOS多任务"
   ▼
6. 任务世界开始运转
   • SysTick 每 1ms 触发 → 检查延时链表、时间片
   • PendSV 在需要时触发 → 上下文切换
   • 你的任务在各自的 while(1) 中运行
   • Idle Task 在没人运行时运行（可以在这里进低功耗）

═══════════════════════════════════════════════════════`}
        </div>
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 500, margin: "0 0 10px" }}>关键配置项速查</h3>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)", gap: 6 }}>
        {[
          { k: "configCPU_CLOCK_HZ", v: "CPU主频", d: "用于 SysTick 计算" },
          { k: "configTICK_RATE_HZ", v: "Tick频率", d: "通常1000（1ms）" },
          { k: "configMAX_PRIORITIES", v: "最大优先级数", d: "通常 5~56" },
          { k: "configMINIMAL_STACK_SIZE", v: "最小栈大小", d: "Idle Task 栈（字）" },
          { k: "configTOTAL_HEAP_SIZE", v: "堆总大小", d: "heap_1/2/4/5 使用" },
          { k: "configMAX_SYSCALL_INTERRUPT_PRIORITY", v: "API安全线", d: "BASEPRI 阈值" },
          { k: "configUSE_PREEMPTION", v: "抢占式调度", d: "1=抢占 0=协作" },
          { k: "configUSE_TIME_SLICING", v: "时间片轮转", d: "同优先级轮流" },
        ].map(c => (
          <div key={c.k} style={{ background: "var(--color-background-secondary)", borderRadius: 6, padding: "8px 10px" }}>
            <code style={{ fontSize: 10, color: "var(--color-text-info)" }}>{c.k}</code>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 2 }}>{c.v}</div>
            <div style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>{c.d}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 12, padding: "12px 14px", background: "var(--color-background-warning)", borderRadius: 8 }}>
        <p style={{ fontSize: 12, color: "var(--color-text-warning)", lineHeight: 1.6, margin: 0 }}>
          <strong>哲学：</strong> vTaskStartScheduler() 是一个"单程票"——它永远不会返回。
          调用它的那一刻，程序的控制流从"线性执行"变为"事件驱动的并发"。
          这是一个质变——如同宇宙大爆炸的那一刻，从单一到多元，从有序到混沌中的有序。
          main() 函数的最后一行之后，世界的运行方式彻底改变了。
        </p>
      </div>
    </div>
  );
}

// ─── Main App ───
export default function FreeRTOSMastery() {
  const [activeSection, setActiveSection] = useState("philosophy");

  const renderSection = () => {
    switch (activeSection) {
      case "philosophy": return <PhilosophySection />;
      case "scheduler": return <SchedulerSection />;
      case "context": return <ContextSection />;
      case "memory": return <MemorySection />;
      case "ipc": return <IPCSection />;
      case "timer": return <TimerSection />;
      case "critical": return <CriticalSection />;
      case "priority": return <PrioritySection />;
      case "tcb": return <TCBSection />;
      case "startup": return <StartupSection />;
      default: return null;
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", fontFamily: "var(--font-sans)" }}>
      {/* Header */}
      <div style={{ marginBottom: 20, paddingBottom: 16, borderBottom: "0.5px solid var(--color-border-tertiary)" }}>
        <h1 style={{ fontSize: 22, fontWeight: 500, margin: "0 0 4px", color: "var(--color-text-primary)" }}>
          FreeRTOS 精通指南
        </h1>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: 0 }}>
          从硬件脉搏到任务协作的深度原理 — 结合设计哲学的全景知识图谱
        </p>
      </div>

      {/* Navigation */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20, flexWrap: "wrap" }}>
        {sections.map(s => (
          <button key={s.id} onClick={() => setActiveSection(s.id)} style={{
            padding: "7px 12px", borderRadius: 8, fontSize: 12,
            border: `0.5px solid ${activeSection === s.id ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
            background: activeSection === s.id ? "var(--color-background-info)" : "var(--color-background-primary)",
            color: activeSection === s.id ? "var(--color-text-info)" : "var(--color-text-secondary)",
            cursor: "pointer", fontWeight: activeSection === s.id ? 500 : 400,
            display: "flex", alignItems: "center", gap: 4,
          }}>
            <span style={{ fontSize: 13 }}>{s.icon}</span> {s.title}
          </button>
        ))}
      </div>

      {/* Content */}
      {renderSection()}

      {/* Footer */}
      <div style={{ marginTop: 24, paddingTop: 12, borderTop: "0.5px solid var(--color-border-tertiary)", fontSize: 11, color: "var(--color-text-tertiary)", textAlign: "center" }}>
        基于 FreeRTOS V10.x 内核源码分析 · Cortex-M 架构
      </div>
    </div>
  );
}
