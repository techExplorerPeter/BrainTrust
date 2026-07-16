# 存储与诊断需求清单

本文基于当前工程代码反向梳理存储和诊断需求，来源包括 `coem/BYD_UKE/gen_bsw` 生成配置、`integration` 集成代码、`rte` 周期任务、`coem/BYD_UKE/components` 业务组件、`mmwave/mmw_user` 射频故障检测代码。

## 1. 存储需求总览

本工程的持久化主要走 AUTOSAR NvM/Fee 体系，少量业务逻辑由手写代码触发读写。核心配置文件为 `coem/BYD_UKE/gen_bsw/NvM/NvM_Cfg.c`，共配置 104 个 NvM Block，BlockID 为 `0..103`。

### 1.1 NvM 初始化与全局读写

- 上电初始化需要调用 `NvM_ReadAll()`，入口在 `integration/BswM_Callout_Stub.c` 的 `BswM_NvM_ReadAll()`。
- `BswM_NvM_ReadAll()` 轮询 `NvM_MainFunction()` 与 `Fee_MainFunction()`，等待 `NVM_REQ_OK`。
- 读超时需要上报 DEM 事件 `DemConf_DemEventParameter_PF_Event_NvM_Read`。
- `BswM_NvM_WriteAll()` 当前包含状态轮询逻辑，但 `NvM_WriteAll()` 调用被注释，需要确认量产关机/掉电路径是否由其他模块触发写入。

### 1.2 NvM Block 清单

| BlockID | 名称 | 长度 |
|---:|---|---:|
| 0 | NvM_MultiBlock | 1 |
| 1 | NvM_ConfigId | 2 |
| 2 | NvMBlock_LogisticData | 128 |
| 3 | NVM_OS_ErrorlogOsErrorHook | 370 |
| 4 | NVM_OS_ErrorlogOsShutdown | 44 |
| 5 | NVM_OS_ErrorlogOsWdgReset | 6 |
| 6 | NVM_OS_ErrorlogActiveReset | 5 |
| 7 | NVM_PMIC_DTC_ERROR | 40 |
| 8 | CustDID_APPVersion | 6 |
| 9 | CustDID_DisBetFrontandRear | 2 |
| 10 | CustDID_DisBetLeftandRight_0x126A | 2 |
| 11 | CustDID_ECUHWVersionNumber | 5 |
| 12 | CustDID_ECUSoftwareCode | 9 |
| 13 | CustDID_FBLVersion | 9 |
| 14 | CustDID_ProductionMode | 1 |
| 15 | NvMBlockDescriptor_ECUConfiguration | 4 |
| 16 | CustDID_TargetPosition_0x1266 | 4 |
| 17 | CustDID_VIN | 17 |
| 18 | CustDID_VariantCoding | 8 |
| 19 | CustDID_WheelBase | 2 |
| 20 | NvM_PowerOn_Counter | 4 |
| 21 | NvM_RadarPosition_ETHOnly | 1 |
| 22 | Cust_SecurityAccesscounter | 1 |
| 23 | Dia_SecurityAccesscounter | 1 |
| 24 | ECUM_CFG_NVM_BLOCK | 4 |
| 25 | NVM_ADAS_HMISwitch | 11 |
| 26 | NVM_Calibration_EffStatus | 1 |
| 27 | NVM_Calibration_OnlineStatus | 30 |
| 28 | NVM_Calibration_TriggerStatus | 30 |
| 29-48 | NVM_ID_DEM_EXTRA_INFO_0..19 | 32 each |
| 49 | NVM_ID_DEM_GENERIC_NV_DATA | 16 |
| 50-89 | NVM_ID_EVMEM_LOC_0..39 | 48 each |
| 90 | NVM_ID_EVT_STATUSBYTE | 218 |
| 91 | NVM_NM_ForceHibernationLatestSts | 1 |
| 92 | NvMBlockDescriptor_Application_Valid_Flag | 1 |
| 93 | NvMBlockDescriptor_Fingerprint_Data | 9 |
| 94 | NvMBlockDescriptor_Reprogramming_Request_Flag | 4 |
| 95 | NvMBlockDescriptor_ResetReason_Type | 1 |
| 96 | NvM_BLDDetStatus | 1 |
| 97 | NvM_Calibration_TargetPosition | 4 |
| 98 | NvM_EDR_Data1 | 4900 |
| 99 | NvM_EDR_Data2 | 4900 |
| 100 | NvM_EDR_WRITE_FLAG | 2 |
| 101 | NvM_FaultMask_Info | 32 |
| 102 | NvM_PFDem_ErrorInfo | 512 |
| 103 | NvM_Security_Key | 32 |

### 1.3 业务存储分类

