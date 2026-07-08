"""Request a running capture_kvaser_asc.py process to stop gracefully."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_package_path(path: Path | None) -> Path | None:
    if path is None or path.is_absolute():
        return path
    return SCRIPT_DIR / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the stop file used by capture_kvaser_asc.py."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--ready-file",
        type=Path,
        help="Ready JSON written by capture_kvaser_asc.py.",
    )
    source.add_argument(
        "--stop-file",
        type=Path,
        help="Stop file path passed to capture_kvaser_asc.py.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=0,
        help="Seconds to wait until the capture process removes the stop file.",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=0.2,
        help="Polling interval while waiting.",
    )
    return parser.parse_args()


def load_stop_file_from_ready(path: Path) -> tuple[Path, str | None]:
    if not path.exists():
        raise ValueError(
            f"ready file not found: {path}. Start capture with "
            f"--ready-file {path} and --stop-file <path> first."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    stop_file = payload.get("stop_file")
    if not stop_file:
        raise ValueError(f"{path} does not contain a stop_file value")
    output = payload.get("output")
    return Path(stop_file), str(output) if output else None


def request_stop(stop_file: Path) -> None:
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.write_text(
        f"stop requested at {datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )


def wait_until_stopped(stop_file: Path, timeout: float, poll: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not stop_file.exists():
            return True
        time.sleep(max(poll, 0.05))
    return not stop_file.exists()


def main() -> int:
    args = parse_args()
    args.ready_file = resolve_package_path(args.ready_file)
    args.stop_file = resolve_package_path(args.stop_file)
    if args.wait < 0:
        raise ValueError("--wait must be >= 0")
    if args.poll <= 0:
        raise ValueError("--poll must be > 0")

    output = None
    if args.ready_file is not None:
        stop_file, output = load_stop_file_from_ready(args.ready_file)
    else:
        stop_file = args.stop_file

    request_stop(stop_file)
    print(f"Stop requested: {stop_file}")
    if output:
        print(f"Capture output: {output}")

    if args.wait > 0:
        if not wait_until_stopped(stop_file, args.wait, args.poll):
            print(
                f"ERROR: capture did not acknowledge stop within {args.wait}s",
                file=sys.stderr,
            )
            return 3
        print("Capture stopped and stop file was cleaned up.")
    return 0


def cli() -> int:
    try:
        return main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
