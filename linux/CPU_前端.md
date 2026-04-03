### 背景

对于做嵌入式而言，是非常有必要了解硬件的实现细节，这样才能对CPU在不同应用场景下的配置优化以达到最佳的性能，也能帮助我们在面对不同硬件特性时，更有效的利用其硬件能力进行软件架构设计和编程实现考虑。
### 1. 微架构概述
CPU的微架构一般分为前端和后端两个部分，在这里我会一一介绍到，本文先介绍前端的相关内容。在我们常用的性能分析Top-Down方法论中在顶层将CPU执行时间分成了<font color="orange">Frontend Bound</font>、<font color="orange">Bad Speculation</font>、<font color="orange">Retiring</font>和<font color="orange">Backend Bound</font>四个部分，如下图所示。其中：
-	<font color="orange">Bad Speculation</font> 表示硬件因为错误的投机预测而被浪费的情况。
-	<font color="orange">Retiring</font> 表示指令正常的完成。
-	<font color="orange">Frontend Bound</font>和<font color="orange">Backend Bound</font> 则对应了我们下面描述的CPU前后端硬件微架构中的行为（关于Top-Down分析方法的具体详解后面我们会单独的写文章去介绍）。

![](.\image\cpuf1.png)
-	**前端：**负责从内存中取指令，并进行译码和重命名；影响其性能的关键主要有：指令cache以及TLB的大小以及带宽、分支预测器的性能、译码Decode和Renaming的宽度等。
-	**后端：**负责指令调度、执行、操作结果回写；影响其性能的原因主要是因为后端没有足够的资源来处理前端发送的指令，这里的资源分为两类，访存资源受限（Memory bound）和计算能力资源受限（core bound）；

![](.\image\cpuf2.png)

下面我们就从CPU的前端微架构进行解释说明：
### 2.取指单元
<font color="orange">取指单元IFU(Instruction Fetch Unit)：</font>我们都知道CPU是按照PC寄存器中保存的地址进行取指的，因此取指单元IFU从PC寄存器中拿到的指令地址后，从L1 ICache取指令，miss后继续在下一级L2和L3 Cache中查找，直到最终出CORE后经过MMU访问DDR，多级Cache的缓存设计本质上都是为了提升取指的性能，因此，ICache的命中率和吞吐就直接影响整个CPU流水最前端的性能，而影响命中率的关键因素其实就是ICache的大小和Cache的替换算法，影响吞吐的关键因素则是Cache的结构（Set-Way、CacheLine大小等）；
### 3.分支预测
<font color="orange">BPU(Branch Prediction Unit)：</font>对于像arm64这样的定长指令集来说，很容易就知道下一条取指的指令位于PC＋４的地址，但问题是指令在内存中排列的顺序并非程序指令的顺序，例如代码下一句的执行逻辑可能是某些直接跳转（B/BL/CBZ）或者间接跳转(BR/RET)指令，所以如果按照顺序往下取指就会导致取到的指令是无效的错误指令，因此需要BPU来做分支预测，即在还没解析分支条件的情况下，先”猜“跳不跳、跳去哪里，以便前端继续取指并送入到解码器，而由于当前PC指向的指令还未译码，因此只能使用指令的地址信息来进行判断，分支预测器本身的实现是非常复杂的，其中有两个比较通用的做法是采用静态预测＋动态预测结合的方式：
－	静态预测：一般采用硬编码的逻辑实现方法，不需要历史信息，例如如果跳转目标地址小于当前地址，认为是循环，预测为跳转等诸如此类的策略，静态预测的方式逻辑电路实现起来简单但是准确率比较低。
－	动态预测：则是需要结合历史行为进行学习和预测，典型的实现包含<font color="orange">BHT(Branch History Table)</font>、<font color="orange">BTB(Branch Target Buffer)</font>、<font color="orange">TAGE(Tagged Geometric Predictor)</font>、<font color="orange">Loop Predictor</font>等等多种结合方式。
下面我们以<font color="orange">BHT(Branch History Table)</font>（主要用于预测是否跳转）举例进行解释说明，首先我们定义一个2bit的饱和计数状态：

  -	<font color="orange">00</font> ->Strongly Not Taken：强烈预测不跳转，除非连续两次跳转才会改变方向
  -	<font color="orange">01</font> ->Weakly Not Taken：预测不跳转，但一次跳转即可改变方向
  -	<font color="orange">10</font> ->Weakly Taken：预测跳转，但一次不跳转即可改变方向
  -	<font color="orange">11</font> ->Strongly Taken：强烈预测跳转，除非连续两次不跳转才会改变方向

