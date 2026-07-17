# CR60 Light BYD Bootloader 详细设计文档与技术要求

> 文档用途：供应商 BM/PBL 等效重实现、接口冻结、代码评审及验收测试。
>
> 文档版本：V3.1（基于无源码 ELF、DWARF、初始化数据及代码截图交叉复核，2026-07-17）<br>
> 结论等级：`[C]` 当前 ELF 的反汇编/DWARF/常量表直接确认；`[S]` 仅由 `BM/` 代码截图确认；`[C+S]` 当前 ELF 与截图一致；`[I]` 由调用关系和命名推断；`[TBC]` 必须通过升级包、诊断规范、硬件资料或 HIL 冻结。<br>
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

分析依据包括 ELF header、program/section header、`.symtab`、`.debug_info`、`.debug_line`、`.rodata/.cinit` 常量、TI ARM objdump 反汇编结果，以及 `BM/` 目录中的会议代码截图。由于没有完整源代码和原始设计文档，本文将“当前 ELF 直接确认的事实”“截图确认但可能属于相邻版本的事实”和“根据函数名/流程推断的设计含义”分开表述。

配套静态证据已保存到 `BM_PBL_Reverse_Engineering_Evidence/`。其中 `*.key_functions.txt` 适合查看关键流程，`*.disassembly.txt` 是全量指令反汇编，`*.dwarf_info.txt` 用于核对结构体和变量信息；证据文件用途和引用规则见该目录的 `README.md`。

地址说明：符号表中的 Thumb 函数地址最低位会置 1，例如 `Boot_Logic` 在符号表显示为 `0x10204961`，实际指令起始地址为 `0x10204960`。本文统一使用去掉 Thumb bit 后的指令地址。

本文件不能替代缺失的源代码、链接脚本、芯片 Flash 数据手册、密钥配置、ODX/PDX 和升级包格式定义。供应商不得把 `[TBC]` 项自行解释为接口；这些项目必须在详细设计评审前形成双方签字的《接口冻结清单》。

## 0. 静态逆向审计声明

本版对启动选择、下载授权、Flash 擦写、App valid 提交、CAN 配置和密码学校验等高风险路径进行了符号表、DWARF、初始化常量和指令级交叉复核。文档的使用边界如下：

1. 标为 `[C]` 的内容可在当前两份 ELF 中找到直接证据；第 9 节给出关键符号或指令地址。
2. 标为 `[S]` 的内容只在 `BM/` 截图中可见。截图没有仓库版本号、编译哈希和完整上下文，不能自动视为当前 ELF 的原始源码。
3. 标为 `[C+S]` 的内容已按控制流、常量、结构体布局或调用顺序与当前 ELF 交叉匹配，但仍不代表逐行源码完全相同。
4. 标为 `[I]` 的内容是由调用关系、变量/函数命名或配置路由得到的解释，不应当替代 ODX、升级包格式或芯片手册。
5. “供应商必须/不得”可能是为了消除当前二进制缺陷而增加的安全要求。若该要求改变掉电、非法输入或故障场景的可观察行为，必须列入差异清单并获得客户批准，不能宣称它已由当前 ELF 实现。
6. 静态反汇编不能证明真实硬件上的 Flash 物理擦除几何、NvM 掉电原子性、HSM key/算法映射、总线时序和所有 NRC。此类结论必须通过 golden image、HIL、掉电注入和诊断一致性测试关闭。

V3.1 复核中确认并修正的关键点：

| 项目 | 当前 ELF 的实际行为 |
| --- | --- |
| BM 重编程请求 | FBL/PBL 重编程请求会检查对应 valid word；只有早期 CAN 强制路径绕过 valid |
| BM CAN 强制失败 | CAN 强制 FBL/PBL 路径绕过 valid，但安全检查失败后直接返回失败；**不回退 App** |
| BM 重编程失败回退 | 仅重编程请求路径在目标 invalid 或安全检查失败后固定尝试 CustApp `0x90000`，不使用动态 `APP_IMAGE_Addr`，也不重跑普通链 |
| BM 生命周期门 | 只有 OnBoard/Customizing 生命周期比较 128 字节 magic；比较失败时，只有 `StayInBootFlag=1/2` 可继续进入对应 Bootloader |
| BM lifecycle 获取失败 | `rbSec_Basic_init` 忽略 lifecycle load/query 返回值；`rbSecBM_CheckLCValid` 对非 1/2 值直接通过，不能宣称当前已对所有 lifecycle 故障 fail closed |
| BM CAN 短帧 | 当前 `CanIf_RxIndication` 固定比较 16 字节，未读取 `SduLength`；短 DLC 可能导致越界读取，不能写成“当前会安全忽略” |
| PBL TransferData 权限 | `ImageM_CheckWritePermission` 只收敛到整个 `LogBlock`，没有收敛到本次 RequestDownload 子窗口 |
| RequestDownload 二次条件 | `ImageM_GetRequestDownloadCondition` 在命中块时检查上下文，但未命中任何块的路径会返回成功；前置 `ImageM_PortOpen` 才是当前实际拒绝门 |
| RequestDownload 清理动作 | `FlasPort_ClearPreviousJob` 只清 260-byte 页缓存，不清异步 FlashPort job；`ImageM_PortOpen` 也不检查 pending 就可替换 context |
| NvM valid 写回 | `NvM_Integration_WriteAll` 同步推进 NvM/MemIf 直到不再 pending，但接口不返回最终写入成功/失败；擦除路径随后继续执行 |
| App NVM 物理影响 | ImageM 不直接擦写 `0x340000..0x3CFFFF`；但 Fee 的两个物理 bank 为 `0x350000..0x38FFFF`、`0x390000..0x3CFFFF`，写 valid flag 时可能发生页写、回收或 bank 迁移 |
| valid 与兼容性顺序 | `ImageM_VerifyDownloadLogBlock` 在其 CRC/Hash/签名结果后更新 CustApp valid；RID `0x0205` 是独立调用链，当前所谓 CompleteCompatible 实际只检查 App flag 是否为 `0xAA` |
| PBL lifecycle CRC 失败 | 初始化忽略返回值，security-enforced 查表不读 valid byte；lifecycle=`0xFF` 时普通镜像退回 `+0x92` 策略字节，不是当前全局 fail-closed |

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

不要把 BM ELF 的 link/entry 地址 `0x20000` 与外部 Flash 中 BM 下载容器的基址混为一谈：PBL `LogBlocks` 和安全校验路径把 BM 镜像标识地址定义为 `0x000000`、长度 `0x20000`，而 BM ELF 自身的 `.sbl_init_code` 链接到 `0x20000`。两组值均为 `[C]`，静态 ELF 不能独自恢复打包工具如何把容器字段、加载地址和运行入口关联起来；供应商必须用当前 BM golden package 和打包器关闭 TBC-02，不得因地址看似重叠而自行平移镜像。

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

下表使用半开区间 `[start,end)`；“可下载”表示当前 PBL `LogBlocks` 白名单允许 `ImageM_PortOpen`。九个 LogBlock、安全扇区和 Fee bank 地址为 `[C]`；仅由 Flash 布局截图补齐的末尾保留区单独标为 `[S]`。

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
| - | ProductionSW/App NVM | `[0x340000,0x350000)` | `0x010000` | ImageM 禁止；当前 Fee 表不包含 |
| - | Customer App NVM / Fee bank 0 | `[0x350000,0x390000)` | `0x040000` | ImageM 禁止；Fee/NvM 管理 |
| - | Customer App NVM / Fee bank 1 | `[0x390000,0x3D0000)` | `0x040000` | ImageM 禁止；Fee/NvM 管理 |
| - | 未定义/保留 | `[0x3D0000,0x3E0000)` | `0x010000` | 禁止 |
| - | 生命周期/安全数据 bank | `[0x3E0000,0x3E1000)` | `0x001000` | 普通 UDS 禁止 |
| - | 安全 key 数据 bank | `[0x3E1000,0x3E2000)` | `0x001000` | 普通 UDS 禁止 |
| - | lifecycle magic bank | `[0x3E2000,0x3E3000)` | `0x001000` | 普通 UDS 禁止；DID `FC00` 专用路径 |
| - | 快速 App 选择扇区 | `[0x3E3000,0x3E4000)` | `0x001000` | 仅 DID `FC01` 专用路径 |
| - | Reserve `[S]` | `[0x3E4000,0x3F0000)` | `0x00C000` | 当前无 ImageM/DID 擦写入口 |
| - | Reserve for future blocks `[S]` | `[0x3F0000,0x400000)` | `0x010000` | 当前无 ImageM/DID 擦写入口 |

`[C]` `LogBlocks` 在 PBL `.data` 中是 9 个 `{base,length}` 记录，数组原始顺序为 BM、FBL、PBL、CustApp、ProductionApp、CustData、ClibData、HSM、WeifuData；表中按地址重新排序展示。关键非易失地址：FBL valid word 位于 `0x08F000`，PBL valid word 位于 `0x04F000`；BM 直接各读取 4 字节。BM 安全 Flash 初始化表依次包含 `0x3E0000/0x3E1000/0x3E2000` 三个 bank，每个读取 `0x200` 字节到 RAM。

`[C]` BM 和 PBL 各自的 Fee 配置表 `rba_FeeFs1x_Prv_Cfg_FlashPropTable_cast` 内容相同，分别位于 `0x1021464C`、`0x1024BF18`，都包含两个 inclusive 物理区间：`0x350000..0x38FFFF` 和 `0x390000..0x3CFFFF`。表中改写为等价半开区间。因此“普通 UDS 禁止”只表示 ImageM/FlashPort 不允许把诊断地址直接指向这些区域；它不表示 Fee/NvM 永不在其中编程或擦除。供应商不得给 BM/PBL 生成互不一致的 Fee bank 配置。

`[S]` `BM/未命名图片.png` 把 `0x340000..0x34FFFF` 标为 ProductionSW NVM，把 `0x350000..0x3CFFFF` 标为 Customer App NVM，与 PBL Fee 两个 bank 的范围一致；同一截图把 `0x3E4000..0x3EFFFF` 和 `0x3F0000..0x3FFFFF` 标为保留区。供应商必须结合实际 Flash 扇区几何验证 ImageM 的任何擦除单元不跨入 NVM；Fee/NvM 则只能在其已冻结的两个 bank 内按事务协议工作，并保持所有非目标逻辑块。

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

#### 3.2.1 `BootM_BootTargetSoftware` 精确控制流

`[C+S]` 当前 ELF 与 `BM/555.png`、`BM/666.png` 中的主流程一致，实际控制顺序如下：

```text
imageId = 0
  -> rbSec_Basic_init()
       失败：进入不可退出循环，不执行启动选择
  -> LoopFor_SafeFrame()
       轮询早期 CAN 强制帧
  -> rbSecBM_CheckLCValid()
       失败且 StayInBootFlag 不是 1/2：进入不可退出循环
       失败但 StayInBootFlag 是 1/2：允许继续
  -> Boot_Logic(&imageId)
       失败：不加载、不跳转
       成功：得到 imageId 和 CurrentBoot_Address
  -> ImageM_LoadCpu()
  -> MailboxIpc_DeInit()
  -> Cdd_Dma_DeInit()
  -> 根据 imageId 交接
```

`[C]` `Boot_Logic` 失败后仍执行 Mailbox/DMA 反初始化，但不会尝试未选中的额外目标，也不会执行任意地址跳转。`ImageM_LoadCpu` 失败同样不交接目标软件。

`[S]` 截图源码在流程中还出现两次 HSM RAM `memset`；当前优化后的 BM ELF 中没有可对应的显式清零调用。可能原因包括编译优化移除、内联或截图来自相邻版本。供应商不得仅凭截图把这两次清零声明为当前 ELF 已执行；是否必须保留需由 HSM RAM 清零安全需求确认。

### 3.3 BM 启动目标地址

BM 使用固定地址选择目标镜像：

| index | 目标 | 起始地址 | 说明 |
| ---: | --- | ---: | --- |
| 0 | App / CustApp | `0x00090000` | 普通应用，默认优先启动 |
| 1 | FBL | `0x00050000` | 客户/功能 Bootloader |
| 2 | PBL | `0x00020000` | 平台 Bootloader / 刷写恢复入口 |
| 0（动态） | ProductionApp | `0x00190000` | 快速 App 选择字为 `PDAP` 时替代 CustApp |

为避免供应商术语歧义，本文将会议中使用的 `pfboot/PlatformBoot/WeifuBoot` 统一映射为当前 ELF 的 `PBL`（地址 `0x20000`），将 `custboot/CustomerBoot` 统一映射为当前 ELF 的 `FBL`（地址 `0x50000`）。`PBL/FBL` 名称和地址来自 ELF `[C]`；`pfboot/custboot` 是项目沟通别名，不表示额外的第五个或第六个启动镜像。

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

#### 3.5.2 设备类型、安全基础初始化与生命周期

`[C]` BM 通过读取设备寄存器低字节 `0x030E0220` 判断安全设备类型，值 `0x0A` 对应 HSSE 路径。该判断影响 HSM 初始化、安全启动认证、早期 CAN 等待计数以及生命周期策略。

`rbSec_Basic_init()` 的当前 ELF 控制流为：

```text
if 非 HSSE:
    basicOk = 1
    rbSecBM_GetECULCState_en()          // 返回值未参与 basicOk
    return basicOk

if HSSE:
    hsmLoadBad = 0
    if LoadHSMFromFlash_u8() != 0:
        hsmLoadBad = 1
    else if Trigger_HSMLoad_u8() != 0:
        hsmLoadBad = 1
    else:
        hsmLoadBad = (check_HSMLoad_Result_u8() == 1)

    fwRet = HSMFWInitialize_u8()         // 即使 hsmLoadBad==1 仍调用
    basicOk = (hsmLoadBad == 0 && fwRet != 1)

    rbSecBM_loadHSMLC_u8()               // 返回值未参与 basicOk
    rbSecBM_GetECULCState_en()           // 返回值未参与 basicOk
    return basicOk
```

以上比较值是指令级事实；没有协议定义时，不把 `fwRet` 的其他数值擅自命名成某个 HSM 错误。`BootM_BootTargetSoftware` 只在 `basicOk==0` 时进入不可退出错误循环。由于两个 lifecycle 函数的返回值均被忽略，“HSM firmware 初始化通过但 lifecycle load/query 失败”不一定使 `rbSec_Basic_init` 返回失败。

