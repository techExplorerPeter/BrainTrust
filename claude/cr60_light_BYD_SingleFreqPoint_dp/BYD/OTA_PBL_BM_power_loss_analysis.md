# CR60 Light BYD OTA / Boot Recovery Analysis

本文基于当前目录下两个 ELF 的静态反汇编结果整理：

- `D_CR60_Light_PBL.elf`: Platform Bootloader, 用于 OTA / UDS 刷写
- `D_CR60_Light_BM.elf`: Boot Manager, 上电后负责选择并启动 PBL / FBL / App

分析时间：2026-07-03

地址说明：两个 ELF 的符号表中 Thumb 函数地址最低位会带 `1`，例如 `Boot_Logic` 在符号表中显示为 `0x10204961`。本文中的函数地址统一写为去掉 Thumb bit 后的实际指令起始地址，例如 `0x10204960`。

## 1. PBL OTA 主流程

`D_CR60_Light_PBL.elf` 是 ARM32 little-endian ELF，入口地址为 `0x20000`。该 ELF 保留了符号表和 DWARF 调试信息，因此可以直接定位 OTA 相关函数。

### 1.1 任务调度

PBL 的关键周期任务：

| 任务 | 函数 | 作用 |
| --- | --- | --- |
| 1ms | `Os_Entry_OsTask_FBL_1ms` | `Dcm_MainFunction`, `CanTp_MainFunction`, CAN read/write, security delay monitor |
| 10ms | `Os_Entry_OsTask_FBL_10ms` | `BootM_MainFunction`, `CanSM`, `ComM`, `EcuM`, `NvM`, `rbSecFls_MainFunction` |
| BgTask | `Os_Entry_OsTask_FBL_BgTask` | `ImageM_MainFunction` |

`ImageM_MainFunction` 内部依次执行：

```text
ImageM_VerifyMainFunction
ImageM_FlashPort_Mainfunction
ImageM_CompleteCompatible_Mainfunction
ImageM_PortWriteExit_Mainfunction
```

说明 OTA 的接收由 DCM / CanTp 处理，实际 flash 写入和校验由 ImageM 后台异步执行。

## 2. OTA 是边接收边写，不是完整收包后再写

从反汇编调用链看，PBL 不是先把完整升级包收完再写 flash，而是：

```text
RequestDownload
  -> 建立下载地址和长度窗口
TransferData
  -> 每包数据进入 DcmAppl_Dcm_WriteMemory
  -> ImageM_PortWrite
  -> FlashPort_Write
  -> 后台 FlashPort_WriteDo 写 flash
RequestTransferExit
  -> FlashPort_WriteExit 补齐最后不足一页的数据
  -> 后续再做完整性 / Hash / 签名校验
```

关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | --- |
| RequestDownload 应用处理 | `DcmAppl_Dcm_ProcessRequestDownload` | `0x10240720` |
| TransferData 写内存 | `DcmAppl_Dcm_WriteMemory` | `0x1023e314` |
| TransferExit 处理 | `DcmAppl_Dcm_ProcessRequestTransferExit` | `0x1024178c` |
| RoutineControl FF00 擦除 | `SWDL_StartEraseMemory_0xFF00` | `0x1024008c` |
| flash 写入排队 | `FlashPort_Write` | `0x10244ee8` |
| flash 写入后台执行 | `FlashPort_WriteDo` | `0x10237824` |
| flash 擦除后台执行 | `FlashPort_EraseDo` | `0x1023c29c` |
| 写入收尾 | `FlashPort_WriteExit` | `0x10240358` |

### 2.1 写入粒度

反汇编显示：

- 写入按 `0x100` 字节页缓冲 / 写入。
- 擦除按最大 `0x10000` 字节分块执行。
- 最后一页不足 `0x100` 字节时，`FlashPort_WriteExit` 会调用 `rba_BswSrv_MemSet8` 将剩余字节补 `0x00` 后写入。

## 3. PBL 完整性与签名校验

写 flash 完成后，PBL 才做校验。关键调用链：

