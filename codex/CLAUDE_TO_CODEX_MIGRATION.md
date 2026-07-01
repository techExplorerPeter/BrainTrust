# Claude to Codex Migration Draft

Created: 2026-07-01

This file is a migration draft from local Claude Code user-level data into Codex-friendly memory. It intentionally avoids copying credentials, account metadata, raw cache files, and full conversation transcripts.

## Source Inventory

- Claude Code user config: `C:\Users\Administrator\.claude.json`
- Claude Code user data: `C:\Users\Administrator\.claude`
- Claude Code global prompt history: `C:\Users\Administrator\.claude\history.jsonl`
- Claude Code project transcripts: `C:\Users\Administrator\.claude\projects\*\*.jsonl`
- Claude memory plugin data: `C:\Users\Administrator\.claude-mem`
- Claude desktop cache/config: `C:\Users\Administrator\AppData\Roaming\Claude`
- Claude desktop app install: `C:\Users\Administrator\AppData\Local\AnthropicClaude`

Useful counts found locally:

- `history.jsonl`: about 278 KB of global prompt history.
- `.claude\projects`: 22 JSONL transcript files across 9 project directories.
- `.claude\projects\*\memory`: 9 Markdown memory files.
- `.claude-mem`: SQLite database plus WAL files, but `sqlite3` was not available in the current shell.

## Migration Decision

Use a layered migration:

1. Keep this file as the audit trail and raw migration summary.
2. Put only stable, reusable facts into Codex memory.
3. Keep project-specific facts in the relevant project `AGENTS.md` or a project memory file.
4. Keep full historical transcripts out of Codex memory unless a specific old decision needs to be recovered.

## Codex Global Memory Candidate

The following items are suitable for global Codex memory because they describe the user's recurring work style, local environment, and durable preferences across projects.

- The user mainly works on embedded automotive radar firmware and tooling on Windows, commonly under `D:\Project`, `D:\Weifu`, and TI mmWave SDK trees.
- The user's common stack includes TI AWR2x44P / mmWave MCU+ SDK, FreeRTOS, CAN/CAN-FD diagnostics, SysConfig, CCS/gmake, R5F/CM4/DSP firmware, and Python parser/packaging tools.
- Prefer concrete local inspection and build verification over speculative advice.
- When dealing with old Claude history, do not import everything verbatim. Extract durable facts, commands, constraints, and resolved debugging conclusions.
- Be careful with Windows shell behavior. Some build scripts depend on running from the expected directory and on `cmd` resolving batch files from the current directory.
- The user often wants end-to-end execution: inspect, edit, build/test, then summarize exact results.

## Project Memory Candidates

These are project-specific memories that should usually live in project-level `AGENTS.md` or a project memory file, not global Codex memory.

### zelos_repo / mmwave_mcuplus_sdk

- Standard full-package build entry is `mmwave_mcuplus_sdk_04_07_00_01\complier.bat` (spelled `complier`, not `compiler`).
- `complier.bat` internally sets SDK/CCS/SysConfig paths, rebuilds DPU and CLI/mmwave libraries, regenerates DBC C code, runs clean/build for `mmwDemoDDM`, and packages via ImageGen.
- On this machine, SysConfig is `D:\ti\sysconfig_1.23.0`; CCS is `D:\ti\ccs1281`.
- In Codex/PowerShell sandbox context, `NoDefaultCurrentDirectoryInExePath` can break batch-file lookup from current directory. If a batch file internally calls another batch file, prefer explicit paths or clear that environment variable for the invoked `cmd`.
- Incremental build for comparison workspace has used `D:\Weifu\git\compare\build_dbg.bat`.
- MSS L2 memory is tight; large new buffers or task stacks may need TCMB RAM sections.

### TimeSync / CAN-FD

- Domain controller TimeSync CAN IDs are `0x40` FR, `0x41` FL, `0x42` RL, `0x43` RR.
- Radar-side CRC algorithm is CRC-16/CCITT-FALSE, poly `0x1021`, init `0xFFFF`, calculated over Byte2..Byte15.
- A previous domain-controller issue produced constant per-ID CRC fields while timestamp/counter bytes changed. Radar code correctly rejected those frames; the fix belongs on the domain-controller side.
- Temporary radar workaround for domain-controller bad CRC: disable or relax `WF_TIME_SYNC_CRC_CHECK_ENABLE`, then re-enable once the controller is fixed.
- Cold-start no-RX/no-TimeSync issue was traced to a FreeRTOS init-order race: CAN RX task could process a TimeSync frame before `wf_time_sync_init()` completed. The fix used a `wfTimeSyncInited` guard in `wf_time_sync.c` to drop early frames.

### GPADC Radar Position Detection

- Radar mounting-position detection uses GPADC external channels MR2/adc6 and MR1/adc5 in `mss_main.c`.
- `gpadc_result[0]` is intentionally mapped to adc6/front-back and `gpadc_result[1]` to adc5/left-right.
- `RAISE_EDGE=100` was too low for measured adc5 GND around 136 and OPEN around 828; threshold should be around 400 after hardware confirmation.
- SysConfig regeneration must include MSS + DSS + DSS CM4 scripts in the same call to avoid broken IPC `gIpcSharedMem[]`/vring generation.

### DebugInfo / SystemInfo

- CAN debugInfo design used CAN-FD standard frame `0x200`, 64 bytes, 66 ms period, and 4 rotating pages.
- Common pages: timing, data path/RF, TimeSync/CAN health, blackbox/stack/reset information.
- Tail CRC is CRC16/CCITT-FALSE.
- `interFrameProcessingMargin` and similar TI stats fields may be dead/unreliable in this project; use explicit timing records when judging overruns.
- Blackbox/noinit data in TCMB may not survive if SBL/ECC initialization clears TCM; verify on hardware.
- Later debuginfo work included parsing `0x200/0x201` and FR `0x202/0x203` dual-radar outputs on a combined CAN line.

### Security / Boot / ProductionSW History

- Older Claude global history includes work on CR production software, container signing/encryption, RustApp/CLDA/BM modules, keys under `tools/Security/localCR_DevKeys`, and reset/watchdog behavior around `Clear_PRODUCTIONSW_Start`.
- These should not be treated as fully migrated yet. Recover details only from the specific project transcript when needed.

### MCP / Local Knowledge

- Older Claude global history includes setup/debugging of MCP servers and a local docs MCP concept for ARM A53 official PDF/manual search.
- The user previously used or investigated `claude-mem`.
- `.claude-mem` exists locally, but SQLite extraction still needs a usable SQLite client or another reader.

## Not Migrated

- OAuth/account details from `.claude.json`.
- Claude cache, telemetry, desktop browser cache, plugin dependencies, and credentials.
- Full raw prompt history and pasted content.
- Large transcript bodies, unless a specific decision/debug conclusion is requested.

## Recommended Next Step

If this draft looks right, merge only `Codex Global Memory Candidate` into the Codex global instruction/memory location, and merge the `zelos_repo`-specific sections into this repository's `AGENTS.md`.
