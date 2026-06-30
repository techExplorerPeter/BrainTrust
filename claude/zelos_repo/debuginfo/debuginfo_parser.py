#!/usr/bin/env python3
"""
debugInfo parser  ——  AWR2x44P mmw_ddm radar runtime debug decoder (schema v2)

The full snapshot is split across two CAN-FD frames sent back-to-back each 66ms:
  0x200  "hot"    half (timing / detection / liveness)   msgIndex=0
  0x201  "detail" half (TimeSync / CAN / black box / res) msgIndex=1
Both carry the same 6-byte common header (incl. rollingCounter) and their own CRC.
Source of truth: mss/wf_debug_info.c + docs/debugInfo_design_note.md 附录A.

Features
  - decode each 64-byte frame -> structured dict (header + half payload)
  - pair the two halves by rollingCounter into one 128B snapshot per cycle
  - CRC-16/CCITT-FALSE check (poly 0x1021, init 0xFFFF, over bytes 0..61)
  - rollingCounter continuity check (gap = dropped/blocked frames)
  - missing-half detection (one of 0x200/0x201 lost on the bus)
  - faultSummary / taskAlive / canFlags bit decoding to names
  - derived margin (660 - tMax_total, 0.1ms units; negative = overrun)
  - cross-cycle trend warning: frameStartCount rising but resultCount frozen
    (= DSP/DPM hang)

The frame half is taken from header byte0[3:0] (msgIndex), not the CAN id, so hex
dumps without an id still decode correctly.

Multi-radar (merged bus): two radars share one electrically-merged CAN bus and
offset their debugInfo ids by position (FL=0x200/0x201, FR=0x202/0x203). Frames are
routed BY CAN ID into a separate per-radar monitor, so .asc captures get one summary
per radar plus a combined whole-bus TX-load total. (msgIndex only separates hot/det
within one radar, so id-less hex dumps fall back to a single merged stream.)

Inputs (auto-detected by extension, or --format)
  - CANoe/CANalyzer .asc  (classic + CAN-FD lines), ids 0x200/0x201 (FL) + 0x202/0x203 (FR)
  - hex dump: one frame per line, 64 hex bytes (optional leading float timestamp)

Usage
  python debuginfo_parser.py capture.asc
  python debuginfo_parser.py frames.hex --format hex --full
  cat frames.hex | python debuginfo_parser.py - --format hex

Pure stdlib, Python 3.7+.
"""

import sys
import argparse
import struct

FRAME_LEN = 64
# CAN ids are matched against the value parsed from the .asc honoring its
# "base hex|dec" header (Vector default = hex), so these are the real 0x200/0x201.
ID_HOT = 0x200   # 512
ID_DET = 0x201   # 513

# --- Multi-radar split -------------------------------------------------------
# Two radars share one (electrically merged) CAN bus. Each radar offsets its
# debugInfo ids by its position so they do NOT collide (firmware wf_debug_info.c:
# FL emits CAN_ID, FR emits CAN_ID + 2):
#   FL (FRONT_LEFT)  -> 0x200 / 0x201
#   FR (FRONT_RIGHT) -> 0x202 / 0x203
# Frames are routed to a per-radar monitor BY CAN ID (the in-frame msgIndex only
# tells hot vs det WITHIN one radar, so it cannot distinguish FL from FR).
RADARS = [
    ("FL", 0x200, 0x201),
    ("FR", 0x202, 0x203),
]
RADAR_IDS = {name: (hot, det) for name, hot, det in RADARS}
ID_TO_RADAR = {}
for _name, _hot, _det in RADARS:
    ID_TO_RADAR[_hot] = _name
    ID_TO_RADAR[_det] = _name
ALL_WANT_IDS = set(ID_TO_RADAR.keys())

CRC_COVER = 62
SCHEMA_VER_EXPECTED = 4
FRAME_BUDGET_100US = 660          # 66ms in 0.1ms units (matches firmware)