```text
ImageM_VerifyDownloadLogBlock_Start
  -> ImageM_VerifyMainFunction
  -> ImageM_VerifyDownloadLogBlock
  -> Crc_CalculateCRC32
  -> SecFlash_SecCtrl
  -> VerifyHashData
  -> verifySecFlashSignature
  -> ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | --- |
| 启动下载 log 校验 | `ImageM_VerifyDownloadLogBlock_Start` | `0x102468a0` |
| 后台校验入口 | `ImageM_VerifyMainFunction` | `0x102439b8` |
| 下载 log / hash / 签名主校验 | `ImageM_VerifyDownloadLogBlock` | `0x1022eee8` |
| Hash 校验 | `VerifyHashData` | `0x10235ae0` |
| 签名校验 | `verifySecFlashSignature` | `0x102368c0` |
| App valid 标志写入 | `ImageM_ImageStatus_WriteApplicationValidFlag` | `0x102446a4` |

## 4. PBL 中 Application Valid 标志

PBL 中的 App 有效标志：

| 符号 | 地址 |
| --- | --- |
| `Application_Valid_Flag` | `0x10228e28` |
| `Application_Valid_Flag_RomBlock` | `0x1024b321` |

编码方式：

```text
0xAA = App 有效
0x55 = App 无效
```

相关函数：

| 函数 | 地址 | 逻辑 |
| --- | --- | --- |
| `ImageM_ImageStatus_ReadApplicationValidFlag` | `0x10248000` | 判断 `Application_Valid_Flag == 0xAA` |
| `ImageM_ImageStatus_WriteApplicationValidFlag` | `0x102446a4` | 参数 1 写 `0xAA`，参数 0 写 `0x55` |
| `ImageM_CheckAppValid` | `0x102476e0` | 检查 App valid |

注意：`ImageM_ImageStatus_WriteApplicationValidFlag()` 会读取全局字节 `0x10228e00`，只有该值等于 `3` 时才真正写 `Application_Valid_Flag`。该字节可理解为当前镜像索引 / 镜像上下文选择。结合升级包分区顺序：

```text
04_CustApp_1M/mss_dss_rss_h_padding.appimage
```

可推断 CustApp 对应的 image index 很可能就是 3。因此只升级 CustApp 时会影响全局 `Application_Valid_Flag`。

## 5. PBL 升级过程中断电会怎样

### 5.1 还没有开始擦除 / 写入时断电

如果还未进入实际擦除流程，`Application_Valid_Flag` 可能还没有被清除。

可能结果：

```text
旧 App 仍完整
Application_Valid_Flag 仍为 0xAA
下次上电 BM 仍可能启动 App
```

### 5.2 已经进入擦除 / 写入阶段后断电

在 `FlashPort_EraseDo` 中，擦除前会检查当前 App 是否有效。如果有效，会先调用：

```text
ImageM_ImageStatus_WriteApplicationValidFlag(0)
```

也就是先把 `Application_Valid_Flag` 写成 `0x55`，然后才开始擦除 / 写 flash。

如果此时断电：

```text
Application_Valid_Flag = 0x55
CustApp 区域可能部分擦除 / 部分写入
本次 OTA 失败
旧 CustApp 通常不能继续启动
```

### 5.3 写完 flash 但还没有完成校验 / 置 valid 时断电

即使 CustApp 数据已经写完，只要还没有完成：

```text
ImageM_VerifyDownloadLogBlock
VerifyHashData
verifySecFlashSignature
ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

那么 `Application_Valid_Flag` 仍不是 `0xAA`。下次上电仍会被 BM 认为 App 无效。

## 6. BM 启动选择逻辑

`D_CR60_Light_BM.elf` 也是 ARM32 little-endian ELF，入口地址为 `0x20000`。

BM 关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | --- |
| main | `main` | `0x102124e6` |
| 初始化 | `BootM_Init` | `0x1020a8ac` |
| 启动目标软件 | `BootM_BootTargetSoftware` | `0x1020941c` |
| 启动选择主逻辑 | `Boot_Logic` | `0x10204960` |
| valid 判断 | `Is_FLAG_Valid` | `0x1020d94c` |
| 加载/启动多核镜像 | `ImageM_LoadCpu` | `0x10208670` |
| 向量表重定位 | `BootM_RelocateVectortable` | `0x10211808` |

`main` 调用顺序：

```text
BootM_Init()
BootM_BootTargetSoftware()
while(1)
```

`BootM_Init()` 会调用：

```text
NvM_Integration_ReadAll()
rbSecFls_Init_MainFunction_BM()
```

因此 BM 上电后会先通过 NvM 读取 PBL / FBL / App 的 valid 状态。

## 7. BM 中的 valid flag

BM 中相关符号：

| 符号 | 地址 | 含义 |
| --- | --- | --- |
| `Fbl_Valid_Flag` | `0x10216f68` | FBL 有效标志 |
| `Pbl_Valid_Flag` | `0x10216f6c` | PBL 有效标志 |
| `Application_Valid_Flag` | `0x10216f9f` | App 有效标志 |
| `Reprogramming_Request_Flag` | `0x10216f74` | 重编程请求标志 |
| `StayInBootFlag` | `0x10216ab8` | BM 当前选择/停留标志 |
| `APP_IMAGE_Addr` | `0x10216abc` | App 镜像地址 |
| `CurrentBoot_Address` | `0x10216ac0` | 当前启动地址 |

