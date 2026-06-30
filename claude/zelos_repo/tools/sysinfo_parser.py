#!/usr/bin/env python3
"""
sysinfo_parser.py - decode + localize the R5F systemInfo / dumptrace frames (CAN id 0x100).

The firmware (mss/wf_sysinfo.c) broadcasts, on every power-up, the crash record stored
in flash from the PREVIOUS power cycle as two CAN-FD frames:
  msgIndex 0 "head": fault type + faulting PC/LR/SP/CPSR + CP15 DFSR/IFSR/DFAR/IFAR
  msgIndex 1 "regs": R0..R12
Both carry a 6-byte common header and a CRC16-CCITT-FALSE over bytes 0..61.

This tool decodes them, checks integrity, decodes the fault-status registers, and (if it
can find the ELF + the TI toolchain) symbolizes the code addresses to function:line and
the data fault address to a variable.

Usage
  python sysinfo_parser.py capture.asc
  python sysinfo_parser.py frames.hex --format hex
  python sysinfo_parser.py capture.asc --elf ../awr2x44P_mmw_demo_mssDDM.xer5f
  python sysinfo_parser.py capture.asc --toolchain "$R5F_CLANG_INSTALL_PATH"

Symbolization defaults: ELF = mmw_ddm/awr2x44P_mmw_demo_mssDDM.xer5f ; toolchain bin =
$R5F_CLANG_INSTALL_PATH/bin. Both are optional - without them you still get the raw
addresses and the fault decode.

Pure stdlib, Python 3.7+.
"""

import sys
import os
import re
import struct
import argparse
import subprocess

FRAME_LEN   = 64
CAN_ID      = 0x100
CRC_COVER   = 62
SCHEMA_VER  = 1

FAULT_TYPE = {0: "none", 1: "undefined-instruction", 2: "prefetch-abort", 3: "data-abort"}
CORE_NAME  = {0: "R5F"}

# Cortex-R5 DFSR/IFSR status field (FS = bit10<<4 | bits[3:0]); common encodings.
FAULT_STATUS = {
    0b00001: "alignment fault",
    0b00000: "background fault (no MPU region / reset value)",
    0b01101: "permission fault (MPU)",
    0b01000: "synchronous external abort",
    0b10110: "asynchronous external abort",
    0b00010: "debug event",
    0b11001: "synchronous parity/ECC error",
    0b11000: "asynchronous parity/ECC error",
    0b00100: "fault on instruction cache maintenance",
}


# --------------------------------------------------------------------------- #
# Frame extraction (CANFD .asc honoring the base, or raw hex)
# --------------------------------------------------------------------------- #
# Valid CAN-FD payload sizes (used to locate the data block unambiguously).
_CANFD_LENS = {12, 16, 20, 24, 32, 48, 64}


def _asc_base(text):
    m = re.search(r"base\s+(hex|dec)", text, re.I)
    return 16 if (not m or m.group(1).lower() == "hex") else 10


def _extract_data(toks, start):
    """Find the data block: a decimal length L (valid CAN/CAN-FD size) immediately
    followed by exactly L two-hex-digit byte tokens. Works for both classic
    ('d <dlc> <bytes>') and CAN-FD ('<BRS> <ESI> <DLC> <DataLen> <bytes>')."""
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


def _extract_asc(text):
    """64-byte frames with CAN id == 0x100. Handles Vector classic ('<id> <dir> d ...')
    AND CAN-FD ('CANFD <ch> <dir> <id> <BRS> <ESI> <DLC> <len> ...') line layouts: the
    id sits next to the Rx/Tx token, on the side that depends on the format."""
    base = _asc_base(text)
    out = []
    for line in text.splitlines():
        toks = line.split()
        if len(toks) < 5:
            continue
        dir_i = next((i for i, t in enumerate(toks) if t in ("Rx", "Tx")), -1)
        if dir_i <= 0:
            continue
        is_fd = toks[1].upper() == "CANFD"
        if is_fd:
            id_tok, data_start = toks[dir_i + 1], dir_i + 2   # id AFTER dir
        else:
            id_tok, data_start = toks[dir_i - 1], dir_i + 1   # id BEFORE dir
        try:
            msg_id = int(id_tok.rstrip("xX"), base)
        except ValueError:
            continue
        if msg_id != CAN_ID:
            continue
        data = _extract_data(toks, data_start)
        if data is not None and len(data) == FRAME_LEN:
            out.append(data)
    return out


def _extract_hex(text):
    out = []
    for line in text.splitlines():
        toks = re.findall(r"[0-9A-Fa-f]{2}", line)
        if len(toks) >= FRAME_LEN:
            out.append(bytes(int(t, 16) for t in toks[:FRAME_LEN]))
    return out


