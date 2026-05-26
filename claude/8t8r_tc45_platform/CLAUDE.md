# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`TC457_8T8R` (Eclipse project name; also `iLLD_TC457_RDR_TRB_ADS_LETH_LWIP` upstream) — bare-metal + FreeRTOS firmware for an 8T8R automotive radar built on:

- **MCU**: Infineon AURIX **TC457DP A-Step** on the **KIT_TC457_RDR_TRB** TriBoard.
- **RF front-end**: Infineon **CTRX 8188** MMIC, driven through the iRFE library and the LETH/RIF interfaces.
- **Networking**: LETH (Lite Ethernet) + LwIP, default IP `192.168.0.10`, radar/monitor data streamed over UDP (port 5002 for monitor, separate UDP frame for radar payload).

Two TriCore cores are used asymmetrically:

- **Core 0** (`Core0_App/Cpu0_Main.c`): system bring-up, `allowAccess()`, retarget UART, CAN (PCAN/VCAN), Ethernet+LwIP, PMIC, temperature monitor, **FreeRTOS scheduler**, and the `radar_eth_client_task` that streams data to the host.
- **Core 1** (`Core1_App/Cpu1_Main.c`): bare-metal loop driving the **MMIC** state machine and the **SPU** signal-processing pipeline (1DFFT → 2DFFT → CFAR → DOA). RDMA is initialized after SPU.

Cross-core handoff goes through `gShareData` (declared in `Global_Data.h`/`.c`) and the volatile flag `g_dataSyncEventFlag` placed in section `.bss.sharedvar`. Core 1 sets the flag when 1DFFT is done; core 0 sends the frame and clears it.

## Build, Flash, Versioning

This is an **AURIX Development Studio** (Eclipse CDT-managed) project, not a Make/CMake project. Build via ADS GUI or the equivalent CDT headless build — there is no top-level `Makefile`.

- Toolchain: **GCC TriCore** (also configured for HighTec/Tasking via the alternate `Lcf_*.lsl` linker scripts). C dialect: `-std=gnu99`, `-msoft-dp-float` (no double-precision FPU), `-gdwarf-3`.
- Target derivative: `tc45xx`. Active build configuration: `TriCore Debug (GCC)`. Build output: `TriCore Debug (GCC)/TC457_8T8R.hex` and `.elf`.
- Required preprocessor defines (set in `.cproject`): `CTRX_8191F=1`, `CTRX8191_B11=1`.
- **Post-build**: ADS runs `tools\file_rename_tool\file_rename_tool.bat`, which:
  1. Reads `sw_version.h` (`SW_MAIN_VERSION`/`SW_SUB_VERSION`/`SW_PATCH`/`SW_BUILD`) via `concat_regex_res.py`.
  2. Renames `TC457_8T8R.hex` to `TC457_8T8R_<branch>_<shortHash>_<version>.hex`.
  3. Copies it into `AppImages/`.

  The script prefers compiled `.exe` siblings of the Python files, falling back to `python concat_regex_res.py` / `python file_rename.py`. **Bump `sw_version.h` for releases** — that is what ends up in the artifact name.
- Flashing/debug is done from ADS (Flash / Debug buttons). To validate Ethernet, ping `192.168.0.10`.

There is **no test suite** in this repo; firmware is validated on hardware.

## Include Paths and Source Layout

`.cproject` contains the canonical include-path list (~150 entries). When adding a new top-level folder, you must also register it in `.cproject` (and `.excludes` if it should be excluded from build), otherwise headers won't resolve.

Build excludes are listed in `.excludes` — notably `External/FreeRTOS/`, `External/lwIP/`, `External/drivers/power/`, `External/ports/`, `External/retarget_io/`, `FreeRTOSConfig.h`, `lwipopts.h`, and a couple of pdl headers. These are referenced through include paths but the listed sources/headers are excluded from automatic build resolution.

## Architecture: the `<Module>_IF` component pattern

Note the directory is spelled **`Compoment/`** (typo, but pervasive — keep it). Every functional component under `Compoment/` follows the same five-file split:

