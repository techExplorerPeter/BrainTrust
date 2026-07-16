# AUTOSAR 存储与诊断配置矩阵

本文用于 AUTOSAR 工具配置输入和开发核对。字段分为“代码已知值”和“工具待确认值”。`TBD` 表示当前代码中未能直接确认，配置前需要由诊断规范、DTC 表、CDD/ARXML 或系统需求补齐。

## 1. 配置来源

| 模块 | 主要配置/代码来源 | 说明 |
|---|---|---|
| NvM/Fee | `coem/BYD_UKE/gen_bsw/NvM/NvM_Cfg.c`、`integration/BswM_Callout_Stub.c` | NVRAM Block、ReadAll/WriteAll、超时 DEM 上报 |
| Dcm | `coem/BYD_UKE/gen_bsw/Dcm/Dcm_Lcfg_Dsd.c`、`Dcm_Lcfg_DspUds.c` | UDS 服务、Session、Security、DID、Routine |
| Dem | `coem/BYD_UKE/gen_bsw/Dem/Dem_Cfg_EventId.h`、`Dem_Cfg_DtcId.h` | Event、DTC Class、Event-DTC 映射 |
| 业务接口 | `coem/BYD_UKE/components/diag`、`components/fm`、`mmwave/mmw_user`、`bswpf/cdd/VOL_Tem_Test` | DID/Routine 回调、故障上报 |

## 2. NvM Block 配置矩阵

工具中建议至少核对以下字段：`BlockId`、`BlockName`、`BlockLength`、`ManagementType`、`NvBlockNum`、`RamBlock`、`RomDefaultBlock`、`CRC`、`ImmediateWrite`、`WriteOnce`、`ReadAll/WriteAll Select`、`Init/SingleBlock Callback`、`Fee Block Mapping`。

当前代码已知：除 BlockID `15` 为 `NVM_BLOCK_REDUNDANT`、NV Block 数为 `2` 外，其余已抽样/生成表项显示为 `NVM_BLOCK_NATIVE`、NV Block 数为 `1`。工具配置时仍建议逐项确认。

