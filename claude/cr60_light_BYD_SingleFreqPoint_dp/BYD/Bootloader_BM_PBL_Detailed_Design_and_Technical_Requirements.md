# CR60 Light BYD Bootloader 详细设计文档与技术要求

> 文档用途：供应商 BM/PBL 等效重实现、接口冻结、代码评审及验收测试。
>
> 文档版本：V2.1（基于无源码 ELF 静态逆向复核，2026-07-16）<br>
> 结论等级：`[C]` 反汇编/DWARF/常量表直接确认；`[I]` 由调用关系和命名推断；`[TBC]` 必须通过升级包、诊断规范或 HIL 冻结。<br>
> 规范用语：“必须/不得”是供应商验收要求；“当前实现”是二进制基线行为；“建议”不是兼容性强制项。

本文基于当前目录下两个 ELF 文件的静态逆向分析编写：

| 镜像 | 角色 | ELF 入口 | 架构 | 主要职责 |
| --- | --- | --- | --- | --- |
| `D_CR60_Light_BM.elf` | Boot Manager, BM | `0x00020000` | ARM32 little-endian, EABI5 | 上电初始化、读取启动状态、选择 App/FBL/PBL、执行安全启动检查和跳转 |
| `D_CR60_Light_PBL.elf` | Primary/Platform Bootloader, PBL | `0x00020000` | ARM32 little-endian, EABI5 | UDS/OTA 下载、Flash 擦写、完整性/Hash/签名校验、更新 App valid flag |

二进制基线：

| 文件 | SHA-256 |
| --- | --- |
| `D_CR60_Light_BM.elf` | `CB02B2FCD702BE6A2F6999F56202E0B58EC15BC2689EF3AE3FE497054624E5C3` |
| `D_CR60_Light_PBL.elf` | `BB8FDA704106300380FC4916807B089E21AFD1CFF97A817629F745B3B69DE300` |

分析依据包括 ELF header、program/section header、`.symtab`、`.debug_info`、`.debug_line`、`.rodata` 常量、TI ARM objdump 反汇编结果。由于没有源代码和原始设计文档，本文将“反汇编直接确认的事实”和“根据函数名/流程推断的设计含义”分开表述。

地址说明：符号表中的 Thumb 函数地址最低位会置 1，例如 `Boot_Logic` 在符号表显示为 `0x10204961`，实际指令起始地址为 `0x10204960`。本文统一使用去掉 Thumb bit 后的指令地址。

本文件不能替代缺失的源代码、链接脚本、芯片 Flash 数据手册、密钥配置、ODX/PDX 和升级包格式定义。供应商不得把 `[TBC]` 项自行解释为接口；这些项目必须在详细设计评审前形成双方签字的《接口冻结清单》。

## 0. 静态逆向审计声明

本版对启动选择、下载授权、Flash 擦写、App valid 提交、CAN 配置和密码学校验等高风险路径进行了符号表、DWARF、初始化常量和指令级交叉复核。文档的使用边界如下：

1. 标为 `[C]` 的内容可在当前两份 ELF 中找到直接证据；第 9 节给出关键符号或指令地址。
2. 标为 `[I]` 的内容是由调用关系、变量/函数命名或配置路由得到的解释，不应当替代 ODX、升级包格式或芯片手册。
3. “供应商必须/不得”可能是为了消除当前二进制缺陷而增加的安全要求。若该要求改变掉电、非法输入或故障场景的可观察行为，必须列入差异清单并获得客户批准，不能宣称它已由当前 ELF 实现。
4. 静态反汇编不能证明真实硬件上的 Flash 物理擦除几何、NvM 掉电原子性、HSM key/算法映射、总线时序和所有 NRC。此类结论必须通过 golden image、HIL、掉电注入和诊断一致性测试关闭。

V2.1 复核中确认并修正的关键点：

| 项目 | 当前 ELF 的实际行为 |
| --- | --- |
| BM 重编程请求 | FBL/PBL 重编程请求会检查对应 valid word；只有早期 CAN 强制路径绕过 valid |
| BM 失败回退 | 强制/重编程目标失败后固定只尝试 CustApp `0x90000`，不使用动态 `APP_IMAGE_Addr` |
| PBL TransferData 权限 | `ImageM_CheckWritePermission` 只收敛到整个 `LogBlock`，没有收敛到本次 RequestDownload 子窗口 |
| RequestDownload 二次条件 | `ImageM_GetRequestDownloadCondition` 在命中块时检查上下文，但未命中任何块的路径会返回成功；前置 `ImageM_PortOpen` 才是当前实际拒绝门 |
| NvM valid 写回 | `NvM_Integration_WriteAll` 同步推进 NvM/MemIf 直到不再 pending，但接口不返回最终写入成功/失败；擦除路径随后继续执行 |

因此，本文可作为供应商重实现输入，但不能被解释为“已经恢复了原始源码”。最终等效性必须由第 15 节的当前 ELF/供应商 ELF 差分测试证明。

## 1. 总体架构

Bootloader 由 BM 和 PBL 两部分组成。BM 是最早参与启动决策的模块，PBL 是刷写执行模块。两者通过非易失状态和固定镜像地址协同工作。

```text
上电/复位
  -> 复位向量 0x20000
  -> BM 初始化硬件、Flash、CAN、NvM、安全 Flash
  -> BM 读取 valid flag / reprogramming request / 安全生命周期状态
  -> BM 根据策略选择 App、FBL 或 PBL
  -> BM 对目标镜像做 SecBoot_Check_Process
  -> BM 加载/释放目标 CPU 或重定位向量表后跳转

进入 PBL 后
  -> EcuM_Init / OS 周期任务启动
  -> DCM + CanTp 接收 UDS 刷写请求
  -> RoutineControl 擦除目标区域
  -> RequestDownload 建立下载窗口
  -> TransferData 边接收边写 Flash
  -> RequestTransferExit 收尾最后一页
  -> ImageM 后台校验 CRC / Hash / 签名
  -> 校验通过后写 Application_Valid_Flag = 0xAA
```

BM 与 PBL 的关键接口不是普通函数调用，而是：

| 接口 | 说明 |
| --- | --- |
| 固定镜像地址 | BM 按 `0x20000/0x50000/0x90000/0x190000` 选择 PBL/FBL/CustApp/ProductionApp |
| NvM / 安全 Flash 状态 | 保存 App/FBL/PBL valid flag、重编程请求和安全生命周期信息 |
| Application valid flag | PBL 在刷写前置 invalid，校验通过后置 valid；BM 上电读取后决定是否启动 App |
| CAN 强制跳转帧 | BM 早期监听扩展 CANFD 帧，可强制优先进入 FBL 或 PBL |

### 1.1 软件分层与责任边界

```text
BM
  启动入口/SoC 初始化
  BootM 启动策略
  NvM/rbSecFls 状态读取
  SecBoot 镜像认证与可选解密
  ImageM 多核 appimage/RPRC 加载
  CAN 早期强制跳转接收

PBL
  EcuM/OS 调度
  CAN Driver -> CanIf -> CanTp -> PduR -> DCM
  SWDL UDS 回调
  ImageM 下载上下文、范围检查、校验状态机
  FlashPort 异步页缓存 -> FlashHandler -> Fls
  NvM/rbSecFls 状态持久化
  CycurSoc/HSM Hash、签名及安全 Flash 服务
```

BM 负责“选择并可信启动”，不得实现通用诊断下载；PBL 负责“授权、擦写、校验及提交有效状态”，不得在未完成认证时提交 App valid。两者通过镜像地址、有效标志、重编程请求以及快速 App 选择字形成跨镜像接口。

## 2. ELF 与内存布局

### 2.1 BM 镜像布局

BM 是 ELF32 ARM 可执行文件，入口 `0x20000`。关键段如下：

| 段 | 地址 | 大小 | 属性 | 说明 |
| --- | ---: | ---: | --- | --- |
| `.sbl_init_code` | `0x00020000` | `0x120` | AX | 异常向量表和早期入口 |
| `.text` | `0x10200280` | `0x12490` | AX | 主代码 |
| `.rodata` | `0x10212710` | `0x2390` | A | 常量、CAN payload、配置表 |
| `.cinit` | `0x10214aa0` | `0x1040` | A | C 初始化数据 |
| `.data` | `0x10216000` | `0x0fb0` | WA | 全局数据 |
| `.bss` | `0x10216fb0` | `0x5c98` | WA | 未初始化数据 |
| `.shared_ram` | `0x102dff20` | `0x15` | WA | 共享 RAM |
| `.shared_booterr` | `0x102dff40` | `0x04` | WA | 安全启动错误码共享区 |
| `.debug_info/.debug_line` | file only | present | - | 保留 DWARF 调试信息 |

BM 的复位向量在 `0x20000`，其中 `reset_addr` 指向 `0x10206bc0`。这说明 ELF 入口处不是完整业务逻辑，而是异常向量和早期启动跳板。

### 2.2 PBL 镜像布局

PBL 同样是 ELF32 ARM 可执行文件，入口 `0x20000`。关键段如下：

| 段 | 地址 | 大小 | 属性 | 说明 |
| --- | ---: | ---: | --- | --- |
| `.sbl_init_code` | `0x00020000` | `0x110` | AX | 异常向量表和早期入口 |
| `.text` | `0x1022b260` | `0x1e4f0` | AX | 主代码 |
| `.os_primitives` | `0x10249750` | `0x50` | AX | OS 原语 |
| `.rodata` | `0x102497a0` | `0x2e68` | A | 常量、配置表 |
| `.cinit` | `0x1022a310` | `0x0f48` | A | C 初始化数据 |
| `.data` | `0x10228000` | `0x0f08` | WA | 全局数据 |
| `.bss` | `0x1021e280` | `0x92b8` | WA | 未初始化数据 |
| `.stack` | `0x00083000` | `0x2000` | WA | 栈区 |
| `.debug_info/.debug_line` | file only | present | - | 保留 DWARF 调试信息 |

PBL 的复位向量 `reset_addr` 指向 `0x10236afc`。

### 2.3 处理器、ABI 与编译约束

`[C]` 两个 ELF 均为 ARMv7-R/Cortex-R5 目标，支持 ARM 与 Thumb-2 指令，使用 VFPv3-D16 和 hard-float ABI；编译器标识为 TI Clang 15.0.7，并采用面向代码尺寸的优化。供应商可更换编译器，但必须保持：

1. 复位向量、异常向量、启动栈和目标 CPU 运行模式与 SoC 启动约定一致。
2. 跨模块或 ROM API 的 AAPCS、参数宽度、结构体对齐和 hard-float ABI 兼容。
3. BM/PBL 映像仍能被当前量产烧录工具、打包工具和安全签名工具处理。
4. 通过 map 文件证明代码、数据、栈、共享 RAM 和安全错误区没有重叠。

### 2.4 外部 Flash 分区与保护边界

下表使用半开区间 `[start,end)`；“可下载”表示当前 PBL `LogBlocks` 白名单允许 `ImageM_PortOpen`。地址和块号为 `[C]`。

