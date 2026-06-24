#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TimeSync CAN-FD CRC checker.

和雷达代码 wf_time_sync_calc_crc16 / wf_time_sync_crc16_update 完全一致:
  - 算法 : CRC-16/CCITT-FALSE  (poly=0x1021, init=0xFFFF, 无反转, xorout=0)
  - 范围 : Byte2..Byte15  共 14 字节 (CRC_COVER_OFFSET=2, CRC_COVER_LEN=14)
  - CRC 字段: Byte0..Byte1, 大端  (B0<<8 | B1)  —— 和 wf_time_sync_get_u16_le 一致(其实是大端)

用法:
  1) 直接传参:   python timesync_crc.py "24 0B 2E A2 7A A8 6A 32 38 7C 20 95 00 00 00 00"
  2) 交互/粘贴:  python timesync_crc.py        然后一行一帧地粘贴, 空行或 Ctrl-Z(回车) 退出
  3) 管道:       echo "24 0B 2E ..." | python timesync_crc.py

输入只要 "数据字节" (B0 开头) 即可; 0x 前缀、逗号、多余空格都能识别。
至少要有 16 个字节 (B0..B15)。
"""

import sys
import re

# ---- 和雷达代码对应的参数, 需要时改这里即可 ----
POLY         = 0x1021
INIT         = 0xFFFF
COVER_OFFSET = 2     # WF_TIME_SYNC_CRC_COVER_OFFSET
COVER_LEN    = 14    # WF_TIME_SYNC_CRC_COVER_LEN
# ------------------------------------------------


def crc16_ccitt_false(data, crc=INIT, poly=POLY):
    """与 wf_time_sync_crc16_update 一致: MSB-first, 无输入/输出反转, 无 xorout。"""
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def parse_bytes(line):
    """从一行文本里提取所有的十六进制字节 (两位十六进制 token)。"""
    toks = re.findall(r'(?:0[xX])?([0-9A-Fa-f]{2})\b', line)
    return [int(t, 16) for t in toks]


def check_frame(data):
    if len(data) < COVER_OFFSET + COVER_LEN:
        return ("字节不够: 需要至少 %d 个, 实际 %d 个"
                % (COVER_OFFSET + COVER_LEN, len(data)))
    field = (data[0] << 8) | data[1]                       # 帧里带的 CRC (大端)
    cover = data[COVER_OFFSET:COVER_OFFSET + COVER_LEN]     # Byte2..15
    calc  = crc16_ccitt_false(cover)
    ok    = (calc == field)
    cover_hex = " ".join("%02X" % b for b in cover)
    return ("CRC字段=0x%04X  计算值=0x%04X  %s\n  校验范围(Byte%d..%d): %s"
            % (field, calc, "通过 OK" if ok else "不通过 FAIL",
               COVER_OFFSET, COVER_OFFSET + COVER_LEN - 1, cover_hex))


def handle_line(line):
    line = line.strip()
    if not line:
        return False  # 空行 -> 结束(交互模式用)
    data = parse_bytes(line)
    if not data:
        print("  (没识别到十六进制字节)")
        return True
    print(check_frame(data))
    return True


def main():
    if len(sys.argv) > 1:
        # 命令行参数模式: 把所有参数拼成一帧
        handle_line(" ".join(sys.argv[1:]))
        return

    if not sys.stdin.isatty():
        # 管道模式: 每行一帧
        for line in sys.stdin:
            if line.strip():
                handle_line(line)
        return

    # 交互模式
    print("粘贴 CAN 报文数据字节 (一行一帧), 空行退出:")
    try:
        while True:
            line = input("> ")
            if not handle_line(line):
                break
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