| BlockID | BlockName | Length | MgmtType | NvBlockNum | 用途 | 工具待确认 |
|---:|---|---:|---|---:|---|---|
| 0 | NvM_MultiBlock | 1 | Native | 1 | NvM 多块管理 | CRC/ReadAll/WriteAll |
| 1 | NvM_ConfigId | 2 | Native | 1 | 配置 ID | CRC/默认值 |
| 2 | NvMBlock_LogisticData | 128 | Native | 1 | 物流/产线数据 | 默认值/写保护 |
| 3 | NVM_OS_ErrorlogOsErrorHook | 370 | Native | 1 | OS ErrorHook 日志 | 写入触发/循环策略 |
| 4 | NVM_OS_ErrorlogOsShutdown | 44 | Native | 1 | OS Shutdown 日志 | 写入触发 |
| 5 | NVM_OS_ErrorlogOsWdgReset | 6 | Native | 1 | WDG Reset 日志 | 写入触发 |
| 6 | NVM_OS_ErrorlogActiveReset | 5 | Native | 1 | Active Reset 日志 | 写入触发 |
| 7 | NVM_PMIC_DTC_ERROR | 40 | Native | 1 | PMIC DTC 错误信息 | Dem 关联 |
| 8 | CustDID_APPVersion | 6 | Native | 1 | APP 版本 DID | 写保护/默认值 |
| 9 | CustDID_DisBetFrontandRear | 2 | Native | 1 | 前后距离参数 | DID/标定绑定 |
| 10 | CustDID_DisBetLeftandRight_0x126A | 2 | Native | 1 | 左右距离参数 | DID/标定绑定 |
| 11 | CustDID_ECUHWVersionNumber | 5 | Native | 1 | ECU HW 版本 | 写保护 |
| 12 | CustDID_ECUSoftwareCode | 9 | Native | 1 | ECU 软件编码 | 写保护 |
| 13 | CustDID_FBLVersion | 9 | Native | 1 | FBL 版本 | 写保护 |
| 14 | CustDID_ProductionMode | 1 | Native | 1 | 生产模式 | DID 0xF1C2 |
| 15 | NvMBlockDescriptor_ECUConfiguration | 4 | Redundant | 2 | ECU 配置 | 冗余恢复策略/CRC |
| 16 | CustDID_TargetPosition_0x1266 | 4 | Native | 1 | 目标安装位置 | 标定/Routine 关联 |
| 17 | CustDID_VIN | 17 | Native | 1 | VIN | DID 0xF190 |
| 18 | CustDID_VariantCoding | 8 | Native | 1 | Variant Coding | DID 0x2100/0xF1A1 |
| 19 | CustDID_WheelBase | 2 | Native | 1 | 轴距 | DID/标定绑定 |
| 20 | NvM_PowerOn_Counter | 4 | Native | 1 | 上电计数 | 写入频率/磨损 |
| 21 | NvM_RadarPosition_ETHOnly | 1 | Native | 1 | 雷达位置 | DID 0xFD17 |
| 22 | Cust_SecurityAccesscounter | 1 | Native | 1 | 客户安全计数 | SecurityAccess 绑定 |
| 23 | Dia_SecurityAccesscounter | 1 | Native | 1 | 诊断安全计数 | SecurityAccess 绑定 |
| 24 | ECUM_CFG_NVM_BLOCK | 4 | Native | 1 | EcuM 配置 | `EcuM_Rb_NvMSingleBlockCallbackFunction` |
| 25 | NVM_ADAS_HMISwitch | 11 | Native | 1 | ADAS HMI 开关 | 信号定义 |
| 26 | NVM_Calibration_EffStatus | 1 | Native | 1 | 标定有效状态 | Routine 关联 |
| 27 | NVM_Calibration_OnlineStatus | 30 | Native | 1 | 在线标定状态 | Routine 关联 |
| 28 | NVM_Calibration_TriggerStatus | 30 | Native | 1 | 标定触发状态 | Routine 关联 |
| 29-48 | NVM_ID_DEM_EXTRA_INFO_0..19 | 32 each | Native | 1 | DEM 扩展信息 | ExtendedData 记录定义 |
| 49 | NVM_ID_DEM_GENERIC_NV_DATA | 16 | Native | 1 | DEM 通用持久数据 | DEM 全局配置 |
| 50-89 | NVM_ID_EVMEM_LOC_0..39 | 48 each | Native | 1 | DEM Event Memory | Primary/镜像/容量策略 |
| 90 | NVM_ID_EVT_STATUSBYTE | 218 | Native | 1 | DEM Event StatusByte | 217 events 映射 |
| 91 | NVM_NM_ForceHibernationLatestSts | 1 | Native | 1 | NM 休眠状态 | NM 需求 |
| 92 | NvMBlockDescriptor_Application_Valid_Flag | 1 | Native | 1 | APP 有效标志 | Boot/刷写 |
| 93 | NvMBlockDescriptor_Fingerprint_Data | 9 | Native | 1 | 刷写指纹 | Boot/诊断 |
| 94 | NvMBlockDescriptor_Reprogramming_Request_Flag | 4 | Native | 1 | 重编程请求 | Boot 跳转 |
| 95 | NvMBlockDescriptor_ResetReason_Type | 1 | Native | 1 | 复位原因 | Boot/EcuReset |
| 96 | NvM_BLDDetStatus | 1 | Native | 1 | Blind Detection 状态 | 故障/算法 |
| 97 | NvM_Calibration_TargetPosition | 4 | Native | 1 | 标定目标位置 | EOL/SDA |
| 98 | NvM_EDR_Data1 | 4900 | Native | 1 | EDR 数据区 1 | DID 0xFA13 |
| 99 | NvM_EDR_Data2 | 4900 | Native | 1 | EDR 数据区 2 | DID 0xFA14 |
| 100 | NvM_EDR_WRITE_FLAG | 2 | Native | 1 | EDR 写标志 | EDR 双区切换策略 |
| 101 | NvM_FaultMask_Info | 32 | Native | 1 | Fault Mask | DID 0xFD14 |
| 102 | NvM_PFDem_ErrorInfo | 512 | Native | 1 | PF DEM 错误信息 | DID/ErrorLog |
| 103 | NvM_Security_Key | 32 | Native | 1 | 安全密钥 | DID 0xFD16/0xFD18/0xFD19 |