| imageId | 分区 | 地址区间 | 长度 | 普通 UDS 擦写 |
| ---: | --- | --- | ---: | --- |
| 0 | BM | `[0x000000,0x020000)` | `0x020000` | 允许 |
| 2 | PlatformBoot/PBL | `[0x020000,0x050000)` | `0x030000` | 允许 |
| 1 | CustBoot/FBL | `[0x050000,0x090000)` | `0x040000` | 允许 |
| 3 | CustApp | `[0x090000,0x190000)` | `0x100000` | 允许 |
| 4 | ProductionApp | `[0x190000,0x290000)` | `0x100000` | 允许 |
| - | 保留区 | `[0x290000,0x2D0000)` | `0x040000` | 禁止 |
| 7 | HSM | `[0x2D0000,0x310000)` | `0x040000` | 允许 |
| 8 | WeifuData | `[0x310000,0x320000)` | `0x010000` | 允许 |
| 5 | CustData | `[0x320000,0x330000)` | `0x010000` | 允许 |
| 6 | ClibData | `[0x330000,0x340000)` | `0x010000` | 允许 |
| - | **App NVM** | **`[0x340000,0x370000)`** | **`0x030000`** | **禁止** |
| - | 未定义/保留 | `[0x370000,0x3E3000)` | `0x073000` | 禁止 |
| - | 快速 App 选择扇区 | `[0x3E3000,0x3E4000)` | `0x001000` | 仅 DID `FC01` 专用路径 |

关键非易失地址：FBL valid word 位于 `0x08F000`，PBL valid word 位于 `0x04F000`；BM 直接各读取 4 字节。供应商必须结合实际 Flash 扇区几何验证任何擦除单元均不跨越 `0x340000` 或 `0x370000`，且不得使用“向外对齐擦除”的方式触及 App NVM。

## 3. BM 详细设计

### 3.1 BM 模块职责

BM 的设计目标是让系统在任何上电场景下选择一个可运行、可验证、可恢复的目标软件。它自身不负责 OTA 数据传输和 Flash 下载写入，核心职责如下：

1. 初始化 CPU/SoC 基础环境、外设、CAN、Flash、NvM、安全 Flash。
2. 读取 App/FBL/PBL valid flag、重编程请求标志和安全生命周期状态。
3. 在上电早期监听强制跳转 CAN 帧。
4. 按优先级选择 App、FBL 或 PBL。
5. 对目标镜像执行安全启动检查。
6. 对 FBL/PBL 类目标重定位向量表并跳转。
7. 对多核 appimage 类目标调用 ImageM 加载并启动 CPU。
8. 记录安全启动结果和错误状态。

### 3.2 BM 入口和主流程

关键函数：

| 功能 | 函数 | 地址 | 反汇编确认行为 |
| --- | --- | ---: | --- |
| 主入口 | `main` | `0x102124e6` | 调用 `BootM_Init`、`BootM_BootTargetSoftware`，然后死循环 |
| 初始化 | `BootM_Init` | `0x1020a8ac` | 初始化 MCU/DMA/FLS/Port/Mailbox/CAN/SPI/TCAN/SBC，读取 NvM |
| 启动目标 | `BootM_BootTargetSoftware` | `0x1020941c` | 初始化安全基础模块、等待安全帧、执行启动逻辑、加载或跳转 |
| 启动选择 | `Boot_Logic` | `0x10204960` | 根据强制标志、重编程请求、valid flag、安全检查选择目标 |

伪代码：

```c
int main(void)
{
    BootM_Init();
    BootM_BootTargetSoftware();

    while (1) {
    }
}
```

`BootM_Init()` 反汇编确认的初始化顺序：

```text
使能 CP15 / FPU 相关配置
Mcu_Init
Cdd_Dma_Init
Fls_Init
Port_Init
MailboxIpc_Init
Can_Init
Spi_Init
TCAN1043_Init
LP87745_SBC_Init
Can_SetControllerMode(controller=0, mode=1)
NvM_Integration_ReadAll
rbSecFls_Init_MainFunction_BM
```

设计含义：

1. BM 必须先能访问 Flash/NvM，才能读取启动状态。
2. BM 在启动决策前已打开 CAN 控制器，因此可以接收早期强制跳转帧。
3. 安全 Flash 初始化在 NvM 读取之后执行，用于加载安全生命周期、magic number 或安全启动所需状态。

### 3.3 BM 启动目标地址

BM 使用固定地址选择目标镜像：

| index | 目标 | 起始地址 | 说明 |
| ---: | --- | ---: | --- |
| 0 | App / CustApp | `0x00090000` | 普通应用，默认优先启动 |
| 1 | FBL | `0x00050000` | 客户/功能 Bootloader |
| 2 | PBL | `0x00020000` | 平台 Bootloader / 刷写恢复入口 |
| 0（动态） | ProductionApp | `0x00190000` | 快速 App 选择字为 `PDAP` 时替代 CustApp |

`Boot_Logic` 中直接出现：

```text
StayInBootFlag == 2 -> 0x20000
StayInBootFlag == 1 -> 0x50000
App path            -> APP_IMAGE_Addr（0x90000 或 0x190000）
```

### 3.4 BM 启动状态变量

关键全局变量：

| 变量 | 地址 | 大小 | 作用 |
| --- | ---: | ---: | --- |
| `StayInBootFlag` | `0x10216ab8` | 1 | CAN 强制跳转标志，`1` 表示 FBL，`2` 表示 PBL |
| `APP_IMAGE_Addr` | `0x10216abc` | 4 | App 镜像地址变量 |
| `CurrentBoot_Address` | `0x10216ac0` | 4 | 当前启动目标地址 |
| `Fbl_Valid_Flag` | `0x10216f68` | 4 | FBL valid flag |
| `Pbl_Valid_Flag` | `0x10216f6c` | 4 | PBL valid flag |
| `Reprogramming_Request_Flag` | `0x10216f74` | 4 | 重编程请求标志 |
| `Application_Valid_Flag` | `0x10216f9f` | 1 | App valid flag |
| `u8_secboot_sta` | `0x10216fa6` | 1 | 安全启动状态 |
| `u32_secboot_err` | `0x102dff40` | 4 | 安全启动错误码 |

### 3.5 Valid flag 判定规则

`Is_FLAG_Valid` 的反汇编逻辑确认如下：

| index | 目标 | 判定规则 | 结果 |
| ---: | --- | --- | --- |
| 0 | App | `Application_Valid_Flag != 0x55` | 非 invalid 即认为可尝试启动 |
| 1 | FBL | `Fbl_Valid_Flag == 0xAAAAAAAA` | 等于 magic 才 valid |
| 2 | PBL | `Pbl_Valid_Flag == 0xAAAAAAAA` | 等于 magic 才 valid |

App 的规则非常重要：BM 不是判断 App flag 必须等于 `0xAA`，而是判断它不等于 `0x55`。PBL 写 App valid 时使用 `0xAA` 表示有效、`0x55` 表示无效。设计实现时要保持这两个模块的差异，否则 erased/default 状态下的行为可能改变。

#### 3.5.1 快速 App 选择与 NvM 旁路

`[C]` `NvM_Integration_ReadAll` 首先同步读取外部 Flash `0x003E3000` 的 4 字节选择字：

| 32-bit 值 | Flash 字节/ASCII | BM 动作 |
| ---: | --- | --- |
| `0x50415543` | `43 55 41 50` / `CUAP` | `Reprogramming_Request_Flag=0`，`Application_Valid_Flag=0xAA`；不重新赋值 `APP_IMAGE_Addr`，因此保持其初始化值 CustApp `0x90000` |
| `0x50414450` | `50 44 41 50` / `PDAP` | `Reprogramming_Request_Flag=0`，`Application_Valid_Flag=0xAA`，选择 ProductionApp `0x190000` |
| 其他值 | - | 初始化 Fee/NvM，并从 NvM 读取重编程请求和 App valid |

随后 BM 不经 NvM，直接从 `0x08F000` 和 `0x04F000` 读取 FBL/PBL valid word。该快速路径会把 RAM 中的 App valid 强制为 `0xAA`，因此它能够覆盖 NvM 中已持久化的 `0x55`。这不是推测，而是当前二进制行为。

供应商实现必须满足：

1. 保持两个 magic、字节序、目标地址和清除重编程请求的行为。
2. DID `FC01` 更新选择字时必须采用掉电可恢复的提交协议；若要求与当前二进制逐字节等效，则必须至少通过掉电注入证明不会形成误识别的完整 magic。
3. 评审时必须明确选择字与 App invalid 的优先级。若保留当前行为，安全分析必须接受“合法 `CUAP/PDAP` 可覆盖 NvM invalid”；若修正为 invalid 优先，则属于经客户批准的行为变更，不能宣称二进制等效。
4. `0x3E3000` 扇区不得与 App NVM 或其他持久化数据共享物理擦除单元。

### 3.6 普通启动优先级

没有强制跳转帧，也没有有效重编程请求时，BM 的普通启动优先级为：

```text
App -> FBL -> PBL
```

设计伪代码：

```c
for (index = 0; index <= 2; index++) {
    if (Is_FLAG_Valid(index)) {
        address = targetAddress[index]; // 0x90000, 0x50000, 0x20000
        result = SecBoot_Check_Process(address, securityInfo);
        secBoot_Record(result, index);
        if (result == 0) {
            boot(index, address);
            return BOOT_OK;
        }
    }
}

return STAY_IN_BM_OR_ERROR;
```

`Boot_Logic` 对每个候选目标都会调用：

```text
SecBoot_Check_Process
secBoot_Record
```

因此 valid flag 只是“允许尝试启动”的前置条件，不等于无条件跳转。目标镜像仍必须通过安全启动检查。

### 3.7 重编程请求优先路径

`Boot_Logic` 会读取 `Reprogramming_Request_Flag`。反汇编中确认的 magic value：

| `Reprogramming_Request_Flag` | 优先目标 | 地址 | 说明 |
| ---: | --- | ---: | --- |
| `0x10021002` | FBL | `0x50000` | 请求进入 FBL |
| `0x10061006` | PBL | `0x20000` | 请求进入 PBL |
| `0x10861086` | PBL | `0x20000` | 请求进入 PBL |
| `0x10821082` | FBL | `0x50000` | 请求进入 FBL |

`[C]` 重编程请求路径会先读取对应目标的 valid word：FBL/PBL 必须为 `0xAAAAAAAA` 才调用 `SecBoot_Check_Process`。目标 invalid 或安全检查失败后，当前实现只尝试 CustApp `0x90000` 作为兜底：App flag 为 `0x55` 或 CustApp 安全检查失败时返回失败并停留 BM；不会重新执行 App -> FBL -> PBL 的完整普通链。该兜底地址由指令常量固定为 `0x90000`，不会使用 ProductionApp `0x190000`。

### 3.8 上电 CAN 强制跳转帧

BM 在 `BootM_BootTargetSoftware()` 中调用：

```text
rbSec_Basic_init
LoopFor_SafeFrame
Boot_Logic
```

`LoopFor_SafeFrame()` 会循环调用 `Can_MainFunction_Read`，直到收到有效强制跳转帧或计数超时。超时次数与设备类型有关：

| 条件 | 循环上限 |
| --- | ---: |
| `rb_IsDeviceTypeHSSE_u8() != 0` | `0x4f` |
| `rb_IsDeviceTypeHSSE_u8() == 0` | `0x8f` |

`CanIf_RxIndication()` 的规则：

1. 检查 CAN ID，屏蔽高 3 bit 后比较。
2. 目标扩展 CANFD ID 为 `0x190C8532`。
3. 比较 16 字节 payload。
4. 匹配 FBL payload 则 `StayInBootFlag = 1`。
5. 匹配 PBL payload 则 `StayInBootFlag = 2`。

