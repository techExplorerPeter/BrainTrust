#!/usr/bin/env python3
"""
0x200 debugInfo parser  ——  AWR2x44P mmw_ddm radar runtime debug frame decoder

Decodes the 64-byte, 4-page-rotating 0x200 CAN-FD frame defined in
  mss/wf_debug_info.c  (firmware source of truth)
  docs/debugInfo_design_note.md  附录A  (byte-offset spec — keep this script in sync with it)

Features
  - decode one 64-byte frame -> structured dict (common header + page payload)
  - reassemble the 4 pages into one snapshot
  - CRC-16/CCITT-FALSE check (poly 0x1021, init 0xFFFF, over bytes 0..61)
  - rollingCounter continuity check (gap = dropped/blocked)
  - faultSummary / taskAlive / canFlags bit decoding to names
  - cross-frame trend warning: frameTriggerReady rising but resultCount frozen
    (= DSP/DPM hang)

Inputs (auto-detected by file extension, or pass --format)
  - CANoe / CANalyzer .asc  (classic CAN and CAN-FD lines both handled)
  - hex dump: one frame per line, 64 space/comma-separated hex bytes
              (optionally prefixed by a float timestamp). Good for serial
              forwarding or manual paste.

Usage
  python debuginfo_parser.py capture.asc
  python debuginfo_parser.py frames.hex --format hex
  python debuginfo_parser.py capture.asc --id 0x200 --full   # dump full snapshot each cycle
  cat frames.hex | python debuginfo_parser.py - --format hex  # read from stdin

This script is pure stdlib (Python 3.7+). No external deps.
"""

import sys
import argparse
import struct

# --------------------------------------------------------------------------- #
# Constants from the spec (附录 A)
# --------------------------------------------------------------------------- #
FRAME_LEN = 64
DEFAULT_ID = 0x200
CRC_COVER = 62          # CRC covers bytes 0..61
SCHEMA_VER_EXPECTED = 1

FAULT_BITS = [
    "OVERRUN", "FRAME_DROP", "SYNC_LOST", "CAN_ERR", "OVER_TEMP", "DTC_ACTIVE",
    "TASK_DEAD", "STACK_LOW", "BLACKBOX", "VEHICLE_TIMEOUT", "ASSERT", "CAN_TX_STALL",
]
TASK_BITS = ["RSP", "CANOUT", "CANREC", "TIMESYNC", "CTRL", "rsvd5", "rsvd6", "rsvd7"]
CAN_FLAG_BITS = ["busOff", "errPassive", "warning"]
STAGE_NAMES = {
    0: "IDLE", 1: "RANGE_START", 2: "DOPPLER_START", 3: "CFAR_START",
    4: "DPC_RESULT", 5: "DOA_DONE", 6: "POSTPROC_DONE",
}
STACK_NAMES = ["ctrl", "rsp", "canout", "canrec", "tsync", "wfdbg", "reg6", "reg7"]

# Enum value->name maps, verified against the firmware headers:
#   mmw_mss.h:131    MmwDemo_SensorState_e
#   wf_time_sync.h:77 WFTimeSyncState
SENSOR_STATE = {0: "INIT", 1: "OPENED", 2: "STARTED", 3: "STOPPED"}
TIMESYNC_STATE = {0: "INIT", 1: "SILENT_WAIT", 2: "SYNCED", 3: "SYNC_LOST"}


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #
def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


def _bits(value: int, names) -> list:
    return [names[i] for i in range(len(names)) if value & (1 << i)]


def u8(d, o):  return d[o]
def i8(d, o):  return struct.unpack_from("<b", d, o)[0]
def u16(d, o): return struct.unpack_from("<H", d, o)[0]
def i16(d, o): return struct.unpack_from("<h", d, o)[0]
def u32(d, o): return struct.unpack_from("<I", d, o)[0]
def i32(d, o): return struct.unpack_from("<i", d, o)[0]


# --------------------------------------------------------------------------- #
# Frame decode
# --------------------------------------------------------------------------- #
def decode_common(d: bytes) -> dict:
    ver_page = d[0]
    state = d[4]
    fault = u16(d, 2)
    alive = d[5]
    crc_rx = u16(d, CRC_COVER)
    crc_calc = crc16_ccitt_false(d[:CRC_COVER])
    sensor = state & 0x0F
    tsync = (state >> 4) & 0x0F
    return {
        "schemaVer": (ver_page >> 4) & 0x0F,
        "pageId": ver_page & 0x0F,
        "rolling": d[1],
        "faultSummary": fault,
        "faults": _bits(fault, FAULT_BITS),
        "sensorState": SENSOR_STATE.get(sensor, sensor),
        "timeSyncState": TIMESYNC_STATE.get(tsync, tsync),
        "aliveBitmap": alive,
        "aliveTasks": _bits(alive, TASK_BITS),
        "crc_ok": crc_rx == crc_calc,
        "crc_rx": crc_rx,
        "crc_calc": crc_calc,
    }