# --- CAN-FD bus-load estimate (rough, this node's TX only) ---------------------
# On-wire time per frame = fixed overhead (independent of payload) + payload bytes.
#   fixed overhead = ~30 nominal-rate bits (SOF/ID/control/ACK/EOF/IFS)
#                  + ~36 data-rate bits  (ESI/DLC/stuff-count/CRC etc.)
#   payload        = 8 data-rate bits per byte
# Configured for THIS bus: 500 kbit/s nominal, 2 Mbit/s data (sample point 80%
# does not affect bit duration, so it is not used here).
CAN_NOM_BITS_US = 1.0 / 0.500     # 2.0 us per nominal-rate bit  (500 kbit/s)
CAN_DAT_BITS_US = 1.0 / 2.000     # 0.5 us per data-rate bit     (2 Mbit/s)
CAN_FIXED_NOM_BITS = 30           # nominal-rate overhead bits per frame
CAN_FIXED_DAT_BITS = 36           # data-rate control/CRC bits per frame
# Pre-folded per-frame and per-byte on-wire microseconds:
CAN_US_PER_FRAME = CAN_FIXED_NOM_BITS * CAN_NOM_BITS_US \
                 + CAN_FIXED_DAT_BITS * CAN_DAT_BITS_US      # ~78 us
CAN_US_PER_BYTE = 8 * CAN_DAT_BITS_US                        # 4.0 us


def bus_load_pct(fps, kbps):
    """Rough on-wire bus occupancy (%) from a node's TX frame/s + KB/s."""
    bus_us_per_sec = fps * CAN_US_PER_FRAME + (kbps * 1024) * CAN_US_PER_BYTE
    return bus_us_per_sec / 1e6 * 100.0


def monitor_bus_load(mon):
    """(txFramesPerSec_peak, txKBytesPerSec_peak, busPct) for one radar's monitor."""
    dm = mon.a["detmax"]
    fps = dm.get("txFramesPerSec", 0)
    kbps = dm.get("txKBytesPerSec", 0)
    return fps, kbps, bus_load_pct(fps, kbps)

FAULT_BITS = [
    "OVERRUN", "FRAME_DROP", "SYNC_LOST", "CAN_ERR", "OVER_TEMP", "DTC_ACTIVE",
    "TASK_DEAD", "STACK_LOW", "BLACKBOX", "VEHICLE_TIMEOUT", "ASSERT", "CAN_TX_STALL",
]
FAULT_HINT = {
    "OVERRUN": "frame processing exceeded 66ms budget",
    "FRAME_DROP": "frames started (RANGE_START) outran completed -> RSP/DSP not keeping up",
    "SYNC_LOST": "TimeSync lost sync (no/late sync master)",
    "CAN_ERR": "CAN-A error-passive/bus-off occurred (on bench: confirm CANoe ACKs, not listen-only)",
    "OVER_TEMP": "front-end over temperature",
    "DTC_ACTIVE": "TimeSync DTC latched",
    "TASK_DEAD": "a periodic task stopped ticking",
    "STACK_LOW": "a task stack ran below threshold",
    "BLACKBOX": "black box holds a record of a previous crash",
    "VEHICLE_TIMEOUT": "vehicle-info CAN message went stale",
    "ASSERT": "an assert was hit this run",
    "CAN_TX_STALL": "CAN-A TX FIFO filled (bus backpressure / no ACK)",
}
# Faults that are usually a bench/environment artifact rather than a firmware bug.
FAULT_BENCH = {"CAN_ERR", "CAN_TX_STALL", "SYNC_LOST", "VEHICLE_TIMEOUT"}
TASK_BITS = ["RSP", "CANOUT", "CANREC", "TIMESYNC", "CTRL", "rsvd5", "rsvd6", "rsvd7"]
CAN_FLAG_BITS = ["busOff", "errPassive", "warning"]
STAGE_NAMES = {
    0: "IDLE", 1: "RANGE_START", 2: "DOPPLER_START", 3: "CFAR_START",
    4: "DPC_RESULT", 5: "DOA_DONE", 6: "POSTPROC_DONE",
}
STACK_NAMES = ["ctrl", "rsp", "canout", "canrec", "tsync", "wfdbg"]
# 0x200[15] cpuTopCode -> task name (matches wf_dbg_taskcode in firmware)
TASK_CODE_NAMES = {
    0: "other", 1: "ctrl", 2: "canout", 3: "canrec", 4: "rfTemp", 5: "enet",
    6: "flash", 7: "carInfo", 8: "timesync", 9: "debug", 10: "DPM", 11: "cli", 12: "edma",
}