BM `.rodata` 中确认的两个 payload：

| CAN ID | Payload | 结果 |
| ---: | --- | --- |
| `0x190C8532` | `02 10 82 46 4F 52 43 45 4A 55 4D 50 A5 B6 C7 D8` | `StayInBootFlag = 1`，优先 FBL |
| `0x190C8532` | `02 10 60 46 4F 52 43 45 4A 55 4D 50 A5 B6 C7 D8` | `StayInBootFlag = 2`，优先 PBL |

ASCII 字段 `46 4F 52 43 45 4A 55 4D 50` 是 `FORCEJUMP`。

技术要求：

1. 强制跳转帧只应在 BM 早期窗口内生效。
2. 匹配必须同时满足 CAN ID 和完整 payload。
3. `[C]` 强制跳转会绕过 FBL/PBL valid flag 检查，但不得绕过 `SecBoot_Check_Process`。
4. 对外测试时必须分别覆盖 `02 10 82 ...` 和 `02 10 60 ...` 两种路径。
5. 当前 `CanIf_RxIndication` 使用固定 16 字节比较，未看到 DLC 先验检查。新实现必须要求 DLC 至少为 16，再精确比较前 16 字节，避免短帧越界读取；合法帧行为保持不变。
6. `0x4F/0x8F` 是循环计数而非已确认的毫秒值，真实接收窗口必须通过目标硬件计时冻结。

#### 3.8.1 强制/重编程启动决策伪代码

```c
if (StayInBootFlag == 1) {
    target = FBL;                         // CAN 强制路径不检查 FBL valid
} else if (StayInBootFlag == 2) {
    target = PBL;                         // CAN 强制路径不检查 PBL valid
} else if (isFblRequest(reprogramFlag)) {
    if (Fbl_Valid_Flag != 0xAAAAAAAA) goto try_cust_app;
    target = FBL;                         // 0x10021002 / 0x10821082
} else if (isPblRequest(reprogramFlag)) {
    if (Pbl_Valid_Flag != 0xAAAAAAAA) goto try_cust_app;
    target = PBL;                         // 0x10061006 / 0x10861086
} else {
    return tryNormalOrder(APP, FBL, PBL); // 每个候选先检查 valid
}

if (SecBoot_Check_Process(target.address, secInfo) == 0) {
    return boot(target);
}
try_cust_app:
if (Application_Valid_Flag != 0x55 &&
    SecBoot_Check_Process(0x90000, secInfo) == 0) {
    return boot(CUST_APP);
}
return BOOT_FAILED;
```

### 3.9 安全启动详细流程

`[C]` `SecBoot_Check_Process` 返回码：

| 返回码 | 阶段 |
| ---: | --- |
| `0x00` | 允许启动 |
| `0xF0` | HSSE 镜像加载失败 |
| `0xF1` | Hash 失败 |
| `0xF2` | 签名失败 |
| `0xF3` | 解密失败 |
| `0xF4` | 安全模块初始化失败 |

安全信息结构 `g_SecBoot_SecInfo` 为 16 字节：`SecBoot_Enc`、`SecBoot_Boot`、`SecBoot_Fls` 各 1 字节，后跟 13 字节保留区。HSSE 路径主要流程为：

```text
读取镜像安全头
  -> 镜像地址 + 0xB00 读取 16 字节头
  -> 从头字段提取描述符数量并按 16 字节扫描 magic
SecBoot_LoadAppImage
  -> 从镜像地址 + 0xAE0 开始读
  -> 分块最大 0x4000，装载到 0x88000000
Hash（算法枚举 5，64 字节摘要）
Signature verify
按策略执行 authenticated decrypt
记录结果并允许/拒绝启动
```

`[C]` 当 `rb_IsDeviceTypeHSSE_u8()==0` 时，函数调用仍存在，但当前路径不强制执行上述密码学认证并可返回成功。因此规范应写成“所有目标都经过统一安全决策入口；密码学强制策略由设备类型、生命周期和安全配置决定”，不能错误要求所有开发样件与 HSSE 量产件表现完全相同。`rbSec_Basic_init` 失败或非法生命周期可导致 BM 停留/死循环，供应商必须保留 fail-closed 行为并提供可诊断错误记录。

### 3.10 BM 加载和跳转方式

`BootM_BootTargetSoftware()` 中对目标类型有两类处理。

对 FBL/PBL 类目标：

```text
BootM_RelocateVectortable(0x20000, 0x0)
blx 0
```

`BootM_RelocateVectortable()` 循环复制 `0x100` 个 32-bit word，即 `0x400` 字节向量表。它把目标向量表从源地址复制到 `0x0`，再通过 `blx 0` 进入目标。

对 App / appimage 类目标：

```text
ImageM_LoadCpu
  -> Bootloader_socConfigurePll
  -> Bootloader_parseMultiCoreAppImage
  -> Bootloader_loadCpu
  -> Bootloader_runCpu
  -> SOC_rcmWaitBSSBootComplete
  -> ImageM_rprcImageLoad
```

设计含义：

1. FBL/PBL 是传统向量表启动模式。
2. App 可能是多核 appimage/RPRC 格式，需要解析镜像并加载多个 CPU。
3. App 路径涉及 PLL 配置、CPU load/run、BSS boot complete 等 SoC 级流程。

`[C]` 当前解析结果支持 4 个 `ImageM_CpuInfo` 项，每项 16 字节：`cpuId`、`clkHz`、`rprcOffset`、`entryPoint`，总计 64 字节。appimage/RPRC 的全部字段、签名范围及多核释放顺序无法仅由 ELF 唯一恢复，必须把现有量产升级包和烧录包作为 golden vectors，冻结字节级解析结果。

## 4. PBL 详细设计

### 4.1 PBL 模块职责

PBL 是实际 OTA / UDS 刷写执行模块。它通过 DCM/CanTp 接收诊断请求，通过 ImageM/FlashPort/Fls 驱动 Flash，并在写入完成后完成校验和 valid flag 更新。

关键职责：

1. 启动 EcuM 和基础软件栈。
2. 处理 UDS 下载相关服务和例程。
3. 打开目标写入端口并检查下载条件。
4. 擦除目标 Flash 区域。
5. 接收 TransferData 并按页写入 Flash。
6. TransferExit 时补齐最后不足一页的数据。
7. 对下载 log block、镜像数据、Hash、签名做验证。
8. 校验通过后把 App valid flag 写为 `0xAA`。
9. 擦写开始前把 App valid flag 写为 `0x55`，防止断电后启动半写镜像。

#### 4.1.1 PBL 分层模块合同

| 层 | 当前模块/符号 | 供应商责任 |
| --- | --- | --- |
| 系统与调度 | EcuM、OS task | 初始化顺序、1/10ms 周期、后台 job 调度 |
| 通信 | Can、CanIf、CanTp、PduR、DCM、CanSM、ComM | CAN FD 收发、ISO-TP 分段、UDS 会话与 NRC |
| 下载适配 | `DcmAppl_*`、`SWDL_*` | 把 UDS 参数转换为 ImageM 操作，不直接绕过权限检查 |
| 镜像管理 | `ImageM_*` | 地址白名单、下载上下文、写权限、兼容性与认证状态机 |
| Flash 适配 | `ImageM_FlashPort_*`、FlashPort、FlashHandler、Fls | 异步 job、页缓存、擦除分块、设备状态轮询 |
| 持久化 | NvM、rbSecFls、BootM | App valid、重编程请求、写回与重启处理 |
| 安全 | CycurSoc/HSM、`SecFlash_SecCtrl` | SecurityAccess、Hash、签名、生命周期和安全 Flash 访问 |

当前 PBL 中存在 `Fbl_WdgM/Fbl_Port` 符号，但相关函数编译为约 4 字节空操作，不能据此声称当前基线启用了软件喂狗。供应商必须在接口冻结时确认硬件 watchdog 的上电默认状态、禁用方式、Flash 擦写最长阻塞时间和喂狗责任；若启用 watchdog，应补充任务超时与复位测试，但不得改变诊断可观察行为。

### 4.2 PBL 入口与 OS 任务

关键函数：

| 功能 | 函数 | 地址 | 说明 |
| --- | --- | ---: | --- |
| 主入口 | `main` | `0x1024927a` | 调用 `EcuM_Init` 后返回 |
| 1ms 任务 | `Os_Entry_OsTask_FBL_1ms` | `0x102465f2` | 推进 CAN/UDS/CanTp 和安全延迟 |
| 10ms 任务 | `Os_Entry_OsTask_FBL_10ms` | `0x10246c54` | 推进 BootM/CanSM/ComM/EcuM/NvM/rbSecFls |
| 20ms 任务 | `Os_Entry_OsTask_FBL_20ms` | `0x102495b3` | 空函数 |
| 后台任务 | `Os_Entry_OsTask_FBL_BgTask` | `0x102495b6` | 跳转 `ImageM_MainFunction` |

1ms 任务确认调用：

```text
ImageM_ActivateTask_ImageM_BgTask
Can_MainFunction_Write
Dcm_MainFunction
Can_MainFunction_Read
Can_MainFunction_BusOff
FBl_SeedAndKey_AttemptDelayMonitor
CanTp_MainFunction
```

10ms 任务确认调用：

```text
BootM_MainFunction
CanSM_MainFunction
ComM_MainFunction_Can_Network_Channel_Can_Network
EcuM_MainFunction
rbSecFls_MainFunction
NvM_MainFunction
```

后台任务确认调用：

```text
ImageM_MainFunction
  -> ImageM_VerifyMainFunction
  -> ImageM_FlashPort_Mainfunction
  -> ImageM_CompleteCompatible_Mainfunction
  -> ImageM_PortWriteExit_Mainfunction
```

设计含义：

1. UDS 传输在 1ms 任务中推进，保证诊断响应和传输层时序。
2. NvM、安全 Flash、网络状态管理在 10ms 任务中推进。
3. Flash 写入、写入收尾、兼容性检查和校验在 ImageM 后台任务中异步推进。

### 4.3 OTA/UDS 主流程

PBL 的刷写流程是“边接收边写入”，不是全部下载完再统一写 Flash。

