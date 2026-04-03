# Aurix Tips

## TriCore Registers Intro (32 Bits)

![image-20260203154211907](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203154211907.png)

- **16**个通用**地址寄存器 A[0]~A[15]** 
- **16**个通用**数据寄存器 D[0]~D[15]**
- **1**个**PC(Program Counter)寄存器**
- **1**个**PSW(Program Status Word)寄存器**
- **1**个**PCXI(Program Context Information Register)寄存器**
- 其它：**CSFRs(Core Special Function Registers)**

其中**PSW、PCXI**不仅仅记录着程序运行的状态信息，而且与PC寄存器一样，是程序切换过程中，**存储(Save)**和**恢复(Restore)上下文**的重要组成部分。

A[10]、A[11]、A[15]、D[15]这四个通用寄存器还有特殊功能：

	-	**A[10] : 栈指针寄存器Stack Pointer(SP) register** 
	-	**A[11] : 返回地址寄存器Return Address(RA) register**
	-	**A[15] : 隐式基地址寄存器Implicit Address register**
	-	**D[15] : 隐式数据寄存器Implicit Data register**

A[0]、A[1]、A[8]、A[9]是系统全局寄存器，也就是说在函数调用、中断发生过程中，上下文的Save和Restore不会存储这四个寄存器中的信息。

**这里需要重点关注的是： A[11]和D[15]寄存器，这两个寄存器对Bug问题的排查非常有用。**

当程序异常的时候：

	-	D[15]寄存器存储记录TIN(Trap Identification Number).
	-	A[11]寄存器记录Trap的入口地址.

如果能获取这两个信息，很多问题可被快速定位。注意，如果Bug问题是异步的(Asynchronous), A[11]寄存器最近捕获的地址并不一定是问题发生点的人口地址。

D[15]寄存器很有用，在TriCore架构中，Trap分为8个等级：MMU(Memory Management Unit)、Internal Protection、Instruction Error、Context Management、System Bus and Peripherals、Assertion Trap、System Call、Non-Maskable Interrupt(NMI)。通过D[15]记录的TIN号即可确认Trap的Class，因此，可以在Trap程序中，将D[15]和A[11]寄存器的信息存储到NVM中，以便于Bug问题的排查。

## Trap System

- TriCore架构将异常分成8个大类(**Class**),每个class都有自己的Trap处理程序，通过每个条目32字节的Trap向量进行访问，并根据硬件定义的trap类号进行索引。在每个大类中，又下分了异常识别号(**TIN**)，在执行异常处理程序的第一条指令之前，TIN由硬件加载到通用寄存器D[15]中。异常又可以进一步分为同步和异步，以及硬件或者软件生成。下面就是TriCore的一场类别，并对每个类别中预先定义的特定异常进行了分类和总结。

![image-20260203174913671](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203174913671.png)

![image-20260203174931253](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203174931253.png)

- 同步Trap和异步Trap
  - 顾名思义，同步Trap就是异常发生与处理在同一时。异步Trap就是异常发生和处理在不同时刻。比如如果我们打开了数据缓存(Data Cache)，在没有使用内存屏障的前提下，我们对数据的写入其实只是往Cache里写，然后程序继续执行后续指令，由Cache负责把数据写到内存中。而Trap只有在Cache把数据往内存写的时候才会被检测到，此时我们的程序已经执行到后面的某个位置了，所以是异步的。对于异步Trap。因为其返回地址已经没有了参考性了。所以此时最好的办法是关闭Cache，是trap变成同步Trap。（CPU_PCONx.PCBYP控制Cache的使能）



- 异常向量表

  - 异常处理是使用异常向量表来管理的，用户需要在PFlash中分配**8*32**字节的内存空间（开头需要256字对齐，即BTV的值能整除256），用来存放异常向量表，每个Class占据32字节的空间。向量表中用来存放跳转指令，用来跳转到用户定义的异常处理程序中。例如发生了Class 4，TIN 2的Trap那么Trap的入口地址为**BTV+32^Class.**

    ![image-20260203175939805](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203175939805.png)