- 诊断 DID 类存储：软件/硬件版本、VIN、Variant Coding、生产模式、目标安装位置、轮距/轴距等，主要对应 BlockID `8..19`。
- 安全访问存储：客户安全计数、诊断安全计数、安全密钥，主要对应 BlockID `22`、`23`、`103`。
- 标定存储：标定有效状态、在线状态、触发状态、目标位置，主要对应 BlockID `26..28`、`97`。
- DEM/DTC 存储：扩展信息、事件内存、状态字节、FaultMask、PF Dem 错误信息，主要对应 BlockID `29..90`、`101`、`102`。
- EDR 存储：`NvM_EDR_Data1`、`NvM_EDR_Data2`、`NvM_EDR_WRITE_FLAG`，由 `rte/OsTask_MMW.c` 20ms 周期调用 `EDR_fun_Init()` 和 `EDR_save_data()`，接口实现在 `coem/BYD_UKE/components/EDR_interface`。
- Boot/刷写相关存储：应用有效标志、指纹数据、重编程请求标志、复位原因，主要对应 BlockID `92..95`。

## 2. 诊断需求总览

诊断主体走 AUTOSAR Dcm/Dem，配置入口在 `coem/BYD_UKE/gen_bsw/Dcm` 与 `coem/BYD_UKE/gen_bsw/Dem`。诊断业务回调位于 `coem/BYD_UKE/components/diag`，故障检测位于 `coem/BYD_UKE/components/fm`、`mmwave/mmw_user`、`bswpf/cdd/VOL_Tem_Test` 以及 COM 自动生成监控代码。

### 2.1 UDS 服务

DoCAN 服务表配置 11 个服务：

| SID | 服务 | 子功能/说明 |
|---:|---|---|
| 0x10 | DiagnosticSessionControl | 0x01、0x02、0x03、0x06、0x60 |
| 0x11 | ECUReset | 0x01 |
| 0x14 | ClearDiagnosticInformation | 清除 DTC |
| 0x19 | ReadDTCInformation | 0x01、0x02、0x04、0x06、0x0A |
| 0x22 | ReadDataByIdentifier | 读取 DID |
| 0x27 | SecurityAccess | 0x01/0x02、0x61/0x62、0x63/0x64 |
| 0x28 | CommunicationControl | 0x00、0x01、0x03 |
| 0x2E | WriteDataByIdentifier | 写 DID |
| 0x31 | RoutineControl | 例程控制 |
| 0x3E | TesterPresent | 0x00 |
| 0x85 | ControlDTCSetting | 0x01、0x02 |

### 2.2 会话与安全等级

- 会话：Default `0x01`、Programming `0x02`、Extended `0x03`、WEIFU `0x06`、Bosch `0x60`。
- 安全等级：`Unlocked_L1`、`Unlocked_L31`、`Unlocked_L32`。
- L1 使用 4 字节 seed/key；L31/L32 使用 250 字节 seed、2000 字节 key。
- 失败延时计数配置为 1000 task counts，触发延时的最大失败次数为 3。

### 2.3 Routine 列表

| RID | 名称/用途 | 回调 |
|---:|---|---|
| 0x0203 | FBL 前置条件检查 | `Dia_Check_FBL_PreCondition_StartRoutine` |
| 0x0302 | SDA 标定 | `Dia_Calibration_SDA_StartRoutine`、`StopRoutine`、`RequestResults` |
| 0x54DF | EOL 静态标定 | `Dia_Calibration_EOL_Static_StartRoutine`、`StopRoutine`、`RequestResults` |
| 0xFD00 | Bosch 安全例程 | `Bosch_RID_Security_0xFD00` |
| 0xFD01 | Bosch Clear ITC | `Bosch_RID_ClearITC_0xFD01` |

### 2.4 DID 列表

配置中出现的 DID 包括：

- Bosch DID：`0xFD12` VersionInfo、`0xFD13` ErrorLog、`0xFD14` FaultMask、`0xFD15` LifeCycleSwitch、`0xFD16` SecurityKey、`0xFD17` RadarPosition_ETHOnly、`0xFD18` SecurityKey、`0xFD19` SecurityKey、`0xFD20..0xFD28`、`0xFD30` InjectFault、`0xFD31` VKI、`0xFDAA`。
- Customer DID：`0x0103` SecurityAccessInvalidCounter、`0x0285` SupplierVoltage、`0x028D` EcuTemperature、`0x1011` VehicleSpeed、`0x2100` VariantCoding、`0x3403` SlowHorizontalAngle、`0x3404` FastHorizontalAngle、`0x3441` FastVerticalAngle、`0x3442` SlowVerticalAngle、`0x3443` SensorMountingSide、`0x3444` PINDirectionANDPosition、`0x3449` Lifecycle_Read、`0x344A` LifecycleSwitch、`0xF180` FBLVersion、`0xF18C` SerialNumber、`0xF190` VIN、`0xF193` HWVersion、`0xF194` ECUSoftwareCode、`0xF195` SWVersion、`0xF199` ProgramDate、`0xF1A1` VariantCodingErase、`0xF1C2` ProductionMode、`0xFA13` EDR0、`0xFA14` EDR1、`0xFF94` DataSet、`0xFF95` DataSetVersion。
- General DID：`0xF186` GetCurSession。

