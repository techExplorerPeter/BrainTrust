# CR60 Light BYD Bootloader 详细设计文档与技术要求

本文基于当前目录下两个 ELF 文件的静态逆向分析编写：

| 镜像 | 角色 | ELF 入口 | 架构 | 主要职责 |
| --- | --- | --- | --- | --- |
| `D_CR60_Light_BM.elf` | Boot Manager, BM | `0x00020000` | ARM32 little-endian, EABI5 | 上电初始化、读取启动状态、选择 App/FBL/PBL、执行安全启动检查和跳转 |
| `D_CR60_Light_PBL.elf` | Primary/Platform Bootloader, PBL | `0x00020000` | ARM32 little-endian, EABI5 | UDS/OTA 下载、Flash 擦写、完整性/Hash/签名校验、更新 App valid flag |

分析依据包括 ELF header、program/section header、`.symtab`、`.debug_info`、`.debug_line`、`.rodata` 常量、TI ARM objdump 反汇编结果。由于没有源代码和原始设计文档，本文将“反汇编直接确认的事实”和“根据函数名/流程推断的设计含义”分开表述。

地址说明：符号表中的 Thumb 函数地址最低位会置 1，例如 `Boot_Logic` 在符号表显示为 `0x10204961`，实际指令起始地址为 `0x10204960`。本文统一使用去掉 Thumb bit 后的指令地址。

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
| 固定镜像地址 | BM 按 `0x20000/0x50000/0x90000` 选择 PBL/FBL/App |
| NvM / 安全 Flash 状态 | 保存 App/FBL/PBL valid flag、重编程请求和安全生命周期信息 |
| Application valid flag | PBL 在刷写前置 invalid，校验通过后置 valid；BM 上电读取后决定是否启动 App |
| CAN 强制跳转帧 | BM 早期监听扩展 CANFD 帧，可强制优先进入 FBL 或 PBL |

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

`Boot_Logic` 中直接出现：

```text
StayInBootFlag == 2 -> 0x20000
StayInBootFlag == 1 -> 0x50000
App path            -> 0x90000
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
| `0x10821082` | PBL | `0x20000` | 请求进入 PBL |

重编程请求路径仍会检查目标 valid flag，并调用 `SecBoot_Check_Process`。如果目标检查失败，BM 会回退到普通优先级路径，继续尝试 App/FBL/PBL。

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
3. 强制跳转只是改变优先级，不能绕过 valid flag 和 secure boot 检查。
4. 对外测试时必须分别覆盖 `02 10 82 ...` 和 `02 10 60 ...` 两种路径。

### 3.9 BM 加载和跳转方式

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
4. 每次擦除最大块大小为 `0x10000` 字节。
5. 擦除通过 `FlashHandler_Erase` 执行。
6. 擦除完成后更新 FlashPort job 状态，并清除 ImageM 后台任务激活条件。

断电保护设计含义：

一旦进入实际擦除/写入阶段，旧 App 会先被标记为 invalid。若此后断电，BM 下一次上电不会按正常路径启动该 App，而会尝试 FBL/PBL 恢复入口。

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
2. Flash 读取和 Hash 更新按 `0x100` 字节块推进。
3. Hash engine job 需要通过 `CheckJobAcceptance` 确认。
4. Hash 比对失败时不得置 App valid。

### 4.11 签名校验

`verifySecFlashSignature()` 的反汇编行为：

1. 根据镜像类型/地址获取 key id。
2. 对镜像内容计算 Hash。
3. 从 Flash 读取 `0x200` 字节签名数据。
4. 调用 `cycursoc_JobConfigDefault` 创建安全 job 配置。
5. 调用 `cycursoc_VerifySignature` 验证签名。
6. 签名失败会更新结果状态，阻止 valid flag 写入。

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

## 5. 断电与异常恢复设计

### 5.1 未进入擦写阶段断电

如果只完成了会话切换、安全访问、RequestDownload 或条件检查，尚未进入实际擦除/写入：

```text
旧 App 可能仍完整
Application_Valid_Flag 可能仍为 0xAA
下次上电 BM 可能继续启动旧 App
```

### 5.2 擦除开始后断电

`FlashPort_EraseDo` 在实际擦除前会先 invalid App：

```text
ImageM_ImageStatus_ReadApplicationValidFlag
如果当前 App valid:
  ImageM_ImageStatus_WriteApplicationValidFlag(0)
  Application_Valid_Flag = 0x55
