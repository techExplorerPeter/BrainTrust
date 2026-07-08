# FlexFlowFlash Agent Flash Tool

This document describes how an agent should use the standalone FlexFlowFlash
wrapper to flash the radar ECU firmware.

## Purpose

`flexflow_flash.py` is a small agent-facing wrapper around the local
FlexFlowFlash command-line mode. It lets an agent trigger the same flash flow
that was previously performed manually in the FlexFlowFlash UI.

The wrapper does not implement UDS, seed/key, CAN transport, erase, download, or
CRC logic. Those behaviors remain owned by FlexFlowFlash and the existing flash
project CSV.

## Files

Installed agent copy:

```text
C:\Users\Administrator\.codex\tools\flexflow_flash.py
C:\Users\Administrator\.codex\tools\flexflow-flash.cmd
```

Project copy:

```text
D:\Project\CR\Project\NotimeSync\debuginfo\zelos_repo\scripts\flexflow_flash.py
D:\Project\CR\Project\NotimeSync\debuginfo\zelos_repo\scripts\flexflow-flash.cmd
```

## External Dependencies

The Python wrapper itself only uses the Python standard library.

Required local tools and files:

```text
C:\Users\Administrator\Downloads\九识软件烧录\FlexFlowFlash__1_0_4_1_win\FlexFlowFlash.exe
C:\Users\Administrator\Downloads\九识软件烧录\1M_CUSTOMER_APP烧录_fffash\CR60Light_SGMW_PF_FBL.csv
C:\Users\Administrator\Downloads\九识软件烧录\1M_CUSTOMER_APP烧录_fffash\mss_dss_rss_h_1M_padding.hex
```

Hardware/runtime requirements:

```text
Kvaser CAN driver installed
Kvaser Leaf v3 connected
DUT powered and connected to CAN
FlexFlowFlash GUI not occupying the same CAN device
```

## Default Behavior

Running the wrapper with no arguments executes:

```text
FlexFlowFlash.exe --cmdLine --projectpath <fixed project CSV> --logfolder <log dir>
```

The fixed project CSV references:

```text
mss_dss_rss_h_1M_padding.hex
```

So the agent must ensure the desired firmware image has already been copied to:

```text
C:\Users\Administrator\Downloads\九识软件烧录\1M_CUSTOMER_APP烧录_fffash\mss_dss_rss_h_1M_padding.hex
```

## Commands

Dry run. This does not flash. Use it to inspect the exact command:

```powershell
python C:\Users\Administrator\.codex\tools\flexflow_flash.py --dry-run
```

Flash using the installed standalone script:

```powershell
python C:\Users\Administrator\.codex\tools\flexflow_flash.py
```

Flash using the installed command wrapper:

```powershell
C:\Users\Administrator\.codex\tools\flexflow-flash.cmd
```

Flash from the firmware project checkout:

```powershell
python scripts\flexflow_flash.py
```

## Options

```text
--dry-run
    Print the FlexFlowFlash command and exit without flashing.

--exe <path>
    Override the FlexFlowFlash.exe path.

--project-dir <path>
    Override the flash project directory.

--hex-file <path>
    Override the hex file path. The default is mss_dss_rss_h_1M_padding.hex
    in the fixed flash project directory.

--log-dir <path>
    Override wrapper/FlexFlowFlash log folder. Relative paths resolve under the
    detected workspace root when possible, otherwise under the current directory.

--use-source
    Use D:\Weifu\Project\flexflowflash_fff\src\main.py --agentFlash instead of
    packaged FlexFlowFlash.exe. Do not use this unless the Python environment
    has all FlexFlowFlash runtime dependencies installed.
```

## Environment Overrides

```text
FLEXFLOW_TOOL_ROOT
    Overrides C:\Users\Administrator\Downloads\九识软件烧录

FLEXFLOW_EXE
    Overrides the FlexFlowFlash.exe path.

FLEXFLOW_SOURCE_ROOT
    Overrides D:\Weifu\Project\flexflowflash_fff for --use-source mode.
```

## Return Codes

```text
0
    FlexFlowFlash process completed successfully.

2
    Local wrapper validation failed, such as missing exe, project CSV, or hex.

other nonzero
    FlexFlowFlash.exe returned an error. Treat as infrastructure/flash failure.
```

## Important Safety Rules For Agents

1. Do not modify the flash project CSV to make flashing appear successful.
2. Do not modify seed/key DLLs, UDS security access parameters, bootloader files,
   linker scripts, secure boot configuration, crypto constants, or key material.
3. Do not treat flash success as firmware test PASS.
4. Functional PASS/FAIL must still come from `logs/result_latest.json`.
5. If flashing fails, report it as a flash/infrastructure failure and do not
   infer DUT behavior from partial logs.
6. Use `--dry-run` before first use on a new machine or changed path setup.

## Known Good Flash Evidence

Manual standalone invocation was verified on 2026-07-08:

```powershell
python flexflow_flash.py
```

The wrapper launched FlexFlowFlash command-line mode, loaded Kvaser CAN,
connected to the device, executed erase/download/CRC/customer flag/reset steps,
and FlexFlowFlash reported:

```text
Process completed successfully.
Log saved to: log_idx1_20260708_082618.csv
flexflow_flash: completed successfully
```

The flash project itself performed `step20_ecuReset`, so an additional reset
step is normally not required immediately after flashing.

## Agent Integration Pattern

For a build-flash-test loop:

1. Build firmware.
2. Copy the generated `mss_dss_rss_h_1M_padding.hex` into the fixed flash
   project directory.
3. Run:

```powershell
python C:\Users\Administrator\.codex\tools\flexflow_flash.py
```

4. If the command returns nonzero, stop and report flash infrastructure failure.
5. If the command returns 0, proceed to CAN capture and JSON judging.
6. Decide PASS/FAIL only from `logs/result_latest.json`.