## 3. DEM/DTC 需求

DEM 配置中 `DEM_EVENTID_COUNT` 为 217。事件覆盖整车通信、标定、供电、温度、PMIC、OS、NvM、mmWave/RF、自检、EDR/快照与假故障注入。

### 3.1 DTC 类别

配置中包含以下 DTC 族：

- 通信类：IPB、Left_BCM、VCU、EPS、MRR、Media、Private CAN、PCAN/SFCAN BusOff，覆盖 Timeout、ALC、CRC、Signal Invalid。
- 生产/标定类：Production Mode、Alignment Never Done、Alignment Not OK、Horizontal Misaligned、EOL NvM No Var。
- 存储/软件类：NvM EOL、FactoryData、SW Failure、SW RIF Failure、SW Temp Failure、HW uC PFlash、Internal uC/System/Hardware Failure。
- 供电/PMIC 类：VBAT 高低压、PowerHigh/PowerLow、PMIC 电压高低、MMIC 电压高低、PMIC watchdog、SPI、Buck/LDO/Boost。
- 雷达/RF 类：Radar Modulation、Modulation Off、MMIC 温度、RF CPU/ESM Fault、TX/RX Gain Phase、TX Power、Phase Shifter、Synthesizer Frequency、Internal Analog Signals。
- 感知状态类：System Blind、Sensor Blind、CUDA Invalid、Antenna Diagram Invalid、Time Sync Fail、Slave Radar Missing。

### 3.2 关键 DEM 事件范围

- `1..8`：Alignment、Production Mode、CAN BusOff、EOL NvM。
- `9..95`：外部 CAN 报文 Timeout/ALC/CRC/Signal Invalid。
- `96..101`：ADCBuf 与 mmWave ADC buffer。
- `102..112`：Antenna、DSP、DualClock、FactoryData、TimeSync。
- `113..125`：内部模拟监控、MR、NvM Read/Write、OS、PLL。
- `126..154`：PMIC 与电源。
- `155..188`：安装错误、RF 状态、RX/TX 监控、车速边界。
- `189..202`：mmWave BSS、DataPath、Sensor Start、SOC/RF 温度。
- `203..217`：`ZZZ_FakeFault_0..14` 假故障注入/测试。

### 3.3 故障上报接口

- 标准故障上报接口为 `Dem_SetEventStatus(..., DEM_EVENT_STATUS_FAILED/PASSED/PREFAILED/PREPASSED)`。
- mmWave/RF 故障检测集中在 `mmwave/mmw_user/mmw_user_faultdetect.c`，包括 PLL、电源、TX/RX 增益相位、TX 功率、相移器、合成器频率、内部模拟量、RF CPU/ESM。
- mmWave 断言类故障在 `mmwave/mmw_user/mmw_user_assertfault.c`，覆盖 ADCBuf、mmWave init/open/start/data path 等。
- 电压温度诊断在 `bswpf/cdd/VOL_Tem_Test/VolAndTemTest.c`，覆盖 SOC/RF 温度、供电高低压。
- 通信信号有效性诊断大量由 `coem/BYD_UKE/components/com/AutoGen` 下自动生成代码上报。

## 4. 需要对外交付的接口清单

建议对外交付时按以下接口域整理：

- 存储接口：`NvM_ReadAll`、`NvM_WriteAll`、`NvM_MainFunction`、`Fee_MainFunction`、各 NvM BlockID、EDR 读写接口。
- 诊断基础接口：UDS SID、Session、安全等级、Routine RID、DID。
- 故障接口：DTC 列表、DEM EventID、`Dem_SetEventStatus` 上报点、故障快照/扩展数据 NvM Block。
- 标定与产线接口：SDA/EOL Routine、生产模式、生命周期、Variant Coding、目标安装位置。
- 安全接口：SecurityAccess 0x27、Bosch Security DID/RID、安全计数与安全密钥 NvM Block。

## 5. 待确认项

- `BswM_NvM_WriteAll()` 中 `NvM_WriteAll()` 被注释，需要确认正式掉电保存路径。
- `ZZZ_FakeFault_0..14` 属于测试/注入类事件，是否对客户交付需要单独确认。
- DID `0xFD20..0xFD28` 在配置中有占位命名，具体信号语义需要结合 arxml 或诊断规范进一步展开。
- 本文为代码反向梳理结果，不等同于客户原始需求规格；对外提交前建议与 DBC、CDD/诊断规范、DTC 表三方交叉校验。
