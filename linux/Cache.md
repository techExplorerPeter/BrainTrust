# 1.MMU

![](.\image\mmu1.png)

MMU 除了完成虚拟地址到物理地址的映射外，还可以控制每个内存区域（一般是页大小为单位)的memory 的访问权限, memory的顺序、cache策略等。有了MMU后，系统中的应用程序对物理内存不感知，每个应用程序都有自己独立、连续的虚拟地址空间，提高对内存的使用效率。

TLB（translation lookaside buffer)是MMU中的一块高速缓存，用于加速虚拟地址到物理地址转换速度的缓存。如果没有TLB，则每次取数据都需要访问页表以获得物理地址及其对应的数据。

因为MMU大家相对比较熟悉，同时TLB内部结构、ASID、页表等跟CPU体系结构相关，我们放到下篇ARM架构和微架构的文章再详细介绍。


# 2.Cache

主要介绍cache的基本原理结构、cache寻址方式、cache各种策略，arm处理器的cache操作、内存属性、PoCket和PoU等概念，我们放到后续文章再介绍。
## 2.1 cache基本概念

![](.\image\cache1.png)

如上图所示，在cache构成中，现在一般都是组相连（set-associative）的，上图4路组相连的cache，为了方便索引内存地址，会将地址拆成3个部分，分别是Tag、Index和offset：

**Line**：也就是一个cacheline，是cache和主存之间交换数据的最小单元；

**Tag**：是memory地址的最高部分，用来标记这个地址的数据是否已经在cache中，在cache中有一块单独Tag RAM来存储这些标记（不包含在cacheline中），每个tag跟每个cacheline一一对应；

**Index**：是memory地址的中间部分，可以用来寻址到具体哪个的cacheline中；

**Offset**：是memory地址的中间部分，这一部分用于表示在当前地址的数据具体在cacheline中的偏移量;

**Way**：我们将cache平均分成多份，每一份就是一路。因此，4路组相连的cache就是将cache平均分成4份;

**Set**：可以把cache当作一个2维矩阵，其中每个元素是一个cache line。而一行是一个set，使用Index bits来定位到某一行（某一个set），一个set又由多个cacheline组成。4路组相连的cache就相当于有一行（一个set）有4个cacheline。

![](.\image\cache2.png)

我们来看一个例子，如上图，一个32-bit的地址，4-way组相连的cache，cacheline大小是8个words（32个bytes）：

- 31-13bit是Tag字段，共19bits；
- 12-5bit是Index字段，共8bit，每个way对应的cacheline有256个；
- 4-0bit是Offset字段，共5bit，其中4-2bit共3个bits可具体找到8个words当中哪一个word；再通过0-1bit，共2个bits来寻址每个word（4个Bytes）当中具体哪个Byte；

此外在cache的具体实现中，每个Tag前面还有一个V（valid）bit位以及在每个cacheline的后面D（Dirty）bit位（这两个标志位也是要单独占用存储空间的）：

- Valid bit：用来标记cacheline中包含的数据是否可以被使用；
- dirty bit：用来标记cacheline中包含的数据是否与主存中一致。
## 2.2 cache组织结构
### 2.2.1 直接映射（direct-mapped）

![](.\image\cache3.png)

直接映射就是主存中的一个Block只能映射到Cache中固定的某一行，如上图所示，相当于每个set只有一个cacheline，一共64个set。直接映射缓存在硬件设计上会更加简单，成本较低，但容易产生cache颠簸（cache thrashing）。
### 2.2.2 组相连（set-associative）

![](.\image\cache4.png)



组相连就是主存中的一个Block能映射到Cache中固定的某几行，如上图所示，相当于每个set有2个cacheline。一共32个set，两份只要有一份有效就能cache命中，硬件成本相对于直接映射缓存更高，但能减少cache颠簸。
### 2.2.3 全相连（full-associative）

![](.\image\cache5.png)



全相连就是主存中的一个Block能映射到Cache中的所有cacheline，如上图所示。即相当于所有的cache line都在一个set内，因此地址中不需要set index部分。硬件实现成本最高，能最大程度的降低cache颠簸。
## 2.3 cache的组织方式
### 2.3.1 VIPT（Virtually Indexed Physically Tagged）

![](.\image\cache6.png)