```

断电结果：

```text
App 标记无效
App 区域可能部分擦除或部分写入
下次上电 BM 不会按普通路径启动 App
BM 尝试 FBL，再尝试 PBL
```

### 5.3 写完但未校验通过前断电

即使 TransferData 全部接收、Flash 已经写完，只要还没有完成：

```text
ImageM_VerifyDownloadLogBlock
VerifyHashData
verifySecFlashSignature
ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

App valid flag 仍不会恢复为 `0xAA`。下次上电仍走恢复路径。

### 5.4 校验通过并写 valid 后断电

如果 Hash 和签名校验通过，且 PBL 已写：

```text
Application_Valid_Flag = 0xAA
```

下次上电 BM 普通启动路径会优先尝试 App `0x90000`，并继续执行 `SecBoot_Check_Process`。只有安全启动也通过时才真正启动 App。

## 6. 安全设计要求

### 6.1 安全启动要求

1. BM 对任何目标启动前必须调用 `SecBoot_Check_Process`。
2. valid flag 不能替代安全启动校验。
3. `secBoot_Record` 必须记录每次安全启动结果。
4. 安全启动错误码应写入共享错误区，例如 `u32_secboot_err`。
5. 强制跳转 CAN 帧和重编程请求不得绕过安全启动。

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
| BM-09 | 重编程请求 `0x10061006/0x10861086/0x10821082` | 优先尝试 PBL |
| BM-10 | 候选目标 secure boot 失败 | 回退尝试下一个目标或停留错误态 |

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

## 10. 已知限制和待确认项

1. 本文基于静态反汇编，没有运行时 trace，因此定时、OS 调度优先级和部分状态机时序需要实车或 HIL 验证。
2. ELF 保留了 DWARF 文件路径和行号，但没有源文件内容，无法确认宏定义、配置生成来源和注释。
3. FBL 镜像本身未在本次输入中作为单独 ELF 分析；BM 中的 FBL 只按地址和 flag 处理。
4. 签名校验中的镜像类型常量和地址表来自反汇编，应结合升级包格式进一步确认字段含义。
5. CANFD OTA 的完整诊断 ID 配置不完全来自这两个 ELF，需要结合诊断描述表、ODX/PDX、xFlash 配置或实车抓包确认。

## 11. 重新实现时的最低兼容要求

如果需要从零实现一个兼容当前行为的 BM+PBL，至少必须满足：

1. 保持 BM 目标地址：PBL `0x20000`、FBL `0x50000`、App `0x90000`。
2. 保持 BM 普通优先级：App -> FBL -> PBL。
3. 保持强制 CAN 帧：ID `0x190C8532`，payload 使用 `02 10 82/60 FORCEJUMP A5 B6 C7 D8`。
4. 保持重编程请求 magic：`0x10021002`、`0x10061006`、`0x10861086`、`0x10821082`。
5. 保持 FBL/PBL valid magic：`0xAAAAAAAA`。
6. 保持 App invalid 值：`0x55`。
7. 保持 PBL 写 App valid 值：`0xAA`。
8. 保持 BM 对 App 的判定：`Application_Valid_Flag != 0x55`。
9. 保持所有启动目标都必须经过 `SecBoot_Check_Process` 等价安全检查。
10. 保持 PBL 擦写前先 invalid App，校验通过后再 valid App。
11. 保持 Flash 写入页大小 `0x100`，最后一页补 `0x00`。
12. 保持 Flash 擦除最大块 `0x10000`。
13. 保持 TransferData 异步写入和 TransferExit 异步收尾机制。
14. 保持 CRC32 + Hash + 签名三层校验后才允许恢复 App valid。
15. 保持 valid flag 写入后的 NvM dirty/status 设置和 WriteAll 持久化。