这个计数器会根据实际执行的结果之间递增或逐渐递减的更新状态值，假设沃恩有1024个BHT表项，由于ARM64是４Byte定长指令，因此我们就可以取指令地址的[11:2]位作为索引查表，架设初始表项的结果是00表示不跳转，这个结果可能不正确，但是在后续流水译码执行时此处是一个跳转逻辑，就可以通过计数+1的方式更新该表项结果，以此来动态的更新该地址的跳转预测结果，当然还可以加上一个GHT的全局历史信息（记录该地址最近多次跳转的结果）来提升预测跳转的准确性，这也给我们软件工程师带来一个启发，我们经常避免不了会写一些复杂的循环嵌套代码，当我们在使用<font color="orange">Top-Down</font>进行性能定位的时候发现某处代码有比较大的branch-miss时，可以考虑拆分循环嵌套，改用最简单直接的顺序逻辑进行替换（后续Top-Down）的讲解专题会详细阐述；

![](.\image\cpuf3.png)
<font color="orange">BHT</font>给出了是否跳转的预测结果，具体的跳转地址则需要<font color="orange">BTB</font>给出，BTB简单理解就是一个大的多级缓存表，用于存储记录一直分支指令的目标地址，因此<font color="orange">BHT</font>和<font color="orange">BTB</font>结合就能基本给出一个分支指令的下一条取值地址；除了上面这些部件，最先进的CPU还在前端增加例如TAGE这种长历史信息表项等等一些新的设计来提升预测的准确性，核心就是因为前端供给的指令如果不正确，那么在后级执行过程中需要FLush流水，会带来非常大的性能损失；同时分支预测还有一个<font color="orange">RAS(Return Address Stack)</font>配合，本质上就是用一个栈队列存放上一个跳转返回地址，深度很大，硬件相应支持函数嵌套能力越强；最终这几个部件协同配合完成前端分支预测的工作；

![](.\image\cpuf4.png)
### 4.前端结构
基本上前端最重要的就是上面这两个部分，分支预测器<font color="orange">BPU</font>负责提供取指地址，取值单元<font color="orange">IFU</font>负责从Cache中获取指令，两者相互配合为后级流水源源不断的提供指令，根据他们之间的关系前端又分为<font color="orange">耦合式前端（Coupled Frontend）</font>和<font color="orange">分离式前端（Decoupled Frontend）</font>两种设计；
<font color="orange">耦合式前端（Coupled Frontend）</font>的设计师BPU预测出下一次的地址后立即发送给IFU进行取指操作，而<font color="orange">分离式前端（Decoupled Frontend）</font>的设计是<font color="orange">BPU</font>作为生产者不停产生取指地址缓存到内部，取值单元从缓存中读取地址，两者之间通过<font color="orange">FTQ（Fetch Target Queue）</font>进行交互，这样分支预测器独立运行，可以投机抢跑，并且抢跑的分支信息还可以提前预取到L1，这种分离式的设计性能上有很大的提升，但是有可能会出现比较大的分支信息记录，因此分离式前端的一个显著特点就是需要比较大容量的<font color="orange">BTB</font>来进行缓存分支信息，<font color="orange">Apple M1就是分离式的前端设计</font>，为了解决大容量的BTB需求，设计上将L1 ICache可作为最后一次BTB进行查询，Android阵营的<font color="orange">Arm Cortex-X系列最新几代的架构也是分离式前端的设计</font>；当前比较先进的CPU支持2 taken/cycle的设计就是分词预测两个分支，一般对应后端的BRU也至少有两个，因为当前地址的预测信息存放到BTB里面，因此支持2 taken/cycle的关键就是BTB要支持双端口的设计。