`[C]` 当前 `rbSec_Basic_init` **不调用** `rbSecBM_CheckLCValid`；后者由 `BootM_BootTargetSoftware` 在早期 CAN 窗口之后单独调用。`[S]` `BM/Weixin Image_20260716172923_869_85.jpg`、`...172924_870_85.jpg` 和 `...172928_873_85.jpg` 的截图把 lifecycle magic 检查放在 `rbSec_Basic_init` 内部，因此截图与当前 ELF 在函数边界上不一致。总体“启动前检查 lifecycle magic”的行为仍一致，但供应商应以当前 ELF 的调用位置为等效基线。

`[C]` BM 与后续软件共享的生命周期信息位于 `g_rbLCInfoFromBM=0x102DFF0C`，DWARF 布局为 4 字节：

```c
typedef struct {
    uint8_t ecuLifeCycle;   // +0
    uint8_t hsmMainState;   // +1
    uint8_t hsmSubState;    // +2
    uint8_t crc8;           // +3，覆盖前 3 字节
} rbLCInfoFromBM_t;
```

`[C]` BM 调用 `Crc_CalculateCRC8(&g_rbLCInfoFromBM,3,0xFF,1)`。函数使用的 256-byte 表以 `00 1D 3A 27 ...` 开始，指令在处理前采用 `0xFF` 初值、处理后按位取反；其等价 CRC 参数为：

```text
width    = 8
poly     = 0x1D
init     = 0xFF
refin    = false
refout   = false
xorout   = 0xFF
coverage = ecuLifeCycle || hsmMainState || hsmSubState（按地址顺序 3 字节）
```

这与 CRC-8/SAE-J1850 参数一致。PBL 的 `sec_Crc_CalculateCRC8` 使用相同查表内容和调用参数，不能替换为 AUTOSAR 中其他 CRC8 变体。

`rbSecBM_GetECULCState_en()` 的失败语义也必须保持诚实：

1. HSSE 路径先把查询得到的 HSM main/sub 字节写入共享结构，再判断 `rbSecBM_GetHSMLCState_en` 返回值。
2. 查询失败时函数返回非零，不更新 `ecuLifeCycle` 和 `crc8`；调用者当前忽略该错误，因此共享区可能保留旧的 lifecycle/CRC。
3. 查询成功且 HSM main state 为 `0..5` 时，写 `ecuLifeCycle=main+1`；main 大于 5 时不改 lifecycle，但仍重新计算 CRC。
4. 非 HSSE 路径写 `ecuLifeCycle=0` 后计算 CRC；main/sub 在此分支不显式归零。
5. `rbSecBM_CheckLCValid` 只对 lifecycle `1/2` 做 magic 比较，其他值包括异常/残留值都直接返回 true。

因此，“无法取得可信 lifecycle 时 fail closed”是供应商应增加的安全要求，不是当前 ELF 的完整基线。若修复为失败即停留 BM，必须作为批准的异常场景行为变更；正常 lifecycle `0..6` 的映射、CRC 和 magic 门控仍须等效。

HSM main state `0..5` 被映射为 ECU lifecycle `1..6`，即 `ecuLifeCycle=hsmMainState+1`。当前 ELF 中可恢复的枚举为：

| 数值 | 生命周期名称 | `rbSecBM_CheckLCValid` 是否检查 128-byte magic | 安全功能是否强制 |
| ---: | --- | --- | --- |
| `0` | NoSecurity | 否，直接通过 | 否 |
| `1` | OnBoard | **是** | 否 |
| `2` | Customizing | **是** | 否 |
| `3` | Operation | 否，直接通过 | **是** |
| `4` | Return | 否，直接通过 | **是** |
| `5` | Development | 否，直接通过 | 否 |
| `6` | Decommission | 否，直接通过 | **是** |
| `0xFF` | Error | 否，当前函数直接通过 | 否/由其他错误路径处理 |

最后一列来自 `rbSecBM_IsLifeCycleEnforced()` 的查表行为：仅 `3/4/6` 返回 true。名称来自 DWARF 枚举 `[C]`；这些状态在量产流程中的业务准入条件仍需 HSM lifecycle 规范确认。

#### 3.5.3 Lifecycle magic number 的读取和判断

`[C+S]` `rbSecFls_Init_MainFunction_BM()` 依次读取三个安全 Flash bank：

| bank | Flash 地址 | RAM 目标 | 读取长度 | 本流程用途 |
| ---: | ---: | --- | ---: | --- |
| 0 | `0x3E0000` | `SecFls_StoreData[0]` | `0x200` | 生命周期/安全数据 |
| 1 | `0x3E1000` | `SecFls_StoreData[1]` | `0x200` | key/安全数据 |
| 2 | `0x3E2000` | `SecFls_StoreData[2]` | `0x200` | lifecycle magic |

每次 `Fls_Read` 后都循环调用 `Fls_MainFunction/Fls_GetStatus`，直到状态等于 `1`；当前循环没有软件超时。三个 bank 完成后设置安全 Flash 已初始化状态。

`rbSecFls_Read_MagicNum(dst,length)` 的当前行为：

1. 安全 Flash 尚未初始化或内部状态为失败值 `2`时返回失败。
2. 将 `length` 上限截断为 `0x200`。
3. 从第三个 RAM bank，即 Flash `0x3E2000` 的镜像，复制到调用者。

`rbSecBM_CheckLCValid()` 的判断不是“任何生命周期都比较 magic”，而是：

```c
bool rbSecBM_CheckLCValid(void)
{
    if (ecuLifeCycle != OnBoard && ecuLifeCycle != Customizing) {
        return true;
    }

    uint8_t actual[128];
    if (rbSecFls_Read_MagicNum(actual, 128) != SUCCESS) {
        return false;
    }
    return bytewise_equal(actual, expectedMagic, 128);
}
```

`[C]` 当前 ELF 内置的期望 magic 为以下精确 128 字节：

```text
FD 3A E8 DD AE DC 51 F9 1D 43 C6 A4 60 B7 DE 66
85 50 98 57 1D E4 DF 9F AB E5 18 BB E1 68 1A E8
69 78 17 39 3B B1 69 8F CE 12 75 7B 50 09 5D BB
78 3E F4 3F E5 DC C1 5E DA B8 BE E6 3D 58 79 19
47 3A 3D EC 35 C8 AD C5 25 72 55 D6 CC D3 AE AF
5B C1 83 0A D9 33 CB D2 15 CB 51 2B BB 5E CA 27
E4 AC 44 21 E3 06 42 F3 B1 F3 1D A8 44 DA 0D B1
84 65 2D C4 0A 6B AB 32 2B 5A 50 91 A6 A9 6B 57
```

判断结果进入 `BootM_BootTargetSoftware` 后形成以下门控：

| Lifecycle magic 结果 | `StayInBootFlag` | 后续行为 |
| --- | ---: | --- |
| 通过或无需检查 | 任意 | 进入 `Boot_Logic` |
| 失败 | `0`/其他 | 不进入启动选择，停在不可退出循环 |
| 失败 | `1` | 允许继续，只按 CAN 强制路径尝试 FBL |
| 失败 | `2` | 允许继续，只按 CAN 强制路径尝试 PBL |

因此，magic 失败不是“自动跳 PBL”。必须在早期 CAN 窗口内收到准确的强制帧，才能绕过该门进入 FBL/PBL；目标仍要通过 `SecBoot_Check_Process`。

`[C]` PBL 的 DID `FC00` 存在一个专用写入口，可擦除 `0x3E2000` 的 `0x1000` 字节扇区并写入 `0x100` 字节。它可能用于生命周期 magic 的部署或更新 `[I]`，但当前 ELF 无法证明诊断层允许的 128/256 字节内容、会话和安全矩阵；供应商必须以诊断规范及产线流程冻结，不得把上述期望 magic 解释为可公开绕过安全生命周期的诊断口令。

### 3.6 普通启动优先级

没有强制跳转帧，也没有有效重编程请求时，BM 的普通启动优先级为：

```text
App -> FBL -> PBL
```

`[C]` `g_BootSequenceCtrl` 的三个初始化地址为 `{0x90000,0x50000,0x20000}`。进入普通路径前，如果 `APP_IMAGE_Addr==0x190000`，`Boot_Logic` 会把 `g_BootSequenceCtrl[0]` 改写为 `0x190000`；否则索引 0 保持 `0x90000`。

等效伪代码：

```c
if (APP_IMAGE_Addr == 0x190000) {
    g_BootSequenceCtrl[0] = 0x190000;
}

for (imageId = 0; imageId < 3; ++imageId) {
    if (!Is_FLAG_Valid(imageId)) {
        continue;
    }

    CurrentBoot_Address = g_BootSequenceCtrl[imageId];
    result = SecBoot_Check_Process(CurrentBoot_Address,
                                   &CurrentBoot_Address);
    secBoot_Record(result, imageId);
    if (result == 0) {
        return BOOT_OK;  // 调用者随后 ImageM_LoadCpu/交接
    }
}

return BOOT_FAILED;
```

`Boot_Logic` 对每个候选目标都会调用：

```text
SecBoot_Check_Process
secBoot_Record
```

因此 valid flag 只是“允许尝试启动”的前置条件，不等于无条件跳转。目标镜像仍必须通过安全启动检查。普通路径某一候选安全检查失败时会继续下一个候选；只有该路径具备完整的 App -> FBL -> PBL 逐项回退。

`[C]` `Boot_Logic` 结束前还更新共享错误字：

1. `StayInBootFlag=1/2` 或重编程请求命中四个 magic 之一时，`u32_secboot_err |= 0xFF000000`。
2. `Application_Valid_Flag != 0x55` 时，`u32_secboot_err |= 0x04`。

第二项是当前指令行为，不能仅凭名称解释为“App invalid 错误位”；它恰好在 App 被当前规则视为可尝试时置位。该共享字的外部诊断编码语义为 `[TBC]`。

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

`[C]` 比较阈值分别为十进制 `79/143`，函数至少执行一次 `Can_MainFunction_Read`，收到 `StayInBootFlag=1/2` 时提前退出。计数器是函数外静态存储，当前函数入口没有显式清零。`[S]` `BM/333.png` 的源码注释把两个窗口描述为约 `35 ms/70 ms`，但 ELF 不能从循环计数唯一换算毫秒；该时间只能作为截图设计信息，必须在目标板测量后冻结。

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
5. `[C]` 当前 `CanIf_RxIndication` 使用固定 16 字节比较，且没有读取 `PduInfoType.SduLength`。这意味着短帧不会被当前函数主动安全忽略，而是仍可能读取 `SduDataPtr` 后 16 字节。新实现必须要求 DLC/长度至少为 16，再精确比较前 16 字节；这是安全增强，合法帧行为保持不变。
6. `0x4F/0x8F` 是循环计数而非已确认的毫秒值，真实接收窗口必须通过目标硬件计时冻结。
7. `[C]` CAN 强制目标的安全检查失败后，`Boot_Logic` 直接返回失败，**不会**尝试 CustApp、ProductionApp 或另一个 Bootloader。

#### 3.8.1 强制/重编程启动决策伪代码

```c
BootResult Boot_Logic(uint8_t *selectedImageId)
{
    /* Priority 1: early CAN force. No valid check and no fallback. */
    if (StayInBootFlag == 1 || StayInBootFlag == 2) {
        *selectedImageId =
            (StayInBootFlag == 1) ? IMAGE_FBL : IMAGE_PBL;
        CurrentBoot_Address =
            (StayInBootFlag == 1) ? 0x50000 : 0x20000;

        result = SecBoot_Check_Process(CurrentBoot_Address,
                                       &CurrentBoot_Address);
        secBoot_Record(result, *selectedImageId);
        return (result == 0) ? BOOT_OK : BOOT_FAILED;
    }

    /* Priority 2: persisted reprogramming request. */
    if (isFblRequest(Reprogramming_Request_Flag) ||
        isPblRequest(Reprogramming_Request_Flag)) {
        bool requestFbl = isFblRequest(Reprogramming_Request_Flag);
        *selectedImageId = requestFbl ? IMAGE_FBL : IMAGE_PBL;
        CurrentBoot_Address = requestFbl ? 0x50000 : 0x20000;

        bool targetValid = requestFbl
            ? (Fbl_Valid_Flag == 0xAAAAAAAA)
            : (Pbl_Valid_Flag == 0xAAAAAAAA);

        if (targetValid) {
            result = SecBoot_Check_Process(CurrentBoot_Address,
                                           &CurrentBoot_Address);
            secBoot_Record(result, *selectedImageId);
            if (result == 0) {
                return BOOT_OK;
            }
        }

        /* Fixed CustApp fallback, not APP_IMAGE_Addr and not full chain. */
        if (Application_Valid_Flag == 0x55) {
            return BOOT_FAILED;
        }
        *selectedImageId = IMAGE_APP;
        CurrentBoot_Address = 0x90000;
        result = SecBoot_Check_Process(0x90000, &CurrentBoot_Address);
        secBoot_Record(result, IMAGE_APP);
        return (result == 0) ? BOOT_OK : BOOT_FAILED;
    }

    /* Priority 3: App -> FBL -> PBL normal chain. */
    return tryNormalOrder();
}
```

该伪代码表达控制流，不是恢复出的原始 C 源码。局部变量名和返回类型为文档化命名；分支优先级、常量、valid 判定、安全检查调用及回退范围为 `[C]`。

#### 3.8.2 启动条件总矩阵

| 优先级 | 触发条件 | 目标 | 是否检查目标 valid | 安全检查失败后 |
| ---: | --- | --- | --- | --- |
| 1 | `StayInBootFlag=1` | FBL `0x50000` | 否 | 直接失败，留在 BM |
| 1 | `StayInBootFlag=2` | PBL `0x20000` | 否 | 直接失败，留在 BM |
| 2 | FBL reprogram magic | FBL `0x50000` | 是，必须 `0xAAAAAAAA` | 尝试 CustApp `0x90000` |
| 2 | PBL reprogram magic | PBL `0x20000` | 是，必须 `0xAAAAAAAA` | 尝试 CustApp `0x90000` |
| 2 fallback | 请求目标 invalid/认证失败，且 App flag != `0x55` | CustApp `0x90000` | App 规则 | 直接失败，不再尝试 FBL/PBL |
| 3 | 无上述触发 | App `0x90000` 或 `0x190000` | App flag != `0x55` | 继续 FBL |
| 3 | App 不可用/认证失败 | FBL `0x50000` | `0xAAAAAAAA` | 继续 PBL |
| 3 | FBL 不可用/认证失败 | PBL `0x20000` | `0xAAAAAAAA` | 失败，留在 BM |