```text
进入 PBL
  -> EcuM_Init
  -> DCM/CanTp 等基础通信任务运行
  -> UDS 会话和安全访问
  -> RoutineControl 0xFF00 擦除目标内存
  -> RequestDownload 建立下载条件
  -> TransferData 分块接收
  -> DcmAppl_Dcm_WriteMemory
  -> ImageM_PortWrite
  -> FlashPort_Write
  -> ImageM_MainFunction / FlashPort_WriteDo 后台写 Flash
  -> RequestTransferExit
  -> ImageM_PortWriteExit_Trigger
  -> FlashPort_WriteExit 补齐最后一页
  -> ImageM_VerifyDownloadLogBlock_Start
  -> ImageM_VerifyMainFunction
  -> CRC32 / Hash / Signature 校验
  -> ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

### 4.4 RequestDownload 设计

关键函数：`DcmAppl_Dcm_ProcessRequestDownload`，地址 `0x10240720`。

反汇编确认流程：

```text
设置默认 NRC = 0x72
记录下载方向/类型相关 flag
ImageM_PortOpen(address, length)
ImageM_GetRequestDownloadCondition(address, length)
ImageM_PortGetMaxNOBL(maxNumberOfBlockLength)
FlasPort_ClearPreviousJob
成功时 NRC = 0
失败时 NRC = 0x31
```

技术要求：

1. RequestDownload 必须先打开 ImageM port。
2. 必须检查目标地址和长度是否满足下载条件。
3. 必须返回 maxNumberOfBlockLength。
4. 条件不满足时返回 UDS NRC `0x31`。
5. 成功后清理上一轮 FlashPort job 状态。

`[C]` `ImageM_PortGetMaxNOBL` 返回 `0x0FFF`，即 RequestDownload 正响应中的最大块长度基线为 4095 字节。DCM 层存在较宽的通用地址配置，但最终授权必须由 ImageM 的九块白名单执行，不能用 DCM 通用上限替代。

#### 4.4.1 下载窗口与地址检查

`[C]` `ImageM_PortOpen(address,size)` 遍历 2.4 节九个 `LogBlocks`，仅当以下条件同时成立时建立上下文：

```text
block.base <= address
address + size <= block.base + block.length
请求的起止地址位于同一个 LogBlock
```

当前二进制没有显式整数溢出保护。供应商必须实现等价正常行为并增加以下防御要求：

1. `size` 必须大于 0。
2. 使用减法形式或宽位运算检查范围，拒绝 `address + size` 溢出。
3. 请求不得跨块，即使两个允许块地址连续也必须拒绝。
4. `[C]` 当前 `ImageM_GetRequestDownloadCondition` 在地址范围命中某个 `LogBlock` 时检查 `imageId/isInit`，但未命中任何块的路径会返回成功。由于 RequestDownload 在此前先调用 `ImageM_PortOpen`，正常调用链仍会拒绝白名单外地址。供应商实现必须显式拒绝 no-match，并再次校验地址、长度与已选上下文；这是安全增强。
5. `[C]` 当前 `ImageM_CheckWritePermission` 只按 `pImgContext.imageId` 检查写请求是否位于该 imageId 的整个 `LogBlock`，没有再次使用 `blockAddress/blockLength` 收紧到 RequestDownload 子窗口。供应商必须增加子窗口检查；这是安全增强要求，不是对当前 ELF 行为的描述。
6. `ImageM_PortErase` 只接受与已打开上下文完全相同的地址和长度，不接受子集、超集或向扇区边界扩张后的范围。
7. 底层若必须按物理扇区擦除，擦除前必须证明所有被影响字节均位于同一允许块；否则拒绝请求。

#### 4.4.2 关键运行时数据结构

以下布局由 DWARF `[C]`，供应商内部可重构，但接口语义和状态迁移必须保留：

```c
typedef struct {                 // sizeof = 16
    uint8_t  imageId;            // +0
    uint8_t  reserved0[3];
    uint32_t blockAddress;       // +4
    uint32_t blockLength;        // +8
    bool     isInit;             // +12
    bool     isValid;            // +13
    bool     isFPBlock;          // +14
    uint8_t  reserved1;
} ImageContext;

typedef struct {                 // sizeof = 16
    uint8_t  jobId;              // 0 none, 1 erase, 2 write
    uint8_t  jobStatus;          // 0 done, 1 pending, 2 failed
    uint8_t  imageId;
    uint8_t  reserved;
    uint32_t address;
    uint32_t length;
    const uint8_t *srcData;
} FlashPortJob;

typedef struct {                 // sizeof = 260
    uint32_t remainingLength;
    uint8_t  tempData[256];
} PreviousWriteJob;
```

写收尾 job 的状态值为 `0=no job`、`1=pending`、`2=done`。任一时刻最多允许一个 FlashPort job；新请求到来时若旧 job 为 pending，必须返回 busy/pending，不得覆盖上下文。

#### 4.4.3 App NVM 保护结论

`[C]` App NVM `[0x340000,0x370000)` 不属于任何 `LogBlocks`。正常 `0x34/0x36` 下载路径和 RID `0xFF00` 擦除路径会因 `ImageM_PortOpen` 失败而拒绝该范围；相邻的 ClibData 块在 `0x340000` 精确结束。因此，按当前 PBL 逻辑升级 App 不会主动擦除 App NVM。

该结论有两个工程前提：底层 Flash 的物理擦除单元不得跨越分区边界，供应商实现不得把擦除范围向 `0x340000` 之外对齐。验收必须读取并比较 NVM 全区升级前后的 SHA-256，并对起点、终点、跨界和整数溢出请求做负向测试。

### 4.5 RoutineControl 擦除设计

关键函数：`SWDL_StartEraseMemory_0xFF00`，地址 `0x1024008c`。

反汇编确认流程：

```text
opstatus == INITIAL:
  ImageM_PortOpen
  ImageM_PortErase
  返回 0x0c 表示 pending / 异步处理中

opstatus == PENDING:
  FlashPort_GetJobStatus
  status == 1 -> 返回 0x0a，继续 pending
  status == 0 -> ImageM_PortClose，成功
  其他状态 -> ImageM_PortClose，失败 NRC 0x72
```

擦除后台函数：`FlashPort_EraseDo`，地址 `0x1023c29c`。

关键行为：

1. 擦除前检查当前 App valid 状态。
2. 如果 App 当前有效，则先调用 `ImageM_ImageStatus_WriteApplicationValidFlag(0)`。
3. `ImageM_ImageStatus_WriteApplicationValidFlag(0)` 会把 `Application_Valid_Flag` 写为 `0x55`。
4. 该函数把 NvM block 2 标记 dirty，并调用同步封装 `NvM_Integration_WriteAll`；封装会循环推进 NvM/MemIf 直到状态不再 pending，但不向调用者返回最终写入结果。
5. 当前擦除流程在封装返回后继续执行，未看到对 NvM 最终 job result 的显式成功判定。
6. 每次擦除最大块大小为 `0x10000` 字节。
7. 擦除通过 `FlashHandler_Erase` 执行。
8. 擦除完成后更新 FlashPort job 状态，并清除 ImageM 后台任务激活条件。

断电保护设计含义：

设计意图是在实际擦除前持久化 invalid。正常 NvM 写回成功时，若此后断电，BM 下一次上电不会按普通路径启动该 App，而会尝试 FBL/PBL 恢复入口。由于当前接口不返回最终写入结果，NvM 写失败和写入原子性必须通过故障/掉电测试确认；供应商实现应在擦除前确认 invalid 已成功持久化，或采用具备同等恢复能力的事务记录。

### 4.6 TransferData 写入设计

关键函数：`DcmAppl_Dcm_WriteMemory`，地址 `0x1023e314`。

反汇编确认流程：

```text
opstatus == INITIAL:
  ImageM_CheckWritePermission(address, length)
  失败 -> NRC 0x13
  成功 -> ImageM_PortWrite(address, length, data)
          返回 0x03，标记写入 job active

opstatus == FORCE_RCRRP:
  返回 pending/继续等待

opstatus == PENDING:
  FlashPort_GetJobStatus
  status == 1 -> 返回 0x02，继续 pending
  status == 2 -> ImageM_PortClose，NRC 0x72，失败
  其他状态 -> 成功，清除 active flag
```

`ImageM_PortWrite` 调用 `FlashPort_Write`。`FlashPort_Write` 的职责是将写请求放入 `ImageM_FlashPortJob`，设置后台任务激活条件，真正写入由 `FlashPort_WriteDo` 完成。

### 4.7 Flash 写入粒度和收尾

关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | ---: |
| 写入请求排队 | `FlashPort_Write` | `0x10244ee8` |
| 后台写入 | `FlashPort_WriteDo` | `0x10237824` |
| 写入收尾 | `FlashPort_WriteExit` | `0x10240358` |

反汇编确认的写入粒度：

| 项目 | 值 |
| --- | ---: |
| 写入页大小 | `0x100` 字节 |
| 擦除最大块大小 | `0x10000` 字节 |
| 最后一页补齐值 | `0x00` |

`FlashPort_WriteDo` 维护页缓存。如果收到的数据不足一页，则复制到缓存；当缓存达到 `0x100` 字节后，调用 `FlashHandler_Write` 写入 Flash。写完一页后清空缓存并更新剩余长度和目标地址。

`FlashPort_WriteExit` 在 TransferExit 后执行：

1. 检查页缓存是否还有剩余字节。
2. 若不足 `0x100`，用 `rba_BswSrv_MemSet8` 补 `0x00`。
3. 调用 `FlashHandler_Write` 写入最后一页。
4. 清除 FlashPort job 的地址、长度、缓存状态。
5. 返回写入收尾结果。

技术要求：

1. TransferData 写入必须支持跨页缓存。
2. Flash 写入必须以 `0x100` 字节对齐提交。
3. 最后一页必须补 `0x00`，不能补 `0xFF`，否则与当前 ELF 行为不一致。
4. 写入任务必须异步化，UDS 层通过 pending 状态等待后台 Flash job 完成。

### 4.8 TransferExit 设计

关键函数：`DcmAppl_Dcm_ProcessRequestTransferExit`，地址 `0x1024178c`。

反汇编确认流程：

```text
如果请求上传标志为 1:
  清标志，直接成功
否则:
  opstatus == INITIAL:
    ImageM_PortWriteExit_Trigger
    返回 0x0a pending
  opstatus == FORCE_RCRRP:
    返回 1
  opstatus == PENDING:
    ImageM_ImageM_PortWriteExit_GetJobStatus
    如果 job status == done:
      读取 ImageM_ImageM_PortWriteExit_GetResult
      非 0 -> NRC 0x72
      清 job status
      返回结果
    否则返回 0x0a pending
```

设计含义：TransferExit 不直接同步写最后一页，而是触发后台收尾 job，并通过 opstatus 轮询等待。

### 4.9 下载校验设计

关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | ---: |
| 启动下载 log block 校验 | `ImageM_VerifyDownloadLogBlock_Start` | `0x102468a0` |
| 后台校验入口 | `ImageM_VerifyMainFunction` | `0x102439b8` |
| 下载 log / CRC / Hash / 签名主校验 | `ImageM_VerifyDownloadLogBlock` | `0x1022eee8` |
| CRC32 | `Crc_CalculateCRC32` | `0x10243818` |
| 安全 Flash 控制 | `SecFlash_SecCtrl` | `0x10240918` |
| Hash 校验 | `VerifyHashData` | `0x10235ae0` |
| 签名校验 | `verifySecFlashSignature` | `0x102368c0` |
| App valid flag 写入 | `ImageM_ImageStatus_WriteApplicationValidFlag` | `0x102446a4` |

`ImageM_VerifyMainFunction()` 的主流程：

```text
如果 Verify_isFinish != 0:
  return
清除 ImageM 后台任务激活条件
读取校验输入地址和结果指针
ImageM_VerifyDownloadLogBlock(downloadLog, result)
Verify_isFinish = 1
清除校验输入地址和结果指针
```

`ImageM_VerifyDownloadLogBlock()` 的主要行为：

1. 以 `0x100` 字节为单位读取 Flash。
2. 调用 `Crc_CalculateCRC32` 计算下载 log block CRC。
3. 比较计算 CRC 和下载记录中的 CRC。
4. 根据镜像地址/类型匹配下载记录表。
5. 读取并计算镜像相关地址、长度、Hash 地址和签名地址。
6. 调用 `SecFlash_SecCtrl`。
7. 在安全条件满足时调用 `VerifyHashData`。
8. 在 Hash 未报错时调用 `verifySecFlashSignature`。
9. 校验目标为 App 且结果无错误时，调用 `ImageM_ImageStatus_WriteApplicationValidFlag(1)`。

### 4.10 Hash 校验

`VerifyHashData()` 的反汇编行为：

```text
清空 0x40 字节本地 hash buffer
读取首个 0x100 字节 Flash 数据
cycursoc_HashStart(algorithm=5, data, len=0x100)
循环读取剩余镜像数据:
  Fls_Read
  Fls_MainFunction / Fls_GetStatus 等待完成
  cycursoc_HashUpdate
