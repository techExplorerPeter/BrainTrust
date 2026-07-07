# AUTOSAR Bootloader 高优先级补充材料

会议日期：2026-07-06  
量产工程基线：`D:\Weifu\Project\CR\BYD_RL\xxx`  
目的：修正项目计划中 Bootloader 权重不足的问题，将 Bootloader/刷写/发布包作为早期并行工作包推进。

## 1. 结论

Bootloader 不能放到项目后期再讨论。对 TI 2944LC AUTOSAR 项目来说，Bootloader 至少要在阶段 0 明确范围，在阶段 1 完成软件路径设计，在阶段 2 完成最小刷写或跳转验证。

原因：

1. 现有 BYD 量产工程已经有完整 Boot/发布包结构，不是纯 APP 工程。
2. Bootloader 会影响 APP 链接地址、分区、镜像格式、版本信息和发布包制作。
3. Bootloader 会影响 DCM、EcuM、BswM 的跳转逻辑。
4. 早期测试需要刷写能力，否则每次集成和台架验证效率会很低。
5. HSM、安全访问、签名校验、数据区合包都和量产发布直接相关。

## 2. 现有量产工程 Boot 基线

现有工程 `coem\BYD_UKE\tools\container_input` 下已经有多段 Boot/APP/数据区输入：

| 目录 | 现有内容 | 新项目意义 |
|---|---|---|
| `01_BootManager` | `BootManager_v4.1.hex`、`BootManager_v4.1.tiimage`、`P_CR60_Light_BM.elf/.map`、ReleaseNote | Boot Manager 是发布包组成部分 |
| `02_PlatformBoot` | `PFBoot_h_V4.2.hex`、ReleaseNote | Platform Boot 需要明确提供方和适配方式 |
| `03_CustBoot` | `CustBoot_h_V4.0_BYD.hex`、`BLU`、ReleaseNote | 客户 Boot/刷写逻辑需要早期确认 |
| `04_CustApp` / `04_CustApp_1M` | APP 占位/命名文件 | APP 镜像、分区大小、链接地址要冻结 |
| `04_ProductionApp` / `04_ProductionApp_1M` | `productionApp_v2.13.hex`、`productionApp_1M_v2.13.hex` | 生产 APP 是发布包组成部分 |
| `06_Hsm` | `cycursoc_hsm_1.5.1_BYD_patched.bin/.hex` | HSM/安全相关不能后置 |
| `07_WeifuData` | `WFDA_BYD.xlsx`、`WFDA_BYD_V1dot1.hex` | 威孚数据区 |
| `08_CustData` | `CUDA_V1.3.hex`、`VKI_BYD_20260318.xlsx` | 客户数据区 |
| `09_ClibData` | `CLDA_V1.3.1.hex` | 标定/库数据区 |

工程里还有 Boot 跳转相关接口痕迹：

1. `Rte_ASW_BASE.h` 中有 `Rte_Call_RPort_BootTarget_GetBootTarget` 和 `Rte_Call_RPort_BootTarget_SelectBootTarget`。
2. `Rte_EcuM_Type.h` 中有 `ECUM_BOOT_TARGET_APP`、`ECUM_BOOT_TARGET_OEM_BOOTLOADER`、`ECUM_BOOT_TARGET_SYS_BOOTLOADER`。
3. `Rte_Dcm_Type.h` / `SchM_BswM_Type.h` 中有 `RTE_MODE_DcmEcuReset_JUMPTOBOOTLOADER`。
4. `OsTask_BSW_SwcRequest.c` 中有 `BswM_Cfg_ImdtBswNotification_BswM_MRP_DCM_DiagnosticSessionControl_JUMPTOBOOTLOADER`。

这些说明：现有量产工程不是“最后手工烧 APP”的模式，而是有 Bootloader、HSM、APP、数据区和发布包概念。

## 3. Bootloader 工作包建议

| 工作项 | 我方责任 | 东软责任 | 交付/验收 |
|---|---|---|---|
| Boot 范围定义 | 定义是否沿用现有 BootManager/PFBoot/CustBoot 思路 | 确认可支持范围 | Boot 范围说明 |
| 分区和链接布局 | 提供 APP 大小、数据区、HSM、外部 Flash 需求 | 配合 APP 链接、刷写地址和 BSW 配置 | Memory map / linker 评审 |
| 跳转 Bootloader | 定义诊断触发场景 | 配置 DCM/EcuM/BswM/RTE 跳转路径 | `11` 或相关服务触发跳转验证 |
| 刷写通道 | 定义 CAN/CANFD/ETH 刷写通道 | 配置 DCM/CanTp/PduR/驱动支持 | 刷写链路验证 |
| 镜像格式 | 定义 hex/tiimage/appimage/VBF 等要求 | 提供生成/转换/合包方案 | 可烧录镜像 |
| 安全访问 | 提供算法/等级/种子密钥要求 | 配置 DCM SecurityAccess | 安全访问测试 |
| HSM/签名 | 确认是否使用 HSM 和签名校验 | 提供集成方案或接口 | HSM/签名验证报告 |
| 发布包 | 定义发布包组成和版本规则 | 输出合包脚本/说明 | 可重复构建发布包 |
| 量产测试 | 定义下线刷写流程和设备 | 配合刷写脚本/日志 | 量产刷写测试报告 |

