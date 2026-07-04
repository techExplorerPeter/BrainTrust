# CR60 Light BYD PBL 详细设计文档

本文基于 `D_CR60_Light_PBL.elf` 的静态反汇编结果整理。PBL 指 Platform Bootloader，主要负责 OTA / UDS 刷写流程，包括下载请求处理、Flash 擦写、完整性校验、签名校验和 App valid flag 更新。

分析对象：

| 项目 | 内容 |
| --- | --- |
| ELF | `D_CR60_Light_PBL.elf` |
| 架构 | ARM32 little-endian |
| ELF 入口 | `0x20000` |
| 分析时间 | 2026-07-03 |

地址说明：ELF 符号表中的 Thumb 函数地址最低位会带 `1`，例如 `DcmAppl_Dcm_WriteMemory` 显示为 `0x1023e315`。本文函数地址统一写为去掉 Thumb bit 后的实际指令起始地址，例如 `0x1023e314`。

## 1. 模块定位

PBL 是 OTA 刷写执行模块。它通过 DCM / CanTp 接收 UDS 下载数据，通过 ImageM / FlashPort 驱动 Flash 擦写，并在写入完成后执行完整性、Hash 和签名校验。

PBL 的关键职责：

1. 响应 UDS 下载相关服务。
2. 按请求擦除目标 Flash 区域。
3. 接收 TransferData 并写入目标分区。
4. 在 TransferExit 后补齐最后不足一页的数据。
5. 对下载结果做 CRC / Hash / 签名校验。
6. 校验通过后设置 App valid flag。
7. OTA 异常或中途断电时，通过 valid flag 阻止 BM 启动不完整 App。

## 2. 任务调度设计

PBL 通过周期任务和后台任务驱动 OTA。

| 任务 | 函数 | 主要职责 |
| --- | --- | --- |
| 1ms | `Os_Entry_OsTask_FBL_1ms` | `Dcm_MainFunction`, `CanTp_MainFunction`, CAN read/write, security delay monitor |
| 10ms | `Os_Entry_OsTask_FBL_10ms` | `BootM_MainFunction`, `CanSM`, `ComM`, `EcuM`, `NvM`, `rbSecFls_MainFunction` |
| BgTask | `Os_Entry_OsTask_FBL_BgTask` | `ImageM_MainFunction` |

`ImageM_MainFunction` 内部执行：

```text
ImageM_VerifyMainFunction
ImageM_FlashPort_Mainfunction
ImageM_CompleteCompatible_Mainfunction
ImageM_PortWriteExit_Mainfunction
```

设计含义：

1. UDS / CAN 传输在 1ms 周期任务中推进。
2. NvM、安全 Flash 和 boot 状态管理在 10ms 周期任务中推进。
3. 实际 Flash 写入、写入收尾和校验由 ImageM 后台任务异步推进。

## 3. OTA 总体流程

PBL 的 OTA 流程不是完整接收升级包后再统一写 Flash，而是边接收 TransferData，边通过 FlashPort 写入。

总体流程：

```text
进入 PBL
  -> BootM_MainFunction 清除重编程请求
  -> UDS 会话 / 安全访问
  -> RoutineControl FF00 擦除目标区域
  -> RequestDownload 建立下载窗口
  -> TransferData 分包接收
  -> DcmAppl_Dcm_WriteMemory
  -> ImageM_PortWrite
  -> FlashPort_Write
  -> FlashPort_WriteDo 后台写 Flash
  -> RequestTransferExit
  -> FlashPort_WriteExit 补齐最后一页
  -> ImageM_VerifyDownloadLogBlock_Start
  -> ImageM_VerifyMainFunction
  -> CRC / Hash / Signature 校验
  -> 校验通过后写 Application_Valid_Flag = 0xAA
```

关键函数：

| 功能 | 函数 | 地址 |
| --- | --- | --- |
| RequestDownload 应用处理 | `DcmAppl_Dcm_ProcessRequestDownload` | `0x10240720` |
| TransferData 写内存 | `DcmAppl_Dcm_WriteMemory` | `0x1023e314` |
| TransferExit 处理 | `DcmAppl_Dcm_ProcessRequestTransferExit` | `0x1024178c` |
| RoutineControl FF00 擦除 | `SWDL_StartEraseMemory_0xFF00` | `0x1024008c` |
| Flash 写入排队 | `FlashPort_Write` | `0x10244ee8` |
| Flash 写入后台执行 | `FlashPort_WriteDo` | `0x10237824` |
| Flash 擦除后台执行 | `FlashPort_EraseDo` | `0x1023c29c` |
| 写入收尾 | `FlashPort_WriteExit` | `0x10240358` |

## 4. 下载与写入策略

反汇编结论：PBL 是边接收边写。

`TransferData` 到达后会进入：

```text
DcmAppl_Dcm_WriteMemory
  -> ImageM_PortWrite
  -> FlashPort_Write
  -> FlashPort_WriteDo
```