# Verified against firmware headers:
#   mmw_mss.h      MmwDemo_SensorState_e
#   wf_time_sync.h WFTimeSyncState
#   soc_rcm.h      SOC_RcmResetCause_e (resetCause) / SOC_WarmResetCause_e (warmResetCause)
SENSOR_STATE = {0: "INIT", 1: "OPENED", 2: "STARTED", 3: "STOPPED"}
TIMESYNC_STATE = {0: "INIT", 1: "SILENT_WAIT", 2: "SYNCED", 3: "SYNC_LOST"}
# resetCause field  <- SOC_rcmGetResetCause() / SOC_RcmResetCause
RESET_CAUSE = {
    0x0: "POWER_ON", 0x1: "WARM", 0x2: "STC", 0x3: "MMR_CPU0_VIM0",
    0x4: "MMR_CPU1_VIM1", 0x5: "MMR_CPU0", 0x6: "MMR_CPU1", 0x7: "DBG_CPU0",
    0x8: "DBG_CPU1", 0x9: "FSM_TRIGGER", 0xA: "UNKNOWN",
}
# warmResetCause field  <- SOC_getWarmResetCause() / SOC_WarmResetCause
WARM_RESET_CAUSE = {
    0x08: "EXT_PAD", 0x09: "POWER_ON", 0x0A: "MSS_WDT",
    0x0C: "TOP_RCM_WARM_CFG", 0x18: "HSM_WDT",
}


# --------------------------------------------------------------------------- #
# Low-level
# --------------------------------------------------------------------------- #
def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


def _bits(value, names):
    return [names[i] for i in range(len(names)) if value & (1 << i)]


def u8(d, o):  return d[o]
def i8(d, o):  return struct.unpack_from("<b", d, o)[0]
def u16(d, o): return struct.unpack_from("<H", d, o)[0]
def u32(d, o): return struct.unpack_from("<I", d, o)[0]
def i32(d, o): return struct.unpack_from("<i", d, o)[0]


# --------------------------------------------------------------------------- #
# Decoders (absolute frame offsets, per docs 附录A)
# --------------------------------------------------------------------------- #
def decode_common(d):
    ver_msg = d[0]
    state = d[4]
    fault = u16(d, 2)
    alive = d[5]
    crc_rx = u16(d, CRC_COVER)
    crc_calc = crc16_ccitt_false(d[:CRC_COVER])
    return {
        "schemaVer": (ver_msg >> 4) & 0x0F,
        "msgIndex": ver_msg & 0x0F,
        "rolling": d[1],
        "faultSummary": fault,
        "faults": _bits(fault, FAULT_BITS),
        "sensorState": SENSOR_STATE.get(state & 0x0F, state & 0x0F),
        "timeSyncState": TIMESYNC_STATE.get((state >> 4) & 0x0F, (state >> 4) & 0x0F),
        "aliveBitmap": alive,
        "aliveTasks": _bits(alive, TASK_BITS),
        "crc_ok": crc_rx == crc_calc,
        "crc_rx": crc_rx,
        "crc_calc": crc_calc,
    }


def decode_hot(d):  # 0x200
    tmax_total = u16(d, 16)
    return {
        "tMax_CM4": u16(d, 6), "tMax_DOA": u16(d, 8), "tMax_postproc": u16(d, 10),
        # offsets 12..15: per-task CPU load %% (FreeRTOS run-time stats, ~0.5s window)
        # offsets 12..15: CPU load %% (FreeRTOS run-time stats)
        "cpuR5AvgPct": u8(d, 12),             # R5 total load, cumulative avg
        "cpuR5PeakPct": u8(d, 13),            # R5 total load, windowed peak (worst spike)
        "cpuRspPct": u8(d, 14),               # algorithm (DOA+perception)
        "cpuCanoutPct": u8(d, 15),            # CAN send (real CPU, ~0)
        "tMax_total": tmax_total,
        "tTotalCur": u16(d, 18),
        "marginMin_derived": FRAME_BUDGET_100US - tmax_total,   # 0.1ms; <0 = overrun
        "overrunCount": u16(d, 20),
        "lastOverrunFrame": u32(d, 22),
        "framePeriodCur": u16(d, 26),
        "framePeriodMaxDev": u16(d, 28),
        "frameStartCount": u32(d, 30),
        "resultCount": u32(d, 34),
        "cfarNumCur": u16(d, 38), "cfarNumMin": u16(d, 40), "cfarNumMax": u16(d, 42),
        "trcNum": u16(d, 44), "intfNumCur": u16(d, 46), "waveIdCur": u16(d, 48),
        "failedTimingReports": u16(d, 50),
        "calibrationReports": u16(d, 52),
        "vehAgeMs": u16(d, 54),
        "tmpRx0": i8(d, 56), "tmpTx0": i8(d, 57), "tmpPm": i8(d, 58), "tmpDig0": i8(d, 59),
        "tempValid": bool(d[60]),
        "lastStage": STAGE_NAMES.get(d[61], d[61]),
    }


