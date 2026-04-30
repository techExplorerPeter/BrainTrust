# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CR60 Light is an automotive millimeter-wave (mmWave) radar signal processing firmware for the **AWR2X44P** (TI dual-core ARM Cortex-R5F + M4 + C66x DSP). It implements ADAS perception (object detection, range/velocity/angle processing) following the **AUTOSAR 4.3.1** architecture, targeting BYD electric vehicles.

## Build Environment Prerequisites

- **TI ARM LLVM Compiler** v3.2.2.LTS — install and set `TI_CGT_ARMLLVM` system environment variable
- **Python 3.10** + SCons 3.1.0: `pip install scons==3.1.0`
- **MinGW64** — required for unit tests; set `MINGW_ROOT` in `settings.py`
- **gcovr** — for coverage reports: `pip install gcovr`

## Build Commands

```bash
# Developer firmware build (COEM)
cd coem\BAIC_B41VS\buildscripts
.\build.bat

# Jenkins/CI firmware build
pushd coem\BAIC_B41VS\buildscripts && call patch.bat && popd
call scons_gen.bat -v BAIC_B41VS -b SERIES -d BAIC_B41VS -p KL30 -c -jenkins -sca -bc
```

Build variants are controlled via `scons_gen.bat` flags:
- Build type: `DEVELOP` / `SERIES` / `ETHDAQ`
- Power supply: `-p KL15` / `-p KL30`
- Antenna mode: `BEAMFORM` / `SYMMETRY`

## Unit Tests

Tests use **Google Test / GMock** on MinGW64. The test list is maintained in `unittest/unittest_list.json`.

```bash
# Run all unit tests (build firmware first, then tests)
scons utJsonFile=unittest/unittest_list.json

# To speed up local runs, comment out unused modules in unittest/unittest_list.json
```

Coverage report: open `build/unittest/reports/index.html` after a test run.

Each test module in `unittest_list.json` specifies `inc_path`, `src_path`, and `test_path`. Unit test files live in a `unittest/` subdirectory alongside the source they test. Test headers use `.hpp` and sources use `.cpp`.

## Architecture

The codebase is organized as a multi-core real-time system with these top-level layers:

### `bswpf/` — Basic Software Platform
AUTOSAR BSW stack: startup code, MCal drivers, RTAOS, and the `pf_Sec` security framework (secure boot, key storage, lifecycle management). This layer is largely generated/vendor-provided.

### `adas/` — ADAS Signal Processing
Two antenna variants sharing the same interface:
- `adas/beamform/` — beamforming-based DOA processing (uses `libdoa_awr2x44P` precompiled DSP library)
- `adas/symmetry/` — symmetry-based processing

Each variant contains:
- `dsp/` — DSP-side signal processing (runs on C66x)
- `algoif/` — Algorithm interface bridging MSS↔DSP (`Algo_Perception.c`, `Algo_SignalProcess.c`)
- `eDMAinterface/` — DMA transfer orchestration between cores
- `perception/` — Object detection and tracking output

### `asw/` — Application Software
Custom radar algorithms organized by function:
- `ASW_BASE` / `ASW_CORE0` — main radar processing loop
- `ASW_CALIBRATION` — online calibration
- `ASW_COM` — CAN/Ethernet communication
- `ASW_NVM` — non-volatile memory management
- `ASW_WDG` — watchdog
- `ASW_XCP` — XCP measurement/calibration protocol

### `mmwave/` — TI mmWave SDK Integration
Reference design integration for AWR2X44P. `mmw_main.c` is the top-level MSS entry point controlling the radar frame loop, ADC, mailbox communication with DSP, and monitoring.

### `rte/` + `integration/` — Runtime & System Integration
AUTOSAR RTE task scheduling (`OsTask_MMW`), ECU startup (`EcuM`), and BSW manager callbacks. This is the glue between AUTOSAR and the radar application.

### `coem/BYD_UKE/` — OEM-Specific Layer
BYD vehicle integration: CAN signal mapping, variant coding, customer-specific tuning parameters, and the `buildscripts/` that invoke SCons with the correct configuration.

### `site_scons/` — Build Tooling
Custom SCons tools: `scons_common.py`, `listfile.py`, `prebuild.py`, `scatools.py` (static analysis). The `SConstruct` dispatches to either firmware build (via `coem_scons`) or unit test build (via `utJsonFile` argument).
