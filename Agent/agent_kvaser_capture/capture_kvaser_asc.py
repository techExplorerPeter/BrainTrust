"""Capture Kvaser CAN/CAN FD traffic and save it as a Vector ASC log."""

from __future__ import annotations

import argparse
import configparser
import contextlib
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import can  # noqa: E402


VALID_CLASSIC_LENGTHS = set(range(0, 9))
VALID_FD_LENGTHS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64}
STOP_REQUESTED = False


@dataclass(frozen=True)
class TxFrame:
    can_id: int
    data: bytes
    is_fd: bool | None = None
    length: int | None = None
    bitrate_switch: bool | None = None


def parse_can_id(value: str) -> int:
    try:
        can_id = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid CAN ID '{value}', use forms like 0x123 or 291"
        ) from exc
    if not 0 <= can_id <= 0x1FFFFFFF:
        raise argparse.ArgumentTypeError(
            f"CAN ID '{value}' is out of range, expected 0x0..0x1FFFFFFF"
        )
    return can_id


def parse_hex_data(value: str) -> bytes:
    compact_data = value.replace(" ", "").replace("_", "")
    if len(compact_data) % 2 != 0:
        raise argparse.ArgumentTypeError("TX data must contain full hex bytes")
    try:
        return bytes.fromhex(compact_data)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid TX data '{value}', use hex bytes"
        ) from exc


def parse_tx_mode(value: str) -> bool:
    normalized = value.strip().lower().replace("-", "")
    if normalized in {"can", "classic", "classiccan"}:
        return False
    if normalized in {"fd", "canfd"}:
        return True
    raise argparse.ArgumentTypeError("TX mode must be can or canfd")


def parse_tx_frame(value: str) -> TxFrame:
    if "," in value:
        parts = [part.strip() for part in value.split(",")]
        if len(parts) not in {4, 5}:
            raise argparse.ArgumentTypeError(
                "invalid TX frame, use CAN_ID,can|canfd,LEN,DATA[,brs|no-brs]"
            )
        can_id = parse_can_id(parts[0])
        is_fd = parse_tx_mode(parts[1])
        try:
            length = int(parts[2], 0)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("TX length must be an integer") from exc
        data = parse_hex_data(parts[3])
        bitrate_switch = None
        if len(parts) == 5:
            brs_text = parts[4].strip().lower().replace("-", "")
            if brs_text in {"brs", "true", "1", "yes"}:
                bitrate_switch = True
            elif brs_text in {"nobrs", "false", "0", "no"}:
                bitrate_switch = False
            else:
                raise argparse.ArgumentTypeError("TX BRS option must be brs or no-brs")
        return TxFrame(
            can_id=can_id,
            data=data,
            is_fd=is_fd,
            length=length,
            bitrate_switch=bitrate_switch,
        )

    if "#" in value:
        can_id_text, data_text = value.split("#", 1)
    elif ":" in value:
        can_id_text, data_text = value.split(":", 1)
    else:
        raise argparse.ArgumentTypeError(
            "invalid TX frame, use CAN_ID#DATA or CAN_ID:DATA, "
            "for example 0x123#021003"
        )

    can_id = parse_can_id(can_id_text)
    return TxFrame(can_id=can_id, data=parse_hex_data(data_text))


def build_filters(can_ids: list[int] | None) -> list[dict[str, int | bool]] | None:
    if not can_ids:
        return None
    return [
        {
            "can_id": can_id,
            "can_mask": 0x1FFFFFFF if can_id > 0x7FF else 0x7FF,
            "extended": can_id > 0x7FF,
        }
        for can_id in can_ids
    ]


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "logs" / f"kvaser_radar_{timestamp}.asc"


def sanitize_filename_part(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if char in invalid_chars else char for char in value)
    sanitized = "_".join(sanitized.split())
    sanitized = sanitized.strip("._ ")
    return sanitized or "capture"


def build_output_path(output: Path | None, output_dir: Path, test_name: str | None) -> Path:
    if output is not None:
        return normalize_output_path(output)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = sanitize_filename_part(test_name) if test_name else "kvaser_radar"
    return normalize_output_path(output_dir / f"{prefix}_{timestamp}.asc")