def decode_det(d):  # 0x201
    free = list(d[56:62])
    stacks = {STACK_NAMES[i]: (None if free[i] == 0xFF else free[i] * 16)
              for i in range(len(STACK_NAMES))}
    return {
        "vehicleRxCount": u16(d, 6),
        "validFrameCount": u16(d, 8),
        "crcErrorCount": u16(d, 10),
        "invalidFrameCount": u16(d, 12),
        "offsetJumpCount": u16(d, 14),
        "offsetUs": i32(d, 16),
        "busOffEverCount": u16(d, 20),
        "canTxStallCount": u16(d, 22),
        "dtcReportCount": u16(d, 24),
        "canErrLogCnt": u16(d, 26),
        "txFramesPerSec": u16(d, 28),         # v4: was bootCount (dead) -> radar TX frames/s
        "uptimeSec": u16(d, 30),
        "bbLine": u16(d, 32), "bbFileHash": u16(d, 34), "bbAssertCount": u16(d, 36),
        "assertCountLive": u16(d, 38),
        "lastErrorCode": i32(d, 40),
        "dtcActive": d[44], "dtcReason": d[45], "lastSeqCounter": d[46],
        "tec": d[47], "rec": d[48],
        "canFlags": _bits(d[49], CAN_FLAG_BITS),
        "resetCause": d[50], "resetCauseName": RESET_CAUSE.get(d[50], hex(d[50])),
        "warmResetCause": d[51], "warmResetCauseName": WARM_RESET_CAUSE.get(d[51], hex(d[51])),
        "bbRecValid": bool(d[52]),
        "txKBytesPerSec": u8(d, 53),          # v4: was bbFromPrevBoot (dead) -> radar TX KB/s
        "sensorStartCount": d[54], "sensorStopCount": d[55],
        "stackFreeBytes": stacks,
    }


def decode_frame(d):
    if len(d) != FRAME_LEN:
        raise ValueError(f"frame must be {FRAME_LEN} bytes, got {len(d)}")
    f = decode_common(d)
    f["half"] = "hot" if f["msgIndex"] == 0 else "det"
    f["payload"] = decode_hot(d) if f["msgIndex"] == 0 else decode_det(d)
    return f