因此升级包数据不会等完整包全部收完并校验通过后才写 Flash。完整性和签名校验发生在写入完成之后。

### 4.1 写入粒度

反汇编确认的 Flash 操作粒度：

| 项目 | 粒度 |
| --- | --- |
| 写入页缓冲 | `0x100` 字节 |
| 擦除最大分块 | `0x10000` 字节 |
| 最后一页补齐 | 不足 `0x100` 字节时补 `0x00` |

`FlashPort_WriteExit()` 负责处理最后不足一页的数据。反汇编中它调用 `rba_BswSrv_MemSet8`，而该函数实际向目标缓冲区写入 `0x00`，因此空余字节是补 `0x00` 后写入 Flash。

## 5. 擦除策略与 App Invalid 保护

PBL 在实际擦除目标 App 区域前，会先将 App valid flag 置为 invalid。

关键行为位于 `FlashPort_EraseDo`：

```text
如果当前 App 有效：
  ImageM_ImageStatus_WriteApplicationValidFlag(0)
  -> Application_Valid_Flag = 0x55

然后执行擦除 / 写入
```

设计含义：

1. 一旦 OTA 进入实际擦写阶段，旧 App 会先被标记为无效。
2. 如果后续写入或校验失败，BM 下次上电不会启动该 App。
3. 这是一种防止半写入镜像被启动的保护策略。

## 6. 完整性与签名校验设计

写 Flash 完成之后，PBL 进入校验阶段。

关键调用链：

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
| 下载 log / Hash / 签名主校验 | `ImageM_VerifyDownloadLogBlock` | `0x1022eee8` |
| Hash 校验 | `VerifyHashData` | `0x10235ae0` |
| 签名校验 | `verifySecFlashSignature` | `0x102368c0` |
| 写 App valid | `ImageM_ImageStatus_WriteApplicationValidFlag` | `0x102446a4` |

校验通过后才会调用：