## 3. NvM 开发与集成矩阵

| 需求项 | 当前实现 | AUTOSAR 工具配置点 | 开发动作 |
|---|---|---|---|
| 上电读取 NVM | `BswM_NvM_ReadAll()` 调用 `NvM_ReadAll()` | NvM ReadAll Select、BswM Init Action | 保持启动阶段调用顺序：NvM/Fee MainFunction 周期调度 |
| 读超时诊断 | 读超时上报 `PF_Event_NvM_Read` | DEM Event 配置、Debounce、DTC 映射 | 确认超时时间和恢复策略 |
| 关机写入 | `BswM_NvM_WriteAll()` 中 `NvM_WriteAll()` 被注释 | NvM WriteAll Select、BswM Shutdown Action | 必须确认正式写入路径，否则掉电数据可能不落盘 |
| EDR 周期保存 | `rte/OsTask_MMW.c` 20ms 调 `EDR_save_data()` | NvM Block 98/99/100 | 核对写频率，避免 Flash 磨损 |
| DID 写入持久化 | 多个 WriteFunc/BoschDID_Write 回调 | DID Write + NvM Block 绑定 | 每个可写 DID 明确是否调用 NvM_WriteBlock |

## 4. Dcm 服务配置矩阵

| SID | 服务 | 子功能 | Allowed Session | Allowed Security | Handler | 配置状态 |
|---:|---|---|---|---|---|---|
| 0x10 | DiagnosticSessionControl | 0x01/0x02/0x03/0x06/0x60 | 全局配置 | 全局配置 | `Dcm_Prv_DspDiagnosticSessionControl` | 已配置 |
| 0x11 | ECUReset | 0x01 | 全局配置 | 全局配置 | `Dcm_Prv_DspEcuReset` | 已配置 |
| 0x14 | ClearDiagnosticInformation | 无 | 全局配置 | 全局配置 | `Dcm_Prv_DspClearDiagnosticInformation` | 已配置 |
| 0x19 | ReadDTCInformation | 0x01/0x02/0x04/0x06/0x0A | 全局配置 | 全局配置 | `Dcm_Prv_DspReadDTCInformation` | 已配置 |
| 0x22 | ReadDataByIdentifier | 无 | DID 级配置 | DID 级配置 | `Dcm_Prv_DspReadDataByIdentifier` | 已配置 |
| 0x27 | SecurityAccess | 0x01/0x02/0x61/0x62/0x63/0x64 | `0x14uL` | 全局配置 | `Dcm_Prv_DspSecurityAccess` | 已配置 |
| 0x28 | CommunicationControl | 0x00/0x01/0x03 | 全局配置 | 全局配置 | `Dcm_Prv_DspCommunicationControl` | 已配置 |
| 0x2E | WriteDataByIdentifier | 无 | `0x14uL` | DID 级配置 | `Dcm_Prv_DspWriteDataByIdentifier` | 已配置 |
| 0x31 | RoutineControl | Routine 级 | `0x14uL` | Routine 级配置 | `Dcm_Prv_DspRoutineControl` | 已配置 |
| 0x3E | TesterPresent | 0x00 | 全局配置 | 全局配置 | `Dcm_Prv_DspTesterPresent` | 已配置 |
| 0x85 | ControlDTCSetting | 0x01/0x02 | 全局配置 | 全局配置 | `Dcm_Prv_DspControlDTCSetting` | 已配置 |

## 5. Session 与 Security 配置矩阵

| 类型 | 名称 | 值 | Boot 行为 | 工具配置点 |
|---|---|---:|---|---|
| Session | Default | 0x01 | No boot | P2/P2*、S3Server |
| Session | Programming | 0x02 | OEM boot | Boot 跳转、刷写前置条件 |
| Session | Extended | 0x03 | No boot | 诊断/标定访问 |
| Session | WEIFU | 0x06 | OEM boot | 私有会话访问控制 |
| Session | Bosch | 0x60 | No boot | Bosch 私有 DID/RID |
| Security | Unlocked_L1 | 0x01 | Seed 4 / Key 4 | 延时 1000、失败 3 次 |
| Security | Unlocked_L31 | 0x31 | Seed 250 / Key 2000 | 延时 1000、失败 3 次 |
| Security | Unlocked_L32 | 0x32 | Seed 250 / Key 2000 | 延时 1000、失败 3 次 |