def normalize_output_path(path: Path) -> Path:
    if path.suffix == "":
        return path.with_suffix(".asc")
    if path.suffix.lower() != ".asc":
        raise ValueError("output file must use the .asc suffix")
    return path


def resolve_package_path(path: Path | None) -> Path | None:
    if path is None or path.is_absolute():
        return path
    return REPO_ROOT / path


def validate_numeric_args(args: argparse.Namespace) -> None:
    if args.channel < 0:
        raise ValueError("channel must be >= 0")
    if args.bitrate <= 0:
        raise ValueError("bitrate must be > 0")
    if args.data_bitrate <= 0:
        raise ValueError("data_bitrate must be > 0")
    if args.duration < 0:
        raise ValueError("duration must be >= 0")
    if args.max_frames < 0:
        raise ValueError("max_frames must be >= 0")
    if args.idle_timeout < 0:
        raise ValueError("idle_timeout must be >= 0")
    if args.timeout <= 0:
        raise ValueError("timeout must be > 0")
    if args.tx_delay < 0:
        raise ValueError("tx_delay must be >= 0")
    if args.tx_period < 0:
        raise ValueError("tx_period must be >= 0")
    if args.tx_count < 0:
        raise ValueError("tx_count must be >= 0")
    if args.print_every < 0:
        raise ValueError("print_every must be >= 0")
    if args.flush_every < 0:
        raise ValueError("flush_every must be >= 0")
    if args.flush_period < 0:
        raise ValueError("flush_period must be >= 0")
    if args.max_file_size < 0:
        raise ValueError("max_file_size must be >= 0")


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config_file(path: Path) -> dict[str, int | bool | str]:
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    if "configs" not in config:
        raise ValueError(f"{path} does not contain a [configs] section")

    section = config["configs"]
    loaded: dict[str, int | bool | str] = {}
    if "interface" in section:
        loaded["interface"] = section["interface"]
    if "channel" in section:
        loaded["channel"] = int(section["channel"], 0)
    if "bitrate" in section:
        loaded["bitrate"] = int(section["bitrate"], 0)
    if "data_bitrate" in section:
        loaded["data_bitrate"] = int(section["data_bitrate"], 0)
    if "fd" in section:
        loaded["fd"] = parse_bool(section["fd"])
    return loaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record radar frames from a Kvaser CAN/CAN FD channel to ASC."
    )
    parser.add_argument("-c", "--channel", type=int, default=None, help="Kvaser channel index.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Read CAN settings from a project configs.ini [configs] section.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="ASC output path. Defaults to <output-dir>/<test-name>_<timestamp>.asc.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "logs",
        help="Directory used for automatic ASC names when --output is not set.",
    )
    parser.add_argument(
        "--test-name",
        help="Test name used in the automatic ASC filename.",
    )
    parser.add_argument(
        "--stop-file",
        type=Path,
        help="Gracefully stop capture when this file exists. Stale files are removed at startup.",
    )
    parser.add_argument(
        "--ready-file",
        type=Path,
        help="Write JSON metadata after capture starts, including pid and output path.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=0,
        help="Capture duration in seconds. Use 0 to run until Ctrl+C.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Stop after this many received frames. Use 0 to disable.",
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=0,
        help="Stop if no frame is received for this many seconds. Use 0 to disable.",
    )
    parser.add_argument(
        "--rx-id",
        action="append",
        type=parse_can_id,
        help="Optional CAN ID filter. Repeat for multiple IDs, for example --rx-id 0x100.",
    )
    parser.add_argument(
        "--tx",
        action="append",
        type=parse_tx_frame,
        help=(
            "Transmit a trigger frame. Repeat for multiple frames. "
            "Formats: CAN_ID#DATA, or CAN_ID,can|canfd,LEN,DATA[,brs|no-brs]. "
            "Example: --tx 0x123,canfd,64,021003,brs."
        ),
    )
    parser.add_argument(
        "--tx-delay",
        type=float,
        default=0,
        help="Delay in seconds before the first TX round.",
    )
    parser.add_argument(
        "--tx-period",
        type=float,
        default=0,
        help="Repeat TX frames every N seconds. Use 0 for one-shot TX.",
    )
    parser.add_argument(
        "--tx-count",
        type=int,
        default=1,
        help="Number of TX rounds. Use 0 for unlimited periodic TX.",
    )
    parser.add_argument(
        "--tx-no-brs",
        action="store_true",
        help="For CAN FD TX frames, disable bitrate switch.",
    )
    parser.add_argument(
        "--print-every",
        type=int,
        default=1000,
        help="Print one frame/status line every N logged events. Use 1 for every frame, 0 to suppress frame lines.",
    )
    parser.add_argument(
        "--flush-every",
        type=int,
        default=100,
        help="Flush ASC data after this many logged events. Use 0 to disable count-based flushing.",
    )
    parser.add_argument(
        "--flush-period",
        type=float,
        default=5.0,
        help="Flush ASC data at least every N seconds while traffic is flowing. Use 0 to disable time-based flushing.",
    )
    parser.add_argument(
        "--fsync",
        action="store_true",
        help="Call os.fsync() on each flush. This is safer on power loss but can reduce throughput.",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=0,
        help="Rotate ASC files after this many bytes. Use 0 to keep a single output file.",
    )
    parser.add_argument("--timeout", type=float, default=1.0, help="Receive timeout in seconds.")
    parser.add_argument("--bitrate", type=int, default=None, help="Nominal bitrate.")
    parser.add_argument("--data-bitrate", type=int, default=None, help="CAN FD data bitrate.")
    parser.add_argument(
        "--fd",
        dest="fd",
        action="store_true",
        default=None,
        help="Use CAN FD mode. Overrides configs.ini fd setting.",
    )
    parser.add_argument(
        "--classic-can",
        dest="fd",
        action="store_false",
        help="Use classic CAN mode instead of CAN FD.",
    )
    return parser.parse_args()


