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