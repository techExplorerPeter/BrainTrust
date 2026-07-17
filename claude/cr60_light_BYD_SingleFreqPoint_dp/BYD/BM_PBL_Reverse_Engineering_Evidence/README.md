# BM/PBL Reverse Engineering Evidence

本目录保存 `D_CR60_Light_BM.elf` 和 `D_CR60_Light_PBL.elf` 的静态逆向证据，用于支撑：

- `Bootloader_BM_PBL_Detailed_Design_and_Technical_Requirements.md`
- 后续 BM/PBL 单项流程分析
- 供应商实现评审和二进制差分测试

## 证据基线

| 文件 | SHA-256 |
| --- | --- |
| `D_CR60_Light_BM.elf` | `CB02B2FCD702BE6A2F6999F56202E0B58EC15BC2689EF3AE3FE497054624E5C3` |
| `D_CR60_Light_PBL.elf` | `BB8FDA704106300380FC4916807B089E21AFD1CFF97A817629F745B3B69DE300` |

完整文件哈希见 `SHA256SUMS.txt`。

## 生成工具

- TI LLVM `tiarmobjdump` 15.0.7
- GNU `readelf` 2.32
- 生成日期：2026-07-16

## 文件说明

| 文件模式 | 内容 | 建议用途 |
| --- | --- | --- |
| `*.key_functions.txt` | 已筛选的启动、下载、擦写、校验和 NvM 关键函数 | 分析具体流程时优先查看 |
| `*.disassembly.txt` | ELF `.text` 等可执行段的全量反汇编 | 追踪完整调用和遗漏函数 |
| `*.sections_symbols.txt` | Section header 和完整符号表 | 查找函数、全局变量、段地址和大小 |
| `*.initialized_data.txt` | `.rodata/.cinit/.data` 十六进制内容 | 核对 CAN ID、payload、地址表和配置常量 |
| `*.elf_metadata.txt` | ELF header、program/section header、符号和 ARM attributes | 核对入口、ABI、CPU 架构和装载布局 |
| `*.dwarf_info.txt` | DWARF 类型、变量、函数和结构体信息 | 还原数据结构字段、大小和源模块名称 |
| `SHA256SUMS.txt` | 两个 ELF 及本目录证据文件的 SHA-256 | 检查证据是否被修改 |

`../BM/` 中的 24 张会议截图是独立的 `[S]` 辅助证据，未被混入 ELF `[C]` 结论。截图与当前 ELF 的逐项一致性见主文档 3.11 节。

## 引用规则

1. 设计文档中的 `[C]` 结论应能在本目录的反汇编、DWARF、符号表或初始化数据中找到直接证据。
2. `[I]` 是基于证据的解释，不能只凭函数名认定为完整协议定义。
3. `[TBC]` 不能由当前 ELF 唯一确定，需要 ODX/PDX、升级包、HSM 配置、Flash 数据手册或 HIL 测试。
4. 行号会随工具版本或重新生成发生变化，正式追溯应同时记录函数名、指令地址和 ELF SHA-256。
5. 本目录是静态证据，不替代目标板上的总线抓包、Flash/NvM 读回、掉电注入和 HSM 故障测试。

## 关键流程入口

BM 关键流程位于 `D_CR60_Light_BM.key_functions.txt`：

- `BootM_Init`
- `BootM_BootTargetSoftware`
- `Boot_Logic`
- `NvM_Integration_ReadAll`
- `CanIf_RxIndication`
- `SecBoot_Check_Process`
- `BootM_RelocateVectortable`
- `ImageM_LoadCpu`

PBL 关键流程位于 `D_CR60_Light_PBL.key_functions.txt`：

- `DcmAppl_Dcm_ProcessRequestDownload`
- `ImageM_PortOpen`
- `ImageM_GetRequestDownloadCondition`
- `ImageM_CheckWritePermission`
- `ImageM_PortErase`
- `FlashPort_EraseDo`
- `FlashPort_WriteDo`
- `FlashPort_WriteExit`
- `ImageM_VerifyDownloadLogBlock`
- `VerifyHashData`
- `verifySecFlashSignature`
- `ImageM_ImageStatus_WriteApplicationValidFlag`
- `NvM_Integration_WriteAll`
- `WriteFunc_0xFC01`

部分后续补查函数未被最初的 `*.key_functions.txt` 摘录完整收录，应在全量文件中按函数名或地址检索：

- BM lifecycle：在 `D_CR60_Light_BM.disassembly.txt`、`D_CR60_Light_BM.sections_symbols.txt` 检索 `rbSec_Basic_init`、`rbSecBM_CheckLCValid`、`rbSecBM_IsLifeCycleEnforced`、`rbSecFls_Read_MagicNum`
- PBL Fee bank：在 `D_CR60_Light_PBL.initialized_data.txt` 检索 `1024bf10`，并在全量反汇编检索 `Fee_Prv_ConfigGetPhysStartAddress` / `Fee_Prv_ConfigGetPhysEndAddress`
- PBL FC00：在 `D_CR60_Light_PBL.disassembly.txt` 检索 `102414a4`
- PBL 安全地址表：在 DWARF/符号文件检索 `SecAddrInfoFri`、`SecAddrInfoSec`、`SecAddrInfoThi`