### 3.9 安全启动详细流程

#### 3.9.1 数据结构和镜像头

`[C]` DWARF 中的安全镜像结构为：

```c
typedef struct {                    // sizeof = 16
    uint32_t EntryHdr_StartAddr;    // +0
    uint32_t EntryHdr_Size;         // +4
    uint32_t EntryHdr_DataAddr;     // +8
    uint32_t EntryHdr_DataSize;     // +12
} SecBt_DataEntry_Header;

typedef struct {                    // sizeof = 16
    uint32_t Image_ID;              // +0
    uint32_t Image_StartAddr;       // +4
    uint32_t Image_Size;            // +8
    uint32_t Image_CRC32;           // +12，当前装载地址计算会使用
} SecBt_DataEntry_Item;

typedef struct {                    // sizeof = 16
    uint8_t SecBoot_Enc;            // +0
    uint8_t SecBoot_Boot;           // +1
    uint8_t SecBoot_Fls;            // +2
    uint8_t reserved[13];
} SecBoot_SecInfo_t;
```

对应运行时全局对象连续位于 `0x10216C0C` 附近：RAM flag、16 字节 image header、16 字节 `_EXE` item、16 字节 security info。

`SecBoot_Init(target)` 的 `[C]` 步骤为：

1. 清零上述安全启动上下文。
2. 从 `target+0x00` 读取 16 字节，并与常量
   `0F 0F 0F 0F F0 F0 F0 F0 62 6C 6F 63 6B 62 65 67`
   精确比较；后 8 字节为 ASCII `blockbeg`。
3. 调用 `SecBoot_ReadImgHeader(target)`。
4. HSSE 设备额外从 `target+0x90` 读取 16 字节 `SecBoot_SecInfo_t`，前三个策略字节必须各自为 `0xA5` 或 `0xB6`，否则初始化失败。
5. 非 HSSE 设备完成镜像头解析后跳过上述策略字节合法性检查。

`SecBoot_ReadImgHeader(target)` 从 `target+0xB00` 读取 16 字节 `SecBt_DataEntry_Header`。描述符数量取 `EntryHdr_Size` 的 bit `[11:4]`，随后从 `EntryHdr_StartAddr` 指向的位置按 16 字节扫描条目，选择第一个 `Image_ID` 字节序对应 `_EXE`，即 32-bit 值 `0x5F455845` 的条目。没有 `_EXE` 时清零 item 并返回失败。

当前 ELF 没有提供镜像头字段的完整生成规范。尤其 `EntryHdr_StartAddr` 是绝对地址、镜像内偏移还是装载后地址，必须用当前量产镜像逐字节冻结；供应商不得只按字段名猜测。

#### 3.9.2 安全启动状态机

`[C]` `SecBoot_Check_Process(target,&CurrentBoot_Address)` 返回码：

| 返回码 | 阶段 |
| ---: | --- |
| `0x00` | 允许启动 |
| `0xF0` | HSSE 镜像加载失败 |
| `0xF1` | Hash 失败 |
| `0xF2` | 签名失败 |
| `0xF3` | 解密失败 |
| `0xF4` | 安全模块初始化失败 |

当前控制流为：

```text
SecBoot_Init(target)
  失败 -> 0xF4

if 非 HSSE:
  CurrentBoot_Address = g_ImageEntry_Item.Image_StartAddr
  return 0

SecBoot_LoadAppImage(target)
  失败 -> 0xF0

if SecBoot_SecCtrl_SecureBoot():
  CalculateHashData() 失败 -> 0xF1
  VerifySignature() 失败 -> 0xF2

if SecBoot_SecCtrl_BlkEnc():
  authenticated decrypt 失败 -> 0xF3

CurrentBoot_Address =
  0x88000030
  + Image_StartAddr
  + Image_Size
  - Image_CRC32
return 0
```

`SecBoot_LoadAppImage` 从 `target+0xAE0` 开始读取，目标 RAM 从 `0x88000000` 开始，每块最大 `0x4000`；总读取字节数由 `_EXE` item 的 `Image_StartAddr + Image_Size + 0x40` 形成。该算式和最终入口算式均直接使用镜像字段，当前指令流未见完整的加法溢出、RAM 白名单或上下界防护。供应商必须用 golden image 保持合法镜像结果，同时在解析层拒绝溢出和越界镜像。

#### 3.9.3 生命周期与策略字节

`[C]` 安全启动和块解密的启用条件为：

```text
secureBootRequired =
    rbSecBM_IsLifeCycleEnforced()
    OR (SecBoot_Boot == 0xA5)

blockDecryptRequired =
    rbSecBM_IsLifeCycleEnforced()
    OR (对应 Enc policy byte == 0xA5)
```

因此 Operation、Return、Decommission 生命周期会强制安全功能，不受镜像将策略字节设置为 `0xB6` 的影响；其他生命周期中 `0xA5` 表示启用，`0xB6` 表示不由该字节启用。`SecBoot_Fls` 的具体业务使用未在本次启动控制流中完整恢复，保持 `[TBC]`。

#### 3.9.4 Hash、签名和解密参数

`[C]` 当前 BM Hash 流程：

1. 算法枚举为 `5`，DWARF/调用语义对应 SHA-512。
2. 以不超过 `0x4000` 的分块处理已加载 RAM。
3. 计算摘要长度必须为 `0x40`。
4. 从镜像 `target+0xA0` 读取期望的 64 字节摘要并比较。

`[C]` 当前签名流程：

1. 从镜像起始处读取 `0xE0` 字节的签名相关头数据。
2. 从 `target+0xE0` 读取 `0x200` 字节签名。
3. 调用安全库时 signature scheme 枚举为 `2`、hash 枚举为 `5`、key id 为 `0xFF02`。
4. 任一 HSM job 接受、轮询或验签失败均归类为 `0xF2`。

`[C]` 当前认证解密路径读取 `target+0xAE0` 和 `target+0xAF0` 的两个 16 字节值，使用 key id `0xFF03`，nonce 长度参数为 `12`，以最大 `0x4000` 分块处理，通过 `0x10232000` scratch RAM，输出从 `0x88000030` 开始。安全库 mode 枚举 `0` 的确切算法名称、tag/AAD 组合和字节序无法由 ELF 唯一映射，必须由 HSM 配置和加密 golden image 冻结。

`[C]` 当 `rb_IsDeviceTypeHSSE_u8()==0` 时，函数仍经过统一 `SecBoot_Init`/头解析入口，但当前路径不执行上述密码学认证与解密，并把 `Image_StartAddr` 作为当前启动地址返回。因此规范应写成“所有目标经过统一安全决策入口；密码学强制策略由设备类型、生命周期和镜像策略决定”，不能错误要求开发样件与 HSSE 量产件表现完全相同。

`rbSec_Basic_init` 失败、需要检查的 lifecycle magic 非法、镜像头非法、Hash/签名/解密失败都不能跳入目标。当前错误处理以停留 BM/不可退出循环为主，供应商必须保留 fail-closed 结果，并提供可追溯的错误记录和受控恢复机制。

### 3.10 BM 加载和跳转方式

`BootM_BootTargetSoftware()` 对所有已选目标先调用 `ImageM_LoadCpu(&imageId)`。加载成功并完成 `MailboxIpc_DeInit/Cdd_Dma_DeInit` 后，再按 imageId 交接。

#### 3.10.1 FBL/PBL 交接

`[C]` 当 `imageId` 为 `1` 或 `2` 时：

```text
BootM_RelocateVectortable(src=0x1021E000, dst=0x00000000)
  -> 复制 0x100 个 32-bit word，共 0x400 字节
BLX 0x00000000
```

原 V2.1 文档把源地址写成目标 Flash `0x20000`，这是不准确的。当前调用点传入的源地址明确是 RAM `0x1021E000`；FBL/PBL 镜像在前面的安全装载流程中已被装入/整理到该 RAM 区域。跳转不是 Cortex-M 风格的“读取 MSP 和 ResetHandler 后设置”，而是直接 `BLX 0`，因此供应商必须保持当前向量入口代码、CPU mode、异常向量映射和 RAM 内容合同。

#### 3.10.2 AppImage 元数据

`[C+S]` `BM/12.png` 至 `BM/17.png`、`BM/777.png` 至 `BM/999.png` 与当前 ELF 的解析结构和调用顺序一致。可恢复结构为：

```c
typedef struct {                  // sizeof = 16
    uint32_t magicStr;            // 0x5254534D，内存字节 "MSTR"
    uint32_t numFiles;
    uint32_t devId;
    uint32_t reserved;
} AppImageMetaHeader;

typedef struct {                  // sizeof = 8
    uint32_t coreId;
    uint32_t imageOffset;
} AppImageCoreRecord;

typedef struct {                  // sizeof = 16
    uint32_t cpuId;
    uint32_t clkHz;
    uint32_t rprcOffset;
    uint32_t entryPoint;
} ImageM_CpuInfo;

typedef struct {                  // sizeof = 64
    ImageM_CpuInfo cpuInfo[4];
} Bootloader_BootImageInfo;
```

`Bootloader_parseMultiCoreAppImage()`：

1. 把栈上的 10 个 `AppImageCoreRecord` 临时项初始化为 `0xFF`。
2. 读取并检查 meta header 的 `MSTR` magic。
3. 按 `numFiles` 读取每个 8 字节 core record。
4. 仅接受 `coreId<=3`，填入对应 `cpuInfo[coreId].rprcOffset` 并设置 core bitmap。
5. 返回解析状态，由 `ImageM_LoadCpu` 决定是否继续。

`[C]` 当前优化指令中没有看到 `numFiles<=10` 的显式边界检查；损坏镜像可导致临时记录数组越界。也没有在该函数中看到对 `devId` 或 `MEND=0x444E454D` 的完整验证。`[S]` 截图常量还给出 device id `55` 和 invalid id `0xDEADBABE`。新实现必须对记录数、乘法、偏移、设备 ID、尾 magic 和输入长度做完整检查；对合法 golden image 的解析结果必须与当前 ELF 相同。

#### 3.10.3 RPRC 解析和段加载

`[C+S]` RPRC magic 为 `0x43525052`，内存字节为 `RPRC`。结构为：

```c
typedef struct {                  // sizeof = 20
    uint32_t magic;
    uint32_t entry;
    uint32_t reservedAddr;
    uint32_t sectionCount;
    uint32_t version;
} ImageM_RprcFileHeader;

typedef struct {                  // sizeof = 20
    uint32_t addr;
    uint32_t reservedAddr;
    uint32_t size;
    uint32_t reservedCrc;
    uint32_t reserved;
} ImageM_RprcSectionHeader;
```

`ImageM_rprcImageLoad()` 的当前步骤：

```text
定位到 cpuInfo.rprcOffset
  -> 读取 20 字节 RPRC file header
  -> magic != RPRC 时失败
  -> 保存 entry 到 cpuInfo.entryPoint
  -> 循环 sectionCount:
       读取 20 字节 section header
       ImageM_translateAddr(cpuId, section.addr)
       从镜像读取 section.size 字节到翻译后的目标地址
```

当前函数中未见 section count 上限、`addr+size` 溢出检查、目标 RAM 白名单、段重叠检查或 reserved CRC 校验。供应商必须增加这些防护，但必须保留有效镜像的地址翻译、段内容和 entry point。

#### 3.10.4 多核加载与释放顺序

`[C]` `ImageM_LoadCpu()` 的顺序为：

```text
Bootloader_socConfigurePll
Bootloader_parseMultiCoreAppImage

若 bitmap bit3:
  Bootloader_loadCpu(cpuInfo[3])
若 bitmap bit2:
  Bootloader_loadCpu(cpuInfo[2])

若前述加载成功且 bit3:
  Bootloader_runCpu(cpuInfo[3])
  Bootloader_socConfigurePllPostApllSwitch
若 bit2:
  Bootloader_runCpu(cpuInfo[2])
若 bit3:
  SOC_rcmWaitBSSBootComplete

若 bitmap bit0 且 cpuInfo[0].rprcOffset != 0xDEADBABE:
  ImageM_rprcImageLoad(cpuInfo[0])

SOC_rcmStartMemInitDSSL3(1)
SOC_rcmWaitMemInitDSSL3(1)
```

App 交接时，`imageId=0`，BM 读取 `bootImageInfo.cpuInfo[0].entryPoint`；非零才执行 `BLX entryPoint`，为零则留在 BM。`cpuId=1` 在当前主流程中的独立加载/释放路径未见，不能凭结构容量声称四个核都会启动。

### 3.11 `BM/` 代码截图与当前 ELF 一致性

截图属于辅助证据，不是完整源码。逐项结论如下：

| 截图 | 内容 | 与当前 BM ELF 的关系 |
| --- | --- | --- |
| `11.png` | `SpeedupApp_flag` 绕过 Fee，选择 Cust/Production App | `[C+S]` 地址、`CUAP/PDAP` 和旁路行为一致；约 `130 ms` 只属截图注释 |
| `12.png`、`14.png`、`15.png`、`17.png` | RPRC 头、section 头和加载循环 | `[C+S]` 结构大小、magic、entry、section 循环一致 |
| `13.png`、`16.png` | `MSTR/MEND/RPRC`、device id、invalid id | `MSTR/RPRC/DEADBABE` 与 ELF 一致；`MEND` 和 device id 的强制校验在当前函数中未确认 |
| `333.png` | `LoopFor_SafeFrame` | `[C+S]` 调用和退出条件一致；阈值 ELF 为 `79/143`，毫秒注释仅 `[S]` |
| `444.png` | `BootM_Init` | `[C+S]` 外设/NvM/安全 Flash顺序一致；ELF 入口还含截图未显示的 CP15/FPU 配置 |
| `555.png`、`666.png` | `BootM_BootTargetSoftware` | 主控制流 `[C+S]`；截图中的 HSM RAM 清零及 lifecycle 检查函数边界与 ELF 有差异 |
| `777.png`、`888.png` | `ImageM_LoadCpu` | `[C+S]` 多核加载、释放和本核 RPRC 顺序一致 |
| `999.png` | `Bootloader_loadCpu` | `[C+S]` 调用结构一致 |
| `Weixin ...172922/25/27...jpg` | lifecycle 读取与 magic 检查 | `[C+S]` 仅 OnBoard/Customizing 比较 128 字节的行为一致 |
| `Weixin ...172923/24/28...jpg` | `rbSec_Basic_init` 内调用 LC check | `[S]` 与当前 ELF 函数边界不一致；当前 ELF 在调用者中单独检查 |
| `Weixin ...172930/32/33...jpg` | PBL SecurityAccess/证书常量片段 | 图像不足以可靠抄录全部 byte array；本文不据此补造密钥或证书值 |
| `未命名图片.png` | 4 MiB Flash/NVM/安全区布局 | `0x350000..0x3CFFFF` 与 Fee 表、`0x3E0000/1000/2000/3000` 与 ELF 交叉一致；`0x3E4000..0x3FFFFF` 保留区仅作 `[S]` 输入 |

