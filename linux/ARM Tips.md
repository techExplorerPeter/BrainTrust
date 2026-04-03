### ARM Cortex-M4的函数调用以及压栈过程原理

几块内容：
	-	了解M4函数调用时，栈的运行情况
	-	ABI(Application Binary Interface) && AAPCS(ARM Architecture Procedure Call Strandard)
	-	满减栈
	-	叶子函数和非叶子函数
	-	函数的"序言/返厂"(Prologue/Epllogure)
#### 1.ABI/AAPCS/调用规约
#### 1.1 ABI(Application Binary Interface，应用二进制接口)
规定二进制层面”怎么互相调用“：参数怎么传，哪些寄存器谁保存，如何返回等

#### 1.2 AAPCS(ARM Architecture Procedure Call Strandard)
ARM的函数调用标准。对于Cortex-M4而言，关键点：
**参数传递**：前4个参数用`r0-r3`；第5个以后走**栈上传参**（低地址先入）。
**返回值**：`r0`(整数/指针)；（启用FPU时，浮点可用｀s0｀）
**寄存器保存约定**：
	-	**调用者保护(caller-saved)**:`r0-r3,r12,lr(在调用点)`等 -> 调用前自己备份，用完自己恢复
	-	**被调者保护(callee-saved)**:`r4-r11(以及s16-s31若使用)` -> 被调函数若使用，**必须在函数内push/pop**.
	-	**对齐要求**：函数入口要求``SP % 8 == 0`,编译器会在序言/返场给你对齐(`sub/add sp,#4/#8`). 

#### 2.栈模型（Cortex—M的”满递减栈“）
**Full-Descending（满减栈）：**
-	**Descending**：栈向**低地址**增长（压栈时`SP`变小）。
-	**Full**：`SP`指向**当前栈顶元素**，压栈 = **先减SP，再写数据**
指令体现：
-	`PUSH {r4-r7,lr}` 等价 `STMDB sp!,{r4-r7,lr}`(先减后写)
-	`POP {r4-r7,pc}` 等价 `LDMIA sp!,{r4-r7,pc}`(先读后加)
#### 3.叶子函数 vs 非叶子函数
-	**叶子函数（Leaf）**：内部**不再调用其他函数**。常见特征：不必保存`lr`;不一定需要建立栈帧。
-	**非叶子函数（Non-Leaf）：**内部**会调用其他函数**。特征：通常需要**保存`lr`**,而且如果用到`r4-r11`,必须`push/pop`这些寄存器

#### 4.函数”序言/返场“（Prologue/Epilogue ）
-	**序言：**进入函数时建立栈帧（`push`/`sub sp,#N/对齐`）；
-	**返场：**退出函数时销毁栈帧（`add sp,#N`/`pop`/`bx lr`或`pop {...,pc}`）.
#### 5.与”函数调用压栈“强相关的指令/序列
-	1.调用/返回/跳转
	-	`BL func` ：调用已知函数（会写LR）。
	-	`BLX Rm`：调用函数指针（寄存器里有目标地址，会写LR）。
	-	`BX LR`：返回到调用者。
	-	`BX Rm`：跳转到寄存器地址（尾调用/函数指针）。
	-	`B label`、`B.W label`：无条件分支（不写`LR`）。
	条件分支：`BEQ`／`BNE`／`BCC`／`BCS`／`BMI`／`BPL`／`BGT`／`BGE`／`BLT`／`BLE`等
	”零比较跳转“：`CBZ Rn,label`/`CBNZ Rn,label`。
-	2.栈帧建立/销毁（满递减栈）
	-	**建栈帧（序言）**
		-	`PUSH {LR}`、`PUSH {R4-R7,LR}`：先减SP再写入（满递减）。
		-	`SUB SP,SP,#N`：为局部变量/对齐分配栈空间。
		-	有时会看到栈指针：
			`PUSH {R7,LR}`/`ADD R7,SP,#0`(把`R7`当frame pointer)。
    -	**销栈帧（返场）**
    	-	`ADD R7,SP,#N`
    	-	`POP {...,PC}`（**弹出并返回**）或`POP {...,LR}`+`BX LR`
   
    		等价长写法：
    		`PUSH {...}` ≈ `STMDB SP!,{...}`
    		`POP {...}` ≈ `LDMIA SP!,{...}`
-	3.参数传递/访问
	-	前4个参数：`R0-R3`。
	-	第5个及以后参数：**栈上传参**（调用点先把值写道`[SP,#...]`）。
		-	常见序列：`STR Rn,[SP,#imm]`(或一次性｀PUSH {...}｀)。
		-	被调函数里，进入后通过基于`SP`的`LDR`取到第5/6个参数。
    -	返回值：`R0`(整数/指针)。浮点可走`S0`（启用FPU时）。
-	4.数据搬运/局部变量
	-	`MOV/MOVS`、`ADD/SUB`、`LSL/LSR/ASR`等
	-	`LDR/STR`（字/半字/字节变体：`LDRH/STRH`、`LDRB/STRB`）
	-	加载常量/地址
		-	`ADD Rd,label`(取相对PC的地址)
		-	`LDR Rd, =imm`(伪指令：生成常量池，再用一次LDR取常量)
		-	`MOVW/MOVT`(把32位常量拆成低/高16位装入寄存器)。
-	5.对齐与占位
	-	`NOP`（常用于对齐/延时/占位）
	-	你也可能看到`IT/ITE`(条件块、ARMv7-M可用，编译器再-O0偶尔会发)

## 栈回溯原理与OS高阶异步栈回溯

![](.\image\stack1.png)



![](.\image\stack2.png)

![](.\image\stack3.png)



![](.\image\stack4.png)

![](.\image\stack5.png)