# --------------------------------------------------------------------------- #
# CRC + field access
# --------------------------------------------------------------------------- #
def crc16_ccitt_false(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def decode_common(d):
    crc_rx = struct.unpack_from("<H", d, CRC_COVER)[0]
    return {
        "schemaVer": (d[0] >> 4) & 0x0F,
        "msgIndex": d[0] & 0x0F,
        "rolling": d[1],
        "valid": d[2],
        "faultType": d[3],
        "recCount": d[4],
        "core": d[5],
        "crc_ok": crc_rx == crc16_ccitt_false(d[:CRC_COVER]),
    }


def decode_head(d):
    return {
        "seq": u32(d, 6), "bootTickFault": u32(d, 10), "bootTickNow": u32(d, 14),
        "pc": u32(d, 18), "lr": u32(d, 22), "sp": u32(d, 26), "cpsr": u32(d, 30),
        "dfsr": u32(d, 34), "ifsr": u32(d, 38), "dfar": u32(d, 42), "ifar": u32(d, 46),
        # diagnostic: raw slot-0 readback at boot
        "dbgMagic": u32(d, 50),
        "dbgCrcStored": struct.unpack_from("<H", d, 54)[0],
        "dbgCrcCalc": struct.unpack_from("<H", d, 56)[0],
        "retention": d[58],   # WF_SYSINFO_RETENTION_CYCLES (auto-clear window)
    }


def decode_regs(d):
    return {"r%d" % i: u32(d, 6 + i * 4) for i in range(13)}


def fault_status_str(fsr):
    fs = ((fsr >> 10) & 1) << 4 | (fsr & 0xF)
    name = FAULT_STATUS.get(fs, "status=0x%02X (see ARM ARM)" % fs)
    wnr = "write" if (fsr >> 11) & 1 else "read"
    return "%s [%s]" % (name, wnr)


# --------------------------------------------------------------------------- #
# Symbolization via the TI ARM-clang toolchain (optional)
# --------------------------------------------------------------------------- #
def _find_tool(toolchain, name):
    cands = []
    if toolchain:
        cands += [os.path.join(toolchain, "bin", name), os.path.join(toolchain, "bin", name + ".exe")]
    env = os.environ.get("R5F_CLANG_INSTALL_PATH")
    if env:
        cands += [os.path.join(env, "bin", name), os.path.join(env, "bin", name + ".exe")]
    cands += [name]  # PATH
    for c in cands:
        try:
            subprocess.run([c, "--version"], capture_output=True, check=False)
            return c
        except OSError:
            continue
    return None


def _default_elf():
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.normpath(os.path.join(here, "..", "awr2x44P_mmw_demo_mssDDM.xer5f"))
    return cand if os.path.exists(cand) else None


class Symbolizer:
    def __init__(self, elf, toolchain):
        self.elf = elf
        self.sym = _find_tool(toolchain, "llvm-symbolizer") if elf else None
        self.dsyms = self._load_data_syms(toolchain) if elf else []

    def code(self, addr):
        """addr -> 'function (file:line)' for an instruction address."""
        if not (self.sym and self.elf):
            return None
        a = addr & ~1  # drop Thumb bit
        try:
            out = subprocess.run([self.sym, "--obj=%s" % self.elf, "0x%X" % a],
                                 capture_output=True, text=True, check=False).stdout.splitlines()
        except OSError:
            return None
        out = [x.strip() for x in out if x.strip()]
        # llvm-symbolizer prints "??" / "??:0:0" for an unmapped/unknown address
        func = out[0] if out else ""
        loc = out[1] if len(out) > 1 else ""
        if func in ("", "??"):
            return None                         # not a real symbol
        if loc.startswith("??"):
            loc = ""
        elif loc:
            # llvm-symbolizer couldn't pin an exact line -> "file:0:col"; the function name
            # is still good (e.g. a fn-pointer call site), so keep the file, drop the ":0:col".
            parts = loc.rsplit(":", 2)
            if len(parts) == 3 and parts[1] == "0":
                loc = parts[0]
        return "%s  (%s)" % (func, loc) if loc else func

    def _load_data_syms(self, toolchain):
        nm = _find_tool(toolchain, "llvm-nm")
        if not (nm and self.elf):
            return []
        try:
            out = subprocess.run([nm, "--print-size", "--numeric-sort", self.elf],
                                 capture_output=True, text=True, check=False).stdout
        except OSError:
            return []
        syms = []
        for ln in out.splitlines():
            p = ln.split()
            # "<addr> <size> <type> <name>"
            if len(p) == 4:
                try:
                    syms.append((int(p[0], 16), int(p[1], 16), p[3]))
                except ValueError:
                    pass
        return syms

    def var(self, addr):
        """addr -> 'variable (+offset)' for a data address, via the symbol table."""
        for base, size, name in self.dsyms:
            if size and base <= addr < base + size:
                off = addr - base
                return "%s+0x%X" % (name, off) if off else name
        return None


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Decode + localize R5F systemInfo (0x100).")
    ap.add_argument("file", help="capture file (.asc / hex), or - for stdin")
    ap.add_argument("--format", choices=["asc", "hex"], help="force input format")
    ap.add_argument("--elf", help="path to awr2x44P_mmw_demo_mssDDM.xer5f")
    ap.add_argument("--toolchain", help="R5F TI ARM-clang root (has bin/llvm-symbolizer)")
    args = ap.parse_args()

    text = sys.stdin.read() if args.file == "-" else open(args.file, "r", errors="ignore").read()
    fmt = args.format or ("asc" if (".asc" in args.file.lower() or "base" in text.lower()) else "hex")
    frames = _extract_asc(text) if fmt == "asc" else _extract_hex(text)

    # latest valid head + regs (last write wins; firmware repeats the pair a few times)
    head = regs = None
    for f in frames:
        c = decode_common(f)
        if not c["crc_ok"] or c["schemaVer"] != SCHEMA_VER:
            continue
        if c["msgIndex"] == 0:
            head = (c, decode_head(f))
        elif c["msgIndex"] == 1:
            regs = (c, decode_regs(f))

    print("=" * 64)
    print("systemInfo / dumptrace (CAN 0x100)   frames=%d" % len(frames))
    print("=" * 64)
    if head is None:
        print("No valid 0x100 'head' frame found (CRC/schema). Nothing to decode.")
        return

    c, h = head
    # diagnostic line (raw slot-0 readback) - helps tell why a write didn't surface
    _, _h = head
    mg, cs, cc = _h["dbgMagic"], _h["dbgCrcStored"], _h["dbgCrcCalc"]
    if mg == 0xFFFFFFFF:
        diag = "block erased / no record in slot 0 (record may be in another slot)"
    elif mg == 0x57465331:
        diag = ("CRC MATCH (record valid)" if cs == cc else
                "CRC MISMATCH (stored=0x%04X calc=0x%04X) -- write not committed/corrupt" % (cs, cc))
    else:
        diag = "garbage magic -> write hit a NON-erased slot"
    print("flash slot0: magic=0x%08X  -> %s" % (mg, diag))

    boots = _h["bootTickNow"]           # power cycles since the last fault/clear
    ret = _h["retention"]

    if c["valid"] == 0:
        print("power cycles since last fault/clear: %d" % boots)
        print("VERDICT: clean - no stored crash record (R5 did not fault in the previous power cycle).")
        return

    left = (ret - boots) if (ret > boots) else 0
    print("aging: this fault is %d power-cycle(s) old; auto-clears at %d -> %d clean cycle(s) left"
          % (boots, ret, left))

    elf = args.elf or _default_elf()
    sym = Symbolizer(elf, args.toolchain)

    ft = FAULT_TYPE.get(c["faultType"], "0x%X" % c["faultType"])
    ago = h["bootTickNow"] - h["bootTickFault"]
    print("FAULT: %s on %s   (seq=%d, %d power-cycle(s) ago)" %
          (ft, CORE_NAME.get(c["core"], c["core"]), h["seq"], ago))
    print("records stored: %d   elf: %s" % (c["recCount"], elf or "(none - addresses only)"))
    print("-" * 64)

    pc_s = sym.code(h["pc"]) or "(not a known symbol; bad/unmapped address)"
    lr_s = sym.code(h["lr"]) or "(not a known symbol)"
    print("faulting PC : 0x%08X  %s" % (h["pc"], pc_s))
    print("caller   LR : 0x%08X  %s" % (h["lr"], lr_s))
    print("task     SP : 0x%08X" % h["sp"])
    print("CPSR        : 0x%08X" % h["cpsr"])

    if c["faultType"] == 3:  # data abort
        var = sym.var(h["dfar"]) or ""
        print("DFSR        : 0x%08X  %s" % (h["dfsr"], fault_status_str(h["dfsr"])))
        print("DFAR (addr) : 0x%08X  %s" % (h["dfar"], ("-> " + var) if var else "(not a known symbol; stack/heap/peripheral)"))
    elif c["faultType"] == 2:  # prefetch abort
        ifar_s = sym.code(h["ifar"]) or "(unmapped / bad jump target -- see caller LR above for the call site)"
        print("IFSR        : 0x%08X  %s" % (h["ifsr"], fault_status_str(h["ifsr"])))
        print("IFAR (addr) : 0x%08X  %s" % (h["ifar"], ifar_s))

    if regs is not None:
        _, r = regs
        print("-" * 64)
        for row in range(0, 13, 4):
            cells = []
            for i in range(row, min(row + 4, 13)):
                cells.append("R%-2d=0x%08X" % (i, r["r%d" % i]))
            print("  " + "  ".join(cells))
    print("=" * 64)


if __name__ == "__main__":
    main()