供应商实现评审必须分别列出“当前 ELF 等效项”“按截图补充但 ELF 未确认项”“有意安全增强项”。三类内容不得混为同一基线。

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
| 镜像管理 | `ImageM_*` | 地址白名单、下载上下文、写权限、认证状态机，以及当前仅检查 App valid 的“兼容性”异步 job |
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
3. Flash 写入、写入收尾、RID 0205 的 App-valid “兼容性”检查和 RID 0212 校验在 ImageM 后台任务中异步推进。

#### 4.2.1 BM 到 PBL 的 lifecycle 交接

`[C]` PBL 不是重新从 HSM 推导 BM 的 lifecycle，而是通过共享地址 `0x102DFF0C` 读取 BM 写入的 4 字节 `{ecuLC,hsmMain,hsmSub,crc8}`。`rbSec_GetECULCStatefromBM_en()`：

1. 复制四个字节到本地。
2. 按 3.5.2 节的 CRC-8/SAE-J1850 参数对前三个字节计算 CRC8。
3. CRC 匹配时，把 ECU lifecycle 和 HSM main state 写入 PBL 的 `g_rbLifeCycle_stInfo`，并把 valid byte 置 `1`。
4. CRC 不匹配时，把 lifecycle 写为 `0xFF`、HSM state 写为 `0`、valid byte 置 `0`，函数返回错误。

`[C]` PBL 初始化调用点没有检查 `rbSec_GetECULCStatefromBM_en()` 的返回值。`rbSec_IsSecurityFeatureEnforced()` 随后直接读取 lifecycle 字节、不读取 valid byte，并与 BM 相同地仅对 `3/4/6` 返回 true；所以 CRC 失败形成的 `0xFF` 会返回 false，而不是全局停机。`SecFlash_SecCtrl` 对 BM 地址 `0` 和 HSM 地址 `0x2D0000` 仍固定启用安全；其他镜像在 lifecycle 不强制时退回读取镜像 `currentAddr+0x92` 是否为 `0xA5`。

供应商必须保持共享地址、CRC 覆盖范围和正常 lifecycle 的安全策略，但应把 CRC/valid 失败改为 fail closed 或受控恢复；这是相对当前异常路径的安全增强。如果内部重构为显式 IPC，也必须保证 PBL 不能把未经完整性保护的 lifecycle 当作可信的“非强制”依据。

### 4.3 OTA/UDS 主流程

PBL 的刷写流程是“边接收边写入”，不是全部下载完再统一写 Flash。下列顺序是当前回调组合所支持的典型升级事务 `[I]`；ELF 中各 DCM callback 独立存在，完整服务先后、会话门和 block sequence counter 仍由 DCM 配置及诊断脚本约束。

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
FlasPort_ClearPreviousJob       // 当前只清 PreviousWriteJob 页缓存
成功时 NRC = 0
失败时 NRC = 0x31
```

技术要求：

1. RequestDownload 必须先打开 ImageM port。
2. 必须检查目标地址和长度是否满足下载条件。
3. 必须返回 maxNumberOfBlockLength。
4. 条件不满足时返回 UDS NRC `0x31`。
5. `[C]` 成功后调用 `FlasPort_ClearPreviousJob`。该函数名中的 `Flas` 是 ELF 原拼写；它只清页缓存，不代表异步 job 已被取消或完成。

`[C]` `ImageM_PortGetMaxNOBL` 返回 `0x0FFF`，即 RequestDownload 正响应中的最大块长度基线为 4095 字节。DCM 层存在较宽的通用地址配置，但最终授权必须由 ImageM 的九块白名单执行，不能用 DCM 通用上限替代。

#### 4.4.1 下载窗口与地址检查

`[C]` `ImageM_PortOpen(address,size)` 遍历 2.4 节九个 `LogBlocks`，仅当以下条件同时成立时建立半开下载窗口 `[address,address+size)`：

```text
block.base <= address
address + size <= block.base + block.length
请求的起止地址位于同一个 LogBlock
```

匹配成功后，数组下标直接成为 `pImgContext.imageId`，并保存原始 `address/size`，设置 `isInit=1`。如果旧 context 已初始化，当前函数先关闭/清理旧 context，再建立新 context。没有匹配时返回非零失败。

当前二进制没有显式整数溢出保护。供应商必须实现等价正常行为并增加以下防御要求：

1. `size` 必须大于 0。
2. 使用减法形式或宽位运算检查范围，拒绝 `address + size` 溢出。
3. 请求不得跨块，即使两个允许块地址连续也必须拒绝。
4. `[C]` 当前 `ImageM_GetRequestDownloadCondition` 在地址范围命中某个 `LogBlock` 时检查 `imageId/isInit`，但未命中任何块的路径会返回成功。由于 RequestDownload 在此前先调用 `ImageM_PortOpen`，正常调用链仍会拒绝白名单外地址。供应商实现必须显式拒绝 no-match，并再次校验地址、长度与已选上下文；这是安全增强。
5. `[C]` 当前 `ImageM_CheckWritePermission` 只按 `pImgContext.imageId` 检查写请求是否位于该 imageId 的整个 `LogBlock`，没有再次使用 `blockAddress/blockLength` 收紧到 RequestDownload 子窗口。供应商必须增加子窗口检查；这是安全增强要求，不是对当前 ELF 行为的描述。
6. `ImageM_PortErase` 只接受与已打开上下文完全相同的地址和长度，不接受子集、超集或向扇区边界扩张后的范围。
7. 底层若必须按物理扇区擦除，擦除前必须证明所有被影响字节均位于同一允许块；否则拒绝请求。
8. `[C]` 当前 `ImageM_PortOpen` 发现旧 context 已初始化时会直接把它归零，没有先检查 `ImageM_FlashPortJob`、write-exit 或 verifier 是否 pending；供应商必须在任何相关异步 job 未完成时拒绝新 RequestDownload，不能覆盖旧 imageId/address/length。

当前三个地址检查层的实际收敛范围不同：

| 函数 | 当前检查范围 | no-match/不一致行为 |
| --- | --- | --- |
| `ImageM_PortOpen` | 请求 `[address,address+size]` 包含于同一个 `LogBlock` | 返回失败，是 RequestDownload 的主要拒绝门 |
| `ImageM_GetRequestDownloadCondition` | 再次遍历块；命中时要求 context 已初始化且 imageId 相同 | **未命中任何块时返回成功** |
| `ImageM_CheckWritePermission` | 只要求 TransferData 位于当前 imageId 对应的整个 `LogBlock` | 不检查本次 `blockAddress/blockLength` 子窗口 |

供应商要实现“当前合法流程等效 + 非法输入安全增强”，必须在差异说明中明确后两项修复，不能把增强后的拒绝行为伪称为当前 ELF 已有。

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

对象地址和状态编码为：

| 对象 | 地址 | 关键状态 |
| --- | ---: | --- |
| `pImgContext` | `0x10228E00` | `imageId` 初值 `0xFF` |
| `ImageM_FlashPortJob` | `0x10228BBC` | `jobId: 0 none,1 erase,2 write`; `jobStatus: 0 done,1 pending,2 failed` |
| `PreviousWriteJob` | `0x10226B98` | `remainingLength` 是当前页缓存字节数 |
| write-exit triggered/result/status | `0x10228EE8/EE9/EEA` | status `0 no job,1 pending,2 done` |

`[C]` `FlasPort_ClearPreviousJob` 对 `PreviousWriteJob` 执行 `remainingLength=0` 和 `memset(tempData,0,256)`；它不读取或清除 `ImageM_FlashPortJob`。Flash 写子状态另有 `0=no job,1=等待/检查 erase status,2=write job` 的编码。任一时刻最多允许一个 FlashPort job；新请求到来时若旧 job 为 pending，必须返回 busy/pending，不得覆盖上下文、页缓存或仍被底层使用的源缓冲。

#### 4.4.3 App NVM 保护结论

必须把“App 镜像擦除”和“Fee/NvM 内部维护”分开回答：

1. `[C]` `[0x340000,0x370000)` 不属于任何 `LogBlocks`。把 `0x34/0x36` 或 RID `0xFF00` 的目标地址直接指定到该范围时，`ImageM_PortOpen` 会拒绝，不产生 ImageM erase/write job。
2. `[C]` CustApp/ProductionApp 的直接镜像分区分别在 `[0x090000,0x190000)` 和 `[0x190000,0x290000)`。正常 App 镜像擦除最大只在这些分区内以 `0x10000` 分块，不会把镜像擦除范围扩展到 `0x340000`。
3. `[C]` 擦除 first-entry 会读取全局 App valid；若等于 `0xAA` 则调用 `ImageM_ImageStatus_WriteApplicationValidFlag(0)`。但该写函数只有在当前 `imageId==3`（CustApp）时才真正更新 block 2 和调用 `NvM_Integration_WriteAll`；ProductionApp `imageId==4` 在此处是 no-op。CustApp 校验结束时同样会按结果写 block 2。
4. `[C]` PBL 的 Fee 物理 bank 是 `[0x350000,0x390000)` 与 `[0x390000,0x3D0000)`，与用户关注范围的 `[0x350000,0x370000)` 相交。CustApp 升级写 App valid/invalid 时，Fee 可能执行页写、垃圾回收或 bank 迁移，因而**可能对该 NVM 物理区执行编程和扇区擦除**。ProductionApp 当前不使用这条 block 2 更新路径，但其他 NvM 状态写入仍必须通过 trace 判断。
5. Fee 的设计责任应是擦除前搬迁并恢复其他有效逻辑 NvM block，因此“物理字节/扇区完全不变”不是正确验收标准；正确标准是除明确由 Bootloader 更新的 block 2/3 外，App 所有逻辑 NvM 数据、CRC、冗余和可读性保持不变。
6. `[0x340000,0x350000)` 不在当前 Fee bank 和 ImageM LogBlocks 中。静态基线下没有 App 升级路径直接访问该区，但仍需用 Flash driver trace 和扇区几何确认底层擦除不跨界。
7. `[C]` `FlashPort_WriteExit` 对最后不足 `0x100` 的数据补 `0x00` 后仍提交完整 256 字节。若 ClibData 等相邻白名单窗口以非页对齐方式恰好结束在 `0x340000`，当前代码没有最后一次“整页物理写仍在 LogBlock 内”的显式检查，存在从允许区间接编程到 NVM 起始处的风险。该风险不是正常 CustApp/ProductionApp 升级路径，也不是 erase，但供应商必须拒绝或有界处理。

所以，对“升级 App 会不会把 App 自己的 NVM 区域擦掉”的准确结论是：

> 正常 CustApp/ProductionApp 镜像擦除不会直接擦 `0x340000-0x370000`。CustApp 升级会写 NvM valid flag，而 Fee 的物理管理区从 `0x350000` 开始，因此 Fee 可能擦写其中的物理扇区；ProductionApp 当前不走 block 2 提交分支。另外，恶意/非对齐的相邻 ClibData 下载存在末页整页写越界风险。Fee 不应丢失 App 的其他逻辑 NVM 数据；仅凭静态 ELF 不能承诺该范围原始字节逐字节不变。

验收必须同时做两类检查：通过 Fls trace 证明 ImageM job 未越界；通过 NvM/Fee 逻辑读回、强制 Fee 换页/回收和逐时间点掉电，证明所有非目标 App NvM block 保持一致。原始 Flash dump 可用于定位物理变化，但不能把 Fee 元数据/页搬迁导致的合法变化直接判为数据丢失。

### 4.5 RoutineControl 擦除设计

关键函数：`SWDL_StartEraseMemory_0xFF00`，地址 `0x1024008c`。

反汇编确认流程：

```text
入口:
  routine output status = 0x10
  NRC = 0

opstatus == INITIAL:
  ImageM_PortOpen
  ImageM_PortErase
  任一步失败 -> 失败
  成功 -> 返回 0x0C，进入异步处理

opstatus == PENDING:
  FlashPort_GetJobStatus
  status == 1 -> 返回 0x0A，继续 pending
  status == 0 -> ImageM_PortClose，output=0，NRC=0，返回成功
  status == 2/其他 -> ImageM_PortClose，output|=1，NRC=0x72，返回失败

opstatus == 2（取消/终止分支；当前 DWARF 未保留枚举名称）:
  ImageM_PortClose
  output|=1
  NRC=0x72
  返回失败
