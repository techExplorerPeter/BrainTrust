# mmWave 射频接口梳理

## 结论

当前 mmWave 射频相关代码不是通过标准 AUTOSAR RTE Port 接口访问射频驱动。实际链路是 `rte/OsTask_MMW.c` 中的 RTA-OS Task 直接调用手写 C 封装接口，再下沉到 TI `MMWave_*` 和 mmWaveLink `rl*` 接口。

RTE 在该链路中主要承担系统调度、COM 映射和 ASW runnable 调用；RF 初始化、配置、启停、动态 profile 切换和监控配置均由手写代码或 TI SDK 接口完成。

## 代码分层

| 层级 | 代码位置 | 作用 |
|---|---|---|
| OS Task 调度 | `rte/OsTask_MMW.c` | 调度 DPM、66ms 算法处理、20ms 监控和 COM 映射 |
| Demo 封装层 | `mmwave/mmw_main.c`, `mmwave/mmw_mss.h` | 封装 sensor open/config/start/stop/control |
| RF 配置层 | `adas/beamform/rfconfig/`, `adas/symmetry/rfconfig/` | 定义 profile、advanced chirp、动态切波逻辑 |
| TI MMWave 层 | `mmwave/mmwave/` | 提供 `MMWave_*` 控制接口 |
| mmWaveLink 层 | `mmwave/mmwavelink/` | 提供 `rl*` 底层 BSS/RF 下发接口 |

## 主要调用链

```text
OsTask_DPM
  -> MmwDemo_mmWaveCtrlTask()
     -> MMWave_execute()
        -> MMWave_executeLink()

MmwDemo_CLIInit()
  -> MmwDemo_openSensor()
     -> MMWave_open()
  -> MmwDemo_configSensor()
     -> MMWave_config()
        -> MMWave_configLink()
        -> rlSetProfileConfig() / advanced chirp / frame config
  -> MmwDemo_startSensor()
     -> RF monitor config
     -> MMWave_start()
        -> MMWave_startLink()
        -> rlSensorStart()

OsTask_Trigger66ms
  -> Mmw_ProfileReload()
     -> rlSetProfileConfig()
     -> rlSetAdvChirpDynLUTAddrOffConfig()
     -> rlSetDynChirpEn()

Period20ms_Task_func
  -> Mmw_Mainfunctin_Monitoring()
```

## 项目封装接口

| 接口 | 文件 | 用途 | 是否 RTE |
|---|---|---|---|
| `MmwDemo_initTask()` | `mmwave/mmw_main.c`, `mmwave/mmw_mss.h` | 初始化 `MMWave_init`、`MMWave_sync` 和 DPM 同步 | 否 |
| `MmwDemo_openSensor(bool isFirstTimeOpen)` | `mmwave/mmw_main.c` | 设置 openCfg、校准数据，调用 `MMWave_open` | 否 |
| `MmwDemo_configSensor()` | `mmwave/mmw_main.c` | 调用 `MMWave_config`，配置 profile、frame、advanced chirp | 否 |
| `MmwDemo_startSensor()` | `mmwave/mmw_main.c` | 配置 RF monitor，启动 datapath，调用 `MMWave_start` | 否 |
| `MmwDemo_stopSensor()` | `mmwave/mmw_main.c` | 调用 `MMWave_stop` 停止 RF | 否 |
| `MmwDemo_mmWaveCtrlTask()` | `mmwave/mmw_main.c` | 执行 `MMWave_execute`，处理 mmWave 异步事件 | 否 |
| `MmwDemo_CLIInit(uint8_t taskPriority)` | `adas/*/rfconfig/mmw_cli.c` | 当前实现绕过 CLI，直接填充配置并启动 sensor | 否 |
| `MmwDemo_CLITriggerFrame()` | `adas/*/rfconfig/mmw_cli.c` | 直接调用 `rlSensorStart(1)` 软件触发帧 | 否 |
| `MmwDemo_CLIStopFrame()` | `adas/*/rfconfig/mmw_cli.c` | 直接调用 `rlSensorStop(1)` 停帧 | 否 |
| `Mmw_ProfileReload()` | `adas/*/rfconfig/Mmw_ReloadProfile.c` | 根据车速、温度切换短波/长波/高温降级 profile | 否 |
| `Mmw_Mainfunctin_Monitoring()` | `mmwave/mmw_monitor.c` | 周期处理 RF 监控结果和 fault status | 否 |

## TI MMWave 接口

接口声明位于 `mmwave/mmwave/mmwave.h`。

| 接口 | 作用 |
|---|---|
| `MMWave_init()` | 初始化 mmWave 控制模块 |
| `MMWave_sync()` | 同步 mmWave 控制模块 |
| `MMWave_open()` | 打开 RF，配置通道、ADC、校准参数 |
| `MMWave_config()` | 下发 profile、chirp、frame 等控制配置 |
| `MMWave_start()` | 启动 RF chirp/frame |
| `MMWave_stop()` | 停止 RF |
| `MMWave_execute()` | 处理 mmWaveLink 异步事件 |
| `MMWave_addProfile()` | FULL config 模式下添加 profile |
| `MMWave_addChirp()` | FULL config 模式下添加 chirp |
| `MMWave_addAdvChirpParam()` | 添加 advanced chirp 参数 |
| `MMWave_addAdvChirpLUTData()` | 添加 advanced chirp LUT 数据 |
| `MMWave_flushCfg()` | 清理已配置的 RF 控制配置 |