![](.\image\cpuf5.png)
### 5.前端性能指标
此外，我们在介绍几个前端比较重要的性能指标：
-	<font color="orange">Fetch Width</font>：表示Cache取指带宽，指<font color="orange">IFU</font>每个cycle能从ICache中能取多少条指令，某些CPU支持Micro Cache微指令缓存，因此还会有Micro取指宽度来衡量微指令取指性能，Fetch Width主要受硬件实现时许影响，同时还跟指令缓存的CacheLine有关，例如Apple的M系列能在一个周期内完成一条CacheLine的取指操作，即支持16 Inst/Cycle的前端取指能力；
-	<font color="orange">Decode Width</font>：表示每个Cycle能译码多少条指令，Decode宽度决定了同时能有多少条指令发送给后级流水线进行操作，前端取指的指令是机器码，需要通过译码器进行译码成Micro Ops微操作指令发送后级流水部件，例如一条加法指令：
    <font color="orange">ADD X3,X1,X2</font>
    可能对应了4条Micro Ops微指令
    |<font color="orange">ReadReg X1 -> Temp1</font>| 从寄存器X1读入数据
    |<font color="orange">ReadReg X2 -> Temp2</font>| 从寄存器X2读入数据
    |<font color="orange">Add Temp1,Temp2->Temp3</font>| 加法操作
    |<font color="orange">WriteReg Temp3->X3</font>| 写入结果
    4条Micro Ops，我们前面讲到的某些CPU为了避免每次都译码耗时耗电，专门设计了Micro Cache缓存之前已译码指令的Micro Ops，即以PC地址为Key进行Micro Cache查找，来跳过Decoder阶段，从而加速前端；而对于ARM系的定长指令集来说，由于Decode本身的译码实现复杂度比较低，单独加一个Micro Cache的Area/Power是不划算的，因此最新的ARM架构CPU很多都已经取消了这一特性，而x86架构的很多CPU还保留了这一设计特性。
### 6.小结
以上基本上就涵盖了CPU前端的关键部分，主要以基本的硬件原理为重点及性能了介绍，下一篇我们将重新回到软件视角，介绍如何通过软件去探查这些硬件的设计细节。

### 背景
在上一篇里我们从硬件的角度认识了CPU前端的几个重要部件和他们的实现原理，本篇我们将站在软件的角度上考虑，看下如何通过软件构造去探查硬件的实现细节；
### 7.取指带宽
在上面我们提到了影响CPU前端性能的重点之一就是取指带宽(即CPU前端每周期能从指令缓存L1 I-cache/uOp cache 中提取多少条指令/字节数)。即流水线中的下图部分：

![](.\image\cpuf6.png)
这里我们需要首先知道探测<font color="orange">CPU微架构</font>的一些方法，即<font color="orange">通过精心构造的指令序列，观察CPU在时序、执行顺序、资源冲突、缓存行为等方面的响应，从而逆向推导出其微架构实现细节</font>；因此我们需要先确定采用的指令及指令流，这里我们采用NOP指令，因为我们探测的是前端资源，所选取的指令最好和CPU后端硬件资源不发生关系，而NOP指令由于不进行任何实际操作，很多现代CPU都对其进行了前端消除的优化，即在经过前端取指译码后就可以标记完成执行，从而不占用CPU后端的硬件资源。