# --------------------------------------------------------------------------- #
# Stateful monitor: pairing, continuity, trend
# --------------------------------------------------------------------------- #
class DebugInfoMonitor:
    def __init__(self):
        self.prev_rolling = None
        self.cur = None            # accumulating cycle: {'rolling','ts','hot','det','common'}
        self.last_trigger = None
        self.last_result = None
        self.frame_count = 0
        # ---- whole-capture aggregates (for --summary) ----
        self.a = {
            "cycles": 0, "crc_err": 0, "schema_err": 0,
            "gaps": 0, "missing_hot": 0, "missing_det": 0,
            "fault_union": 0,
            "sensor_states": set(), "sync_states": set(),
            "hotmax": {}, "detmax": {}, "stack_min": {},
            "bb_seen": False, "lastErr": 0,
            "trig_first": None, "trig_last": None,
            "res_first": None, "res_last": None,
            "top_pct": 0, "top_name": "-",
            "reset": None, "warmreset": None, "boot": 0, "uptime": 0,
            "ts_first": None, "ts_last": None,
        }

    def _agg_max(self, bucket, payload, keys):
        d = self.a[bucket]
        for k in keys:
            v = payload.get(k)
            if isinstance(v, int):
                d[k] = v if k not in d else max(d[k], v)

    def _finalize(self, cyc):
        """Return (snapshot_dict, warnings) for a completed/closed cycle."""
        warns = []
        self.a["cycles"] += 1
        if cyc.get("hot") is None:
            self.a["missing_hot"] += 1
            warns.append(f"cycle roll={cyc['rolling']}: 0x200(hot) missing")
        if cyc.get("det") is None:
            self.a["missing_det"] += 1
            warns.append(f"cycle roll={cyc['rolling']}: 0x201(det) missing")
        return cyc, warns

    def feed(self, ts, data):
        f = decode_frame(data)
        self.frame_count += 1
        warns = []
        completed = None
        a = self.a

        if f["schemaVer"] != SCHEMA_VER_EXPECTED:
            a["schema_err"] += 1
            warns.append(f"schemaVer={f['schemaVer']} (parser expects {SCHEMA_VER_EXPECTED}; offsets may be wrong)")
        if not f["crc_ok"]:
            a["crc_err"] += 1
            warns.append(f"CRC MISMATCH rx={f['crc_rx']:#06x} calc={f['crc_calc']:#06x}")

        a["fault_union"] |= f["faultSummary"]
        a["sensor_states"].add(f["sensorState"])
        a["sync_states"].add(f["timeSyncState"])
        if a["ts_first"] is None and isinstance(ts, float):
            a["ts_first"] = ts
        if isinstance(ts, float):
            a["ts_last"] = ts

        r = f["rolling"]
        if self.cur is None or r != self.cur["rolling"]:
            if self.cur is not None:
                completed, cw = self._finalize(self.cur)
                warns = cw + warns
            if self.prev_rolling is not None:
                gap = (r - self.prev_rolling) & 0xFF
                if gap != 1:
                    a["gaps"] += 1
                    warns.append(f"rollingCounter gap={gap} (dropped/blocked cycles)")
            self.prev_rolling = r
            self.cur = {"rolling": r, "ts": ts, "hot": None, "det": None, "common": f}

        self.cur[f["half"]] = f["payload"]
        self.cur["common"] = f
        self.cur["ts"] = ts

        pl = f["payload"]
        if f["half"] == "hot":
            self._agg_max("hotmax", pl, [
                "tMax_CM4", "tMax_DOA", "tMax_postproc", "tMax_total",
                "overrunCount", "framePeriodMaxDev",
                "cpuR5AvgPct", "cpuR5PeakPct", "cpuRspPct", "cpuCanoutPct"])
            trig, res = pl["frameStartCount"], pl["resultCount"]
            if a["trig_first"] is None:
                a["trig_first"], a["res_first"] = trig, res
            a["trig_last"], a["res_last"] = trig, res
            if self.last_trigger is not None and trig > self.last_trigger and res == self.last_result:
                warns.append("frameStartCount rising but resultCount frozen -> DSP/DPM hang suspected")
            self.last_trigger, self.last_result = trig, res
        else:  # det
            self._agg_max("detmax", pl, [
                "tec", "rec", "busOffEverCount", "canTxStallCount", "canErrLogCnt",
                "crcErrorCount", "invalidFrameCount", "offsetJumpCount",
                "bbAssertCount", "assertCountLive",
                "txFramesPerSec", "txKBytesPerSec"])
            a["bb_seen"] = a["bb_seen"] or pl["bbRecValid"]
            if pl["lastErrorCode"] != 0:
                a["lastErr"] = pl["lastErrorCode"]
            a["reset"], a["warmreset"] = pl["resetCause"], pl["warmResetCause"]
            a["uptime"] = max(a["uptime"], pl["uptimeSec"])
            for name, free in pl["stackFreeBytes"].items():
                if free is not None:
                    a["stack_min"][name] = free if name not in a["stack_min"] else min(a["stack_min"][name], free)

        f["warnings"] = warns
        f["ts"] = ts
        f["completed_cycle"] = completed
        return f

    def flush(self):
        if self.cur is not None:
            snap, warns = self._finalize(self.cur)
            self.cur = None
            return snap, warns
        return None, []