`Is_FLAG_Valid()` 判断规则：

```text
index 0: App
  Application_Valid_Flag != 0x55 认为有效

index 1: FBL
  Fbl_Valid_Flag == 0xAAAAAAAA 认为有效

index 2: PBL
  Pbl_Valid_Flag == 0xAAAAAAAA 认为有效
```

## 8. BM 启动顺序和跳转地址

BM 的普通启动顺序为：

```text
index 0: App  -> 0x00090000
index 1: FBL  -> 0x00050000
index 2: PBL  -> 0x00020000
```

这些地址是 BM 选择的镜像起始地址 / flash appimage 地址。加载成功后：

- FBL / PBL 类型目标会重定位向量表到 `0x0`，然后 `blx 0`。
- App 类型目标走 `bootImageInfo` 中的 entry point。

相关反汇编证据：

```text
Boot_Logic:
  0x10204988: r0 = 0x20000
  0x1020498e: r0 = 0x50000
  0x102049fe: r0 = 0x90000

BootM_BootTargetSoftware:
  ImageM_LoadCpu(...)
  if selected index is 1 or 2:
      BootM_RelocateVectortable(0x1021e000, 0x0)
      blx 0
  else:
      blx bootImageInfo.entryPoint
```

## 9. Reprogramming_Request_Flag 的特殊路径

`Boot_Logic` 中会先检查 `Reprogramming_Request_Flag`。

相关常量：

```text
0x10021002 -> 优先尝试 FBL, 地址 0x50000
0x10061006 -> 优先尝试 PBL, 地址 0x20000
0x10861086 -> 优先尝试 PBL, 地址 0x20000
0x10821082 -> 优先尝试 PBL, 地址 0x20000
```

这些特殊路径不是无条件跳转。BM 会先检查对应 FBL / PBL 的 valid flag，随后还会调用 `SecBoot_Check_Process`。如果检查失败，会回退到后续普通启动选择逻辑。

但是 PBL 中 `BootM_MainFunction` 会在进入后清除 reprogramming request：

```text
BootM_ClearReprogrammingRequestFlag()
```

所以如果 PBL 已经启动过并进入 OTA 流程，之后断电重启时，常见路径不再是靠 reprogramming request 强制进 PBL，而是走普通 valid 启动顺序。

## 10. PBL 中 CustApp 升级中断电后，BM 会跳哪里

根据 PBL 和 BM 的组合逻辑，典型场景如下：

```text
CustApp OTA 开始
  -> PBL 擦除前清 Application_Valid_Flag = 0x55
  -> 边接收 TransferData 边写 CustApp flash
  -> 中途断电

下次上电
  -> BM BootM_Init 调 NvM_Integration_ReadAll()
  -> BM 读取 Application_Valid_Flag / Fbl_Valid_Flag / Pbl_Valid_Flag
  -> App flag == 0x55，App 无效
  -> BM 跳过 App 0x90000
  -> 检查 FBL valid
  -> 如果 FBL valid，启动 FBL 0x50000
  -> 如果 FBL invalid，再检查 PBL valid，启动 PBL 0x20000
  -> 如果 FBL/PBL 都 invalid，BM 无可启动目标，停在 BM / 返回错误路径
```

因此结论是：

```text
只升级 CustApp 时，如果已经进入擦写阶段后断电：
  本次 OTA 失败；
  App 被 BM 判定无效；
  BM 优先跳 FBL 0x50000；
  FBL 无效时才跳 PBL 0x20000；
  两者都无效时才停留在 BM。
```

## 11. 需要注意的边界

1. `0x20000 / 0x50000 / 0x90000` 是 BM 选择的镜像地址，不应简单等同于最终 CPU PC。
2. FBL / PBL 加载后，BM 会将向量表搬到 `0x0` 并 `blx 0`。
3. App 类型目标由 `bootImageInfo` 的 entry point 启动。
4. 本文中 CustApp 对应当前镜像索引 `3` 是根据反汇编分支和升级包分区顺序推断；`ImageM_ImageStatus_WriteApplicationValidFlag()` 中全局字节 `0x10228e00 == 3` 才写 App valid 是反汇编直接确认。
5. BM 侧 App valid 判断必须按实际 ELF 保持为 `Application_Valid_Flag != 0x55`，不要改写成 `== 0xAA`。
6. `FlashPort_WriteExit()` 最后一页补齐值为 `0x00`，这是根据 `rba_BswSrv_MemSet8` 反汇编确认的修正点。