## 6. DID 配置矩阵

权限组说明：

- `Customer Read`：Read Session `0x17`，Read Security `0xFFFFFFFF`。
- `Customer ReadWrite`：Read Session `0x7`，Read Security `0xFFFFFFFF`；Write Session `0x4`，Write Security `0x2`。
- `Customer Write`：Write Session `0xFFFFFFFF`，Write Security `0x2`。
- `Bosch Read`：Read Session `0x10`，Read Security `0xFFFFFFFF`。
- `Bosch ReadWrite`：Read Session `0x10`，Read Security `0xFFFFFFFF`；Write Session `0x10`，Write Security `0x4`。
- `Bosch Write`：Write Session `0x10`，Write Security `0x4`。

| DID | 名称 | Size | R/W | 权限组 | 回调/接口 | NvM/备注 |
|---:|---|---:|---|---|---|---|
| 0x0103 | SecurityAccessInvalidCounter | 1 | R | Customer Read | `ReadFunc_*` | Block 23/22 需确认 |
| 0x0285 | SupplierVoltage | 1 | R | Customer Read | `ReadFunc_*` | 实时电压 |
| 0x028D | EcuTemperature | 1 | R | Customer Read | `ReadFunc_*` | 实时温度 |
| 0x1011 | VehicleSpeed | 2 | R | Customer Read | `ReadFunc_*` | 车辆速度 |
| 0x2100 | VariantCoding | 8 | R/W | Customer ReadWrite | `WriteFunc_0x2100` | Block 18 |
| 0x3403 | SlowHorizontalAngle | 4 | R | Customer Read | `ReadFunc_*` | 标定角度 |
| 0x3404 | FastHorizontalAngle | 4 | R | Customer Read | `ReadFunc_*` | 标定角度 |
| 0x3441 | FastVerticalAngle | 4 | R | Customer Read | `ReadFunc_*` | 标定角度 |
| 0x3442 | SlowVerticalAngle | 4 | R | Customer Read | `ReadFunc_*` | 标定角度 |
| 0x3443 | SensorMountingSide | 1 | R | Customer Read | `ReadFunc_*` | 安装侧 |
| 0x3444 | PINDirectionANDPosition | 1 | R | Customer Read | `ReadFunc_*` | 安装方向/位置 |
| 0x3449 | Lifecycle_Read | 1 | R | Customer Read | `ReadFunc_*` | 生命周期 |
| 0x344A | LifecycleSwitch | 1 | R/W | Customer ReadWrite | `WriteFunc_0x344A` | 生命周期切换 |
| 0xF180 | FBLVersion | 9 | R | Customer Read | `ReadFunc_*` | Block 13 |
| 0xF186 | GetCurSession | 1 | R | Customer Read | `ReadFunc_0xF186` | 当前会话 |
| 0xF18C | SerialNumber | 30 | R | Customer Read | `ReadFunc_*` | 序列号 |
| 0xF190 | VIN | 17 | R/W | Customer ReadWrite | `WriteFunc_0xF190` | Block 17 |
| 0xF193 | HWVersion | 5 | R | Customer Read | `ReadFunc_*` | Block 11 |
| 0xF194 | ECUSoftwareCode | 9 | R | Customer Read | `ReadFunc_*` | Block 12 |
| 0xF195 | SWVersion | 6 | R | Customer Read | `ReadFunc_*` | Block 8/APPVersion |
| 0xF199 | ProgramDate | 4 | R | Customer Read | `ReadFunc_*` | 编程日期 |
| 0xF1A1 | VariantCodingErase | 8 | W | Customer Write | `WriteFunc_0xF1A1` | Block 18 擦除/复位 |
| 0xF1C2 | ProductionMode | 1 | R/W | Customer ReadWrite | `WriteFunc_0xF1C2` | Block 14 |
| 0xFA13 | EDR0 | 65 | R | Customer Read | `ReadFunc_*` | Block 98 |
| 0xFA14 | EDR1 | 65 | R | Customer Read | `ReadFunc_*` | Block 99 |
| 0xFF94 | DataSet | 9 | R | Customer Read | `ReadFunc_*` | 数据集 |
| 0xFF95 | DataSetVersion | 6 | R | Customer Read | `ReadFunc_*` | 数据集版本 |
| 0xFD12 | VersionInfo | 100 | R | Bosch Read | `BoschDID_0xFD12_VersionInfo_Read` | Bosch 私有 |
| 0xFD13 | ErrorLog | 150 | R | Bosch Read | `BoschDID_0xFD13_ErrorLog_Read` | Block 102 相关 |
| 0xFD14 | FaultMask | 32 | R/W | Bosch ReadWrite | `BoschDID_0xFD14_FaultMask_Read/Write` | Block 101 |
| 0xFD15 | LifeCycleSwitch | 2 | R/W | Bosch ReadWrite | `BoschDID_0xFD15_LifeCycleSwitch_Read/Write` | 生命周期 |
| 0xFD16 | SecurityKey | 1536 | W | Bosch Write | `BoschDID_0xFD16_SecurityKey_Write` | Block 103 需确认 |
| 0xFD17 | RadarPosition_ETHOnly | 1 | R/W | Bosch ReadWrite | `BoschDID_0xFD17_RadarPosition_Read/Write` | Block 21 |
| 0xFD18 | SecurityKey | 36 | W | Bosch Write | `BoschDID_0xFD18_SecurityKey_Write` | Security |
| 0xFD19 | SecurityKey | 544 | W | Bosch Write | `BoschDID_0xFD19_SecurityKey_Write` | Security |
| 0xFD20 | BoschDID_0xFD20 | 64 | R | Bosch Read | `BoschDID_0xFD20_Read` | 语义 TBD |
| 0xFD21 | BoschDID_0xFD21 | 41 | R | Bosch Read | `BoschDID_0xFD21_Read` | 语义 TBD |
| 0xFD22 | BoschDID_0xFD22 | 16 | R | Bosch Read | `BoschDID_0xFD22_Read` | 语义 TBD |
| 0xFD23 | BoschDID_0xFD23 | 66 | R | Bosch Read | `BoschDID_0xFD23_Read` | 语义 TBD |
| 0xFD24 | BoschDID_0xFD24 | 66 | R | Bosch Read | `BoschDID_0xFD24_Read` | 语义 TBD |
| 0xFD25 | BoschDID_0xFD25 | 66 | R | Bosch Read | `BoschDID_0xFD25_Read` | 语义 TBD |
| 0xFD26 | BoschDID_0xFD26 | 66 | R | Bosch Read | `BoschDID_0xFD26_Read` | 语义 TBD |
| 0xFD27 | BoschDID_0xFD27 | 66 | R | Bosch Read | `BoschDID_0xFD27_Read` | 语义 TBD |
| 0xFD28 | BoschDID_0xFD28 | 66 | R | Bosch Read | `BoschDID_0xFD28_Read` | 语义 TBD |
| 0xFD30 | InjectFault | 4 | R/W | Bosch ReadWrite | `BoschDID_0xFD30_InjectFault_Read/Write` | 假故障/注入 |
| 0xFD31 | VKI | 90 | R | Bosch Read | `BoschDID_0xFD31_VKIRead` | Bosch 私有 |
| 0xFDAA | BoschDID_0xFDAA | 640 | R | Bosch Read | `BoschDID_0xFDAA_Read` | 语义 TBD |