# --------------------------------------------------------------------------- #
# Input front-ends  (yield (ts, data))
# --------------------------------------------------------------------------- #
def _open(path):
    return sys.stdin if path == "-" else open(path, "r", encoding="utf-8", errors="replace")


_CANFD_LENS = {8, 12, 16, 20, 24, 32, 48, 64}


def _extract_data(toks, start):
    """Find the data block: a decimal length L (valid CAN/CAN-FD payload size)
    immediately followed by exactly L two-hex-digit byte tokens. Works for both
    classic ('d <dlc> <bytes>') and CAN-FD ('<BRS> <ESI> <DLC> <DataLen> <bytes>')
    because the BRS/ESI/DLC flags never look like 'length + L hex bytes'."""
    for i in range(start, len(toks)):
        t = toks[i]
        if not t.isdigit():
            continue
        L = int(t)
        if L < 1 or (L not in _CANFD_LENS and L > 8):
            continue
        chunk = toks[i + 1: i + 1 + L]
        if len(chunk) == L and all(len(x) == 2 for x in chunk):
            try:
                return bytes(int(x, 16) for x in chunk)
            except ValueError:
                continue
    return None


def _asc_base(path):
    """Read the .asc 'base hex|dec' directive (Vector default hex). stdin -> hex."""
    if path == "-":
        return 16
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip().lower()
                if s.startswith("base "):
                    return 10 if "dec" in s else 16
                if (" rx " in (" " + s + " ")) or (" tx " in (" " + s + " ")):
                    break
    except OSError:
        pass
    return 16


def iter_asc(path, want_ids):
    base = _asc_base(path)
    with _open(path) as fh:
        for line in fh:
            toks = line.split()
            if len(toks) < 5:
                continue
            dir_i = next((i for i, t in enumerate(toks) if t in ("Rx", "Tx")), -1)
            if dir_i <= 0:
                continue
            is_fd = toks[1].upper() == "CANFD"
            if is_fd:
                # <time> CANFD <ch> <dir> <id> <BRS> <ESI> <DLC> <DataLen> <data..>
                id_tok, data_start = toks[dir_i + 1], dir_i + 2
            else:
                # <time> <ch> <id> <dir> d <dlc> <data..>
                id_tok, data_start = toks[dir_i - 1], dir_i + 1
            try:
                msg_id = int(id_tok.rstrip("xX"), base)
            except ValueError:
                continue
            if msg_id not in want_ids:
                continue
            data = _extract_data(toks, data_start)
            if data is None or len(data) != FRAME_LEN:
                continue
            try:
                ts = float(toks[0])
            except ValueError:
                ts = None
            yield ts, msg_id, data


def iter_hex(path, want_ids):
    with _open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            toks = line.replace(",", " ").split()
            ts = None
            if toks and "." in toks[0] and not any(c in "abcdefABCDEF" for c in toks[0]):
                try:
                    ts = float(toks[0]); toks = toks[1:]
                except ValueError:
                    pass
            try:
                data = bytes(int(x, 16) for x in toks)
            except ValueError:
                continue
            if len(data) == FRAME_LEN:
                # hex dumps carry no CAN id -> cannot split radars; single stream.
                yield ts, None, data


# --------------------------------------------------------------------------- #
# Pretty print
# --------------------------------------------------------------------------- #
def fmt_ts(ts):
    return f"{ts:10.4f}" if isinstance(ts, float) else "      -   "


def print_line(f, label=""):
    faults = ",".join(f["faults"]) or "-"
    tag = f"{label:2s} " if label else ""
    print(f"[{fmt_ts(f['ts'])}] {tag}{f['half']:3s} roll={f['rolling']:3d} "
          f"sensor={f['sensorState']} sync={f['timeSyncState']} "
          f"alive={','.join(f['aliveTasks']) or '-'} faults={faults}")
    for w in f["warnings"]:
        print(f"            !! {w}")


def print_snapshot(cyc):
    print(f"  --- snapshot roll={cyc['rolling']} ---")
    for half in ("hot", "det"):
        pl = cyc.get(half)
        tag = "0x200" if half == "hot" else "0x201"
        if pl is None:
            print(f"  {tag} ({half}): <missing>")
            continue
        print(f"  {tag} ({half}):")
        for k, v in pl.items():
            print(f"     {k:22s} = {v}")