既然如此，那我们是不是可以直接构造大量连续的NOP指令，然后通过测量其执行的延迟<font color="orange">Latency</font>来获得取指带宽呢？答案是否定的，由于前端的取指宽度有可能大于后级的Decoder或者Renaming，因此这种方式测量的瓶颈并不是取指的宽度，而是<font color="orange">Decode Width</font>或者Rename Width，这也给我们引出一个在探测CPU微架构时的核心策略：即排除流水线其他模块的影响，尽可能的<font color="orange">构造探测对象结构或功能的瓶颈</font>。

既然如此，那么前端取指的瓶颈是什么呢？根据Cache的相关知识我们知道在采用 VIPT（Virtually Indexed Physically Tagged）或 PIPT（Physically Indexed Physically Tagged）I-Cache 的微架构中，CPU 取指操作涉及到以下两个关键步骤：
-	<font color="orange">访问 I-TLB</font>：**将虚拟地址转换为物理地址**；
-	<font color="orange">访问 I-Cache</font>：**根据物理地址读取指令内容**。

由于大多数**ARM架构处理器**每次取指周期中，I-TLB 通常只能执行一次页表转换，当指令跨越页边界（page boundary）时，则需要两个周期完成取指过程——即第一个周期只能从当前页末取回少量转换完成的指令，第二个周期才从下一页继续获取剩余指令。根据这个特点结合上面介绍的NOP指令特性，我们可以通过以下方式，构造CPU 每轮取指都经历跨页，从而迫使其进入“带宽受限”的状态：
-	**将循环起始地址放在页的末尾，只有一条 nop**；
-	**紧接着在下一页中布置大量连续的 nop**；
-	**最后以一条 jmp 返回页尾的 nop 开头，构成闭环**。
```
Page N:   1:
Page N:   nop
Page N+1: nop
Page N+1: nop
Page N+1: nop
Page N+1: ...
Page N+1: jmp 1b
```

假设我们探测的目标处理器特性如下：

- **每周期最多取指宽度为 W（即W条指令）**；
- **后端能够执行最多 E 条 nop 指令/周期**。

通过我们前面的分析和推导，可以得出如下预设：

- **第一周期只能 fetch 到页末的 1 条 nop**；
- **第二周期开始，如果 fetch width 不足以一次性从页 1 中取到 E 条 nop，则后端无法保持 E 的执行吞吐**；
- **只有当 W ≥ E + 1 时，才有可能维持后端的满速运行**。