## 7. Routine 配置矩阵

| RID | Routine | Start | Stop | Result | Allowed Session | Allowed Security | 前置条件 | NvM/业务关联 |
|---:|---|---|---|---|---|---|---|---|
| 0x0203 | FBL 前置条件检查 | `Dia_Check_FBL_PreCondition_StartRoutine` | N/A | N/A | `0x4uL` | `0xFFFFFFFFuL` | `Dia_RID_0x0203_PreconditionCheck` | Boot/刷写 |
| 0x0302 | SDA 标定 | `Dia_Calibration_SDA_StartRoutine` | `Dia_Calibration_SDA_StopRoutine` | `Dia_Calibration_SDA_RequestResults` | `0x4uL` | `0x2uL` | `Dia_RID_SDA_PreconditionCheck` | Block 26/27/28/97 |
| 0x54DF | EOL 静态标定 | `Dia_Calibration_EOL_Static_StartRoutine` | `Dia_Calibration_EOL_Static_StopRoutine` | `Dia_Calibration_EOL_Static_RequestResults` | `0x4uL` | `0x2uL` | `Dia_RID_EOL_PreconditionCheck` | Block 26/27/28/97 |
| 0xFD00 | Bosch Security | `Bosch_RID_Security_0xFD00` | N/A | N/A | TBD | TBD | TBD | Security |
| 0xFD01 | Bosch Clear ITC | `Bosch_RID_ClearITC_0xFD01` | N/A | N/A | TBD | TBD | TBD | DTC/ITC |