cycursoc_HashFinish(outputLen=0x40)
读取期望 hash，长度 0x100
如果输出长度 != 0x40 -> 错误 0x04
memcmp(计算 hash, 期望 hash, 0x40)
相等 -> 状态 0
不等 -> 错误 0x04
```

技术要求：

1. Hash 输出长度为 `0x40` 字节。
2. `[C]` 算法枚举值 `5` 对应 SHA-512；供应商必须输出 64 字节 SHA-512 摘要。
3. Flash 读取和 Hash 更新按 `0x100` 字节块推进。
4. Hash engine job 需要通过 `CheckJobAcceptance` 确认。
5. Hash 比对失败时不得置 App valid。

### 4.11 签名校验

`verifySecFlashSignature()` 的反汇编行为：

1. 根据镜像类型/地址获取 key id。
2. 对镜像内容计算 Hash。
3. 从 Flash 读取 `0x200` 字节签名数据。
4. 调用 `cycursoc_JobConfigDefault` 创建安全 job 配置。
5. 调用 `cycursoc_VerifySignature` 验证签名。
6. 签名失败会更新结果状态，阻止 valid flag 写入。

`[C]` 当前安全库的签名方案配置枚举值为 `2`，签名读取长度为 `0x200`。仅凭 ELF 不能可靠确定枚举 2 对应的公钥算法、曲线/模数、padding、摘要封装、key slot 和字节序；这些参数必须从当前 HSM 配置和至少一组成功/失败 golden image 冻结。供应商不得仅按“枚举值 2”猜测算法。

反汇编中可见特定镜像类型长度常量：

| 条件 | 参与签名计算的长度 |
| --- | ---: |
| 镜像类型/地址为 `0x2d0000` | `0x3f800` |
| 镜像类型/地址为 `0x000000` | `0x1f800` |
| 默认路径 | `0x2e0` |

这些值应理解为当前镜像格式/安全 Flash 布局相关常量，重新实现时不能随意修改。

### 4.12 Application valid flag 设计

PBL 中的 App valid 变量：

| 变量 | 地址 | 大小 | 说明 |
| --- | ---: | ---: | --- |
| `Application_Valid_Flag` | `0x10228e28` | 1 | RAM/NvM block 中的 App valid flag |
| `Application_Valid_Flag_RomBlock` | `0x1024b321` | 1 | ROM/default block 常量 |
| `writeNvmflag` | `0x10228e2b` | 1 | NvM 写标志 |

`ImageM_ImageStatus_WriteApplicationValidFlag()` 的规则：

```text
仅当当前 image context == 3 时才写 Application_Valid_Flag
参数 r0 == 1 -> 写 0xAA
参数 r0 != 1 -> 写 0x55
然后:
  NvM_SetRamBlockStatus(block=2, status=1)
  NvM_Integration_WriteAll
```

`0xAA` 来自 `mvneq r1, #0x55`，即 `~0x55 & 0xFF = 0xAA`。

技术要求：

1. App valid flag 有效值必须为 `0xAA`。
2. App invalid flag 必须为 `0x55`。
3. 写 flag 后必须设置 NvM RAM block dirty/status，并执行 NvM 写回。
4. 当前 ELF 只有 image context 为 `3` 时才写 App valid flag。若新设计支持多镜像，必须明确 image index 与 valid flag 的映射。
5. BM 侧对 App 的 valid 判定是 `!= 0x55`，PBL 侧写入是 `0xAA/0x55`，两者必须保持兼容。

特别注意：ProductionApp 的 imageId 为 4，而当前函数仅对 imageId 3 更新 App valid；ProductionApp 的启动允许主要由 `PDAP` 快速选择路径强制形成。供应商不得擅自让 imageId 4 复用 CustApp 的 block 2 提交流程，除非 TBC-10/TBC-12 明确批准。

NvM 接口块合同：App valid 使用 block 2；重编程请求使用 block 3。`BootM_ClearReprogrammingRequestFlag` 把请求清零并把 block 3 标记 dirty，后续 `BootM_MainFunction` 推进 block 2、block 3 及 WriteAll。供应商必须保证复位前写回完成，或在未完成时维持可恢复状态。

### 4.13 DID FC01 快速 App 选择写入

`[C]` `WriteFunc_0xFC01` 是普通 ImageM 白名单之外的专用写入口：

```text
擦除 0x003E3000，长度 0x1000
  -> 轮询 Fls 直到结束
从 FC01 请求数据写入 0x003E3000，长度 0x100
  -> 轮询 Fls 直到结束
```

它用于写入 BM 3.5.1 节读取的 `CUAP/PDAP` 快速选择字，不经过九个 `LogBlocks`，也不触及 `[0x340000,0x370000)` App NVM。供应商必须保持地址、擦除长度和 256 字节写长度，并按诊断规范严格校验 FC01 请求长度、会话和安全级别。当前函数本身未确认存在允许值白名单；是否仅允许 `CUAP/PDAP` 和清除值属于 TBC-04/TBC-10。新实现不得把该 DID 扩展为可指定任意地址的 Flash 写接口。

### 4.14 校验请求与兼容性例程

`[C]` RID `0x0212` 触发下载校验，当前实现对同一流程最多接受 8 次请求计数（0 到 7）；超限路径返回值 `0x09`，其对外 NRC 映射需由诊断规范 `[TBC]`。RID `0x0205` 执行完整兼容性检查，并在 App invalid 时把结果按位合入 `0x05`。供应商必须保持例程的异步/pending 语义、结果记录格式以及 App invalid 对兼容性结果的影响。

## 5. 断电与异常恢复设计

### 5.1 未进入擦写阶段断电

如果只完成了会话切换、安全访问、RequestDownload 或条件检查，尚未进入实际擦除/写入：

```text
旧 App 可能仍完整
Application_Valid_Flag 可能仍为 0xAA
下次上电 BM 可能继续启动旧 App
```

### 5.2 擦除开始后断电

`[C]` `FlashPort_EraseDo` 在实际擦除前先发起并同步推进 App invalid 的 NvM 写回：

```text
ImageM_ImageStatus_ReadApplicationValidFlag
如果当前 App valid:
  ImageM_ImageStatus_WriteApplicationValidFlag(0)
  Application_Valid_Flag = 0x55
  NvM_SetRamBlockStatus(block 2, dirty)
  NvM_Integration_WriteAll
```

当 NvM 写回成功时，预期断电结果为：

```text
App 标记无效
App 区域可能部分擦除或部分写入
下次上电 BM 不会按普通路径启动 App
BM 尝试 FBL，再尝试 PBL
```

当前 `NvM_Integration_WriteAll` 会等待状态退出 pending，但不返回最终成功/失败结果。因此，“任何擦除开始后的断电都必然看到 `0x55`”不能仅靠反汇编证明。必须通过 NvM 写失败注入及逐时间点掉电测试冻结当前 ECU 行为；供应商实现要求在实际擦除前确认 invalid 持久化成功，否则不得擦除 App。

### 5.3 写完但未校验通过前断电

即使 TransferData 全部接收、Flash 已经写完，只要还没有完成：