## mmWaveLink/RL 底层接口

| 接口 | 作用 | 典型调用位置 |
|---|---|---|
| `rlSetProfileConfig()` | 下发 profile 配置 | `mmwave_link_common.c`, `Mmw_ReloadProfile.c` |
| `rlSensorStart()` | 启动 sensor/frame | `mmwave_link_common.c`, `mmw_cli.c` |
| `rlSensorStop()` | 停止 sensor/frame | `mmwave_link_common.c`, `mmw_cli.c` |
| `rlSetAdvChirpDynLUTAddrOffConfig()` | 动态修改 advanced chirp LUT 偏移 | `adas/symmetry/rfconfig/Mmw_ReloadProfile.c` |
| `rlSetDynChirpEn()` | 使能动态 chirp 更新 | `adas/symmetry/rfconfig/Mmw_ReloadProfile.c` |
| `rlRfGetTemperatureReport()` | 读取 RF 温度报告 | `mmwave/mmw_main.c` |

## RF 配置数据接口

| 数据 | 文件 | 说明 |
|---|---|---|
| `gProfile_cfg[4]` | `adas/*/rfconfig/rf_config.c` | RF profile 参数数组 |
| `gAdvChirp_cfg[11]` | `adas/*/rfconfig/rf_config.c` | advanced chirp 参数数组 |
| `gAdvChirp_ptr[11]` | `adas/*/rfconfig/rf_config.c` | chirp 配置和 LUT 数据指针 |
| `gAdvChirp_cfg_change` | `adas/*/rfconfig/rf_config.c` | 动态修改 chirp idle time 使用 |
| `gAdvChirp_ptr_change` | `adas/*/rfconfig/rf_config.c` | 动态 chirp 修改指针 |
| `rlAdvPtr_t` | `adas/*/rfconfig/sys_conf.h` | advanced chirp 配置和 LUT 指针结构 |

## RF 监控相关接口

RF monitor 配置在 `MmwDemo_startSensor()` 中完成，监控结果在 `Mmw_Mainfunctin_Monitoring()` 和 `mmw_user_*` 接口中处理。

| 接口 | 作用 |
|---|---|
| `MmwaveLink_monitorReportCountInit()` | 清零 RF monitor 报告计数 |
| `MmwaveLink_setRfAnaMonConfig()` | 配置模拟监控总开关 |
| `MmwaveLink_rlRfDigMonPeriodicConfig()` | 配置数字周期监控 |
| `MmwaveLink_setRfTxPowMonConfig()` | 配置 TX power monitor |
| `MmwaveLink_setRfRxGainPhaMonConfig()` | 配置 RX gain/phase monitor |
| `MmwaveLink_setRfRxIfStageMonConfig()` | 配置 RX IF stage monitor |
| `MmwaveLink_setRfPllContrlVoltMonConfig()` | 配置 PLL control voltage monitor |
| `MmwaveLink_setRfDualClkCompMonConfig()` | 配置 dual clock comparator monitor |
| `MmwaveLink_setRfTempMonConfig()` | 配置 RF temperature monitor |
| `MmwaveLink_setRfSynthFreqMonConfig()` | 配置 synthesizer frequency monitor |
| `MmwaveLink_setRfTxPhShiftMonConfig(tx)` | 配置 TX phase shift monitor |
| `MmwaveLink_setRfAdvTxGainPhaseMismatchMonConfig()` | 配置 advanced TX gain/phase mismatch monitor |

## 变体说明

RF 配置存在两套变体：

| 变体 | 路径 | 说明 |
|---|---|---|
| Beamform | `adas/beamform/rfconfig/` | beamforming 相关 RF 配置 |
| Symmetry | `adas/symmetry/rfconfig/` | symmetry 相关 RF 配置 |

编译时由 SCons 参数 `antenna` 选择变体。未指定时，`SConstruct` 默认添加 `PF_BUILD_ANTENNA_BEAMFORM`，并选择 `adas/beamform`。

## 注意事项

- `MmwDemo_initTask()` 是 RF 控制模块初始化入口，但 `rte/OsTask_MMW.c` 中 `OsTask_MmWaveCtrl` 对它的调用当前被注释，需要确认实际启动路径是否由其他初始化代码触发。
- `MmwDemo_CLIInit()` 名称保留 CLI 语义，但当前实现不是交互式 CLI，而是直接填充配置并启动 sensor。
- 对外提交接口列表时，建议按“项目封装接口、TI MMWave SDK 接口、mmWaveLink/RL 底层接口、RF 配置数据接口、RF 监控接口”五类交付。