## 8. DEM/DTC 配置矩阵

工具中需要配置/核对：`EventId`、`EventName`、`DTCClass`、`DTCValue`、`DebounceAlgorithm`、`OperationCycle`、`AgingCycle`、`Healing`、`EventMemoryDestination`、`SnapshotRecord`、`ExtendedDataRecord`、`EnableCondition`、`StorageCondition`。

### 8.1 DTC Class 清单

| ID | DTC Class |
|---:|---|
| 1 | DTC_IPB_SIGNAL_INVALID |
| 2 | DTC_IPB_ALC |
| 3 | DTC_IPB_CRC |
| 4 | DTC_Left_BCM_SIGNAL_INVALID |
| 5 | DTC_Left_BCM_ALC |
| 6 | DTC_Left_BCM_CRC |
| 7 | DTC_PRODUCTION_MODE_ACTIVE |
| 8 | DTC_ALIGNMENT_NEVER_DONE |
| 9 | DTC_ALIGNMENT_NOT_OK |
| 10 | DTC_BOSCH_DRIVETESTACTIVE |
| 11 | DTC_FACTORYDATA_FAILURE |
| 12 | DTC_HW_UC_PFLASH |
| 13 | DTC_INTERNAL_POWER_MANAGEMENT_SYS_FAILURE |
| 14 | DTC_INTERNAL_UC_SYS_FAILURE |
| 15 | DTC_INTERNAL_HW_FAILURE |
| 16 | DTC_POWER_MANAGEMENT_CHIP_VOLTAGE_HIGH |
| 17 | DTC_MMIC_VOLTAGE_HIGH |
| 18 | DTC_POWER_MANAGEMENT_CHIP_VOLTAGE_LOW |
| 19 | DTC_MMIC_VOLTAGE_LOW |
| 20 | DTC_RADAR_MODULATION_CONFIGURE |
| 21 | DTC_RADAR_MODULATION |
| 22 | DTC_SW_FAILURE |
| 23 | DTC_SW_RIF_FAILURE |
| 24 | DTC_SW_TEMP_FAILURE |
| 25 | DTC_UC_TEMPERATURE_OUTOFRANGE |
| 26 | DTC_MMIC_TEMPERATURE_OVER_MAXIMUM |
| 27 | DTC_MMIC_TEMPERATURE_OVER_OPERATION |
| 28 | DTC_ADC_SELF_TEST_FAILURE |
| 29 | DTC_NVM_EOL_NO_VAR |
| 30 | DTC_CUDA_Invalid |
| 31 | DTC_SYS_BLIND |
| 32 | DTC_SENSOR_BLIND |
| 33 | DTC_HORIZONTAL_MISALIGNED |
| 34 | DTC_AntennaDiagram_INVALID |
| 35 | DTC_Time_SYNC_FAIL |
| 36 | DTC_Modulation_OFF |
| 37 | DTC_PCAN_BUSOFF |
| 38 | DTC_EPS_TIMEOUT |
| 39 | DTC_IPB_TIMEOUT |
| 40 | DTC_Left_BCM_TIMEOUT |
| 41 | DTC_VCU_SIGNAL_INVALID |
| 42 | DTC_SFCAN_BUSOFF |
| 43 | DTC_CMRR_DACORE_OOS |
| 44 | DTC_Private_Can_ALC |
| 45 | DTC_Private_Can_CRC |
| 46 | DTC_Private_Can_TIMEOUT |
| 47 | DTC_Media_TIMEOUT |
| 48 | DTC_Media_CRC |
| 49 | DTC_EPS_ALC |
| 50 | DTC_EPS_CRC |
| 51 | DTC_EPS_SIGNAL_INVALID |
| 52 | DTC_MRR_TIMEOUT |
| 53 | DTC_MRR_ALC |
| 54 | DTC_MRR_CRC |
| 55 | DTC_VCU_TIMEOUT |
| 56 | DTC_VBAT_HIGH |
| 57 | DTC_VBAT_LOW |
| 58 | DTC_VCU_ALC |
| 59 | DTC_VCU_CRC |