```text
ImageM_VerifyDownloadLogBlock
VerifyHashData
verifySecFlashSignature
ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

在前置 invalid 已成功持久化的条件下，App valid flag 不会恢复为 `0xAA`，下次上电走恢复路径。若前置 NvM 写入失败，则当前 ELF 的静态行为不足以保证该结论，见 TBC-13。

### 5.4 校验通过并写 valid 后断电

如果 Hash 和签名校验通过，且 PBL 已成功持久化：

```text
Application_Valid_Flag = 0xAA
```

下次上电 BM 普通启动路径会优先尝试 App `0x90000`，并继续执行 `SecBoot_Check_Process`。只有安全启动也通过时才真正启动 App。

当前 valid=`0xAA` 的写入同样通过 `NvM_Integration_WriteAll` 同步推进到非 pending，但调用链不返回最终写入结果。供应商必须在宣布升级完成或复位前确认 valid 提交成功；当前 ECU 在写入失败时的对外响应和复位行为需通过故障注入冻结。

### 5.5 快速选择字对掉电恢复的影响

上述“invalid 后 BM 不启动 App”的结论仅在 `0x3E3000` 不是合法 `CUAP/PDAP` 时成立。若快速选择字仍有效，BM 当前实现会强制 RAM 中 `Application_Valid_Flag=0xAA`，从而覆盖 NvM 的 `0x55`。这是现有设计的安全缺口/产品策略耦合点，供应商不得在文档中忽略。

量产方案必须在以下两种策略中冻结一种：

1. **完全兼容策略**：保留覆盖行为，但升级事务在置 App invalid 前先原子清除快速选择字，并证明清除持久化先于 App 擦除。
2. **安全增强策略**：BM 即使识别 `CUAP/PDAP` 也仍以持久化 invalid 为最高优先级。该策略更稳健，但属于行为变更，必须由客户批准并回归所有量产升级包。

## 6. 安全设计要求

### 6.1 安全启动要求

1. BM 对任何目标启动前必须调用 `SecBoot_Check_Process`。
2. valid flag 不能替代安全启动校验。
3. `secBoot_Record` 必须记录每次安全启动结果。
4. 安全启动错误码应写入共享错误区，例如 `u32_secboot_err`。
5. 强制跳转 CAN 帧和重编程请求不得绕过安全启动。
6. 只有 CAN 强制跳转允许绕过对应 FBL/PBL valid flag；重编程请求必须检查目标 valid。两条路径均不得绕过安全决策，认证失败必须 fail closed。
7. 非 HSSE 设备的密码学旁路只能由受控设备类型/生命周期配置触发，不得由诊断报文或普通 NvM 数据开启。
8. 安全初始化失败、生命周期非法、Hash/签名/解密失败均不得跳入未经认证的目标。

### 6.2 刷写安全要求

1. PBL 必须要求诊断会话和安全访问达到刷写权限。
2. `DcmAppl_Dcm_WriteMemory` 必须调用 `ImageM_CheckWritePermission`。
3. 擦除、写入、校验失败时不得置 App valid。
4. Hash 比对必须使用完整 `0x40` 字节结果。
5. 签名校验必须覆盖当前镜像定义的数据范围。
6. 签名数据读取长度为 `0x200` 字节。
7. 安全库 `cycursoc_*` 的 job acceptance 失败必须视为校验失败。

### 6.3 NvM 状态一致性要求

1. 写 App valid/invalid 后必须调用 `NvM_SetRamBlockStatus`。
2. 必须调用 `NvM_Integration_WriteAll` 将 flag 持久化。
3. BM 启动时必须调用 `NvM_Integration_ReadAll`。
4. 擦写前 invalid 写入必须先于 Flash erase。
5. 校验通过后的 valid 写入必须晚于 CRC/Hash/签名全部成功。

## 7. 诊断与 UDS 行为要求

### 7.1 服务、子功能和标识符基线

`[C]` `Dcm_Cfg_DsdServiceTable0_acst` 含 11 个服务：

| SID | 服务 | 当前支持项 |
| ---: | --- | --- |
| `0x10` | DiagnosticSessionControl | 子功能 `0x01/0x02/0x03/0x06` |
| `0x11` | ECUReset | 子功能 `0x01/0x03` |
| `0x22` | ReadDataByIdentifier | DID `AFF5/F109/F10A/FC00/FC01/FD15` |
| `0x27` | SecurityAccess | `0x61` 获取 challenge，`0x62` 提交 response |
| `0x2E` | WriteDataByIdentifier | 包含 FC01 专用写入口 |
| `0x31` | RoutineControl | RID `0x0205/0x0212/0xFF00` |
| `0x34` | RequestDownload | 最大块长度 `0x0FFF` |
| `0x35` | RequestUpload | 已配置，精确权限/范围 `[TBC]` |
| `0x36` | TransferData | ISO-TP/CAN FD 分块传输 |
| `0x37` | RequestTransferExit | 异步最后页收尾 |
| `0x3E` | TesterPresent | 子功能 `0x00` |

DID 的精确长度、缩放、编码、读写权限与会话矩阵应以项目现有 BYD 诊断表为规范源；本表只证明当前 ELF 存在相应配置。供应商应提交由诊断表自动生成或逐项追溯的 DCM 配置，不得只凭符号名补字段定义。

### 7.2 CAN/CanTp 通信基线

`[C]` PBL Can/CanIf 配置中直接确认的 ID 和帧参数：

| 方向 | CAN ID | 帧型 | 用途 |
| --- | ---: | --- | --- |
| Rx | `0x7DF` | 11-bit standard | 功能寻址 |
| Rx | `0x74C` | 11-bit standard | 物理寻址 |
| Tx | `0x7CC` | 11-bit standard, DLC 上限 64 | 诊断响应 |
| Rx | `0x190C8532` | 29-bit extended | 硬件接收过滤项/项目专用帧 |

表中的 ID、标准/扩展类型和 Tx 长度来自配置常量；“功能寻址/物理寻址/诊断响应”的业务解释为 `[I]`，与常规 UDS 分配及当前 PDU 路由一致，但仍须用 ODX/PDX 和 HIL 抓包冻结。

CAN FD 支持两个时序配置，具体运行时选择条件 `[TBC]`：

| 配置 | 仲裁相位 | 数据相位 | BRS |
| --- | --- | --- | ---: |
| A | 1000 kbit/s；Prop=8, P1=6, P2=5, SJW=1, BRP=4 | 5000 kbit/s；Prop=2, P1=2, P2=3, SJW=2, BRP=2, TDC=100 | 1 |
| B | 500 kbit/s；Prop=32, P1=31, P2=16, SJW=1, BRP=2 | 2000 kbit/s；Prop=8, P1=7, P2=4, SJW=4, BRP=2, TDC=180 | 1 |

CanTp 的 TX data length 为 64，主函数周期为 1ms。配置表中两组超时 tick 为：组 0 `As/Ar=1000, Bs/Br=250, Cs/Cr=3`；组 1 `As/Ar=1000, Bs/Br=100, Cs/Cr=250`。tick 到实际毫秒的映射及两组的 PDU 归属必须在 HIL 中冻结。

### 7.3 SecurityAccess 基线

`[C]` 安全访问采用 Bosch/CycurSoc challenge-response 接口：`rbDiaSecurityAccess_GetChallenge` 与 `VerifyResponse`，级别子功能为 `0x61/0x62`。`FBl_SeedAndKey_GetAttemptCounter_L1` 和 `SetAttemptCounter` 在当前 ELF 中是返回成功的桩函数，未看到持久化尝试计数；仅确认 `FBl_SeedAndKey_AttemptDelayMonitor` 每 1ms 调用。

供应商不得未经确认新增或删除对外可观察的锁定策略。密钥材料、challenge 长度、response 长度、算法、失败延时、复位后延时是否保留均为安全接口冻结项；量产密钥不得出现在源代码、普通 Flash、测试日志或交付文档中。

### 7.4 NRC 与异步行为

PBL 中可确认的 UDS 相关函数和 NRC：

| 场景 | 函数 | NRC/返回 |
| --- | --- | --- |
| RequestDownload 条件错误 | `DcmAppl_Dcm_ProcessRequestDownload` | `0x31` |
| RequestDownload 默认失败 | `DcmAppl_Dcm_ProcessRequestDownload` | `0x72` |
| WriteMemory 权限/长度错误 | `DcmAppl_Dcm_WriteMemory` | `0x13` |
| Flash 写入失败 | `DcmAppl_Dcm_WriteMemory` | `0x72` |
| RoutineControl 擦除失败 | `SWDL_StartEraseMemory_0xFF00` | `0x72` |
| TransferExit 收尾失败 | `DcmAppl_Dcm_ProcessRequestTransferExit` | `0x72` |
| 异步处理中 | 多个函数 | `0x0a` / pending |

技术要求：

1. 长时间 Flash 操作必须通过 pending/RCRRP 机制处理。
2. DCM 主函数必须在 1ms 任务周期推进。
3. CanTp 主函数必须在 1ms 任务周期推进。
4. Flash job 状态必须能被 UDS 层轮询。
5. 失败时必须关闭 ImageM port，避免残留 job 影响下一次刷写。

## 8. 测试要求

### 8.1 BM 启动选择测试

| 编号 | 条件 | 期望 |
| --- | --- | --- |
| BM-01 | App flag != `0x55`，App secure boot 通过 | 启动 App `0x90000` |
| BM-02 | App flag = `0x55`，FBL flag = `0xAAAAAAAA`，FBL secure boot 通过 | 启动 FBL `0x50000` |
| BM-03 | App/FBL invalid，PBL flag = `0xAAAAAAAA`，PBL secure boot 通过 | 启动 PBL `0x20000` |
| BM-04 | `StayInBootFlag = 1` | 优先尝试 FBL |
| BM-05 | `StayInBootFlag = 2` | 优先尝试 PBL |
| BM-06 | CAN ID `0x190C8532` + `02 10 82 FORCEJUMP A5B6C7D8` | 设置 `StayInBootFlag = 1` |
| BM-07 | CAN ID `0x190C8532` + `02 10 60 FORCEJUMP A5B6C7D8` | 设置 `StayInBootFlag = 2` |
| BM-08 | 重编程请求 `0x10021002` | 优先尝试 FBL |
| BM-09 | 重编程请求 `0x10061006/0x10861086` 且 PBL valid | 尝试 PBL并执行安全检查 |
| BM-10 | 强制/重编程目标 invalid 或安全检查失败 | 仅回退 CustApp `0x90000`；App 不可用或失败则停留 BM，不重跑普通链 |
| BM-11 | 重编程请求 `0x10821082` 且 FBL valid | 尝试 FBL `0x50000` 并执行安全检查 |
| BM-11A | 任一重编程请求对应 FBL/PBL invalid | 不检查该目标安全启动，回退 CustApp `0x90000` |
| BM-12 | `0x3E3000=CUAP` | 清重编程请求、App RAM flag=`0xAA`，`APP_IMAGE_Addr` 保持初始化值 `0x90000` |
| BM-13 | `0x3E3000=PDAP` | 清重编程请求、App RAM flag=`0xAA`、选择 `0x190000` |
| BM-14 | `0x3E3000` 为其他值 | 从 NvM 读取 App valid 和重编程请求 |
| BM-15 | 强制 CAN 帧 DLC `<16` | 忽略且无越界访问 |
| BM-16 | HSSE Hash/签名/解密/加载/初始化分别失败 | 分别记录 `F1/F2/F3/F0/F4`，不得启动目标 |

### 8.2 PBL 刷写测试

| 编号 | 条件 | 期望 |
| --- | --- | --- |
| PBL-01 | RequestDownload 合法地址和长度 | 返回成功和 maxNumberOfBlockLength |
| PBL-02 | RequestDownload 非法地址或长度 | NRC `0x31` |
| PBL-03 | 擦除 App 前 App valid | 先写 `Application_Valid_Flag = 0x55` |
| PBL-04 | 擦除长度大于 `0x10000` | 分块擦除 |
| PBL-05 | TransferData 跨 `0x100` 页边界 | 正确缓存并按页写入 |
| PBL-06 | 最后一页不足 `0x100` | TransferExit 补 `0x00` 后写入 |
| PBL-07 | CRC32 失败 | 不写 App valid |
| PBL-08 | Hash 失败 | 不写 App valid，错误状态为 Hash 失败 |
| PBL-09 | 签名失败 | 不写 App valid |
| PBL-10 | CRC/Hash/签名全部通过 | 写 `Application_Valid_Flag = 0xAA` 并 NvM 写回 |
| PBL-11 | RequestDownload 最大块长度查询 | 返回 `0x0FFF` |
| PBL-12 | 请求恰好结束于任一 LogBlock 末端 | 接受；末端后 1 字节拒绝 |
| PBL-13 | 请求跨两个相邻白名单块 | NRC `0x31`，不产生 Flash job |
| PBL-14 | 地址加长度发生 32-bit 溢出或长度为 0 | 拒绝，不产生 Flash job |
| PBL-15 | 擦除范围不是已打开上下文的精确范围 | 拒绝 |
| PBL-16 | 对 `[0x340000,0x370000)` 任意擦除/下载 | 拒绝，App NVM 全区内容不变 |
| PBL-17 | 从 ClibData 尾部跨入 `0x340000` | 拒绝，边界扇区和 NVM 内容不变 |
| PBL-18 | DID FC01 合法写 | 仅擦 `0x3E3000+0x1000`，写 256 字节，BM 正确选择 App |
| PBL-19 | DID FC01 长度/会话/安全级错误 | 拒绝且选择扇区不变 |
| PBL-20 | Flash job pending 时插入新 job | 不覆盖原 job，上层收到 busy/pending |
| PBL-21 | RID 0212 第 1 至第 8 次请求 | 按当前计数策略接受；第 9 次按冻结的 NRC 拒绝 |

### 8.3 断电恢复测试

| 编号 | 断电点 | 期望 |
| --- | --- | --- |
| POW-01 | RequestDownload 前断电 | 旧 App 行为不变 |
| POW-02 | 擦除前 invalid flag 写完后断电 | BM 不启动 App，进入 FBL/PBL 恢复 |
| POW-03 | 擦除中断电 | BM 不启动 App，进入 FBL/PBL 恢复 |
| POW-04 | TransferData 写入中断电 | BM 不启动 App，进入 FBL/PBL 恢复 |
| POW-05 | TransferExit 后、校验前断电 | BM 不启动 App |
| POW-06 | Hash/签名校验中断电 | BM 不启动 App |
| POW-07 | 写 `0xAA` valid 后断电 | BM 下次优先尝试 App |
| POW-08 | FC01 擦除后、写入前断电 | BM 不误识别 `CUAP/PDAP`，按 NvM 路径启动 |
| POW-09 | FC01 写入 4 字节 magic 的每个字节边界断电 | 不形成错误目标选择；结果符合冻结的事务策略 |
| POW-10 | 快速选择字有效、App invalid 后断电 | 验证 5.5 节选定策略，不允许文档与实车行为不一致 |

## 9. 反汇编证据摘要

### 9.1 BM 证据

| 证据 | 位置 |
| --- | --- |
| `main -> BootM_Init -> BootM_BootTargetSoftware -> while(1)` | `main` `0x102124e6` |
| BM 初始化调用 `NvM_Integration_ReadAll` 和 `rbSecFls_Init_MainFunction_BM` | `BootM_Init` `0x1020a8ac` |
| 上电安全帧等待调用 `Can_MainFunction_Read` | `LoopFor_SafeFrame` `0x1020f0d4` |
| CAN ID 和 payload 比较后写 `StayInBootFlag` | `CanIf_RxIndication` `0x1020cfd8` |
| 强制跳转 FBL/PBL 地址 | `Boot_Logic` `0x10204980` 到 `0x10204992` |
| 重编程请求 magic value 比较 | `Boot_Logic` `0x10204994` 到 `0x102049c8` |
| App valid 判断为 `!= 0x55` | `Is_FLAG_Valid` `0x1020d952` 到 `0x1020d95c` |
| FBL/PBL valid 判断为 `0xAAAAAAAA` | `Is_FLAG_Valid` `0x1020d95e` 到 `0x1020d976` |
| 每个候选目标调用 `SecBoot_Check_Process` | `Boot_Logic` 多处 |
| 向量表复制 `0x100` 个 word | `BootM_RelocateVectortable` `0x10211808` |
| App 多核镜像加载 | `ImageM_LoadCpu` `0x10208670` |
| 快速选择字 `CUAP/PDAP` 与 ProductionApp 地址 | `NvM_Integration_ReadAll` 调用链及常量交叉引用 |
| CAN 强制路径跳过 valid；重编程路径检查 valid；失败只回退 CustApp | `Boot_Logic` `0x1020497c` 到 `0x10204a18` |
| 安全启动返回码 `F0` 至 `F4` | `SecBoot_Check_Process` |

### 9.2 PBL 证据

| 证据 | 位置 |
| --- | --- |
| PBL main 调用 `EcuM_Init` | `main` `0x1024927a` |
| 1ms 任务推进 DCM/CanTp/CAN | `Os_Entry_OsTask_FBL_1ms` `0x102465f2` |
| 10ms 任务推进 BootM/NvM/rbSecFls | `Os_Entry_OsTask_FBL_10ms` `0x10246c54` |
| 后台任务调用 `ImageM_MainFunction` | `Os_Entry_OsTask_FBL_BgTask` `0x102495b6` |
| RequestDownload 调用 `ImageM_PortOpen` 和条件检查 | `DcmAppl_Dcm_ProcessRequestDownload` `0x10240720` |
| TransferData 调用 `ImageM_PortWrite` | `DcmAppl_Dcm_WriteMemory` `0x1023e314` |
| 擦除前写 App invalid | `FlashPort_EraseDo` `0x1023c2d2` 到 `0x1023c2e6` |
| 每次擦除最大 `0x10000` | `FlashPort_EraseDo` `0x1023c2ee` 到 `0x1023c2f4` |
| 写入页大小 `0x100` | `FlashPort_WriteDo` / `FlashPort_WriteExit` |
| TransferExit 触发写入收尾 | `DcmAppl_Dcm_ProcessRequestTransferExit` `0x1024178c` |
| CRC32 计算下载 log block | `ImageM_VerifyDownloadLogBlock` `0x1022ef32` 到 `0x1022ef3c` |
| Hash 校验 | `VerifyHashData` `0x10235ae0` |
| 签名校验 | `verifySecFlashSignature` `0x102368c0` |
| 校验通过后写 App valid | `ImageM_VerifyDownloadLogBlock` `0x1022f110` 到 `0x1022f11a` |
| App valid 写 `0xAA/0x55` 并 NvM 写回 | `ImageM_ImageStatus_WriteApplicationValidFlag` `0x102446a4` |
| 九个下载白名单区间 | `LogBlocks` 配置表及 `ImageM_PortOpen` |
| RequestDownload no-match 返回及前置拒绝门 | `ImageM_GetRequestDownloadCondition` `0x10241290`、`ImageM_PortOpen` `0x10240870` |
| TransferData 只按整个 LogBlock 检查 | `ImageM_CheckWritePermission` `0x10244674` |
| FC01 擦 `0x3E3000/0x1000` 并写 `0x100` | `WriteFunc_0xFC01` `0x102414f0` |
| 最大下载块长度 `0x0FFF` | `ImageM_PortGetMaxNOBL` |
| Hash 枚举 5、摘要 64 字节 | `VerifyHashData` DWARF 与反汇编 |
| 签名读取 `0x200` 字节、scheme=2 | `verifySecFlashSignature` `0x102368c0` |
| NvM WriteAll 同步轮询但不返回 job result | `NvM_Integration_WriteAll` `0x10243672` |
| 两套 CAN FD 位时序与诊断 ID | `CanConfigSet_ETAS_CAN_CanControllerBaudrateConfig_0/1`、`CanIf_Prv_RxPduConfig_tacst`、`CanIf_TxPduGen_a` |
| 诊断服务、DID、RID 和 CAN ID | DCM/CanIf/Can 配置常量表 |

## 10. 已知限制和待确认项

以下项目不能由两个 ELF 唯一恢复，必须在供应商编码前关闭：

| TBC ID | 待冻结项 | 所需输入/验证 |
| --- | --- | --- |
| TBC-01 | SoC 型号、启动 ROM 合同、核启动顺序、时钟和 MPU/cache 属性 | 芯片手册、现有硬件初始化记录、JTAG trace |
| TBC-02 | appimage/RPRC、下载 log、镜像头、Hash/签名字段的字节级格式 | 当前量产升级包、打包/签名工具、golden image |
| TBC-03 | 签名 scheme=2 的算法、参数、key slot、证书/公钥轮换 | HSM/CycurSoc 配置及安全团队规范 |
| TBC-04 | 全部 DID 的长度/编码/权限、RID 结果格式和 NRC 映射 | BYD 诊断表、ODX/PDX、实车抓包 |
| TBC-05 | CAN 两套波特率的选择条件、CanTp PDU 到超时组的映射 | 网络设计、HIL 总线测试 |
| TBC-06 | 安全生命周期枚举及 HSSE/非 HSSE 的量产允许策略 | HSM 生命周期规范 |
| TBC-07 | OS 任务优先级、栈水位、最坏执行时间、Flash 操作超时 | 目标板测量、静态栈分析 |
| TBC-08 | watchdog 的启用状态、窗口、喂狗责任和复位原因持久化 | 硬件安全需求、目标板测试 |
| TBC-09 | 外部 Flash 型号、页/扇区几何、写保护、耐久性和掉电行为 | Flash 数据手册和板级原理图 |
| TBC-10 | 快速选择字与 NvM invalid 的最终优先级策略 | 客户安全评审决定 |
| TBC-11 | FBL 自身的诊断/刷写能力和与 BM/PBL 的分工 | FBL ELF/源码或供应商接口文档 |
| TBC-12 | ProductionApp/CustApp 切换、兼容性规则和回滚策略 | 产品升级策略与发布流程 |
| TBC-13 | App invalid/valid 的 NvM 最终 job result、掉电原子性及写失败时的诊断/复位行为 | NvM 配置、Fee/Flash 故障注入、逐时间点掉电测试 |

本文基于静态分析，没有运行时 trace；函数名和结构名来自保留符号/DWARF，但宏、生成器输入和源代码注释不可见。任何“与当前完全相同”的声明必须以第 15 节差分测试为准，而不是只比较本文件中的函数名。

## 11. 重新实现时的最低兼容要求

如果需要从零实现一个兼容当前行为的 BM+PBL，至少必须满足：

1. 保持 BM 目标地址：PBL `0x20000`、FBL `0x50000`、CustApp `0x90000`、ProductionApp `0x190000`。
2. 保持 BM 普通优先级：App -> FBL -> PBL。
3. 保持强制 CAN 帧：ID `0x190C8532`，payload 使用 `02 10 82/60 FORCEJUMP A5 B6 C7 D8`。
4. 保持重编程请求映射：`0x10021002/0x10821082` -> FBL，`0x10061006/0x10861086` -> PBL。
5. 保持 FBL/PBL valid magic：`0xAAAAAAAA`。
6. 保持 App invalid 值：`0x55`。
7. 保持 PBL 写 App valid 值：`0xAA`。
8. 保持 BM 对 App 的判定：`Application_Valid_Flag != 0x55`。
9. 保持所有启动目标都经过统一安全决策入口；仅 CAN 强制目标跳过 valid，重编程目标必须检查 valid。
10. 保持 PBL 擦写前先 invalid App，校验通过后再 valid App。
11. 保持 Flash 写入页大小 `0x100`，最后一页补 `0x00`。
12. 保持 Flash 擦除最大块 `0x10000`。
13. 保持 TransferData 异步写入和 TransferExit 异步收尾机制。
14. 保持 CRC32 + SHA-512 + 签名三层校验后才允许恢复 App valid。
15. 保持 valid flag 写入后的 NvM dirty/status 设置和 WriteAll 持久化。
16. 保持九个 LogBlock 的地址、imageId 和单块包含检查；App NVM `[0x340000,0x370000)` 永久拒绝普通擦写。
17. 保持 `CUAP/PDAP`、FC01 专用扇区和 CustApp/ProductionApp 选择行为，除非 TBC-10 批准安全增强变更。
18. 保持 UDS 服务、子功能、DID/RID、CAN ID、最大块长度及异步 NRC 的对外兼容性。
19. 保持 HSSE 安全启动错误分类、共享错误记录和 fail-closed 处理。
20. 保持 appimage/RPRC 对当前所有量产镜像的字节级兼容。

## 12. 供应商系统需求

### 12.1 BM 需求

| ID | 强制需求 | 验证方法 |
| --- | --- | --- |
| BM-REQ-001 | BM 必须从 `0x20000` 启动并完成 SoC、Flash、NvM、安全模块和早期 CAN 初始化。 | map/反汇编/JTAG |
| BM-REQ-002 | BM 必须按 3.5.1 节读取快速选择字，再按对应路径读取 NvM 或强制 App 选择。 | 单元/HIL |
| BM-REQ-003 | BM 必须直接读取 `0x8F000/0x4F000` 的 FBL/PBL valid word，并按 `0xAAAAAAAA` 判断。 | 故障注入 |
| BM-REQ-004 | 无强制和重编程请求时必须按 App、FBL、PBL 顺序逐一执行 valid 与安全检查。 | 决策矩阵 |
| BM-REQ-005 | CAN 强制路径必须绕过目标 valid；重编程路径必须检查目标 valid。两者在失败后只尝试 CustApp `0x90000`。 | 分支覆盖/HIL |
| BM-REQ-006 | CAN 强制帧必须同时匹配 29-bit ID、DLC 和完整 16 字节 payload。 | 总线模糊测试 |
| BM-REQ-007 | BM 必须区分并持久/共享记录安全初始化、加载、Hash、签名和解密失败。 | HSM 故障注入 |
| BM-REQ-008 | FBL/PBL 启动必须复制 `0x400` 字节向量表到 `0x0`，完成必要反初始化后跳转。 | JTAG/内存检查 |
| BM-REQ-009 | App 启动必须兼容当前多核 appimage/RPRC，支持最多 4 个 CPU 描述项。 | golden images |
| BM-REQ-010 | 无可启动目标时必须留在 BM 安全错误态，不得执行未验证地址。 | 负向测试 |

### 12.2 PBL 需求

| ID | 强制需求 | 验证方法 |
| --- | --- | --- |
| PBL-REQ-001 | PBL 必须实现 4.1.1 的分层，并禁止 DCM/SWDL 绕过 ImageM 地址权限。 | 设计/代码评审 |
| PBL-REQ-002 | PBL 必须运行 1ms、10ms 和后台状态机；长操作不得阻塞 DCM 的周期推进。 | 时序测量 |
| PBL-REQ-003 | PBL 必须仅允许 2.4 节九个 LogBlock，且每个请求完整位于一个块内。 | 边界/模糊测试 |
| PBL-REQ-004 | PBL 必须永久保护 `[0x340000,0x370000)`，包括底层扇区对齐后的实际擦除范围。 | 全区哈希/逻辑分析 |
| PBL-REQ-005 | RequestDownload 必须返回 maxNumberOfBlockLength `0x0FFF` 并清理上一轮非 pending 状态。 | UDS 测试 |
| PBL-REQ-006 | 擦除请求必须等于已打开窗口，分块最大 `0x10000`，失败必须关闭端口并保持 invalid。 | Flash fault injection |
| PBL-REQ-007 | 写入必须按 `0x100` 页缓存，支持跨页，最后一页使用 `0x00` 补齐。 | 边界数据比对 |
| PBL-REQ-008 | 任一时刻最多一个 Flash job，job/context 不得被新请求覆盖。 | 并发请求测试 |
| PBL-REQ-009 | App 擦除前必须先将 block 2 的 valid 持久化为 `0x55`。 | 掉电注入 |
| PBL-REQ-010 | 仅 CRC32、SHA-512、签名和兼容性全部通过后，imageId 3 才可写 `0xAA`。 | 篡改测试 |
| PBL-REQ-011 | 重编程请求清除必须更新 NvM block 3，并在复位前完成或保证恢复。 | 复位注入 |
| PBL-REQ-012 | FC01 必须只访问 `[0x3E3000,0x3E4000)`，不得复用为任意地址写接口。 | 安全测试 |
| PBL-REQ-013 | PBL 必须实现第 7 节诊断和 CAN 基线，并由诊断表冻结权限矩阵。 | CANoe/诊断一致性 |
| PBL-REQ-014 | SecurityAccess 和 HSM 服务必须 fail closed，密钥不得进入普通软件交付物。 | 安全评审 |
| PBL-REQ-015 | 所有 Flash/HSM pending 状态必须可超时、可取消或可由复位安全恢复。 | 超时/复位测试 |

### 12.3 质量与安全需求

| ID | 强制需求 |
| --- | --- |
| QUA-REQ-001 | 供应商必须提供 MISRA/CERT-C 规则集、静态分析报告及全部 deviation 的理由和批准记录。 |
| QUA-REQ-002 | 所有地址加法、长度换算、页/扇区对齐必须有溢出和越界检查。 |
| QUA-REQ-003 | 所有外部输入长度必须先检查再访问，包括 CAN DLC、UDS payload、DID、签名和镜像头。 |
| QUA-REQ-004 | 安全相关比较不得泄漏密钥材料；私钥不得进入 ECU，公钥/slot 更新必须受认证。 |
| QUA-REQ-005 | 生产版本必须关闭未授权 debug、内存读回和任意地址上传/下载能力。 |
| QUA-REQ-006 | 构建必须可复现，输出 ELF、HEX/BIN、map、符号、编译器版本、配置输入和 SHA-256 清单。 |
| QUA-REQ-007 | 需求、设计、代码、单元测试、集成测试必须双向追溯，不允许孤立代码或未验证需求。 |
| QUA-REQ-008 | 供应商必须提交 WCET、CPU 负载、最大栈水位、Flash 擦写超时和启动时间测量。 |

## 13. 状态机详细设计

### 13.1 BM 状态机

| 状态 | 入口动作 | 退出条件 | 下一状态 |
| --- | --- | --- | --- |
| RESET | 复位向量和最小硬件初始化 | 入口完成/异常 | INIT/ERROR |
| INIT | SoC、CAN、Flash、NvM、安全模块初始化 | 成功/失败 | EARLY_CAN/ERROR |
| EARLY_CAN | 在计数窗口接收强制帧 | 匹配或超时 | SELECT |
| SELECT | 评估 StayInBoot、重编程、快速选择、valid | 得到候选/无候选 | AUTH/ERROR |
| AUTH | 对候选执行统一安全决策并记录结果 | 成功/失败 | LOAD/FALLBACK |
| FALLBACK | 强制路径只评估 App；普通路径取下一候选 | 有候选/耗尽 | AUTH/ERROR |
| LOAD | App 多核加载或 FBL/PBL 向量搬移 | 成功/失败 | HANDOVER/ERROR |
| HANDOVER | 反初始化冲突外设、同步缓存并释放 CPU/跳转 | 不应返回 | 目标软件 |
| ERROR | 保持安全状态和诊断信息 | 受控复位 | RESET |

### 13.2 PBL 下载状态机

| 状态 | 允许事件 | 必须动作 | 失败处理 |
| --- | --- | --- | --- |
| IDLE | 会话切换/SecurityAccess | 建立授权上下文 | NRC/延时 |
| OPEN | RequestDownload/RID FF00 | 白名单和范围检查，创建 ImageContext | 关闭 context |
| INVALIDATE | App 擦除前 | block 2=`0x55` 并确认持久化 | 不执行擦除 |
| ERASE_PENDING | Flash erase job | 每次最大 `0x10000`，周期轮询 | job failed、保持 invalid |
| RECEIVE | TransferData | 序号、地址、长度、窗口权限检查 | NRC、不得越界写 |
| WRITE_PENDING | 页写 job | 256 字节提交、更新剩余地址/长度 | job failed、保持 invalid |
| EXIT_PENDING | TransferExit | 末页补零并写入 | NRC `0x72`、保持 invalid |
| VERIFY_PENDING | RID 0212/校验触发 | CRC32、SHA-512、签名、兼容性 | 记录具体失败 |
| COMMIT | App imageId 3 全部通过 | block 2=`0xAA` 并 WriteAll | 保持 invalid |
| COMPLETE | 响应完成/清重编程请求/复位 | 确认 block 2/3 持久化 | 延迟复位或报错 |

取消、S3 超时、总线中断或 ECUReset 到来时，不得把 ERASE_PENDING 之后的状态直接提交为 valid。任何非法状态迁移均应清理 RAM job/context，保留持久化 invalid，并允许下次进入 PBL 恢复。

### 13.3 Flash job 状态机

```text
NONE(0)
  -> submit erase/write