```
<Module>Drv.c/.h        — driver implementation (init + main API)
<Module>DrvCfg.c/.h     — board/instance configuration tables and getters
<Module>DrvIsr.c/.h     — ISRs and interrupt-priority constants
<Module>DrvRte.c/.h     — Run-Time Environment glue: ISR callback dispatch, app-facing helpers
<Module>DrvType.h       — shared types/enums for the module
```

`Drv` exposes `<Module>Drv_init()` and operations; `DrvRte` is the layer the application code (`Cpu0_Main.c`, etc.) calls. Existing components: **CAN_IF** (PCAN+VCAN over QSPI2), **ENET_IF** (LETH+LwIP, plus radar UDP framing in `radar_eth_*`), **PMIC_IF**, **RDMA_IF**, **RF_IF** (MMIC driver + 8188 RIF + waveform tables), **SPU_IF** (signal-processing pipeline + filter coefficients), **Tool_IF** (TimeRecord). Follow this layout when adding a new peripheral component.

## Library Layout

- `Libraries/iLLD/TC45x/` — Infineon Low-Level Drivers split by `CpuGeneric/<Periph>/Std` and `Tricore/<Periph>/Std`. Headers prefixed `Ifx*`. Module list (Adc, Asclin, Canxl, Clock, Dma, Fce, Hsphy, Leth, Pms, Ppuc, Qspi, Rdma, Rif, Rmem, Smm, Smu, Spu, Src, Stm, Vmt, Wtu, …) reflects what `Cpu0_Main` and `AllowAccess` configure.
- `Libraries/iRFE/` — Infineon RF Engine, with `include/8188/`, `src/8188/`, `wrappers/` (GPIO/SPI/Time HAL bindings), and CTRX firmware blobs in `ctrx_firmware/`. The `wrappers/` files are what bind iRFE to this platform's iLLD.
- `Libraries/Infra/` — `Ipc/`, `Platform/`, `Sfr/TC45x/_Reg/`, `Ssw/TC45x/Tricore/` (Startup software). `Configurations/Ifx_Cfg_Ssw*.c` are the SSW entry stubs.
- `Libraries/Service/CpuGeneric/SysSe/` — Bsp / Time / Math helpers (notably `ClockP_getTimeUsec()` used by TimeRecord).
- `Libraries/Platform/`, `Libraries/Logger/` — board abstractions and logging.
- `External/` — third-party + glue: **FreeRTOS** kernel + `External/ports/FreeRTOS/GCC/` port, **lwIP** stack + `External/ports/lwIP/`, **bsp** (`include/bsp/kit_tc457_rdr_trb.h`), **pdl** (Infineon Peripheral Driver Library: `ifx_geth.c`, `ifx_leth.c`, `ifx_dre.c`, etc.), **retarget_io** (UART stdio retarget), **drivers/ethernet/phy**, and **temp_monitor** (split into `tc457/` for the on-chip DTS/VTMON and `ctrx8188/` for MMIC temperature, surfaced via `getChipTemperature()`).

## Critical configuration files