- **Trap处理流程**  <TriCore TC1.8 architecture manual volume 1  - > 6 Trap system -> 6.2 Trap handling -> 6.2.5 Entering a trap handler>

  - Trap发生后，如果系统能够处理该类型的Trap，并且返回后系统能够继续运行，则属于可恢复的Trap。如果该Trap发生后系统后续无法继续与逆行，则属于不可回复Trap。**绝大多数的Trap都属于可恢复Trap**。

  - Trap响应

    - 可恢复Trap发生后，内核会执行如下响应步骤：

      1. Trap发生后的第一个动作是保存上部分上下文.
      2. 返回**地址寄存器A[11]**会更新为导致该Trap的指令位置、
      3. Trap的子类**TIN**值被保存到通用寄存器**D[15].**
      4. 如果中断栈寄存器没有被使用(即[PSW.IS](https://psw.is/) = 0的情况)，则栈寄存器A[10]会被设置为中断栈指针地址ISP，并将PSW.IS置1.
      5. I/O模式被切换到Supervisor Mode，也就是最高级的特权模式，这意味着启用所有权限：[PSW.IO](https://psw.io/) = 10B。.
      6. 保护寄存器集被设置为0：PWS.PRS=000B.
      7. 调用深度计数器（CDC）被清零，并设置调用深度限值为64，PSW.CDC=0000000B.
      8. 调用深度检查使能：PSW.CDE=1.
      9. PSW的安全位被设置为SYSCON寄存器中的值PSW.S=SYSCON.TS.
      10. 禁用对全局寄存器A[0], A[1], A[8], A[9]的写权限：PSW.GW=0.
      11. 全局中断位被关闭：ICR.IE=0. (为此CPU禁用中断系统：[ICR.IE](https://icr.ie/) = 0。‘旧的’ [ICR.IE](https://icr.ie/) 和 ICR.CCPN 分别被保存到 PCXI.PIE 和 PCXI.PCPN 中。ICR.CCPN 保持不变)。
      12. 按照Trap类在异常向量表中查询入口地址，并开始执行.(访问陷阱向量表以获取陷阱处理程序的第一条指令)

      尽管陷阱会使ICR.CCPN保持不变，但其处理程序仍会在中断被禁用的情况下开始执行。因此，它们可以执行关键初始操作而不被打断，直到它们明确重新启用中断。

    - 对于不可恢复Trap，执行响应步骤如下(对于不可恢复的FCU（上下文使用超限）陷阱，初始状态有所不同。上部上下文无法保存。仅保证以下状态：):

      1. Trap的子类TIN值被保存到通用寄存器D[15].
      2. 如果中断栈寄存器没有被使用，则栈寄存器A[10]会被设置为中断栈指针地址ISP，并将PSW.IS置1.
      3. I/O模式被切换到Supervisor Mode，也就是最高级的特权模式,这意味着启用所有权限：[PSW.IO](https://psw.io/) = 10B.
      4. 保护寄存器集被设置为0：PWS.PRS=0.
      5. PSW的安全位被设置为SYSCON寄存器中的值PSW.S=SYSCON.TS.
      6. 全局中断被关闭：ICR.IE=0 (为此CPU禁用中断系统：[ICR.IE](https://icr.ie/) = 0。ICR.CCPN 保持不变).
      7. 按照Trap类查询异常向量表并开始执行(访问陷阱向量表以获取FCU陷阱处理程序的第一条指令).

    - 上下文使用超限（FCU）就属于不可恢复Trap

- Trap处理程序

​    Trap处理程序是由用户自定的，用户可以在其中编写中断处理代码，进行异常修复、记录等事务。一种处理方法是将Trap的相关信息进行保存，然后执行复位，以尝试最大限度地恢复系统。

![image-20260203182838879](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203182838879.png)

![image-20260203183641562](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203183641562.png) 

![image-20260203183500498](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203183500498.png)

- Trap退出
  - Trap退出仅仅是通过一条**RFE指令**实现的 **__asm("rfe")**
    1. 将返回地址加载到PC中，注意此时仍然指向发生Trap的那条指令，所以如果问题没有修复，仍然会重新进Trap，这也是为什么一般都采取复位的Trap处理方式
    2. 恢复全局中断使能位：ICR.IE = PCXI.PIE
    3. 恢复中断优先级位：ICR.CCPN = PCXI.PCPN
    4. 将保存的高上下文恢复

- **相关寄存器：<具体的各寄存器bit位代表的含义可以查看手册Aurix TC45x user manual - > 5 Cental Processing Unit -> 5.6 Register -> 5.6.1 Register of CPU>**

  - Trap向量标指针寄存器BTV

    ![image-20260203184855431](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203184855431.png)

- 程序同步错误寄存器**PSTR**

  ![image-20260203184937067](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203184937067.png)

- 数据同步错误寄存器**DSTR**

  ![image-20260203185001346](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260203185001346.png)

- 数据异步错误寄存器**DATR**

  ![image-20260204103313734](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260204103313734.png)

  ![image-20260204103330739](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260204103330739.png)

- 数据错误地址寄存器**DEADD**

![image-20260204103353115](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260204103353115.png)

### 实践举例

- 暂停程序运行，调用Call Stack，发现进入了ShutdownOS，从这就可以看出是Core2 10ms任务函数出问题了。

![image-20260204105141947](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260204105141947.png)

-  观察结构体Os_const_coreconfiguration中Trap相关的信息，结构体中的TrapInfo会记录Trap发生时的Class，TIN以及返回地址。

  ![image-20260204105205395](C:\Users\Administrator\AppData\Roaming\Typora\typora-user-images\image-20260204105205395.png)