因此，通过调整 nop 的数量，测量指令block的执行时长，从而就可以得到CPU前端的取指带宽信息。为了让执行代码尽可能减少受编译器的影响，我们采用汇编实现核心指令流，下面是根据我们根据前面的理论推导实现的指令block：
```
// ifetch_blocks.S (ARM64)

// 这里可以根据实际进行调整，基本上当前已知最先进的CPU前端取指宽度16，两个周期最大32条指令取指宽度，因此这里设置循环的最大NOP数量40
#ifndef NOP_PER_BLOCK
#define NOP_PER_BLOCK 40
#endif

        .text
        .align  2

// ---- 一个 block（Page0 & Page1） ----
// 每个 block 的 page0 只在页尾放 1 条 nop
// page1 紧随其后，放 NOP_PER_BLOCK 条 nop + tail。

        // 第一个 block：跳到它开始
        .macro FIRST_BLOCK name
        .balign 4096
        .space  4096 - 4
\name\()_FIRST:
        nop                        // page0 尾部，仅 1 条 nop

        // page1: K 条 nop
        .rept   NOP_PER_BLOCK
        nop
        .endr

        // tail: 用于控制循环跳转
        subs    x0, x0, #1
        b.ne    0f
        ret                        // x0 == 0 时返回到 C
0:      b       1f                 // 跳到“下一 block”的 page0尾
        .endm

        // 中间 block：为了覆盖不同codesize
        .macro MIDDLE_BLOCK name
        .balign 4096
        .space  4096 - 4
1:      nop

        .rept   NOP_PER_BLOCK
        nop
        .endr

        subs    x0, x0, #1
        b.ne    0f
        ret
0:      b       1f
        .endm

        // 最后一个 block：继续时回到第一个 block
        .macro LAST_BLOCK_TO_FIRST name
        .balign 4096
        .space  4096 - 4
1:      nop

        .rept   NOP_PER_BLOCK
        nop
        .endr

        subs    x0, x0, #1
        b.ne    0f
        ret
0:      b       \name\()_FIRST     // 回到第一个 block 的 page0尾
        .endm

// ---- blocks == 1 的特例：单 block 自环 ----
        .macro GEN_RING1 name
        .global \name
\name:
        b       \name\()_FIRST

        .balign 4096
        .space  4096 - 4
\name\()_FIRST:
        nop

        .rept   NOP_PER_BLOCK
        nop
        .endr

        subs    x0, x0, #1
        b.ne    0f
        ret
0:      b       \name\()_FIRST
        .endm

// ---- 生成一个含 N 个 blocks 的环 ----
        .macro GEN_RING name, blocks
        .global \name
\name:
        b       \name\()_FIRST

        FIRST_BLOCK \name

        .if (\blocks-2) > 0
        .rept   (\blocks-2)
        MIDDLE_BLOCK \name
        .endr
        .endif

        .if (\blocks) >= 2
        LAST_BLOCK_TO_FIRST \name
        .endif
        .endm

// ---- 实例化 9 个RING Block：遍历1..256 blocks ----
        GEN_RING1       itlb_loop_b1
        GEN_RING        itlb_loop_b2,    2
        GEN_RING        itlb_loop_b4,    4
        GEN_RING        itlb_loop_b8,    8
        GEN_RING        itlb_loop_b16,   16
        GEN_RING        itlb_loop_b32,   32
        GEN_RING        itlb_loop_b64,   64
        GEN_RING        itlb_loop_b128,  128
        GEN_RING        itlb_loop_b256,  256
```
剩下的我们通过C来构造测量执行时长的部分：
```
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

#ifndef NOP_PER_BLOCK
#define NOP_PER_BLOCK 40   // 与汇编文件中保持一致
#endif

#define PAGE_SIZE 4096
// 汇编提供的 9 个ring block，读者可以自行增加获得更细腻的结果
void itlb_loop_b1   (uint64_t iters);
void itlb_loop_b2   (uint64_t iters);
void itlb_loop_b4   (uint64_t iters);
void itlb_loop_b8   (uint64_t iters);
void itlb_loop_b16  (uint64_t iters);
void itlb_loop_b32  (uint64_t iters);
void itlb_loop_b64  (uint64_t iters);
void itlb_loop_b128 (uint64_t iters);
void itlb_loop_b256 (uint64_t iters);

static inline uint64_t rd_cntvct(void){ uint64_t v; __asm__ volatile("mrs %0, S3_3_C14_C0_2":"=r"(v)); return v; }
static inline uint64_t rd_cntfrq(void){ uint64_t v; __asm__ volatile("mrs %0, S3_3_C14_C0_0":"=r"(v)); return v; }
static inline uint64_t ns_now_raw(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

typedef void (*loop_fn_t)(uint64_t);
typedefstruct {int blocks; loop_fn_t fn; } entry_t;

int main(void){
    constsize_t page_size   = PAGE_SIZE;
    constsize_t block_bytes = page_size * 2;  // 一个 block = 8KB
    constdouble insts_iter  = (double)NOP_PER_BLOCK + 4.0;

    entry_t table[] = {
        { 1,   itlb_loop_b1   },
        { 2,   itlb_loop_b2   },
        { 4,   itlb_loop_b4   },
        { 8,   itlb_loop_b8   },
        { 16,  itlb_loop_b16  },
        { 32,  itlb_loop_b32  },
        { 64,  itlb_loop_b64  },
        { 128, itlb_loop_b128 },
        { 256, itlb_loop_b256 },
    };

    printf("code_size_bytes,cycles_per_iter,inst_per_cycle\n");
    for (size_t i=0; i<sizeof(table)/sizeof(table[0]); ++i){
        int blocks = table[i].blocks;
        loop_fn_t fn = table[i].fn;

        // warmup
        fn(30000);

        // 迭代次数（小 code size 多迭代）
        uint64_t N;
        size_t code_bytes = (size_t)blocks * block_bytes;
        if (blocks <= 16)       N = 50000000ull;
        elseif (blocks <= 64)  N = 10000000ull;
        elseif (blocks <= 128) N = 3000000ull;
        else                    N = 2000000ull;

        uint64_t t0 = ns_now_raw();
        fn(N);
        uint64_t t1 = ns_now_raw();

        double ns_per_iter  = (double)(t1 - t0) / (double)N;
        double ipc             = (ns_per_iter > 0.0) ? (insts_iter / ns_per_iter) : 0.0;
        printf("%zu,%.6f,%.6f\n", code_bytes, ns_per_iter, ipc);
        fflush(stdout);
    }
    return0;
}
```
我们再用如下的python将我们的微架构探测代码在高通8650绑定在Cortex-X4核上测试，结果进行直观画图展示：
```
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("ifbw_result.csv")

plt.figure(figsize=(8,5))
plt.plot(df["code_size_bytes"], df["inst_per_cycle"], marker="o", linewidth=1)

plt.xscale("log", base=2)

xticks = [2**i for i in range(13, 22)]
plt.xticks(xticks, [str(v) for v in xticks], rotation=45)

plt.xlabel("Code size (bytes)")
plt.ylabel("Instructions per cycle (IPC)")
plt.title("ARM64 Frontend Fetch Bandwidth vs Code Size (stride-sampled)")
plt.grid(True, which="both", ls="--", alpha=0.6)
plt.tight_layout()
plt.show()
```