```

擦除后台函数：`FlashPort_EraseDo`，地址 `0x1023c29c`。

关键行为：

1. `ImageM_PortErase` 只在请求地址、长度与已打开 context 完全相等时调用 `FlashPort_Erase`。
2. `FlashPort_Erase` 在没有 pending job 时写入 `jobId=1/jobStatus=1/imageId/address/length`，激活后台任务并设置 first-entry；已有 pending job 时返回非零。
3. `[C]` 长度为 0 时 `FlashPort_Erase` 当前分支返回 0，可能被上层解释为受理，但不会形成合理的擦除事务；这是必须修复的非法输入缺陷。
4. 擦除 first-entry 时检查当前 App valid 状态。
5. 如果当前 context 为 CustApp 且 App 状态为有效值，则先调用 `ImageM_ImageStatus_WriteApplicationValidFlag(0)`。
6. `ImageM_ImageStatus_WriteApplicationValidFlag(0)` 把 `Application_Valid_Flag` 写为 `0x55`。
7. 该函数把 NvM block 2 标记 dirty，并调用同步封装 `NvM_Integration_WriteAll`；封装会循环推进 NvM/MemIf 直到状态不再 pending，但不向调用者返回最终写入结果。
8. 当前擦除流程在封装返回后继续执行，未看到对 NvM 最终 job result 的显式成功判定。
9. 每次从剩余范围取 `min(remaining,0x10000)` 作为一个擦除块。
10. `FlashHandler_Erase` 同步调用 `Fls_Erase`，随后循环 `Fls_MainFunction/Fls_GetStatus` 直到状态为 `1`；当前无软件超时。
11. 底层立即返回成功时，更新 address/remaining 并保持 job pending；失败时置 `jobStatus=2`。全部完成后置 done 并清除后台激活条件。

断电保护设计含义：

设计意图是在实际擦除前持久化 invalid。正常 NvM 写回成功时，若此后断电，BM 下一次上电不会按普通路径启动该 App，而会尝试 FBL/PBL 恢复入口。由于当前接口不返回最终写入结果，NvM 写失败和写入原子性必须通过故障/掉电测试确认；供应商实现应在擦除前确认 invalid 已成功持久化，或采用具备同等恢复能力的事务记录。

### 4.6 TransferData 写入设计

关键函数：`DcmAppl_Dcm_WriteMemory`，地址 `0x1023e314`。

反汇编确认流程：

```text
opstatus == INITIAL:
  ImageM_CheckWritePermission(address, length)
  失败 -> NRC 0x13，返回 1
  成功 -> ImageM_PortWrite(address, length, data)
          标记写入 job active，返回 3

opstatus == 2（取消/终止分支）:
  NRC 保持 0，返回 1

opstatus == PENDING:
  FlashPort_GetJobStatus
  status == 1 -> 返回 2，继续 pending
  status == 2 -> ImageM_PortClose，NRC 0x72，清 active，返回 1
  status == 0 -> NRC 0，清 active，返回 0
```

`ImageM_PortWrite` 调用 `FlashPort_Write`。`FlashPort_Write` 的职责是将写请求放入 `ImageM_FlashPortJob`，设置后台任务激活条件，真正写入由 `FlashPort_WriteDo` 完成。

`[C]` INITIAL 分支调用 `ImageM_PortWrite/FlashPort_Write` 后没有根据其返回值改变结果，随后仍把 active flag 置 1 并返回 3。若底层因已有 pending job 拒绝新请求，上层可能仍进入轮询；供应商实现必须对提交返回值做一致的 busy/error 处理。另一个接口合同是 `srcData` 只保存指针而不复制整块数据，故 DCM/传输缓冲在 job 完成前必须保持有效，或新实现必须在提交时拥有化复制数据。

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

`[C]` 更精确的分支行为如下：

```text
首次后台调用:
  仅清 first-entry flag 并返回，不处理数据

cacheCount != 0:
  free = 0x100 - cacheCount
  if incomingLength < free:
    全部追加到 cache
    cacheCount += incomingLength
    当前 job length = 0
  else:
    复制 free 字节填满 cache
    写 0x100 字节到 currentAddress - oldCacheCount
    currentAddress += free
    srcData += free
    incomingLength -= free
    cacheCount = 0
    cache 内容清 0

cacheCount == 0:
  if incomingLength >= 0x100:
    从 srcData 直接写 0x100 字节到 currentAddress
    address/srcData += 0x100
    incomingLength -= 0x100
  else:
    将全部 incoming data 复制到 cache
    cacheCount = incomingLength
    当前 job length = 0

当前 job length == 0:
  FlashHandler status == 0 -> jobStatus = 0
  FlashHandler status != 0 -> jobStatus = 2
  jobId = 0
  清后台激活条件
```

每次后台调用至多提交一个完整页；若仍有输入长度则保留 pending，由后续后台周期继续。

`FlashPort_WriteExit` 在 TransferExit 后执行：

1. 检查页缓存是否还有剩余字节。
2. 若不足 `0x100`，用 `rba_BswSrv_MemSet8` 补 `0x00`；该 helper 的反汇编明确把 fill byte 固定为 0。
3. 调用 `FlashHandler_Write` 写入最后一页。
4. 把 imageId 清为 `0xFF`，清除 FlashPort job 的地址、长度、源指针、handler 状态及全部缓存。
5. `FlashHandler` 状态为 0 时返回 0，否则返回 1；无缓存时直接返回 0。

技术要求：

1. TransferData 写入必须支持跨页缓存。
2. Flash 写入必须以 `0x100` 字节对齐提交。
3. 最后一页必须补 `0x00`，不能补 `0xFF`，否则与当前 ELF 行为不一致。
4. 写入任务必须异步化，UDS 层通过 pending 状态等待后台 Flash job 完成。
5. 当前逻辑会把最后一页实际写满 `0x100` 字节。新实现必须在 RequestDownload/TransferExit 前证明该物理页仍完全位于授权 `LogBlock`，或要求地址和镜像长度满足页边界；不得因补齐越过 `0x340000` 等保护边界。该拒绝检查在当前 ELF 中未明确看到，属于安全增强。

### 4.8 TransferExit 设计

关键函数：`DcmAppl_Dcm_ProcessRequestTransferExit`，地址 `0x1024178c`。

反汇编确认流程：

```text
如果请求上传标志为 1:
  清标志，直接成功
否则:
  opstatus == INITIAL:
    ImageM_PortWriteExit_Trigger
    返回 0x0A pending
  opstatus == 2（取消/终止分支）:
    返回 1
  opstatus == PENDING:
    ImageM_ImageM_PortWriteExit_GetJobStatus
    如果 job status != 2:
      返回 0x0A pending
    如果 job status == 2:
      读取 ImageM_ImageM_PortWriteExit_GetResult
      非 0 -> NRC 0x72
      清 job status
      返回结果
```

内部状态迁移：

```text
ImageM_PortWriteExit_Trigger:
  triggered = 1
  status = 0
  激活 ImageM 后台任务

ImageM_PortWriteExit_Mainfunction:
  triggered == 1 且 status != 1 时:
    triggered = 0
    清后台激活条件
    ImageM_PortWriteExit()

ImageM_PortWriteExit:
  status = 1
  result = FlashPort_WriteExit()
  status = 2
```

设计含义：TransferExit 对 DCM 是异步 job，但实际最后一页写入在后台入口内同步等待 Fls 完成。若后台任务不再运行，DCM 会持续看到 pending；当前代码没有独立的软件超时。

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

异步参数对象为：

| 对象 | 地址 | 当前语义 |
| --- | ---: | --- |
| `i_input` | `0x102274AC` | 保存输入地址，不复制输入内容 |
| `i_result` | `0x102274B4` | 保存调用者结果指针，后台完成时写入 |
| `Verify_isFinish` | `0x10228EF9` | Start 写 `0`，后台完成写 `1` |

`ImageM_VerifyDownloadLogBlock_Start` 没有检查旧 verifier 是否正在执行，直接覆盖两个指针并重新激活后台任务。正常 DCM 串行调用可能避免冲突，但函数自身不提供互斥。供应商必须在 verifier pending 时拒绝第二次 Start，或为每个 job 拥有化保存输入和结果；取消、会话超时和复位必须使旧指针不可再被后台使用。

`ImageM_VerifyDownloadLogBlock()` 的主要行为：

#### 4.9.1 CRC32 基线

`[C]` CRC 范围不是固定分区，而是当前 `pImgContext.blockAddress/blockLength`：

```text
crc = 0xFFFFFFFF
firstCall = 1
address = context.blockAddress
remaining = context.blockLength

while remaining != 0:
  Fls_Read(address, buffer, 0x100)
  等待 Fls status == 1
  count = min(remaining,0x100)
  crc = Crc_CalculateCRC32(buffer,count,crc,firstCall)
  firstCall = 0
  address += count
  remaining -= count

DataM_U8ArrayIsEqual(requestCrc,&crc,4)
  相等 -> result = 0
  不等 -> result = 0x0C
```

`DataM_U8ArrayIsEqual` 的反汇编明确返回 `1=全部相等、0=任一字节不同`，所以 `0x0C` 的含义可确定为 CRC32 不匹配。输入 4 字节与 CPU 内存中的 CRC 表示直接比较；升级包中的端序必须用 golden package 冻结。

`[C]` 循环中的 `Fls_Read` 长度始终为 `0x100`，只有送入 `Crc_CalculateCRC32` 的 `count` 才取 `min(remaining,0x100)`。因此最后不足一页时，当前实现可能只使用 1..255 字节，却仍向后多读到完整 256 字节；例如校验 ClibData 末尾的非页对齐子窗口时，读访问可能越过 `0x340000`，但这是读取，不会造成 NVM 擦除或编程。供应商应把物理 read 收敛到剩余长度，或证明越界读的映射和故障行为与当前平台兼容；任何修正都不得改变参与 CRC 的字节集合和结果。

#### 4.9.2 安全地址映射结构

DWARF `[C]`：

```c
typedef struct {                  // 5 entries, sizeof each = 28
    uint32_t imageaddr;
    uint32_t hasdateaddr;         // DWARF 原拼写
    uint32_t hasexelenaddr;
    uint32_t hasexeaddr;
    uint32_t usercertaddr;
    uint32_t usercertlengthaddr;
    uint32_t signatureAddr;
} ImageSecAddrInfoFriType;

typedef struct {                  // 2 entries, sizeof each = 16
    uint32_t imageaddr;
    uint32_t usercertaddr;
    uint32_t usercertlengthaddr;
    uint32_t signatureAddr;
} ImageSecAddrInfoSecType;

typedef struct {                  // 1 entry, sizeof = 20
    uint32_t imageaddr;
    uint32_t hasdateaddr;
    uint32_t hasexelenaddr;
    uint32_t hasexeaddr;
    uint32_t signatureAddr;
} ImageSecAddrInfoThiType;
```

第一组 5 个初始化记录可直接解码为：

| image | imageaddr | hash data | hash-exe length field | hash-exe data | user cert | cert length field | signature |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FBL | `0x050000` | `0x0500A0` | `0x050B0C` | `0x050AE0` | `0x0504E0` | `0x0504E3` | `0x0502E0` |
| PBL | `0x020000` | `0x0200A0` | `0x020B0C` | `0x020AE0` | `0x0204E0` | `0x0204E3` | `0x0202E0` |
| CustApp | `0x090000` | `0x0900A0` | `0x090B0C` | `0x090AE0` | `0x0904E0` | `0x0904E3` | `0x0902E0` |
| ProductionApp | `0x190000` | `0x1900A0` | `0x190B0C` | `0x190AE0` | `0x1904E0` | `0x1904E3` | `0x1902E0` |
| CustData | `0x320000` | `0x3200A0` | `0x320B0C` | `0x320AE0` | `0x3204E0` | `0x3204E3` | `0x3202E0` |

第三组 ClibData 记录为：

```text
imageaddr       = 0x330000
hash data       = 0x3300A0
hash length     = 0x330B04
hash-exe data   = 0x330AE0
signature       = 0x3302E0
```

`[TBC]` 第二组 2-entry 表在符号地址 `0x10228C4C` 与 `.cinit` 中肉眼可识别的 `{0x000000,...}` / `{0x2D0000,...}` 记录之间存在 4 字节起始偏差；当前代码按符号地址访问，不能在没有真实升级包和运行时 RAM dump 的情况下擅自“修正”该表。供应商必须用 BM/HSM 两类当前成功包、启动后的 `0x10228C40..0x10228C70` RAM dump 和校验 trace 冻结真实字段。

#### 4.9.3 安全校验门控和特殊镜像

`SecFlash_SecCtrl()` 的 `[C]` 逻辑：

```text
非 HSSE:
  return false

HSSE 且 currentAddr == 0 或 currentAddr == 0x2D0000:
  return true

HSSE 其他地址:
  if lifecycle 为 3/4/6:
    return true
  else:
    读取 currentAddr + 0x92 的 1 字节
    return (byte == 0xA5)
```

随后主校验流程为：

| currentAddr | secure control 为 true 时的后续 |
| ---: | --- |
| `0x310000` WeifuData | 跳过 Hash 和签名 |
| `0x000000` BM | 跳过 `VerifyHashData`，执行签名 |
| `0x2D0000` HSM | 跳过 `VerifyHashData`，执行签名 |
| 其他映射镜像 | 当前 result 为 0 时执行 Hash；仍为 0 时执行签名 |

secure control 为 false 时只保留前面的 CRC32 路径。这里的“跳过”是当前 ELF 行为，不代表推荐安全策略；供应商不得自行改变，除非客户安全评审批准并重新冻结升级包。

#### 4.9.4 结果码和 App 提交

当前可直接确认的校验结果：

| 结果 | 来源 |
| ---: | --- |
| `0x00` | 当前执行的校验均成功 |
| `0x01` | 签名/证书/key 处理失败路径 |
| `0x04` | Hash 输出长度或摘要比较失败 |
| `0x06` | `pImgContext.imageId==0xFF` |
| `0x07` | Hash/HSM job 接受或执行失败路径 |
| `0x0A` | App valid 写接口报告失败的预留路径 |
| `0x0C` | CRC32 不匹配 |

`[C]` 当 `imageId==3` 时，无论校验成功还是失败都会执行：

```text
context.isValid = (result == 0)
ImageM_ImageStatus_WriteApplicationValidFlag(context.isValid)
```

因此成功写 `0xAA`，失败再次写 `0x55`。该写函数当前始终返回 0，所以将 result 改成 `0x0A` 的分支在现有实现中不可达。`imageId==4` 的 ProductionApp 不进入该 valid 更新分支。

### 4.10 Hash 校验

`VerifyHashData()` 的反汇编行为：

```text
清空 0x40 字节本地 hash buffer
从 HasexeAddr 读取首个固定 0x100 字节 Flash 数据
cycursoc_HashStart(algorithm=5, data, len=0x100)
HasexeAddr += 0x100
remaining_Len -= 0x100
循环读取 min(remaining_Len,0x100):
  Fls_Read
  Fls_MainFunction / Fls_GetStatus 等待完成
  cycursoc_HashUpdate
