# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This is a **TI mmWave SDK workspace** for the **AWR2x44P** automotive radar SoC. It is a collection of pre-integrated TI packages plus a customized multi-core radar demo application. The primary editable application lives entirely inside `mmwave_mcuplus_sdk_04_07_00_01/ti/demo/awr2x44P/mmw_ddm/`.

The five packages in the repo:

| Directory | Version | Role |
|---|---|---|
| `mmwave_mcuplus_sdk_04_07_00_01/` | 4.07.00.01 | mmWave control library, DPM, data-path algorithms, **demo app** |
| `mcu_plus_sdk_awr2x44p_10_00_00_07/` | 10.00.00.07 | Base MCU SDK — FreeRTOS, peripheral drivers, networking (LwIP, CPSW) |
| `mmwave_dfp_02_04_17_00/` | 2.04.17.00 | Device Firmware Package — radarss firmware binaries bundled into the appimage |
| `dsplib_c66x_3_4_0_0/` | 3.4.0.0 | TI DSP library for C66x |
| `mathlib_c66x_3_1_2_1/` | 3.1.2.1 | TI Math library for C66x |

## Build Environment Setup

All build tools are expected under `D:/ti` (Windows) or `~/ti` (Linux):

| Tool | Default path |
|---|---|
| CCS 12.8.1 | `D:/ti/ccs1281/ccs` |
| TI ARM Clang 3.2.2 | `$CCS/tools/compiler/ti-cgt-armllvm_3.2.2.LTS` |
| TI C6000 CGT 8.3.12 | `$CCS/tools/compiler/ti-cgt-c6000_8.3.12` |
| SysConfig 1.22.0 | `D:/ti/sysconfig_1.22.0` |

Before any make invocation, source the environment script from the demo directory:

```bash
# Linux
cd mmwave_mcuplus_sdk_04_07_00_01
source scripts/unix/setenv.sh   # sets MMWAVE_SDK_INSTALL_PATH, MCU_PLUS_AWR2X44P_INSTALL_PATH, etc.

# Windows — run from mmwave_mcuplus_sdk_04_07_00_01 directory
call scripts\windows\setenv.bat
```

> **Note:** `setenv.sh` contains a placeholder `__MMWAVE_SDK_TOOLS_INSTALL_PATH__` that must be replaced with the actual tools root (default: `D:/ti` or `~/ti`). The variable `MMWAVE_SDK_DEVICE` defaults to `awr2544`; change to `awr2x44P` for this project.

## Building the Demo

The main demo makefile is at `mmwave_mcuplus_sdk_04_07_00_01/ti/demo/awr2x44P/mmw_ddm/makefile`.

```bash
cd mmwave_mcuplus_sdk_04_07_00_01/ti/demo/awr2x44P/mmw_ddm

# Build all (MSS + DSS + CM4 binaries, then package into appimage)
make all DEV_CLASS=MASTER DEV_POS=FR PROFILE=release

# Build only signal-chain demo (DDM waveform, no Ethernet)
make mmwDemoDDM DEV_CLASS=MASTER DEV_POS=FR PROFILE=release

# Build Ethernet variant
make mmwDemoDDMEnet DEV_CLASS=MASTER DEV_POS=FR PROFILE=release

# Package appimage from already-compiled ELFs
make bin DEV_CLASS=MASTER DEV_POS=FR

# Clean
make clean

# Regenerate SysConfig files (needed after modifying .syscfg files)
make syscfg
```

**`DEV_CLASS`** — `MASTER` or `SLAVE` (sets `DEV_CLASS_VALUE` compile macro).  
**`DEV_POS`** — `FL` / `FR` / `RL` / `RR` (front/rear, left/right) → expands to `FRONT_LEFT` etc. in C macros.  
**`PROFILE`** — `release` (default) or `debug`.

Build outputs:
- `awr2x44P_mmw_demo_mssDDM.xer5f` — R5F ELF
- `awr2x44P_mmw_demo_dssDDM.xe66` — C66x ELF
- `awr2x44P_mmw_demo_dss_cm4DDM.xem4` — M4 ELF
- `awr2x44P_mmwDDM_<githash>_<DEV_CLASS>_<DEV_POS>_<suffix>.appimage` — flashable multi-core image
- `*.appimage.hs` — signed image for HS-SE devices

To build individual per-core sub-makefiles directly, navigate into `mss/`, `dss/`, or `dss_cm4/` and invoke the `.mak` file:
```bash
make -f mmw_mss.mak PROFILE=release
make -f mmw_dss.mak PROFILE=release
make -f mmw_dss_cm4.mak PROFILE=release
```

## Building MCU Plus SDK Libraries

The base peripheral and RTOS libraries (compiled separately, required before the demo build):

```bash
cd mcu_plus_sdk_awr2x44p_10_00_00_07
make -f makefile.awr2x44p libs PROFILE=release
```

Individual library targets:
```bash
make -f makefile.awr2x44p drivers_r5f.ti-arm-clang PROFILE=release
make -f makefile.awr2x44p freertos_r5f.ti-arm-clang PROFILE=release
make -f makefile.awr2x44p freertos_c66.ti-c6000 PROFILE=release
```