def print_summary(mon, label=None):
    a = mon.a
    faults = _bits(a["fault_union"], FAULT_BITS)
    hm, dm = a["hotmax"], a["detmax"]
    dur = (a["ts_last"] - a["ts_first"]) if (a["ts_first"] is not None and a["ts_last"] is not None) else None

    print("=" * 64)
    if label and label in RADAR_IDS:
        hot, det = RADAR_IDS[label]
        print(f"debugInfo summary  —  {label}  ({hot:#05x}/{det:#05x})")
    else:
        print("debugInfo capture summary")
    print("=" * 64)
    line = f"frames={mon.frame_count}  cycles={a['cycles']}"
    if dur is not None:
        line += f"  duration={dur:.2f}s"
    print(line)
    print(f"sensorState   : {', '.join(sorted(map(str, a['sensor_states'])))}")
    print(f"timeSyncState : {', '.join(sorted(map(str, a['sync_states'])))}")
    rc = RESET_CAUSE.get(a["reset"], "?") if a["reset"] is not None else "-"
    wrc = WARM_RESET_CAUSE.get(a["warmreset"], "?") if a["warmreset"] is not None else "-"
    print(f"uptime={a['uptime']}s  resetCause={a['reset']}({rc})  warmResetCause={a['warmreset']}({wrc})")
    print(f"frameStart {a['trig_first']}->{a['trig_last']}   resultCount {a['res_first']}->{a['res_last']}")
    tmaxs = ", ".join(f"{k[5:]}={hm[k]}" for k in
                      ["tMax_CM4", "tMax_DOA", "tMax_postproc", "tMax_total"]
                      if k in hm)
    print(f"timing max-hold (0.1ms): {tmaxs or '(all 0 — sensor not running)'}")
    print(f"overrun max={hm.get('overrunCount', 0)}  framePeriodMaxDev max={hm.get('framePeriodMaxDev', 0)}")
    print(f"CPU load: R5 avg={hm.get('cpuR5AvgPct', 0)}% peak={hm.get('cpuR5PeakPct', 0)}%  "
          f"rsp(algo)={hm.get('cpuRspPct', 0)}%  canout={hm.get('cpuCanoutPct', 0)}%")
    print(f"CAN-A  tec max={dm.get('tec', 0)}  rec max={dm.get('rec', 0)}  "
          f"busOffEver={dm.get('busOffEverCount', 0)}  txStall max={dm.get('canTxStallCount', 0)}  CEL max={dm.get('canErrLogCnt', 0)}")
    fps, kbps, busPct = monitor_bus_load(mon)
    print(f"CAN-A TX rate (peak): {fps} frames/s  {kbps} KB/s  (this radar's own bus contribution)")
    print(f"est. bus load (this radar): ~{busPct:.0f}%  "
          f"(500K/2M; rough, TX only — see combined total below)")
    print(f"TimeSync  crcErr={dm.get('crcErrorCount', 0)}  invalid={dm.get('invalidFrameCount', 0)}  jump={dm.get('offsetJumpCount', 0)}")
    print(f"blackbox record: {'YES' if a['bb_seen'] else 'no'}   assertLive max={dm.get('assertCountLive', 0)}   lastErrorCode={a['lastErr']}")
    if a["stack_min"]:
        print("stack free min : " + ", ".join(f"{k}={v}B" for k, v in a["stack_min"].items()))
    print(f"integrity      : CRC err={a['crc_err']}  schema err={a['schema_err']}  "
          f"rolling gaps={a['gaps']}  missing hot/det={a['missing_hot']}/{a['missing_det']}")

    # ---- verdict ----
    print("-" * 64)
    hard = []   # firmware/system concerns
    if a["crc_err"]:
        hard.append(f"{a['crc_err']} CRC errors (bus noise, or firmware/parser schema out of sync)")
    if a["schema_err"]:
        hard.append("schema version mismatch — rebuild firmware & parser together")
    for fb in faults:
        if fb not in FAULT_BENCH:
            hard.append(f"{fb}: {FAULT_HINT.get(fb, '')}")
    bench = [fb for fb in faults if fb in FAULT_BENCH]

    if not hard and not bench:
        print("VERDICT: OK — no faults, no integrity issues.")
    else:
        if hard:
            print("VERDICT: NEEDS ATTENTION")
            for h in hard:
                print(f"  [!] {h}")
        else:
            print("VERDICT: OK (firmware) - only bench/environment faults below")
        for fb in bench:
            print(f"  [bench] {fb}: {FAULT_HINT.get(fb, '')}")
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser(description="debugInfo parser (schema v2, dual-frame)")
    ap.add_argument("input", help="capture file, or '-' for stdin")
    ap.add_argument("--format", choices=["auto", "asc", "hex"], default="auto")
    ap.add_argument("--full", action="store_true",
                    help="print the full reassembled snapshot at the end of each cycle")
    ap.add_argument("--summary", action="store_true",
                    help="suppress per-frame lines; print only the whole-capture health verdict")
    ap.add_argument("--skip", metavar="N|Xs", default=None,
                    help="drop the capture-start artifact: '16' = skip first 16 frames, "
                         "'0.05s' = skip frames before t=0.05s")
    args = ap.parse_args()

    skip_frames, skip_time = 0, None
    if args.skip:
        if args.skip.lower().endswith("s"):
            skip_time = float(args.skip[:-1])
        else:
            skip_frames = int(args.skip)

    fmt = args.format
    if fmt == "auto":
        fmt = "asc" if args.input.lower().endswith(".asc") else "hex"
    reader = iter_asc if fmt == "asc" else iter_hex
    want_ids = ALL_WANT_IDS

    # One monitor per radar, created lazily as its frames first appear, so a
    # single-radar capture reports only the radar actually present. "single" is
    # the fallback bucket for id-less hex input.
    monitors = {}        # name -> DebugInfoMonitor
    order = []           # first-seen radar order

    def get_mon(name):
        m = monitors.get(name)
        if m is None:
            m = DebugInfoMonitor()
            monitors[name] = m
            order.append(name)
        return m

    read_idx = 0
    for ts, msg_id, data in reader(args.input, want_ids):
        read_idx += 1
        if read_idx <= skip_frames:
            continue
        if skip_time is not None and isinstance(ts, float) and ts < skip_time:
            continue
        name = ID_TO_RADAR.get(msg_id, "single") if msg_id is not None else "single"
        mon = get_mon(name)
        f = mon.feed(ts, data)
        if not args.summary:
            print_line(f, label=(name if name != "single" else ""))
            if args.full and f["completed_cycle"] is not None:
                print_snapshot(f["completed_cycle"])

    for name in order:
        snap, warns = monitors[name].flush()
        if not args.summary:
            for w in warns:
                print(f"            !! {w}")
            if args.full and snap is not None:
                print_snapshot(snap)

    total_frames = sum(m.frame_count for m in monitors.values())
    if total_frames == 0:
        ids = "/".join(f"0x{i:X}" for i in sorted(ALL_WANT_IDS))
        print(f"no {ids} frames found (format={fmt}). Check --format.", file=sys.stderr)
        sys.exit(1)

    if args.summary:
        loads = []
        for name in order:
            print_summary(monitors[name], label=(name if name != "single" else None))
            fps, kbps, pct = monitor_bus_load(monitors[name])
            loads.append((name, fps, kbps, pct))
        # Combined whole-bus total when more than one radar was seen.
        real = [x for x in loads if x[0] != "single"]
        if len(real) > 1:
            total = sum(x[3] for x in real)
            print("=" * 64)
            print("combined CAN-A bus load  (all radars on this merged bus, TX only, rough)")
            print("  " + "   ".join(f"{n}~{p:.0f}%" for n, _f, _k, p in real)
                  + f"   ->  TOTAL ~{total:.0f}%")
            print("  (500K/2M; per-radar TX estimate summed; judge headroom with "
                  "txStall/tec/busOff, not this %.)")
            print("=" * 64)
    else:
        seen = ", ".join(f"{n}={monitors[n].frame_count}" for n in order)
        print(f"\n{total_frames} frames decoded ({seen}). (run with --summary for a health verdict)")


if __name__ == "__main__":
    main()