cycursoc_HashFinish(outputLen=0x40)
从 HasDataAddr 读取期望 hash 容器，长度 0x100
如果输出长度 != 0x40 -> 错误 0x04
memcmp(计算 hash, 期望 hash, 0x40)
相等 -> 状态 0
不等 -> 错误 0x04
任一 Hash job acceptance/执行失败 -> 错误 0x07
```

技术要求：

1. Hash 输出长度为 `0x40` 字节。
2. `[C]` 算法枚举值 `5` 对应 SHA-512；供应商必须输出 64 字节 SHA-512 摘要。
3. Flash 读取和 Hash 更新按 `0x100` 字节块推进。
4. Hash engine job 需要通过 `CheckJobAcceptance` 确认。
5. Hash 比对失败时不得置 App valid。
6. 首块长度当前固定为 `0x100`，没有先判断 `remaining_Len<0x100`；支持的镜像格式应保证长度充分，新实现仍必须显式拒绝过短/下溢输入。
7. 函数原地修改全局 `HasexeAddr/remaining_Len`，不可重入。供应商可以改为局部 context，但不得允许两个验证 job 并发复用同一状态。

对第一组安全地址记录，`remaining_Len` 由 Flash 中两个 32-bit 长度字段相加并再加 `0x40` 形成：读取 `hasexelenaddr`，再读取 `hasexelenaddr-8`。ClibData 第三组使用其专用地址组合。长度字段的端序、语义和是否包含 header 必须以当前升级包格式冻结；所有加法必须做溢出检查。

### 4.11 签名校验

`verifySecFlashSignature()` 的反汇编行为：

1. 如果 `currentAddr==0x330000`，直接使用 `pubkeyID`；其他地址调用 `InjectCert_GetKeyId(result)` 从镜像证书建立/取得临时 key id。
2. 如果证书/key 获取已把 result 置为非零，则不继续验签。
3. 按镜像地址选择签名覆盖长度，并调用 `CalculateHashData`。
4. 从全局 `signatureAddr` 读取 `0x200` 字节签名。
5. 调用 `cycursoc_JobConfigDefault` 创建安全 job 配置。
6. 调用 `cycursoc_VerifySignature(scheme=2,hash=5,keyId,hash,signatureLen=0x200,...)`。
7. 轮询 `cycursoc_PollJob`，直到 job 不 busy；要求最终 job state 为 `3` 且结果 byte 为 0。
8. 任何提交、轮询、状态或验签失败都把 result 置 `0x01`。
9. 结束时按 key id 条件擦除注入的临时 key；ClibData 的固定 public key 路径不按同样方式删除。

`[C]` 当前安全库的签名方案配置枚举值为 `2`，签名读取长度为 `0x200`。仅凭 ELF 不能可靠确定枚举 2 对应的公钥算法、曲线/模数、padding、摘要封装、key slot 和字节序；这些参数必须从当前 HSM 配置和至少一组成功/失败 golden image 冻结。供应商不得仅按“枚举值 2”猜测算法。

反汇编中可见特定镜像类型长度常量：

| 条件 | 参与签名计算的长度 |
| --- | ---: |
| 镜像类型/地址为 `0x2d0000` | `0x3f800` |
| 镜像类型/地址为 `0x000000` | `0x1f800` |
| 默认路径 | `0x2e0` |

这些值应理解为当前镜像格式/安全 Flash 布局相关常量，重新实现时不能随意修改。

`CalculateHashData`/验签轮询以及相关 `Fls_GetStatus` 循环中没有独立软件超时。供应商必须增加受控超时和错误清理，同时通过差分测试保持正常 job 的 pending/响应时序。`BM/` 中三张 SecurityAccess 截图分辨率不足以可靠恢复证书 byte array 或 key material，因此本文不抄录、也不推测这些值。

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

`[C]` `ImageM_ImageStatus_ReadApplicationValidFlag()` 只在 RAM flag **精确等于 `0xAA`** 时返回 true。这与 BM 的“只要不等于 `0x55` 就可尝试 App”并不相同。若 flag 是擦除值或其他异常值，BM 可能认为 App 可尝试，而 PBL 擦除 first-entry 可能认为它原本不是 valid，从而不重复持久化 `0x55`。供应商必须：

1. 若要求正常场景二进制等效，保留 `0xAA/0x55` 的标准写值和 BM 判定。
2. 对任何即将擦除 CustApp 的事务，无条件确认持久化 invalid，不能仅依赖旧值恰好为 `0xAA`；这是安全增强。
3. 对所有其他 flag 值建立故障测试和迁移策略，不得把 erased value 默认为可信 App。

技术要求：

1. App valid flag 有效值必须为 `0xAA`。
2. App invalid flag 必须为 `0x55`。
3. 写 flag 后必须设置 NvM RAM block dirty/status，并执行 NvM 写回。
4. 当前 ELF 只有 image context 为 `3` 时才写 App valid flag。若新设计支持多镜像，必须明确 image index 与 valid flag 的映射。
5. BM 侧对 App 的 valid 判定是 `!= 0x55`，PBL 侧写入是 `0xAA/0x55`，两者必须保持兼容。

特别注意：ProductionApp 的 imageId 为 4，而当前函数仅对 imageId 3 更新 App valid；ProductionApp 的启动允许主要由 `PDAP` 快速选择路径强制形成。供应商不得擅自让 imageId 4 复用 CustApp 的 block 2 提交流程，除非 TBC-10/TBC-12 明确批准。

NvM 接口块合同：App valid 使用 block 2；重编程请求使用 block 3。`BootM_ClearReprogrammingRequestFlag` 把请求清零并把 block 3 标记 dirty，后续 `BootM_MainFunction` 推进 block 2、block 3 及 WriteAll。

`[C]` `NvM_Integration_WriteAll()` 调用 `NvM_WriteAll()` 后，循环推进 NvM/MemIf 和 watchdog hook，直到两个状态都不再是 pending 值 `2`；函数没有返回值，也不读取/向上返回最终 request result。供应商必须保证复位前写回确认成功，或在未完成/失败时维持可恢复状态；若增加显式失败返回，需同步冻结 NRC 和复位行为。

### 4.13 DID FC00/FC01 安全扇区专用写入

`[C]` `WriteFunc_0xFC00` 和 `WriteFunc_0xFC01` 是普通 ImageM 白名单之外的两个结构相同的专用写入口：

| DID | 函数/地址 | 固定 Flash 地址 | 擦除长度 | 固定写长度 | 与 BM 的关系 |
| --- | --- | ---: | ---: | ---: | --- |
| `FC00` | `WriteFunc_0xFC00` `0x102414A4` | `0x3E2000` | `0x1000` | `0x100` | BM 从该 bank 前 128 字节读取 lifecycle magic；DID 具体用途为 `[I]` |
| `FC01` | `WriteFunc_0xFC01` `0x102414F0` | `0x3E3000` | `0x1000` | `0x100` | BM 读取前 4 字节 `CUAP/PDAP` |

两个函数的当前控制流：

```text
*errorCode = 0
if data == NULL:
  return 1

ret = Fls_Erase(fixedAddress,0x1000)
等待 Fls status == 1
if ret != 0:
  return ret

ret = Fls_Write(fixedAddress,data,0x100)
等待 Fls status == 1
return ret
```

当前函数只返回 `Fls_Erase/Fls_Write` 的立即返回值，等待结束后没有读取最终 job result，也没有软件超时；函数本身不检查 DID 请求实际长度、允许内容、会话或安全级别。这些保护必须由 DCM 配置和新实现显式承担。

FC01 不经过九个 `LogBlocks`，也不触及 `[0x340000,0x370000)` App NVM。供应商必须保持两个固定地址、擦除长度和 256 字节写长度，并严格校验请求长度、会话和安全级别。FC00 只应接受经批准的 lifecycle provisioning 数据；FC01 是否仅允许 `CUAP/PDAP` 和清除值属于 TBC-04/TBC-10。两个 DID 均不得扩展为可指定任意地址的 Flash 写接口。

### 4.14 校验请求与兼容性例程

#### 4.14.1 RID `0x0212` MemoryCheck

`[C]` 入口为 `SWDL_StartCheckRoutine_0x0212` `0x1023EB80`，DWARF 原型参数依次为：

```c
Std_ReturnType SWDL_StartCheckRoutine_0x0212(
    const uint32_t input,
    Dcm_OpStatusType OpStatus,
    uint8_t *RoutineInfo,
    uint8_t *CheckResult,
    Dcm_NegativeResponseCodeType *ErrorCode);
```

关键全局对象：

| 对象 | 地址 | 当前用途 |
| --- | ---: | --- |
| `ImageM_Verification_NumberofVerificationRequest` | `0x10228E8C` | 8-bit 请求累计计数 |
| `Security_key` | `0x10228E90` | 保存 4-byte `input`，随后作为 verifier 输入 |
| verifier finish/job byte | `0x10228EF9` | `0` 未完成，`1` 完成 |

当前 opstatus 流程：

```text
每次入口:
  *RoutineInfo = 0x10

OpStatus == 0:
  if requestCount <= 7:
    Security_key = input
    ImageM_VerifyDownloadLogBlock_Start(&Security_key, CheckResult)
    requestCount++
    return 0x0A                       // pending
  else:
    *ErrorCode = 0x09
    return 1

OpStatus == 2:
  ImageM_PortClose()
  *RoutineInfo |= 0x01                // 0x10 -> 0x11
  *ErrorCode = 0x09
  return 1

其他 OpStatus:
  if ImageM_VerifyGetJobStatus() != 1:
    return 0x0A                       // pending
  *ErrorCode = (*CheckResult == 0) ? 0 : 1
  return 0
```

`requestCount` 在当前函数中只增不减，整个 ELF 对 `0x10228E8C` 也未发现其他运行时写引用；除启动时 `.cinit` 初始化外，未看到 PortClose 或单次下载结束后清零。因此可确认的是“PBL 本次 RAM 生命周期最多受理 8 次 initial 校验触发”，不能擅自写成“每个下载事务自动恢复 8 次”。第九次路径是 `Std_ReturnType=1`、`ErrorCode=0x09`，不是函数直接返回 `0x09`；DCM 最终如何把内部 `0x09` 转成总线 NRC 必须由 ODX/实车 trace 冻结 `[TBC-04]`。

`OpStatus==2` 分支只关闭 `pImgContext`，没有在该函数中清 verifier finish byte、后台激活条件或请求计数。静态控制流因此允许已触发的后台校验继续或留下可被后续请求观察的状态；供应商若实现真正取消，必须清理 job、结果指针和 activation，并把这一故障场景差异列入批准清单。

#### 4.14.2 RID `0x0205` CompleteCompatible

`[C]` 入口为 `SWDL_CheckCompleteCompatible_0x0205` `0x10242F24`，DWARF 参数为 `OpStatus`、`RoutineInfo*`、`uint32 CheckResult*`、`ErrorCode*`。异步状态对象：

| 对象 | 地址 | 编码 |
| --- | ---: | --- |
| `ImageM_CompleteCompatibleJob` | `0x10228E84` | `0=no job, 1=pending, 2=done` |
| `ImageM_CompleteCompatible_JobTriggered` | `0x10228E85` | `1` 表示后台任务待执行 |
| `CompleteCompatibleCheckResult` | `0x10228E88` | 32-bit 结果 |

当前控制流：

```text
每次入口:
  *ErrorCode = 0
  *RoutineInfo = 0x10

OpStatus == 0:
  ImageM_CompleteCompatibleCheck_Trigger()
  // job=1, triggered=1，激活 ImageM background task

OpStatus == 2:
  *RoutineInfo = 0x11
  *ErrorCode = 0x72
  return 1

job != 2:
  return 0x0A                         // pending

job == 2:
  *CheckResult = CompleteCompatibleCheckResult
  return 0