### 8.2 Event 范围配置矩阵

| EventID 范围 | Event 族 | DTC 族 | 上报代码 | 工具待确认 |
|---|---|---|---|---|
| 1-8 | Alignment/Production/BusOff/EOL | Alignment、Production、BusOff、NVM_EOL | FM/COM/业务 | Debounce、Aging、Snapshot |
| 9-76 | EPS/IPB/BCM/VCU/Media 通信 | Timeout/ALC/CRC/Signal Invalid | `components/com/AutoGen` | ComM/PduR 使能条件 |
| 77-95 | 私有雷达 CAN 通信 | Private CAN ALC/CRC/Timeout | `components/com/AutoGen` | 主从雷达网络条件 |
| 96-101 | ADCBuf/mmWave ADC | ADC_SELF_TEST_FAILURE | `mmw_user_assertfault.c` | 上电自检策略 |
| 102-112 | Antenna/DSP/Clock/Factory/TimeSync | Antenna、Internal、Factory、TimeSync | `mmw_user`/FM | Snapshot/扩展数据 |
| 113-125 | 内部模拟量/NvM/OS/PLL | Internal HW/uC、SW、NvM | `mmw_user_faultdetect.c`、BswM | 是否立即存储 |
| 126-154 | PMIC/电源 | PMIC、电压高低、Power | PMIC/VOL_Tem | EnableCondition |
| 155-188 | RF/TX/RX/车速 | RF/Internal/CMRR | `mmw_user_faultdetect.c` | 阈值与 Debounce |
| 189-202 | mmWave BSS/DataPath/温度 | Internal、Temp | `mmw_user_assertfault.c`、`VolAndTemTest.c` | 启动阶段屏蔽 |
| 203-217 | FakeFault | 多个测试 DTC | Fault Injection | 是否客户交付 |

## 9. 开发落地检查表

| 检查项 | 必须完成 |
|---|---|
| NvM | 确认 `NvM_WriteAll()` 正式调用路径；补齐 CRC、默认值、WriteOnce、ImmediateWrite；确认 EDR 写频率与 Flash 寿命 |
| Dcm DID | 每个可写 DID 确认写入后是否同步 NvM；补齐 NRC 策略；确认 Bosch DID `0xFD20..0xFD28/0xFDAA` 语义 |
| Dcm Routine | 补齐 Start/Stop/Result 参数长度、NRC、Pending、超时、车辆状态前置条件 |
| Dem | 补齐 217 个 Event 的 debounce、operation cycle、aging、snapshot、extended data、clear 行为 |
| 安全 | SecurityAccess 计数器、延时、掉电保持、安全密钥写入权限需与客户规范一致 |
| 交付 | 用本矩阵与 ARXML、DTC 表、诊断 CDD/ODX、客户需求逐项交叉校验 |

## 10. 当前不能直接确认的配置项

- NvM 每个 Block 的 CRC 类型、默认 ROM 数据、RAM Block 符号、Write Protection、Immediate Write 尚未逐项确认。
- Fee/Fls 的物理分区、Block 编号映射、磨损均衡策略需要结合 Fee 配置文件确认。
- DEM Event 到 DTC 的完整 217 行矩阵已在生成头文件中存在，但 DTC 数值、快照和扩展数据内容需结合 DTC 表确认。
- Routine `0xFD00/0xFD01` 的会话、安全和输入输出参数需要结合 Bosch 诊断规范确认。
- DID `0xFD20..0xFD28`、`0xFDAA` 的业务含义当前只从代码命名无法完整确认。