PENDING(1)
  -> Fls_MainFunction + GetStatus
  -> success: DONE(0)
  -> driver/error/timeout: FAILED(2)
DONE/FAILED
  -> 上层读取结果并显式 clear
  -> NONE
```

供应商内部枚举可以不同，但不得在结果被消费前重用 job 缓冲；源数据缓冲在 write job 完成前必须保持有效。

## 14. 接口冻结与供应商交付物

### 14.1 编码前必须冻结的接口

1. 完整 4 MiB Flash 分区、物理扇区表、各分区所有者和写保护策略。
2. BM/PBL/FBL/App 的镜像格式、链接地址、入口、头字段、Hash/签名覆盖范围和 padding。
3. App 多核 CPU 表、加载地址、PLL/时钟、核释放顺序和超时。
4. NvM block 2/3 的布局、默认值、冗余/CRC、写周期和掉电原子性。
5. FBL/PBL valid word 的生产、更新、擦除和恢复流程。
6. 全部 UDS 服务会话/安全矩阵、DID/RID 数据格式、NRC 和 P2/P2*/S3 时间。
7. CAN 波特率选择、ID、CanTp 参数、网络唤醒/休眠和 BusOff 恢复。
8. HSM 生命周期、key slot、签名算法、SecurityAccess 和安全错误处理。
9. 快速选择字 TBC-10 策略、FC01 权限以及 Cust/Production App 发布流程。
10. watchdog、复位原因、错误日志和现场恢复策略。

### 14.2 供应商强制交付物

1. 《Bootloader 软件架构设计》和与本文逐条差异说明。
2. 《BM 详细设计》《PBL 详细设计》、状态机、时序图、接口数据字典和 Flash 分区图。
3. 全部源码、生成配置、链接脚本、构建脚本、固定工具版本和可复现构建说明。
4. 编译输出：ELF、HEX/BIN、map、符号文件、反汇编、SHA-256 和烧录包。
5. 镜像打包/签名/验签工具及其版本化格式规范；密钥按安全流程另行管理。
6. 单元、集成、HIL、诊断一致性、掉电注入、模糊测试和安全测试报告。
7. 静态分析、MISRA deviation、代码覆盖率、栈/性能/WCET 和开源软件清单。
8. 需求到测试的双向追溯矩阵，以及所有 TBC 的关闭证据。
9. 量产烧录、升级、回滚、故障恢复、版本识别和售后诊断操作说明。
10. 与当前 ELF 的差分测试报告，列出每一项有意行为变更及客户批准记录。

## 15. 验收策略与通过准则

### 15.1 差分基线

在同一 ECU/HIL 上对“当前 ELF”和“供应商 ELF”施加相同输入，采集 CAN、复位原因、外部 Flash、NvM、共享错误区和启动目标。至少覆盖第 8 节全部用例、九个分区的边界值、所有 UDS 服务、所有安全失败类型及所有掉电点。

通过条件：

1. 除已批准变更外，UDS 正/负响应、NRC、pending 行为、CAN ID/DLC 和启动目标一致。
2. 所有当前量产升级包均能完成下载、认证和启动；任何单字节篡改均不得提交 valid。
3. App NVM `[0x340000,0x370000)` 在 CustApp、ProductionApp、BM、FBL、PBL、HSM 和数据块升级前后逐字节一致。
4. 边界、跨区、溢出、短帧、乱序块、重复块和并发 job 不产生越界读写。
5. 在擦除、每页写、TransferExit、验证和 valid/NvM 写回的每个关键点断电，系统都能进入已冻结的安全恢复路径。
6. HSSE 量产生命周期下，未签名、错 key、错 Hash、错签名、截断和回滚镜像按安全策略拒绝。
7. BM 无合法目标时保持安全状态；不得因无效指针、损坏头或超长字段跳转。
8. 满足已冻结的启动时间、诊断响应时间、栈水位、CPU 负载和 Flash 操作超时指标。

### 15.2 退出门槛

以下条件全部满足后才可接受供应商版本：零个开放的安全高危/严重缺陷；零个未批准的二进制兼容差异；所有 TBC 已签字关闭；需求和分支覆盖达到双方约定；量产包回归、NVM 保持、掉电恢复和 HSM 安全测试全部通过；交付物可在客户环境中独立复现构建。

## 16. 最终结论

本文已能作为供应商重实现的架构和详细设计输入，但它不是源码的数学等价恢复。已确认的核心功能包括：BM 四目标选择、两类强制入口、普通/重编程/CAN 强制路径差异、快速 App 选择、HSSE 安全启动、PBL UDS/OS/ImageM/FlashPort 分层、九块下载白名单、App NVM 逻辑保护、页写/擦除、CRC32/SHA-512/签名以及 NvM valid 的写回调用链。物理擦除影响、NvM 写失败和掉电原子性仍必须按 TBC-09/TBC-13 在目标板上验证。

供应商实现“功能与现在相同”的最终判据不是代码结构相似，而是：冻结所有 TBC 后，通过当前 ELF 与新 ELF 的同输入差分测试，并满足第 12 节需求和第 15 节验收门槛。
