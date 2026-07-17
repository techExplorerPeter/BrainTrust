# AUTOSAR 东软会议发言提纲 - Bootloader 修正版

会议日期：2026-07-06  
用途：在原会议提纲基础上增加 Bootloader 高优先级议题。

## 开场补充

我方补充一点：Bootloader 不能后置。现有 BYD 量产工程已经有 `tools\container_input` 发布包结构，包含 BootManager、PlatformBoot、CustBoot、ProductionApp、HSM、威孚数据、客户数据和标定数据。因此本项目阶段 0 就需要把 Bootloader/刷写/发布包范围定下来。

## 会上需要新增确认

| 问题 | 东软答复 | Owner | 截止时间 |
|---|---|---|---|
| Bootloader 是否纳入东软本次范围？ |  | 东软 |  |
| BootManager/PFBoot/CustBoot 由谁提供？ |  | 双方 |  |
| 是否支持 CAN/CANFD UDS 刷写？ |  | 东软 |  |
| 是否支持 APP 跳 Bootloader、Bootloader 跳 APP？ |  | 东软 |  |
| DCM/EcuM/BswM 跳转 Bootloader 如何配置？ |  | 东软 |  |
| APP 镜像格式和地址如何定义？ |  | 双方 |  |
| HSM/安全访问/签名是否纳入？ |  | 双方 |  |
| 发布包是否包含 Boot、APP、HSM、WFDA/CUDA/CLDA？ |  | 双方 |  |
| 最小刷写演示第几周完成？ |  | 东软 |  |

## 修正后的阶段计划重点

| 阶段 | Bootloader 目标 | 验收 |
|---|---|---|
| 阶段 0 | 冻结 Bootloader 范围、提供方、刷写通道、镜像格式 | Boot 支持方案 |
| 阶段 1 | 完成 DCM/EcuM/BswM 跳转路径设计或 stub | 跳转路径评审 |
| 阶段 2 | 完成最小刷写或离线烧录闭环 | 刷写后 APP 可运行 |
| 阶段 3 | 冻结 Boot 接口、镜像格式、Memory map、发布包 | Boot 接口冻结表 |
| 阶段 4 | 完整量产刷写和发布包验收 | 刷写测试报告 + 发布包 |

## 更新后的 MVP 验收口径

MVP 不只看 AUTOSAR 能不能起来，还要看 Bootloader 路径是否可继续推进：

1. OS/BSW/RTE 能启动。
2. CAN、DCM、DEM、NvM、WdgM 最小闭环跑通。
3. `MmWaveCtrl/DPM/TriggerWave` 等价任务可运行。
4. mailbox/EDMA 空链路可验证。
5. DCM/EcuM/BswM 跳转 Bootloader 路径完成配置或 stub。
6. APP 镜像格式、链接地址、发布包结构有初版。
7. 阶段 2 明确完成最小刷写演示。