def make_tx_message(
    frame: TxFrame,
    default_is_fd: bool,
    default_bitrate_switch: bool,
) -> can.Message:
    is_fd = default_is_fd if frame.is_fd is None else frame.is_fd
    bitrate_switch = (
        default_bitrate_switch
        if frame.bitrate_switch is None
        else frame.bitrate_switch
    )
    length = len(frame.data) if frame.length is None else frame.length

    valid_lengths = VALID_FD_LENGTHS if is_fd else VALID_CLASSIC_LENGTHS
    if length not in valid_lengths:
        mode = "CAN FD" if is_fd else "classic CAN"
        raise ValueError(f"{mode} TX length {length} is not a valid DLC payload length")
    if len(frame.data) > length:
        raise ValueError("TX data is longer than the specified TX length")

    data = frame.data.ljust(length, b"\x00")

    if not is_fd and len(data) > 8:
        raise ValueError("classic CAN TX data must be 8 bytes or less")
    if is_fd and len(data) > 64:
        raise ValueError("CAN FD TX data must be 64 bytes or less")
    return can.Message(
        arbitration_id=frame.can_id,
        data=data,
        is_extended_id=frame.can_id > 0x7FF,
        is_fd=is_fd,
        bitrate_switch=bitrate_switch if is_fd else False,
        is_rx=False,
        timestamp=time.time(),
    )


def validate_tx_frames(
    tx_frames: list[TxFrame],
    bus_is_fd: bool,
    default_bitrate_switch: bool,
) -> None:
    for frame in tx_frames:
        if frame.is_fd and not bus_is_fd:
            raise ValueError(
                "TX frame requests CAN FD, but the bus is configured as classic CAN"
            )
        make_tx_message(frame, bus_is_fd, default_bitrate_switch)


def send_tx_round(
    bus: can.BusABC,
    logger: can.Listener,
    tx_frames: list[TxFrame],
    is_fd: bool,
    bitrate_switch: bool,
    print_every: int,
    event_count: int,
) -> int:
    sent = 0
    for frame in tx_frames:
        msg = make_tx_message(frame, is_fd, bitrate_switch)
        bus.send(msg)
        logger(msg)
        sent += 1
        event_count += 1
        maybe_print_frame("TX", event_count, msg, print_every)
    return sent


def maybe_print_frame(prefix: str, event_count: int, msg: can.Message, print_every: int) -> None:
    if print_every <= 0 or event_count % print_every != 0:
        return
    print(
        f"{prefix:<2} {event_count:>8} "
        f"{msg.timestamp:.6f} "
        f"{'FD' if msg.is_fd else 'CAN'} "
        f"{msg.arbitration_id:08X} "
        f"{msg.data.hex(' ').upper()}"
    )