此种方式index取自虚拟地址，tag取自物理地址，一般可以先进行部分cacheline的查找，同步进行MMU的地址翻译（因为MMU中有TLB存在，相当于物理地址对应虚拟地址的cache）总体延迟较低，等地址翻译完成，获得物理tag，最最后再进行tag的比较。采用虚拟地址作为index，所以可能存在别名问题，当然也可以由硬件完成别名（不同的虚拟地址映射相同的物理地址，同一个物理地址的数据被加载到不同的cacheline中）的识别和解决。



### 2.3.2 PIPT（Physically Indexed Physically Tagged）

![](.\image\cache7.png)

Tag和index都取自物理地址。所以不会有歧义（指不同的数据在cache中具有相同的tag和index，即相同的虚拟地址映射不同的物理地址就会出现）和别名的问题，所有的查找都要等MMU翻译完成，所以性能相对较低。

## 2.4 cache策略

### 2.4.1 分配策略

- **读分配（Read Allocate）**：仅在CPU发出读请求时分配cacheline。如果是写请求并且miss，则直接将数据写入到主存中，cache不受影响；
- **写分配（Write Allocate）**：更准确的说法应该是读写分配策略，在cache读或者cache写，并且miss时为该数据分配cacheline。该分配策略通常与处理器内核write-back写策略配合使用；

### 2.4.2 更新策略

- **写直通（write through）**：缓存中的修改会传播到下一级的存储上，即使hit时也不例外，没有一致性问题，但没有写write-back效率高；
- **写回（write back）**：只有当缓存块被替换的时候，被修改的数据块会写到下一级存储上，并不是每次写都会对下一级存储有写操作，但会有不一致的情况出现。

### 2.4.3 替换策略

当 cache miss 的时候，就需要决定将哪个cacheline给替换掉，组相连和全相连执行替换，常见的替换策略如下：

- Round-robin：轮流替换组内的cacheline，比如对于2路组关联的cache，首先替换组内的第一行，然后是第二行，再回到第一行，依次循环往复；；
- Pseudo-random：随机替换组内的cacheline，比如对于2路组关联的cache，随机替换掉其中的一行；
- Least Recently Used (LRU) ：按照最近最少使用的方式替换掉组内的cacheline

行文至此我们已经了解了处理器的各个主要特性及工作原理。下面我们实际粗略过下ARM Cortex-A9处理器的微架构，看下都用到了哪些技术来提升处理器性能。

# **3. Cache是什么，解决了什么问题**

**Cache的核心作用**：

把“经常访问“的指令和数据临时存放到更快的小容量存储里，减少从速度更慢的存储（如片上flash、外部存储）取数的等待时间，从而提升平均性能和总线效率。

**基本原理：**

**时间/空间局部性：**近期用过的、相邻的数据/指令可能很快再次使用

**按”行“（cache line）填充：**Cortex-M7的行大小通常为32字节，一次抓取一行

**命中/未命中：**命中直接从cache读；未命中才会去慢速存储取并填充

**写策略与替换：**数据cache通常为写回（write-back）、写分配（write-allocate），配合某种替换策略

![image-20251125144830712](.\image\image-20251125144830712.png)

# **4.为什么在MCU（以S32K3为例）更需要cache**

![image-20251125144955187](.\image\image-20251125144955187.png)

**CPU与Flash速度相差较大：**S32K3上的Cortex-M7主频可以达到百兆以上，而片上Flash为保证可靠性需要多个等待周期（wait states）。无cache时候，每次取指/取数都要等Flash，性能大幅度受限。

**总线带宽与功耗：**Cache减少对Flash/外设总线的访问次数，降低总线压力与功耗。

**平均性能vs.最坏情况：**cache能显著提升平均性能（常见2x甚至更多），但降低时间确定性；在功能安全/实时最严苛任务上要权衡。

**外部存储/XIP 场景：**若从外部QSPI NOR XIP或大块数据驻外设存储，cache的收益更大

# 5.哪些数据适合放在缓存中

**CPU频繁访问且有重用的数据**：例如控制环路的状态变量、滤波/矩阵/FFT中的工作缓冲、算法的中间结果。

**具有时间或空间局部性**：连续数组、结构体中的相邻字段、循环内重复读写同一个小集合。32字节为常见的cache line，能在同一行内反复命中收益高。

**读多写少的常量/查找表**：如系数表、正弦表、校准表，位于Flash或SRAM的只读数据，命中率高且无一致性风险。

**工作集小于或接近D-cache容量**：热点数据规模与缓存大小匹配时，命中率与性能最优（常见16-32KB量级）。