## 4. 修正后的阶段计划

### 阶段 0：Bootloader 范围和支持性确认，1-2 周

必须完成：

1. 确认 Bootloader 是否纳入东软范围。
2. 确认由谁提供 BootManager、PlatformBoot、CustBoot。
3. 确认刷写通道：CAN/CANFD/ETH。
4. 确认是否需要 HSM、安全访问、签名校验。
5. 确认 APP 镜像格式：hex、tiimage、appimage、VBF 或其他。
6. 确认 APP 分区大小：是否需要 1M 版本、2M 版本或其他。
7. 确认发布包组成：BootManager、PFBoot、CustBoot、APP、HSM、WFDA、CUDA、CLDA。

东软阶段 0 交付：

1. Bootloader 支持方案。
2. Bootloader/APP/HSM/数据区发布包映射表。
3. 刷写链路风险清单。
4. 最小刷写验证计划。

### 阶段 1：Bootloader 软件路径设计，3-4 周内并行

必须完成：

1. DCM/EcuM/BswM 跳转 Bootloader 的配置设计。
2. APP 链接地址和镜像输出格式初版。
3. Bootloader 与 APP 的版本信息、兼容关系定义。
4. 刷写服务和安全访问配置设计。
5. 发布包目录结构初版。

验收：

1. APP 可按目标地址生成镜像。
2. DCM/EcuM/BswM 跳转路径完成配置或 stub 验证。
3. Bootloader 阻塞项明确。

### 阶段 2：最小刷写链路验证，3-4 周内并行

必须完成：

1. APP 跳 Bootloader 最小验证。
2. Bootloader 跳 APP 最小验证。
3. 至少一种刷写方式跑通：离线烧录、CAN/CANFD UDS 刷写或东软约定方式。
4. 生成一个可追溯测试发布包。

验收：

1. 最小刷写流程可演示。
2. 刷写后 APP 可启动。
3. 版本 DID 可读取。
4. 失败场景和恢复策略有记录。

### 阶段 3：Bootloader 接口冻结

冻结内容：

1. Bootloader 跳转接口。
2. DCM 服务和安全等级。
3. APP 镜像格式。
4. Memory map / linker。
5. 发布包组成和命名规则。
6. HSM/签名校验边界。
7. 量产刷写流程。

### 阶段 4：量产刷写和发布包验收

必须完成：

1. 完整刷写测试报告。
2. 完整发布包。
3. 版本追溯说明。
4. 异常刷写恢复测试。
5. 量产烧录流程说明。

## 5. 今天会议必须问东软的问题

1. Bootloader 是否包含在本次报价和交付范围？
2. 东软能否提供 TI 2944LC 的 Bootloader，还是只配合 APP/BSW 跳转？
3. 是否支持现有量产工程这种 `BootManager + PlatformBoot + CustBoot + APP + HSM + Data` 的发布包结构？
4. 刷写通道支持 CAN/CANFD 还是 ETH？
5. DCM 支持哪些刷写相关 UDS 服务？
6. SecurityAccess 算法由谁提供？东软是否负责集成？
7. HSM 是否纳入？如果纳入，HSM 固件、密钥、签名由谁负责？
8. APP 镜像格式是什么？hex、tiimage、appimage、VBF 是否支持？
9. 是否支持 Bootloader 跳 APP、APP 跳 Bootloader 的闭环验证？
10. 最早第几周能完成最小刷写演示？

## 6. 更新后的会议口径

> Bootloader 对我们不是后期可选项。现有 BYD 量产工程已经有 BootManager、PlatformBoot、CustBoot、ProductionApp、HSM 和数据区发布包结构，所以 TI 2944LC 项目必须从阶段 0 就把 Bootloader/刷写/发布包纳入计划。第一版 MVP 除了 OS/BSW/RTE、CAN、DCM、DEM、NvM、WdgM 和雷达控制链路，也要至少完成 Boot 跳转路径设计或 stub 验证；阶段 2 要争取完成最小刷写链路验证。