![](.\image\cpuf7.png)
可以看到，在64KB范围内，取指宽度能够很好的维持在9.5左右，这也和官方发布的L1I Cache大小64KB，10 inst./cycle的数据相符合。这里我们只固定了几个采样测试点，读者可以按照参考上面的代码设置更细的步长stride，从而获得更加顺滑的曲线结果。
### 8.分支预测
除了取指带宽，前端另外一个重要部件就是分支预测器，上一篇我们讲过分支预测器主要包括逻辑单元和缓存单元：

-	**逻辑单元：用于推测分支是否发生，强调预测准确率，这部分的设计芯片厂商各有千秋，并且也在不断迭代优化，因此我们这里不做过多介绍；**

-	**缓存单元：如BTB用于存储历史分支目标地址，以支持快速跳转取指，强调覆盖范围； 缓存越大就能保存越多的分支记录信息，简单理解就是越大越好，但芯片设计又是一个极度讲究PPA(Power，Performance，Area)平衡的工程，到底多大合适，就是一个比较讲究的事，这里我们以BTB(用来缓存分支跳转的目标地址)容量探测为例，看下如何探查它的详细设计。**

根据之前的知识，我们知道BTB 本质上是一块针对跳转目标地址的 Cache，其大小决定了处理器能同时追踪多少个独立的分支目标。超出容量的分支目标将被逐出，从而造成性能下降。考虑到ARM体系结构中的指令定长为4 Byte，因此我们借鉴之前的思路通过构造高密度的分支指令流，逐步填满 BTB，进而观察性能指标（如 IPC、执行延迟）是否发生突变，从而推测出 BTB 的容量边界：
```
// 1 branch per 4 byte
1: b 1f
1: b 1f
1: b 1f
1: b 1f
...
```
同时，由于Cache通常采用多路组相连结构，所以分支跳转指令的密度会影响指令块在 BTB Cache 中的命中率，因此为了便于观察硬件在不同分支指令密度下的组相连命中特性，我们可以在分支指令之间插入不同数量的 NOP 指令，以人为调节分支指令的密度：
```
// 1 branch per 8 byte
1: b 1f
   nop
1: b 1f
   nop
...
```