- `Global_Config.h` — feature flags: `MMIC_FRAME_PERIOD_MS`, `IS_USING_MMIC_CONTINUE_WAVE_MODE`, `IS_USING_TIME_RECORD` (gates the `TimestampRecord`/`CurTimePeriodRecord` macros in `Compoment/Tool_IF/TimeRecord.h`), `IS_USING_SAVE_ALL_RD_MAP`.
- `Global_Data.h` / `Global_Data.c` — `gShareData` (cross-core), RSP dimensions (`RSP_ADC_SAMPLE_NUM=512`, `RSP_RAMP_NUM=1536`, `RSP_SUBFRAME_NUM=3`, `RSP_RANGE_FFT_BIN_NUM`, `RSP_DOP_FFT_BIN_NUM=512`, `RSP_ANT_RX_NUM=8`, `RSP_ANT_TX_NUM=8`, `RSP_DOP_CFAR_OBJ_NUM=4096`), MMIC waveform select (`MMIC_WAVEFORM_SELECT`: 0=CALIB, 1=SPARSE, 2=UNIFORM — must match the waveform table sourced from `Compoment/RF_IF/{CalibWave,SparseWaveform_3TDM,UniformWaveform_3TDM}/`).
- `FreeRTOSConfig.h` — single-core (Core 0): preemption on, 500 MHz CPU clock, 1 kHz tick, 64 KB heap, `configMAX_PRIORITIES=10`. The multi-core defines are commented out.
- `lwipopts.h` — LwIP tunables.
- `Configurations/Ifx_Cfg*.{c,h}` — SSW + trap configuration.
- `Lcf_{Gcc,Hightec,Tasking}_Tricore_Tc.lsl` — per-toolchain linker control files. The GCC variant is what the active build uses.
- `sw_version.h` — version components consumed by the post-build rename script (see Build section).
- `Core0_App/AllowAccess.c` — `allowAccess()` opens up RMEM0..RMEM9, DLMU0/1, DSPR0/1, PSPR0/1, voltage rails (vddhsif, vddphphy1, vddphy1), and SFR access for ADC/PPUC/QSPI/ASCLIN/I2C/CLOCK/SRC/PORT/PMS/HSPHY/DMA/FCE/SMM/STM/RIF/RDMA/RMEM/SPU/VMT to all masters via `IfxApApu`. **Must run before any peripheral that crosses the protection boundary.**

## Data flow (per radar frame)

1. Core 1 polls the MMIC SM (`MmicDrv_RunMain`); on `DAS_SEQUENCE_FINISH` it triggers `SpuDrv_MainRun(SPU_RUN_1DFFT)`, increments `gShareData.frameIdx`, and updates `gShareData.waveId`.
2. SPU completes 1DFFT (`SPU_RUN_1DFFTDone`) → core 1 chains to `SPU_RUN_2DFFT` and sets `g_dataSyncEventFlag = 1`.
3. Core 0's `radar_eth_client_task` wakes on the flag, reads chip temperatures, fills `measurement_header_tt`/`measurement_payload_tt` and `udp_transmit_indication_frame_tt` (sequence_number = `frameIdx`, waveId, totalSizeOfBytes, packet count using a 1450-byte UDP MTU), sends header + payload over Ethernet via `EnetDrvRte_send_data_freeRtos[_ex]()`, then clears the flag.
4. SPU output buffers (`cubeData`, `rdMapData`, `cfarObjData`, `antChannelData`, `rngFFTOutData`) live in RMEM and are exposed by `SpuDrv_GetMemAddr(SPU_Outpu_Addr_e)`.

## Code generation tools (`tools/`)

- **`tools/measurement_gen_tool/generate_eth_types.py`** — generates `Compoment/ENET_IF/radar_eth_measurement.h` (and similar `radar_eth_*` typedefs) from `measurement/measurementConfig.json` using a Jinja2 template. The naming rule is `config_name` → file `radar_eth_<config_name>.h` and header guard, and `messages[].name` → `<name>_tt` typedef. Run with `python generate_eth_types.py` (requires `pip install jinja2`). See `tools/measurement_gen_tool/README_JINJA2_GENERATOR.md` for the full schema. **If you change `measurementConfig.json`, regenerate the header before building.**
- **`tools/file_rename_tool/`** — post-build versioning (already wired into the ADS build).

## Conventions

- Header guard style: `#ifndef <FILE>_H` / `#define <FILE>_H`.
- File header block (Liujie style on internal modules):
  ```
  * File name: ...
  * Brief: ...
  * Author: ...
  * Module: ...
  * Version 1.0
  ```
  Infineon-licensed sources keep the BSL-1.0 banner — don't strip it.
- Section attributes (e.g. `__attribute__((section(".bss.sharedvar")))`) are load-bearing for cross-core variables; the linker scripts place them. Don't move such variables without checking the `.lsl` files.
- Component types are typedef'd with `_t` (or `_tt` for generator-produced UDP frame structs).
- `Compoment` is a typo but is the actual directory name and appears in include paths — do not "fix" it.