def decode_page0(d):  # 时序/超时
    return {
        "tMax_CM4": u16(d, 6), "tMax_DOA": u16(d, 8), "tMax_postproc": u16(d, 10),
        "tMax_canTx": u16(d, 12), "tMax_enetTx": u16(d, 14), "tMax_total": u16(d, 16),
        "tTotalCur": u16(d, 18),
        "marginMin": i16(d, 20),
        "overrunCount": u16(d, 22),
        "lastOverrunFrame": u32(d, 24),
        "lastStage": STAGE_NAMES.get(d[28], d[28]),
        "framePeriodCur": u16(d, 30),
        "framePeriodMaxDev": u16(d, 32),
        "resultCount": u32(d, 34),
    }


def decode_page1(d):  # 数据通路/RF
    return {
        "frameTriggerReady": u32(d, 6),
        "resultCount": u32(d, 10),
        "cfarNumCur": u16(d, 14), "cfarNumMin": u16(d, 16), "cfarNumMax": u16(d, 18),
        "trcNum": u16(d, 20), "intfNumCur": u16(d, 22), "waveIdCur": u16(d, 24),
        "tmpRx0": i8(d, 26), "tmpTx0": i8(d, 27), "tmpPm": i8(d, 28), "tmpDig0": i8(d, 29),
        "tempValid": bool(d[30]),
        "failedTimingReports": u16(d, 32),
        "calibrationReports": u16(d, 34),
        "vehAgeMs": u16(d, 36),
        "vehicleRxCount": u32(d, 38),
    }


def decode_page2(d):  # TimeSync/CAN
    flags = d[25]
    return {
        "offsetUs": i32(d, 6),
        "validFrameCount": u32(d, 10),
        "crcErrorCount": u16(d, 14),
        "invalidFrameCount": u16(d, 16),
        "offsetJumpCount": u16(d, 18),
        "dtcActive": d[20], "dtcReason": d[21], "lastSeqCounter": d[22],
        "tec": d[23], "rec": d[24],
        "canFlags": _bits(flags, CAN_FLAG_BITS),
        "busOffEverCount": u16(d, 26),
        "canTxStallCount": u16(d, 28),
        "dtcReportCount": u16(d, 30),
        "canErrLogCnt": u32(d, 32),
    }


def decode_page3(d):  # 黑匣子/资源
    free = list(d[22:30])
    stacks = {STACK_NAMES[i]: (None if free[i] == 0xFF else free[i] * 16)
              for i in range(8)}
    return {
        "resetCause": d[6], "warmResetCause": d[7],
        "bootCount": u16(d, 8),
        "uptimeMs": u32(d, 10),
        "bbRecValid": bool(d[14]), "bbFromPrevBoot": bool(d[15]),
        "bbLine": u16(d, 16), "bbFileHash": u16(d, 18), "bbAssertCount": u16(d, 20),
        "stackFreeBytes": stacks,
        "lastErrorCode": i32(d, 30),
        "sensorStartCount": d[34], "sensorStopCount": d[35],
        "assertCountLive": u16(d, 36),
    }


_PAGE_DECODERS = {0: decode_page0, 1: decode_page1, 2: decode_page2, 3: decode_page3}


def decode_frame(d: bytes) -> dict:
    if len(d) != FRAME_LEN:
        raise ValueError(f"frame must be {FRAME_LEN} bytes, got {len(d)}")
    out = decode_common(d)
    dec = _PAGE_DECODERS.get(out["pageId"])
    out["payload"] = dec(d) if dec else {}
    return out


# --------------------------------------------------------------------------- #
# Stateful monitor: continuity, reassembly, trend warnings
# --------------------------------------------------------------------------- #
class DebugInfoMonitor:
    def __init__(self):
        self.prev_rolling = None
        self.pages = {}            # pageId -> latest payload
        self.last_trigger = None
        self.last_result = None
        self.frame_count = 0

    def feed(self, ts, data) -> dict:
        f = decode_frame(data)
        self.frame_count += 1
        warns = []

        if f["schemaVer"] != SCHEMA_VER_EXPECTED:
            warns.append(f"schemaVer={f['schemaVer']} (parser expects {SCHEMA_VER_EXPECTED}; offsets may be wrong)")
        if not f["crc_ok"]:
            warns.append(f"CRC MISMATCH rx={f['crc_rx']:#06x} calc={f['crc_calc']:#06x}")

        if self.prev_rolling is not None:
            gap = (f["rolling"] - self.prev_rolling) & 0xFF
            if gap != 1:
                warns.append(f"rollingCounter gap={gap} (dropped/blocked frames)")
        self.prev_rolling = f["rolling"]

        self.pages[f["pageId"]] = f["payload"]

        # cross-frame trend: trigger rising but result frozen -> DSP/DPM hang
        if f["pageId"] == 1:
            trig = f["payload"]["frameTriggerReady"]
            res = f["payload"]["resultCount"]
            if self.last_trigger is not None:
                if trig > self.last_trigger and res == self.last_result:
                    warns.append("frameTriggerReady rising but resultCount frozen -> DSP/DPM hang suspected")
            self.last_trigger, self.last_result = trig, res

        f["warnings"] = warns
        f["ts"] = ts
        return f

    def snapshot(self) -> dict:
        return dict(self.pages)