通过前面的分析我们可以预设：

- **当分支数量较少时，所有跳转目标可保留在 BTB 中，预测命中率高，性能稳定；**
- **当分支数量增加到某个阈值时，BTB 被污染，部分分支预测失效，发生 mispredict，性能开始劣化；**
- **通过识别该“性能突变点”对应的分支数量，可反推 BTB 的容量上限。 代码如下：**
```
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>
#include <string.h>
#include <errno.h>

#define AARCH64_INS_NOP  0xD503201Fu
#define AARCH64_INS_RET  0xD65F03C0u

static inline uint32_t encode_b(int32_t imm_bytes) {
    int64_t imm = imm_bytes >> 2;
    uint32_t imm26 = (uint32_t)(imm & 0x03FFFFFF);
    return0x14000000u | imm26;
}

static inline uint64_t read_cntvct(void) {
    uint64_t v;
    asm volatile ("mrs %0, cntvct_el0" : "=r"(v));
    return v;
}

static double diff_nsec(struct timespec a, struct timespec b){
    return (a.tv_sec - b.tv_sec)*1e9 + (a.tv_nsec - b.tv_nsec);
}

typedef void (*codefn_t)(void);

void *gen_chain(int num_blocks, int nops_per_block, size_t *out_size) {
    int instrs_per_block = nops_per_block + 1;
    size_t block_bytes = (size_t)instrs_per_block * 4;
    size_t total = block_bytes * (size_t)num_blocks + 4096;

    void *buf = mmap(NULL, total, PROT_READ | PROT_WRITE,
                     MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    if (buf == MAP_FAILED) { perror("mmap"); returnNULL; }

    uint8_t *p = (uint8_t*)buf;
    uintptr_t base = (uintptr_t)p;

    for (int i = 0; i < num_blocks; ++i) {
        uint8_t *block = p + (size_t)i * block_bytes;
        for (int j = 0; j < nops_per_block; ++j) {
            uint32_t ins = AARCH64_INS_NOP;
            memcpy(block + (size_t)j*4, &ins, 4);
        }
        uintptr_t branch_addr = (uintptr_t)block + (size_t)nops_per_block * 4;
        uintptr_t dst = (i+1 < num_blocks)
                        ? base + (size_t)(i+1) * block_bytes
                        : base + (size_t)num_blocks * block_bytes;
        int64_t imm_bytes = (int64_t)dst - (int64_t)branch_addr;
        if ((imm_bytes & 3) != 0) { fprintf(stderr, "unaligned branch\n"); munmap(buf,total); returnNULL; }
        int64_t max_offset = ((1LL<<25)-1)*4, min_offset = -((1LL<<25)*4);
        if (imm_bytes<min_offset || imm_bytes>max_offset) { fprintf(stderr,"branch too far\n"); munmap(buf,total); returnNULL; }
        uint32_t b_ins = encode_b((int32_t)imm_bytes);
        memcpy(block + (size_t)nops_per_block*4, &b_ins, 4);
    }
    uint8_t *ep = p + (size_t)num_blocks * block_bytes;
    uint32_t ret_ins = AARCH64_INS_RET;
    memcpy(ep, &ret_ins, 4);

    __builtin___clear_cache((char*)buf, (char*)buf + total);
    if (mprotect(buf, total, PROT_READ|PROT_EXEC) != 0) { perror("mprotect"); munmap(buf,total); returnNULL; }
    if (out_size) *out_size = total;
    return buf;
}

int main(void) {
    constint runs = 10000;
    constint nops_values[] = {0,1,2,4,8,16};
    constint n_nops = sizeof(nops_values)/sizeof(nops_values[0]);

    printf("nops_per_block,branch_number,avg_cycles_per_run,avg_ns_per_run,total_cycles,total_ns\n");

    for (int ni=0; ni<n_nops; ++ni) {
        int nops = nops_values[ni];
        for (int nb=1; nb<=16384; nb*=2) {
            size_t code_size=0;
            void *fn = gen_chain(nb, nops, &code_size);
            if (!fn) break;
            codefn_t f = (codefn_t)fn;
            for (int w=0; w<10; ++w) f();

            uint64_t t0 = read_cntvct();
            struct timespec s0,s1;
            clock_gettime(CLOCK_MONOTONIC_RAW,&s0);
            for (int r=0;r<runs;++r) f();
            uint64_t t1 = read_cntvct();
            clock_gettime(CLOCK_MONOTONIC_RAW,&s1);

            uint64_t cycles = t1 - t0;
            double ns = diff_nsec(s1,s0);
            double avg_cycles = (double)cycles / runs;
            double avg_ns = ns / runs;

            printf("%d,%d,%.6f,%.6f,%llu,%.0f\n",
                   nops, nb, avg_cycles, avg_ns,
                   (unsignedlonglong)cycles, ns);

            munmap(fn, code_size);
        }
    }
    return0;
}
```
同样我们通过python将输出结果进行图形化：
```
# -*- coding: utf-8 -*-
import sys
import pandas as pd
import matplotlib.pyplot as plt

def main():
    if len(sys.argv)<2:
        print("Usage: python plot_btb.py result.csv")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1])

    xticks = [1]
    v = 1
    while v < 16384:
        v *= 2
        xticks.append(v)

    plt.figure(figsize=(8,5))
    for nops, group in df.groupby("nops_per_block"):
        g = group.sort_values("branch_number")
        plt.plot(g["branch_number"], g["avg_cycles_per_run"],
                 marker="o", linewidth=1, label=f"nops={nops}")
    plt.xscale("log", base=2)
    plt.xticks(xticks, [str(x) for x in xticks])
    plt.xlim(1,16384)
    plt.xlabel("Branch number (blocks)")
    plt.ylabel("Avg cycles per run")
    plt.title("BTB probe (cycles/run)")
    plt.grid(True, which="both", ls="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig("btb_cycles_vs_branch.png", dpi=160)

    plt.figure(figsize=(8,5))
    for nops, group in df.groupby("nops_per_block"):
        g = group.sort_values("branch_number")
        plt.plot(g["branch_number"], g["avg_ns_per_run"],
                 marker="o", linewidth=1, label=f"nops={nops}")
    plt.xscale("log", base=2)
    plt.xticks(xticks, [str(x) for x in xticks])
    plt.xlim(1,16384)
    plt.xlabel("Branch number (blocks)")
    plt.ylabel("Avg ns per run")
    plt.title("BTB probe (ns/run)")
    plt.grid(True, which="both", ls="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig("btb_ns_vs_branch.png", dpi=160)

if __name__=="__main__":
    main()
```
我们在高通SM8750超大核上测试结果如下：

![](.\image\cpuf8.png)

可以看到在满足理论延迟条件下，BTB容量在2048个entry位置有比较明显的突变，这也是高通官方宣布的L0 BTB的容量大小，并且不同密度的分支指令在容量突变点上也有变化，这就是因为受到Cache硬件本身组相连结构的影响，具体相关知识我们在下一篇Cache文章内容中详细讲解，这里暂时不再继续展开。

### 小结
最后要重点说明一下，上面探查CPU微架构硬件的测试方法和代码都是基于上一篇中讲到的硬件原理，我们讲解的也是最普适基础的一种实现方式，CPU微架构发展日新月异，很多IC厂商和硬件架构师都在不断优化这些设计，因此如果你发现这些构造的探查方式结果不符合预期的话，不应简单视为方法失效，更可能反映出特定实现的设计取舍或创新。此时可以针对性调整探查条件并做对照实验，复现实验现象并据此推断出可能的设计细节。

### 引用

-	**Measuring Reorder Buffer Capacity**

-	**CPU微架构分析-杰哥的知识库**

-	**如何测量真正的取指带宽-知乎-JamesAslan**