## Multi-Core Architecture (AWR2x44P)

The SoC has three programmable cores running asymmetrically:

| Core | Binary suffix | Role |
|---|---|---|
| R5F (MSS) | `.xer5f` | Master control: FreeRTOS tasks, CLI, mmWave control, CAN/MCAN output, Ethernet, OTA, IPC to DSP |
| C66x (DSS) | `.xe66` | Signal processing: range FFT, Doppler FFT, CFAR, AoA/DOA via HWA+EDMA, IPC to MSS |
| M4 (CM4) | `.xem4` | Coprocessor: auxiliary compute (perception pre-processing, DDM separation) |

The final appimage bundles all three core ELFs plus the radarss firmware blob at fixed core IDs:
```
MSS@0  CM4@2  DSS@1  radarss@3
```

IPC between cores uses the `ti/control/dpm/` Data Path Manager (DPM) and `ipc_mss.c` / `ipc_dss.c` glue. The DPM `Pong` (DSP) side runs the object-detection DPC; the `Ping` (MSS) side controls the sequence and receives results.

## Demo Application Structure (`mmw_ddm/`)

```
mmw_ddm/
├── makefile                  # Top-level demo makefile (DEV_CLASS, DEV_POS, PROC_CHAIN)
├── include/
│   ├── mmw_config.h          # GUI monitor selection, sensor config, CLI cfg structs
│   ├── mmw_output.h          # Output TLV type definitions sent over UART/Ethernet
│   └── radar_sys_config.h    # CAN message IDs, stack sizes
├── mss/                      # R5F source
│   ├── mss_main.c            # FreeRTOS tasks, mmWave init, DPM start
│   ├── mmw_cli.c             # CLI command parser (sensorStart/Stop, cfar params, etc.)
│   ├── mss_can_output.c      # MCAN frame packing and transmission
│   ├── ota.c / ota_uniflash.c # Over-the-air firmware update
│   ├── rf_config.c           # mmWave profile/chirp/frame config
│   ├── wf_*.c/h              # Waveform helpers (DDM, calibration, Bosch CRS)
│   ├── ipc_mss.c             # MSS-side DPM IPC callbacks
│   ├── mss.syscfg            # SysConfig for R5F (clocks, pinmux, peripherals)
│   └── mss_enet.syscfg       # SysConfig variant with Ethernet
├── dss/                      # C66x source
│   ├── dss_main.c            # DSP task, HWA trigger, result DMA to MSS
│   └── dss.syscfg
├── dss_cm4/                  # M4 source
│   ├── dss_cm4_main.c
│   └── dss_cm4.syscfg
├── perception/               # Perception library integration
├── Zelos_can_protocol/       # CAN output protocol (Zelos variant)
├── P11_can_protocol/         # CAN output protocol (P11 variant)
├── profiles/                 # .cfg radar profiles (awr2944P, awr2E44P)
└── lib/                      # Pre-built perception library archives
```

## Key Libraries in `mmwave_mcuplus_sdk_04_07_00_01/ti/`

- **`control/mmwave/`** — mmWave control driver (`mmwave.h`): open/close/start/stop sensor, calibration.
- **`control/dpm/`** — Data Path Manager: routes commands and results between MSS and DSP via IPC.
- **`datapath/dpc/objectdetection/objdethwaDDMA/`** — Object detection DPC for DDM waveform, uses HWA for range/Doppler FFT and C66x DSPLIB for CFAR/AoA.
- **`datapath/dpedma/`** — EDMA channel management for data path DMA transfers.
- **`demo/common/`** — Shared demo utilities: `mmwdemo_rfparser.c` (profile→config), `mmwdemo_monitor.c` (temperature, LVDS), `mmwdemo_board.c`.
- **`alg/`** — Algorithm primitives (MUSIC DOA, CFAR variants, angle estimation).
- **`platform/`** — SoC-level pinmux, clock, and MPU configuration.

## SysConfig

Peripheral configuration (clocks, DMA channels, interrupt routing, pinmux) is done via SysConfig `.syscfg` files. After editing a `.syscfg` file, regenerate the C source:

```bash
# From mmw_ddm/
make syscfg          # regenerates mssgenerated/, dssgenerated/, m4generated/

# Or open interactive GUI
make syscfg-gui      # opens SysConfig NW.js GUI
```

Generated files in `mssgenerated/`, `dssgenerated/`, `m4generated/` are checked in — do not edit them manually.

## Flashing

Use TI Uniflash or the SBL UART/QSPI bootloader from MCU Plus SDK. The appimage is a multi-core RPRC container. For CCS-based loading, set `DOWNLOAD_FROM_CCS=yes` in `setenv.sh`.

There is **no automated test suite**; validation is done on hardware (AWR2x44P EVM).

## Version

Demo version lives in `mmwave_mcuplus_sdk_04_07_00_01/ti/utils/sw_version.h` (`SW_MAIN_VERSION`, `SW_SUB_VERSION`, `SW_PATCH`). The makefile reads it via Python regex to embed in the release appimage filename.
