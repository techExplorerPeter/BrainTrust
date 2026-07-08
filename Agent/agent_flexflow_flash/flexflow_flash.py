#!/usr/bin/env python3
"""Run FlexFlowFlash through the agent-controlled command-line entry."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


HEX_NAME = "mss_dss_rss_h_1M_padding.hex"
PROJECT_FILE_NAME = "CR60Light_SGMW_PF_FBL.csv"
DEFAULT_SOURCE_ROOT = Path(r"D:\Weifu\Project\flexflowflash_fff")
WORKSPACE_MARKERS = ("mmwave_mcuplus_sdk_04_07_00_01", ".git")


def burn_word() -> str:
    return chr(0x70E7) + chr(0x5F55)


def tool_root_name() -> str:
    return chr(0x4E5D) + chr(0x8BC6) + chr(0x8F6F) + chr(0x4EF6) + burn_word()


def default_tool_root() -> Path:
    configured = os.getenv("FLEXFLOW_TOOL_ROOT")
    if configured:
        return Path(configured)
    return Path.home() / "Downloads" / tool_root_name()


def default_project_dir() -> Path:
    return default_tool_root() / ("1M_CUSTOMER_APP" + burn_word() + "_fffash")


def default_exe() -> Path:
    return default_tool_root() / "FlexFlowFlash__1_0_4_1_win" / "FlexFlowFlash.exe"


def find_workspace_root() -> Path:
    starts = [Path.cwd(), Path(__file__).resolve().parent]
    for start in starts:
        candidates = [start, *start.parents]
        for candidate in candidates:
            if any((candidate / marker).exists() for marker in WORKSPACE_MARKERS):
                return candidate
    return Path.cwd()


def build_command(args) -> tuple[list[str], Path]:
    project_dir = Path(args.project_dir or default_project_dir())
    hex_file = Path(args.hex_file or project_dir / HEX_NAME)
    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = find_workspace_root() / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    if not project_dir.is_dir():
        raise FileNotFoundError(f"FlexFlowFlash project directory not found: {project_dir}")
    if not (project_dir / PROJECT_FILE_NAME).is_file():
        raise FileNotFoundError(f"FlexFlowFlash project file not found: {project_dir / PROJECT_FILE_NAME}")
    if not hex_file.is_file():
        raise FileNotFoundError(f"FlexFlowFlash hex file not found: {hex_file}")

    source_root = Path(args.source_root or os.getenv("FLEXFLOW_SOURCE_ROOT") or DEFAULT_SOURCE_ROOT)
    source_main = source_root / "src" / "main.py"
    if args.use_source and source_main.is_file():
        cmd = [
            sys.executable,
            str(source_main),
            "--agentFlash",
            "--agentProjectDir",
            str(project_dir),
            "--agentHexFile",
            str(hex_file),
            "--agentDataLogFolder",
            str(project_dir / "data_logs"),
            "--logFolder",
            str(log_dir.resolve()),
        ]
        return cmd, source_root / "src"

    exe = Path(args.exe or os.getenv("FLEXFLOW_EXE") or default_exe())
    if not exe.is_file():
        raise FileNotFoundError(f"FlexFlowFlash executable not found: {exe}")
    project_file = project_dir / PROJECT_FILE_NAME
    cmd = [
        str(exe),
        "--cmdLine",
        "--projectpath",
        str(project_file),
        "--logfolder",
        str(log_dir.resolve()),
    ]
    return cmd, exe.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", help="FlexFlowFlash source root")
    parser.add_argument("--exe", help="Path to packaged FlexFlowFlash.exe")
    parser.add_argument("--project-dir", help="FlexFlowFlash project directory")
    parser.add_argument("--hex-file", help="Hex file used by the fixed flash project")
    parser.add_argument("--log-dir", default="logs/flexflow", help="Folder for FlexFlowFlash logs")
    parser.add_argument("--use-source", action="store_true", help="Use source checkout instead of packaged exe")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without running flash")
    args = parser.parse_args()

    try:
        cmd, cwd = build_command(args)
    except Exception as exc:
        print(f"flexflow_flash: {exc}", file=sys.stderr)
        return 2

    print("flexflow_flash: running " + " ".join(f'"{p}"' if " " in p else p for p in cmd))
    if args.dry_run:
        return 0

    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        print(f"flexflow_flash: failed with exit code {completed.returncode}", file=sys.stderr)
        return completed.returncode

    print("flexflow_flash: completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