def get_logger_file(logger: can.Listener):
    writer = getattr(logger, "writer", logger)
    return getattr(writer, "file", None)


def flush_logger(logger: can.Listener, force_fsync: bool = False) -> None:
    file_obj = get_logger_file(logger)
    if file_obj is None:
        return
    file_obj.flush()
    if force_fsync:
        os.fsync(file_obj.fileno())


def create_logger(output: Path, max_file_size: int) -> can.Listener:
    if max_file_size > 0:
        return can.SizedRotatingLogger(
            base_filename=str(output),
            max_bytes=max_file_size,
        )
    return can.Logger(str(output))


def log_marker_event(logger: can.Listener, message: str, timestamp: float | None = None) -> None:
    writer = getattr(logger, "writer", logger)
    log_event = getattr(writer, "log_event", None)
    if callable(log_event):
        log_event(message, time.time() if timestamp is None else timestamp)


def request_stop(signum, _frame) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"Stop requested by signal {signum}.")


def setup_signal_handlers() -> None:
    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signum = getattr(signal, signal_name, None)
        if signum is not None:
            with contextlib.suppress(ValueError):
                signal.signal(signum, request_stop)


def prepare_stop_file(stop_file: Path | None) -> None:
    if stop_file is None:
        return
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    if stop_file.exists():
        stop_file.unlink()


def cleanup_stop_file(stop_file: Path | None) -> None:
    if stop_file is not None and stop_file.exists():
        with contextlib.suppress(OSError):
            stop_file.unlink()


def stop_file_requested(stop_file: Path | None) -> bool:
    return stop_file is not None and stop_file.exists()