```

后台 `ImageM_CompleteCompatible_Mainfunction` `0x10246860` 消费 trigger，调用 `ImageM_CompleteCompatibleCheck` `0x102460EC` 并保存结果。尽管函数名包含“CompleteCompatible”，当前检查函数只调用 `ImageM_CheckAppValid`：

```text
Application_Valid_Flag == 0xAA -> result = 0
Application_Valid_Flag != 0xAA -> result = 1，再 OR 0x05，最终 result = 0x05
job = 2
```

静态 ELF 中没有在该函数里发现版本号、依赖关系、CustApp/ProductionApp 组合或数据区兼容性比较。因此当前可兼容基线是“异步返回 App valid 状态，结果为 `0/5`”，而不是完整的软件兼容性算法。若供应商按产品需求增加真实兼容性矩阵，属于 TBC-12 关闭后的有意功能增强，必须保持诊断接口格式并在差异清单中批准；不得把新增逻辑描述为当前 ELF 已实现。

RID `0x0205` 的 `OpStatus==2` 分支也只设置 `RoutineInfo=0x11`、`ErrorCode=0x72` 并返回失败，未清 `ImageM_CompleteCompatibleJob` 或 trigger。供应商的取消处理必须防止后台 job 在取消后写入旧结果，同时不把增强行为误记为当前 ELF 基线。

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

上述调用在所有 erase first-entry 上都可能发生，但 `ImageM_ImageStatus_WriteApplicationValidFlag` 内部只在当前 `imageId==3` 时真正写 block 2；所以以下掉电结论针对 CustApp。ProductionApp `imageId==4` 的可恢复提交策略必须按 TBC-10/TBC-12 另行冻结。

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
| RID 0212 校验未完成 | `SWDL_StartCheckRoutine_0x0212` | 返回 `0x0A` / pending |
| RID 0212 计数超限或 `OpStatus==2` | `SWDL_StartCheckRoutine_0x0212` | `Std_ReturnType=1`、内部 `ErrorCode=0x09`；总线 NRC `[TBC]` |
| RID 0205 未完成 | `SWDL_CheckCompleteCompatible_0x0205` | 返回 `0x0A` / pending |
| RID 0205 `OpStatus==2` | `SWDL_CheckCompleteCompatible_0x0205` | `Std_ReturnType=1`、`ErrorCode=0x72` |
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
| BM-04 | `StayInBootFlag = 1`，FBL valid 任意 | 不检查 valid，直接安全检查 FBL |
| BM-05 | `StayInBootFlag = 2`，PBL valid 任意 | 不检查 valid，直接安全检查 PBL |
| BM-06 | CAN ID `0x190C8532` + `02 10 82 FORCEJUMP A5B6C7D8` | 设置 `StayInBootFlag = 1` |
| BM-07 | CAN ID `0x190C8532` + `02 10 60 FORCEJUMP A5B6C7D8` | 设置 `StayInBootFlag = 2` |
| BM-08 | 重编程请求 `0x10021002` | 优先尝试 FBL |
| BM-09 | 重编程请求 `0x10061006/0x10861086` 且 PBL valid | 尝试 PBL并执行安全检查 |
| BM-10 | CAN 强制 FBL/PBL 的安全检查失败 | 直接失败并留在 BM；不回退任何 App |
| BM-11 | 重编程请求 `0x10821082` 且 FBL valid | 尝试 FBL `0x50000` 并执行安全检查 |
| BM-11A | 任一重编程请求对应 FBL/PBL invalid | 不检查该目标安全启动，回退 CustApp `0x90000` |
| BM-11B | 任一重编程请求目标安全检查失败 | 固定回退 CustApp `0x90000`；不使用 `0x190000`，不重跑普通链 |
| BM-12 | `0x3E3000=CUAP` | 清重编程请求、App RAM flag=`0xAA`，`APP_IMAGE_Addr` 保持初始化值 `0x90000` |
| BM-13 | `0x3E3000=PDAP` | 清重编程请求、App RAM flag=`0xAA`、选择 `0x190000` |
| BM-14 | `0x3E3000` 为其他值 | 从 NvM 读取 App valid 和重编程请求 |
| BM-15 | 强制 CAN 帧 DLC `<16` | 供应商实现安全忽略且无越界访问；记录为相对当前固定 16 字节读取的批准安全差异 |
| BM-16 | HSSE Hash/签名/解密/加载/初始化分别失败 | 分别记录 `F1/F2/F3/F0/F4`，不得启动目标 |
| BM-17 | lifecycle=OnBoard/Customizing，128-byte magic 完全匹配 | 进入 `Boot_Logic` |
| BM-18 | lifecycle=OnBoard/Customizing，magic 任一字节错误，且无强制帧 | 不进入 `Boot_Logic`，保持 fail-closed |
| BM-19 | lifecycle magic 错误，同时收到合法 FBL/PBL FORCEJUMP | 允许进入对应强制路径，但目标仍必须安全检查 |
| BM-20 | lifecycle=Operation/Return/Development/Decommission | `rbSecBM_CheckLCValid` 不比较 magic；安全功能强制性按 3/4/6 表执行 |
| BM-21 | 对 `{ecuLC,hsmMain,hsmSub}` 做 CRC 参数/字节序测试 | BM 生成和 PBL 重算均使用 poly `0x1D`、init/xorout `0xFF`、非反射，结果逐字节一致 |
| BM-22 | HSM firmware 初始化成功，但 lifecycle load/query 返回失败或 main state >5 | 记录当前共享区残留/直接通过行为；供应商安全增强实现停留 BM，并列入批准差异 |
| BM-23 | `numFiles>10`、coreId>3、损坏 RPRC sectionCount/size/address | 新实现拒绝且不写越界 RAM；合法 golden image 结果与当前 ELF一致 |
| BM-24 | HSSE/非 HSSE 早期 CAN 窗口 | 指令循环阈值分别 `79/143`；实际时间满足冻结值 |

### 8.2 PBL 刷写测试

| 编号 | 条件 | 期望 |
| --- | --- | --- |
| PBL-01 | RequestDownload 合法地址和长度 | 返回成功和 maxNumberOfBlockLength |
| PBL-02 | RequestDownload 非法地址或长度 | NRC `0x31` |
| PBL-03 | 擦除 CustApp imageId 3 前 App flag=`0xAA` | 先发起 block 2 写 `Application_Valid_Flag = 0x55`，再开始首个 erase |
| PBL-04 | 擦除长度大于 `0x10000` | 分块擦除 |
| PBL-05 | TransferData 跨 `0x100` 页边界 | 正确缓存并按页写入 |
| PBL-06 | 最后一页不足 `0x100` | TransferExit 补 `0x00` 后写入 |
| PBL-07 | CustApp CRC32 失败 | 写入/保持 `0x55`，不得写 `0xAA`；结果 `0x0C` |
| PBL-08 | CustApp Hash 失败 | 写入/保持 `0x55`，不得写 `0xAA`；结果为对应 Hash 失败码 |
| PBL-09 | CustApp 签名失败 | 写入/保持 `0x55`，不得写 `0xAA`；结果为对应签名失败码 |
| PBL-10 | CRC/Hash/签名全部通过 | 写 `Application_Valid_Flag = 0xAA` 并 NvM 写回 |
| PBL-11 | RequestDownload 最大块长度查询 | 返回 `0x0FFF` |
| PBL-12 | 请求恰好结束于任一 LogBlock 末端 | 接受；末端后 1 字节拒绝 |
| PBL-13 | 请求跨两个相邻白名单块 | NRC `0x31`，不产生 Flash job |
| PBL-14 | 地址加长度发生 32-bit 溢出或长度为 0 | 拒绝，不产生 Flash job |
| PBL-15 | 擦除范围不是已打开上下文的精确范围 | 拒绝 |
| PBL-16 | 把普通 UDS 擦除/下载地址直接设为 `[0x340000,0x370000)` 内任意范围 | 拒绝，不产生 ImageM/Fls 镜像 job；该请求前后原始内容不变 |
| PBL-17 | 从 ClibData 尾部跨入 `0x340000` | 拒绝，不产生 ImageM/Fls 镜像 job |
| PBL-18 | DID FC01 合法写 | 仅擦 `0x3E3000+0x1000`，写 256 字节，BM 正确选择 App |
| PBL-19 | DID FC01 长度/会话/安全级错误 | 拒绝且选择扇区不变 |
| PBL-20 | Flash job pending 时插入新 job | 不覆盖原 job，上层收到 busy/pending |
| PBL-21 | 同一次 PBL 上电后对 RID 0212 发起第 1 至第 8 次 initial 请求，再发第 9 次 | 前 8 次启动 verifier；第 9 次 `Std_ReturnType=1`、内部 `ErrorCode=0x09`，总线 NRC 按 TBC-04 冻结 |
| PBL-22 | 完整 CustApp 升级，Fee 不触发回收 | block 2 valid 按事务变化；所有其他 App NvM 逻辑块值保持一致 |
| PBL-23 | 预填充 Fee 至升级时强制 bank 换页/垃圾回收 | 允许 `[0x350000,0x3D0000)` 物理布局变化，但所有非目标 NvM 逻辑块、CRC 和冗余读回一致 |
| PBL-24 | CustApp/ProductionApp 升级前后比较 `[0x340000,0x350000)` | 原始字节不变，且 Fls trace 无该区 erase/write |
| PBL-25 | DID FC00 正/负向测试 | 仅授权流程可擦写 `0x3E2000`；错误长度/会话/安全级不得改变 lifecycle magic |
| PBL-26 | RID 0205，App flag=`0xAA`/非 `0xAA` | 异步 job 经 `1 -> 2`；CheckResult 分别为 `0x00000000/0x00000005` |
| PBL-27 | RID 0205 执行期间检查调用 trace | 当前基线只调用 `ImageM_CheckAppValid`，不得把未实现的版本/依赖检查写进等效性结论 |
| PBL-28 | CustApp 擦除前 flag 为非 `0xAA` 且非 `0x55` | 记录当前 ELF 与安全增强实现差异；供应商实现必须在首个 erase job 前确认 `0x55` 已持久化 |
| PBL-29 | 校验窗口最后不足 `0x100`，特别是 ClibData 尾部 | CRC 仅覆盖声明长度；记录当前 ELF 的整页 read 与供应商有界 read 差异，均不得产生 erase/write |
| PBL-30 | RID 0212/0205 pending 时发送 `OpStatus==2` 对应取消事件 | 当前基线残留状态可复现；供应商增强实现清理 job/trigger/指针且旧结果不得污染下一事务 |
| PBL-31 | RID 0212 verifier pending 时再次发 initial 触发 | 当前覆盖风险纳入差分；供应商实现拒绝/排队，不覆盖 `i_input/i_result` |
| PBL-32 | erase/write/write-exit pending 时发送新的 RequestDownload | 当前 context/cache 覆盖风险纳入差分；供应商实现返回 busy/sequence error，旧 job 数据保持不变 |
| PBL-33 | 篡改 `0x102DFF0C` CRC，分别校验 BM/HSM 和普通镜像 | 复现当前 BM/HSM 固定安全、普通镜像退回 `+0x92` 的行为；供应商增强实现对不可信 lifecycle fail closed |
| PBL-34 | ClibData 下载窗口非页对齐结束于 `0x340000`，随后 TransferExit | 记录当前整页补零风险；供应商实现拒绝或只写授权字节，`[0x340000,...)` 无 ImageM program |

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
| HSM lifecycle 读取、ECU lifecycle 转换 | `rbSecBM_GetHSMLCState_en` `0x1020e16a`、`rbSecBM_GetECULCState_en` `0x1020c2a0` |
| lifecycle magic 只在指定状态比较 | `rbSecBM_CheckLCValid` `0x1020d5a0`、`rbSecFls_Read_MagicNum` `0x1020ed80` |
| lifecycle 安全强制查表 | `rbSecBM_IsLifeCycleEnforced` `0x102108ac` |
| lifecycle 共享结构 CRC8 参数 | BM `Crc_CalculateCRC8` `0x1020F044` 及表 `0x10213A0C`；PBL `sec_Crc_CalculateCRC8` `0x10244A04` 及表 `0x1024A9FC` |
| `rbSec_Basic_init` 与 lifecycle magic 检查是两个独立调用 | `BootM_BootTargetSoftware` 调用点 `0x10209424`、`0x10209432` |
| FBL/PBL 跳转前向量源是 RAM `0x1021E000` | `BootM_BootTargetSoftware` 调用点 `0x1020947a` 到 `0x10209484`、`BootM_RelocateVectortable` `0x10211808` |
| BM Fee bank 配置与 PBL 相同 | BM `rba_FeeFs1x_Prv_Cfg_FlashPropTable_cast` `0x1021464C` 及 `.rodata` |
| 截图与 ELF 的函数边界差异 | `BM/555.png`、`BM/666.png`、`BM/Weixin Image_20260716172923_869_85.jpg` 与上述两个独立调用点交叉核对 |

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
| 下载上下文和异步 job 的实际布局 | `pImgContext` `0x10228E00`、`ImageM_FlashPortJob` `0x10228BBC`、`PreviousWriteJob` `0x10226B98` 及其 DWARF 类型 |
| RequestDownload no-match 返回及前置拒绝门 | `ImageM_GetRequestDownloadCondition` `0x10241290`、`ImageM_PortOpen` `0x10240870` |
| RequestDownload 所谓 previous job 清理只清页缓存 | `FlasPort_ClearPreviousJob` `0x10247FC4`，目标 `PreviousWriteJob` `0x10226B98` |
| TransferData 只按整个 LogBlock 检查 | `ImageM_CheckWritePermission` `0x10244674` |
| FC00 擦 `0x3E2000/0x1000` 并写 `0x100` | `WriteFunc_0xFC00` `0x102414a4` |
| FC01 擦 `0x3E3000/0x1000` 并写 `0x100` | `WriteFunc_0xFC01` `0x102414f0` |
| 最大下载块长度 `0x0FFF` | `ImageM_PortGetMaxNOBL` |
| Hash 枚举 5、摘要 64 字节 | `VerifyHashData` DWARF 与反汇编 |
| 签名读取 `0x200` 字节、scheme=2 | `verifySecFlashSignature` `0x102368c0` |
| NvM WriteAll 同步轮询但不返回 job result | `NvM_Integration_WriteAll` `0x10243672` |
| Fee 两个物理 bank 的 inclusive 边界 | `rba_FeeFs1x_Prv_Cfg_FlashPropTable_cast` `0x1024BF18` 的 16 字节常量；`Fee_Prv_ConfigGetPhysStartAddress` `0x102493e6`、`Fee_Prv_ConfigGetPhysEndAddress` `0x1023af78` |
| 三组安全镜像地址结构及第二组偏移疑点 | `SecAddrInfoFri` `0x102286F0`、`SecAddrInfoSec` `0x10228C4C`、`SecAddrInfoThi` `0x10228D88`，结合 DWARF 和 `.cinit` |
| RID 0212 的 8 次上电周期计数和异步结果 | `SWDL_StartCheckRoutine_0x0212` `0x1023EB80`、`ImageM_Verification_NumberofVerificationRequest` `0x10228E8C`、`Security_key` `0x10228E90` |
| RID 0205 当前只检查 App flag，结果为 0/5 | `SWDL_CheckCompleteCompatible_0x0205` `0x10242F24`、`ImageM_CompleteCompatibleCheck` `0x102460EC`、`ImageM_CheckAppValid` `0x102476E0` |
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
| TBC-06 | lifecycle 枚举值已由 DWARF 恢复，但各状态的量产进入/退出条件、provisioning 权限及 HSSE/非 HSSE 允许策略未知 | HSM lifecycle 规范、生产烧录流程和安全评审 |
| TBC-07 | OS 任务优先级、栈水位、最坏执行时间、Flash 操作超时 | 目标板测量、静态栈分析 |
| TBC-08 | watchdog 的启用状态、窗口、喂狗责任和复位原因持久化 | 硬件安全需求、目标板测试 |
| TBC-09 | 外部 Flash 型号、页/扇区几何、写保护、耐久性和掉电行为 | Flash 数据手册和板级原理图 |
| TBC-10 | 快速选择字与 NvM invalid 的最终优先级策略 | 客户安全评审决定 |
| TBC-11 | FBL 自身的诊断/刷写能力和与 BM/PBL 的分工 | FBL ELF/源码或供应商接口文档 |
| TBC-12 | ProductionApp/CustApp 切换和回滚策略，以及是否需要在 RID 0205 当前“仅检查 App valid”之外增加真正的版本/依赖/镜像组合兼容性规则 | 产品升级策略、发布矩阵和 golden package |
| TBC-13 | App invalid/valid 的 NvM 最终 job result、掉电原子性及写失败时的诊断/复位行为 | NvM 配置、Fee/Flash 故障注入、逐时间点掉电测试 |
| TBC-14 | Fee 中每个 NvM block 的物理/逻辑映射、block 2/3 的冗余与 CRC、垃圾回收及 bank 迁移原子性 | NvM/Fee 生成配置、逻辑块清单、Fee trace 和掉电测试 |
| TBC-15 | `SecAddrInfoSec` 符号地址与 `.cinit` 可识别记录之间的 4 字节偏移，以及 BM/HSM 镜像实际字段映射 | 当前成功升级包、启动后 RAM dump、HSM 校验 trace |

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
16. 保持九个 LogBlock 的地址、imageId 和单块包含检查；App NVM 永久拒绝普通 ImageM 擦写。Fee 仅可管理 `[0x350000,0x3D0000)`，并必须保持非目标逻辑 NvM block。
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
| BM-REQ-005 | CAN 强制路径必须绕过目标 valid，认证失败后直接失败；重编程路径必须检查目标 valid，目标 invalid/认证失败后只尝试 CustApp `0x90000`。 | 分支覆盖/HIL |
| BM-REQ-006 | CAN 强制帧必须同时匹配 29-bit ID、DLC 和完整 16 字节 payload。 | 总线模糊测试 |
| BM-REQ-007 | BM 必须区分并持久/共享记录安全初始化、加载、Hash、签名和解密失败。 | HSM 故障注入 |
| BM-REQ-008 | FBL/PBL 启动必须复制 `0x400` 字节向量表到 `0x0`，完成必要反初始化后跳转。 | JTAG/内存检查 |
| BM-REQ-009 | App 启动必须兼容当前多核 appimage/RPRC，支持最多 4 个 CPU 描述项。 | golden images |
| BM-REQ-010 | 无可启动目标时必须留在 BM 安全错误态，不得执行未验证地址。 | 负向测试 |
| BM-REQ-011 | OnBoard/Customizing 必须比较 `0x3E2000` 前 128 字节 magic；失败时仅合法早期 FORCEJUMP 1/2 可旁路到相应 Bootloader。 | magic/生命周期矩阵 |
| BM-REQ-012 | BM 必须验证 AppImage/RPRC 的记录数、偏移、段地址、长度、重叠和 RAM 白名单，且保持所有 golden image 的加载与核释放结果。 | 模糊测试/JTAG |
| BM-REQ-013 | BM 写 `0x102DFF0C` 时必须对前三字节使用 3.5.2 节精确 CRC8 参数，并把结果写到偏移 `+3`。 | CRC 向量、RAM trace |
| BM-REQ-014 | 新实现取得 lifecycle 失败、值越界或共享数据无法完整生成时必须 fail closed；这是相对当前忽略返回值/残留值路径的安全增强，正常状态行为不得改变。 | HSM 故障注入、差异审批 |

### 12.2 PBL 需求

| ID | 强制需求 | 验证方法 |
| --- | --- | --- |
| PBL-REQ-001 | PBL 必须实现 4.1.1 的分层，并禁止 DCM/SWDL 绕过 ImageM 地址权限。 | 设计/代码评审 |
| PBL-REQ-002 | PBL 必须运行 1ms、10ms 和后台状态机；长操作不得阻塞 DCM 的周期推进。 | 时序测量 |
| PBL-REQ-003 | PBL 必须仅允许 2.4 节九个 LogBlock，且每个请求完整位于一个块内。 | 边界/模糊测试 |
| PBL-REQ-004 | ImageM/FlashPort 必须拒绝对 `[0x340000,0x3D0000)` 的直接下载/擦除，并保证页/扇区对齐不越界；BM/PBL Fee 配置必须一致，Fee 只可在其两个 bank 内维护 NvM，且不得丢失非目标逻辑块。 | 配置比对、Fls trace、NvM 逻辑读回、Fee 回收/掉电测试 |
| PBL-REQ-005 | RequestDownload 必须返回 maxNumberOfBlockLength `0x0FFF`；只有在所有相关 job 已完成且结果已消费后才可清 `PreviousWriteJob` 页缓存。 | UDS、并发状态测试 |
| PBL-REQ-006 | 擦除请求必须等于已打开窗口，分块最大 `0x10000`，失败必须关闭端口并保持 invalid。 | Flash fault injection |
| PBL-REQ-007 | 写入必须按 `0x100` 页缓存，支持跨页，最后一页使用 `0x00` 补齐。 | 边界数据比对 |
| PBL-REQ-008 | 任一时刻最多一个 Flash job；erase/write/write-exit/verifier 任一 pending 时，新 RequestDownload 不得覆盖 job、context、页缓存或异步结果指针。 | 并发请求测试 |
| PBL-REQ-009 | CustApp imageId 3 擦除前必须先将 block 2 的 valid 持久化为 `0x55`；ProductionApp 的独立提交策略按 TBC-12 冻结。 | 掉电注入 |
| PBL-REQ-010 | 对 imageId 3 必须保持当前提交规则：CRC32 以及按安全门控实际启用的 SHA-512/签名均成功时写 `0xAA`，任一失败写 `0x55`。RID `0x0205` 兼容性是独立调用链，其与 valid 提交的最终顺序按 TBC-12 冻结，不得宣称当前 ELF 已把它作为同一前置门。 | 篡改测试、调用顺序 trace |
| PBL-REQ-011 | 重编程请求清除必须更新 NvM block 3，并在复位前完成或保证恢复。 | 复位注入 |
| PBL-REQ-012 | FC00/FC01 必须分别只访问 `[0x3E2000,0x3E3000)`、`[0x3E3000,0x3E4000)`，每次固定擦 `0x1000`、写 `0x100`，不得复用为任意地址写接口。 | 安全测试、Fls trace |
| PBL-REQ-013 | PBL 必须实现第 7 节诊断和 CAN 基线，并由诊断表冻结权限矩阵。 | CANoe/诊断一致性 |
| PBL-REQ-014 | SecurityAccess 和 HSM 服务必须 fail closed，密钥不得进入普通软件交付物。 | 安全评审 |
| PBL-REQ-015 | 所有 Flash/HSM pending 状态必须可超时、可取消或可由复位安全恢复。 | 超时/复位测试 |
| PBL-REQ-016 | PBL 必须按 3.5.2 节精确 CRC8 参数校验 BM 在 `0x102DFF0C` 交接的 lifecycle；校验失败时不得把 `0xFF` 当成可信的“安全不强制”。fail-closed 是相对当前 fallback 的安全增强。 | CRC 向量、RAM 篡改、故障注入 |
| PBL-REQ-017 | NvM/Fee 必须把“退出 pending”和“最终写成功”分开处理；block 2/3 最终失败时不得继续执行依赖持久化成功的擦除、提交或复位。该要求是对当前封装缺口的安全增强。 | Fee/Fls 故障注入 |
| PBL-REQ-018 | RID 0212 必须保持 4-byte input、异步 pending、原始 CheckResult 和每次 PBL RAM 生命周期最多 8 次 initial 触发的当前接口基线；是否重置计数属于行为变更。 | UDS 状态机、复位测试 |
| PBL-REQ-019 | RID 0205 等效基线必须异步返回 `0`（App flag=`0xAA`）或 `5`（其他值）。新增版本/依赖兼容性检查必须按 TBC-12 批准并形成接口版本。 | UDS/HIL、调用 trace |
| PBL-REQ-020 | CRC32 必须只计算声明下载窗口内的字节；最后不足 256 字节时不得因物理读取跨界导致 fault，更不得形成任何 erase/write。 | 边界窗口、Fls trace |
| PBL-REQ-021 | verifier pending 时不得由第二次 RID 0212 覆盖 `i_input/i_result`；取消或超时后后台不得解引用旧 DCM 缓冲。 | 并发请求、内存监测 |

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
| FALLBACK | 仅重编程路径固定尝试 CustApp；普通路径取下一候选；CAN 强制路径无 fallback | 有候选/耗尽 | AUTH/ERROR |
| LOAD | App 多核加载或 FBL/PBL 向量搬移 | 成功/失败 | HANDOVER/ERROR |
| HANDOVER | 反初始化冲突外设、同步缓存并释放 CPU/跳转 | 不应返回 | 目标软件 |
| ERROR | 保持安全状态和诊断信息 | 受控复位 | RESET |

### 13.2 PBL 下载状态机

下表是根据调用链重建的设计状态，不是 ELF 中存在的单一枚举。`[C]` 表示当前可观察基线；`[R]` 表示供应商必须补上的故障安全要求。尤其是 NvM 当前只等待退出 pending，不能把它写成已经确认最终持久化成功。

| 状态 | 允许事件 | 必须动作 | 失败处理 |
| --- | --- | --- | --- |
| IDLE | 会话切换/SecurityAccess | 建立授权上下文 | NRC/延时 |
| OPEN | RequestDownload/RID FF00 | 白名单和范围检查，创建 ImageContext | 关闭 context |
| INVALIDATE | CustApp imageId 3 擦除前 | `[C]` block 2=`0x55`、标 dirty、WriteAll 并等待退出 pending；`[R]` 读取最终 result 并确认持久化 | `[C]` 当前缺少最终结果门；`[R]` 失败时不得擦除 |
| ERASE_PENDING | Flash erase job | 每次最大 `0x10000`，周期轮询 | job failed、保持 invalid |
| RECEIVE | TransferData | 序号、地址、长度、窗口权限检查 | NRC、不得越界写 |
| WRITE_PENDING | 页写 job | 256 字节提交、更新剩余地址/长度 | job failed、保持 invalid |
| EXIT_PENDING | TransferExit | 末页补零并写入 | NRC `0x72`、保持 invalid |
| VERIFY_PENDING | RID 0212/校验触发 | `[C]` CRC32、按门控启用的 SHA-512/签名；RID 0205 另行异步检查 App flag 并返回 `0/5` | 记录具体失败，imageId 3 写回 invalid |
| COMMIT | imageId 3 的当前 verifier result 为 0 | `[C]` block 2=`0xAA`、WriteAll 并等待退出 pending；`[R]` 确认最终 result | `[C]` 当前缺少最终结果门；`[R]` 失败时维持 invalid/恢复态 |
| COMPLETE | 响应完成/清重编程请求/复位 | `[C]` 推进 block 2/3 和 WriteAll；`[R]` 确认最终持久化后才复位 | 延迟复位或报错 |

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
4. NvM block 2/3 的布局、默认值、冗余/CRC、写周期和掉电原子性，以及 Fee 全部逻辑 block 到两个物理 bank 的映射、换页和垃圾回收规则。
5. FBL/PBL valid word 的生产、更新、擦除和恢复流程。
6. 全部 UDS 服务会话/安全矩阵、DID/RID 数据格式、NRC 和 P2/P2*/S3 时间。
7. CAN 波特率选择、ID、CanTp 参数、网络唤醒/休眠和 BusOff 恢复。
8. HSM 生命周期、key slot、签名算法、SecurityAccess 和安全错误处理。
9. 快速选择字 TBC-10 策略、FC00/FC01 权限以及 Cust/Production App 发布流程。
10. `SecAddrInfoSec` 的真实运行时字段、BM/HSM 签名容器格式及 TBC-15 的 4 字节偏移结论。
11. watchdog、复位原因、错误日志和现场恢复策略。

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
3. ImageM 不得直接擦写 `[0x340000,0x3D0000)`；`[0x340000,0x350000)` 原始字节保持一致。Fee bank 的物理布局允许因 valid flag 和回收变化，但除批准的 Bootloader-owned block 外，全部 App NvM 逻辑数据、CRC、冗余和掉电恢复结果必须一致。
4. 边界、跨区、溢出、短帧、乱序块、重复块和并发 job 不产生越界读写。
5. 在擦除、每页写、TransferExit、验证和 valid/NvM 写回的每个关键点断电，系统都能进入已冻结的安全恢复路径。
6. HSSE 量产生命周期下，未签名、错 key、错 Hash、错签名、截断和回滚镜像按安全策略拒绝。
7. BM 无合法目标时保持安全状态；不得因无效指针、损坏头或超长字段跳转。
8. 满足已冻结的启动时间、诊断响应时间、栈水位、CPU 负载和 Flash 操作超时指标。

### 15.2 退出门槛

以下条件全部满足后才可接受供应商版本：零个开放的安全高危/严重缺陷；零个未批准的二进制兼容差异；所有 TBC 已签字关闭；需求和分支覆盖达到双方约定；量产包回归、NVM 保持、掉电恢复和 HSM 安全测试全部通过；交付物可在客户环境中独立复现构建。

## 16. 最终结论

本文已能作为供应商重实现的架构和详细设计输入，但它不是源码的数学等价恢复。已确认的核心功能包括：BM 四目标选择、普通/重编程/CAN 强制三类路径、lifecycle magic 与 CRC8 合同、快速 App 选择、HSSE 安全启动、AppImage/RPRC 加载、PBL UDS/OS/ImageM/FlashPort 分层、九块下载白名单、Fee 的两个 NVM bank、页写/擦除、CRC32/SHA-512/签名、RID 0212/0205 状态机以及 NvM valid 写回调用链。

正常 App ImageM 擦除不直接进入 App NVM；CustApp 的 NvM valid 事务可能使 Fee 擦写 `0x350000` 起的物理 bank，相邻 ClibData 的非对齐末页还存在当前整页写风险。因此验收必须同时看 ImageM/Fls 物理 trace 和 NvM 逻辑数据保持，不能用整区 raw hash 代替 Fee 一致性。当前已明确标出的异常路径缺口包括 lifecycle 返回值被忽略、PBL CRC-invalid fallback、RequestDownload context/cache 可覆盖、TransferData 子窗口未收敛、NvM/FC00/FC01 不检查最终 job result，以及 RID 0205 实际只检查 App valid。这些只能作为当前基线缺陷或批准的安全增强处理，不能被补写成当前已有功能。物理擦除与掉电行为、完整 Fee block 映射、安全地址表偏移和真实兼容性策略仍必须按 TBC-09、TBC-12 至 TBC-15 在目标板及配套工具链上关闭。

供应商实现“功能与现在相同”的最终判据不是代码结构相似，而是：冻结所有 TBC 后，通过当前 ELF 与新 ELF 的同输入差分测试，并满足第 12 节需求和第 15 节验收门槛。