# --------------------------------------------------------------------------- #
# Input front-ends
# --------------------------------------------------------------------------- #
def _open(path):
    return sys.stdin if path == "-" else open(path, "r", encoding="utf-8", errors="replace")


def iter_asc(path, want_id):
    """CANoe/CANalyzer .asc. Handles classic and CAN-FD lines heuristically:
    locate the Rx/Tx direction token, the message id is the token before it,
    after the 'd' data marker comes <len> then <len> hex data bytes."""
    with _open(path) as fh:
        for line in fh:
            toks = line.split()
            if len(toks) < 4:
                continue
            dir_i = next((i for i, t in enumerate(toks) if t in ("Rx", "Tx")), -1)
            if dir_i <= 0:
                continue
            id_tok = toks[dir_i - 1].rstrip("xX")   # extended ids end with 'x'
            try:
                msg_id = int(id_tok, 16)
            except ValueError:
                continue
            if msg_id != want_id:
                continue
            if "d" not in toks[dir_i:]:
                continue
            d_i = dir_i + toks[dir_i:].index("d")
            try:
                dlen = int(toks[d_i + 1])
                data = bytes(int(x, 16) for x in toks[d_i + 2: d_i + 2 + dlen])
            except (ValueError, IndexError):
                continue
            if len(data) != dlen:
                continue
            try:
                ts = float(toks[0])
            except ValueError:
                ts = None
            yield ts, data


def iter_hex(path, want_id):
    """One frame per line: 64 hex bytes (space/comma separated), optional leading
    float timestamp. Lines starting with # are comments. `want_id` is ignored."""
    with _open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.replace(",", " ")
            toks = line.split()
            ts = None
            if "." in toks[0] and all(c not in toks[0] for c in "abcdefABCDEF"):
                try:
                    ts = float(toks[0]); toks = toks[1:]
                except ValueError:
                    pass
            try:
                data = bytes(int(x, 16) for x in toks)
            except ValueError:
                continue
            if len(data) == FRAME_LEN:
                yield ts, data


# --------------------------------------------------------------------------- #
# Pretty print
# --------------------------------------------------------------------------- #
def fmt_ts(ts):
    return f"{ts:10.4f}" if isinstance(ts, float) else "      -   "


def print_line(f):
    faults = ",".join(f["faults"]) or "-"
    print(f"[{fmt_ts(f['ts'])}] p{f['pageId']} roll={f['rolling']:3d} "
          f"sensor={f['sensorState']} sync={f['timeSyncState']} "
          f"alive={','.join(f['aliveTasks']) or '-'} faults={faults}")
    for w in f["warnings"]:
        print(f"            !! {w}")


def print_snapshot(snap):
    print("  --- reassembled snapshot ---")
    for pid in sorted(snap):
        print(f"  Page{pid}:")
        for k, v in snap[pid].items():
            print(f"     {k:22s} = {v}")


def main():
    ap = argparse.ArgumentParser(description="0x200 debugInfo parser")
    ap.add_argument("input", help="capture file, or '-' for stdin")
    ap.add_argument("--format", choices=["auto", "asc", "hex"], default="auto")
    ap.add_argument("--id", default=hex(DEFAULT_ID), help="CAN id (hex), default 0x200")
    ap.add_argument("--full", action="store_true",
                    help="dump full reassembled snapshot at end of every 4-page cycle")
    args = ap.parse_args()

    want_id = int(args.id, 16)
    fmt = args.format
    if fmt == "auto":
        fmt = "asc" if args.input.lower().endswith(".asc") else "hex"
    reader = iter_asc if fmt == "asc" else iter_hex

    mon = DebugInfoMonitor()
    seen_pages = set()
    for ts, data in reader(args.input, want_id):
        f = mon.feed(ts, data)
        print_line(f)
        seen_pages.add(f["pageId"])
        if args.full and seen_pages >= {0, 1, 2, 3}:
            print_snapshot(mon.snapshot())
            seen_pages.clear()

    if mon.frame_count == 0:
        print(f"no 0x{want_id:X} frames found (format={fmt}). "
              f"Check --id / --format.", file=sys.stderr)
        sys.exit(1)
    print(f"\n{mon.frame_count} frames decoded.")


if __name__ == "__main__":
    main()