def write_ready_file(path: Path | None, output: Path, stop_file: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "output": str(output),
        "stop_file": str(stop_file) if stop_file else None,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def should_flush(
    logged_events: int,
    last_flush_events: int,
    last_flush_time: float,
    flush_every: int,
    flush_period: float,
) -> bool:
    if flush_every > 0 and logged_events - last_flush_events >= flush_every:
        return True
    if flush_period > 0 and time.monotonic() - last_flush_time >= flush_period:
        return True
    return False


def main() -> int:
    global STOP_REQUESTED
    STOP_REQUESTED = False
    setup_signal_handlers()
    args = parse_args()
    args.config = resolve_package_path(args.config)
    args.output = resolve_package_path(args.output)
    args.output_dir = resolve_package_path(args.output_dir)
    args.ready_file = resolve_package_path(args.ready_file)
    args.stop_file = resolve_package_path(args.stop_file)
    loaded: dict[str, int | bool | str] = {}
    if args.config:
        loaded = load_config_file(args.config)
        interface = str(loaded.get("interface", "kvaser")).lower()
        if interface and interface != "kvaser":
            raise ValueError(f"unsupported interface '{interface}', expected 'kvaser'")

    args.channel = args.channel if args.channel is not None else loaded.get("channel", 0)
    args.bitrate = args.bitrate if args.bitrate is not None else loaded.get("bitrate", 500000)
    args.data_bitrate = (
        args.data_bitrate
        if args.data_bitrate is not None
        else loaded.get("data_bitrate", 2000000)
    )
    args.fd = args.fd if args.fd is not None else loaded.get("fd", True)

    validate_numeric_args(args)
    tx_frames = args.tx or []
    validate_tx_frames(tx_frames, args.fd, not args.tx_no_brs)
    args.output = build_output_path(args.output, args.output_dir, args.test_name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prepare_stop_file(args.stop_file)

    bus_config = {
        "interface": "kvaser",
        "channel": args.channel,
        "bitrate": args.bitrate,
        "fd": args.fd,
        "can_filters": build_filters(args.rx_id),
    }
    if args.fd:
        bus_config["data_bitrate"] = args.data_bitrate

    count = 0
    sent_count = 0
    logged_events = 0
    tx_rounds_done = 0

    bus = None
    logger = None
    try:
        capture_start_time = time.time()
        bus = can.interface.Bus(**bus_config)
        logger = create_logger(args.output, args.max_file_size)
        log_marker_event(logger, "Capture started", capture_start_time)
        write_ready_file(args.ready_file, args.output, args.stop_file)

        print(
            f"Recording Kvaser {'CAN FD' if args.fd else 'classic CAN'}: "
            f"channel={args.channel}, fd={args.fd}, bitrate={args.bitrate}, "
            f"data_bitrate={args.data_bitrate if args.fd else 'n/a'}, output={args.output}"
        )
        print(
            f"Console frame output: every {args.print_every} event(s)"
            if args.print_every > 0
            else "Console frame output: disabled"
        )
        if args.ready_file:
            print(f"Ready file: {args.ready_file}")
        stop_hints = []
        if args.duration > 0:
            stop_hints.append(f"duration={args.duration}s")
        else:
            stop_hints.append("Ctrl+C")
        if args.stop_file:
            stop_hints.append(f"create stop file: {args.stop_file}")
        print("Stop condition: " + " or ".join(stop_hints) + ".")

        end_time = None if args.duration == 0 else time.monotonic() + args.duration
        last_frame_time = time.monotonic()
        last_flush_time = time.monotonic()
        last_flush_events = 0
        next_tx_time = None
        if tx_frames:
            next_tx_time = time.monotonic() + args.tx_delay

        while not STOP_REQUESTED and (end_time is None or time.monotonic() < end_time):
            if stop_file_requested(args.stop_file):
                print(f"Stop file detected: {args.stop_file}")
                break
            now = time.monotonic()
            if next_tx_time is not None and now >= next_tx_time:
                sent_now = send_tx_round(
                    bus,
                    logger,
                    tx_frames,
                    args.fd,
                    not args.tx_no_brs,
                    args.print_every,
                    logged_events,
                )
                sent_count += sent_now
                logged_events += sent_now
                if sent_now > 0 and should_flush(
                    logged_events,
                    last_flush_events,
                    last_flush_time,
                    args.flush_every,
                    args.flush_period,
                ):
                    flush_logger(logger, force_fsync=args.fsync)
                    last_flush_time = time.monotonic()
                    last_flush_events = logged_events
                tx_rounds_done += 1
                if args.tx_period > 0 and (
                    args.tx_count == 0 or tx_rounds_done < args.tx_count
                ):
                    next_tx_time = now + args.tx_period
                else:
                    next_tx_time = None

            recv_timeout = args.timeout
            if next_tx_time is not None:
                recv_timeout = min(recv_timeout, max(next_tx_time - time.monotonic(), 0))

            msg = bus.recv(recv_timeout)
            if msg is None:
                if stop_file_requested(args.stop_file):
                    print(f"Stop file detected: {args.stop_file}")
                    break
                if args.idle_timeout > 0 and time.monotonic() - last_frame_time >= args.idle_timeout:
                    print(f"No frame received for {args.idle_timeout}s, stopping.")
                    break
                continue
            last_frame_time = time.monotonic()
            logger(msg)
            count += 1
            logged_events += 1
            maybe_print_frame("RX", logged_events, msg, args.print_every)
            if should_flush(
                logged_events,
                last_flush_events,
                last_flush_time,
                args.flush_every,
                args.flush_period,
            ):
                flush_logger(logger, force_fsync=args.fsync)
                last_flush_time = time.monotonic()
                last_flush_events = logged_events
            if args.max_frames > 0 and count >= args.max_frames:
                print(f"Reached max frame count {args.max_frames}, stopping.")
                break
    except KeyboardInterrupt:
        print("\nCapture stopped by user.")
    finally:
        if logger is not None:
            with contextlib.suppress(Exception):
                log_marker_event(logger, f"Capture stopped: rx={count}, tx={sent_count}")
            with contextlib.suppress(Exception):
                flush_logger(logger, force_fsync=True)
            with contextlib.suppress(Exception):
                logger.stop()
        if bus is not None:
            with contextlib.suppress(Exception):
                bus.shutdown()
        cleanup_stop_file(args.stop_file)

    print(f"Saved {count} RX frame(s) and {sent_count} TX frame(s) to {args.output}")
    return 0


def cli() -> int:
    try:
        return main()
    except (ValueError, can.CanError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