```text
ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

也就是将 `Application_Valid_Flag` 写为 `0xAA`。

## 7. Application Valid Flag 设计

PBL 中 App 有效标志如下：

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

`ImageM_ImageStatus_WriteApplicationValidFlag()` 内部会读取全局字节 `0x10228e00`，只有该值等于 `3` 时才真正写 `Application_Valid_Flag`。该字节可理解为当前镜像索引 / 镜像上下文选择。结合升级包分区命名：

```text
04_CustApp_1M/mss_dss_rss_h_padding.appimage
```

可推断 CustApp 对应的 image index 很可能是 3。这里需要区分：

1. `0x10228e00 == 3` 才写 App valid 是反汇编直接确认。
2. CustApp 对应当前镜像索引 3 是根据分区顺序和命名推断。

## 8. 断电策略设计

PBL 的断电保护核心是 valid flag 先失效、写完并校验通过后再恢复有效。

### 8.1 尚未进入擦除 / 写入阶段断电

如果 OTA 只完成了会话切换、下载准备或部分前置流程，还未执行实际擦除：

```text
旧 App 可能仍完整
Application_Valid_Flag 可能仍为 0xAA
下次上电 BM 仍可能启动旧 App
```

### 8.2 已进入擦除 / 写入阶段断电

如果已经进入 `FlashPort_EraseDo`，PBL 会先执行：

```text
ImageM_ImageStatus_WriteApplicationValidFlag(0)
```

此时断电结果：

```text
Application_Valid_Flag = 0x55
CustApp 区域可能部分擦除 / 部分写入
本次 OTA 失败
旧 CustApp 通常不能继续启动
下次上电 BM 不会启动 App
```

### 8.3 写完但未校验通过前断电

即使 TransferData 已全部接收，Flash 也已经写完，只要尚未完成：

```text
ImageM_VerifyDownloadLogBlock
VerifyHashData
verifySecFlashSignature
ImageM_ImageStatus_WriteApplicationValidFlag(1)
```

那么 `Application_Valid_Flag` 仍不会恢复为 `0xAA`。

下次上电时：

```text
BM 读取到 App invalid
BM 跳过 App 0x90000
BM 优先尝试 FBL 0x50000
FBL 无效时尝试 PBL 0x20000
```

### 8.4 校验通过并写 valid 后断电

如果 PBL 已经完成 Hash / 签名校验，并成功写入：

```text
Application_Valid_Flag = 0xAA
```

那么下次上电时 BM 会认为 App 有效，普通启动路径会优先启动 App `0x90000`。

## 9. 只升级 CustApp 时的中断电行为

只升级 CustApp 时，关键取决于断电发生在哪个阶段。

| 断电时机 | App flag | CustApp 内容 | 下次 BM 行为 |
| --- | --- | --- | --- |
| 擦除前 | 可能仍为 `0xAA` | 旧 App 可能完整 | 可能继续启动 App |
| 擦除 / 写入中 | `0x55` | 部分擦除 / 部分写入 | 跳过 App，优先启动 FBL |
| 写完但未校验通过 | `0x55` | 新数据可能完整但未确认 | 跳过 App，优先启动 FBL |
| 校验通过并置 valid 后 | `0xAA` | 新 App 有效 | 启动 App |

因此，PBL 的设计不是双备份无感切换，也不是完整包校验后才覆盖旧 App。它是在擦写前先置 invalid，然后边接收边写，最后校验通过再置 valid。

## 10. 与 BM 的接口关系

PBL 与 BM 通过持久化状态衔接：

| 状态 | PBL 行为 | BM 行为 |
| --- | --- | --- |
| `Application_Valid_Flag = 0xAA` | 校验通过后写入 | 普通路径下允许启动 App |
| `Application_Valid_Flag = 0x55` | 擦除前 / 失败时保持 invalid | 跳过 App |
| `Reprogramming_Request_Flag` | PBL 进入后清除 | BM 上电时决定是否强制进 FBL/PBL |

PBL 中的 `BootM_MainFunction` 会调用：

```text
BootM_ClearReprogrammingRequestFlag()
```

因此 PBL 启动并进入 OTA 后，如果升级中途断电，下次常见路径是 BM 根据 valid flag 正常选择，而不是一直靠 reprogramming request 强制回 PBL。

另外，BM 上电阶段存在安全帧入口。若 BM 在进入 `Boot_Logic()` 前收到扩展 CAN ID `0x190C8532`，且 payload 为：

```text
02 10 60 46 4F 52 43 45 4A 55 4D 50 A5 B6 C7 D8
```

则 BM 会设置 `StayInBootFlag = 2`，优先尝试启动 PBL `0x20000`。因此在 CustApp 升级失败、App invalid 的场景下，可以通过该上电安全帧让 BM 优先进入 PBL，而不是无安全帧时默认优先进入 FBL。

对应地，payload：

```text
02 10 82 46 4F 52 43 45 4A 55 4D 50 A5 B6 C7 D8
```

会设置 `StayInBootFlag = 1`，优先尝试 FBL `0x50000`。

CustBoot / FBL OTA 进入 FBL 后使用的 UDS CANFD ID 来自 xFlash FBL 包的 `project_config.txt`：

| 雷达位置 | Request CAN ID | Response CAN ID | Functional CAN ID | SeedKey DLL |
| --- | --- | --- | --- | --- |
| FL | `0x760` | `0x768` | `0x7DF` | `BYDCR_FL_SeednKey.dll` |
| FR | `0x761` | `0x769` | `0x7DF` | `BYDCR_FR_SeednKey.dll` |
| RL | `0x7D4` | `0x7DC` | `0x7DF` | `BYDCR_RL_SeednKey.dll` |
| RR | `0x7C2` | `0x7CA` | `0x7DF` | `BYDCR_RR_SeednKey.dll` |

这组 ID 是 CustBoot / FBL OTA 通信 ID，不是 PBL 的 OTA 诊断 ID，也不是 BM 上电安全帧 ID。

## 11. 设计结论

PBL 的 OTA 策略可以概括为：

1. OTA 数据通过 UDS / CanTp 分包进入 PBL。
2. PBL 不是完整接收升级包并校验后才写 Flash，而是边接收边写。
3. 进入实际擦写前，PBL 会先将 App valid flag 清为 `0x55`。
4. TransferData 写入完成后，PBL 再执行 CRC / Hash / 签名校验。
5. 只有校验通过后，PBL 才将 App valid flag 写回 `0xAA`。
6. 只升级 CustApp 时，如果擦写阶段中途断电，本次 OTA 失败，BM 下次上电会跳过 App。
7. 断电后由 BM 按 App、FBL、PBL 的顺序重新仲裁，其中 App invalid 且无安全帧干预时优先进入 FBL `0x50000`，FBL 不可用才进入 PBL `0x20000`。
8. 如果 BM 上电安全帧指定 PBL，则 BM 会优先尝试 PBL `0x20000`。
9. CustBoot / FBL OTA 的 CANFD ID 需要按雷达安装位置选择：FL `0x760/0x768`，FR `0x761/0x769`，RL `0x7D4/0x7DC`，RR `0x7C2/0x7CA`。

实现 Agent 注意事项：

1. `FlashPort_WriteExit()` 对最后不足 `0x100` 字节的页补 `0x00`，不是补 `0xFF`。
2. 写 `Application_Valid_Flag` 前要检查当前镜像索引 / 上下文字节是否为 `3`；反汇编中该字节地址为 `0x10228e00`。
3. 擦除阶段先置 `Application_Valid_Flag = 0x55`，校验通过后再置 `0xAA`，这个顺序是断电保护的核心。
4. OTA 数据路径是 TransferData 边收边写，不能实现成完整包缓存校验后才写 Flash。
5. 如果实现恢复入口，需要同时考虑 BM 的 `0x190C8532` 上电安全帧对 FBL/PBL 选择的影响。
6. 不要混用 BM 安全帧 ID、PBL OTA 诊断 ID 和 CustBoot / FBL OTA 诊断 ID。
