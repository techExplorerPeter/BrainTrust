from __future__ import annotations

import hashlib
import io
import math
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE_MD = ROOT / "Bootloader_BM_PBL_Detailed_Design_and_Technical_Requirements.md"
OUTPUT_DOCX = ROOT / "Bootloader_BM_PBL_Supplier_High_Level_Design.docx"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

NAVY = "1A2E44"
BLUE = "38709F"
TEAL = "27858A"
GREEN = "4D8957"
ORANGE = "DA8735"
RED = "B24849"
INK = "26323B"
MID_GREY = "5B6770"
LIGHT_GREY = "F2F5F7"
LINE_GREY = "CBD3D9"
WHITE = "FFFFFF"
PALE_BLUE = "EAF2F8"
PALE_GREEN = "EAF4EC"
PALE_ORANGE = "FCF2E7"
PALE_RED = "F8EAEA"


def rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size=size)


def text_lines(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for source_line in text.split("\n"):
        if not source_line:
            lines.append("")
            continue
        current = ""
        for ch in source_line:
            trial = current + ch
            if current and draw.textbbox((0, 0), trial, font=fnt)[2] > width:
                lines.append(current)
                current = ch
            else:
                current = trial
        if current:
            lines.append(current)
    return lines


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    padding: int = 20,
    line_gap: int = 8,
) -> None:
    x0, y0, x1, y1 = box
    lines = text_lines(draw, text, fnt, max(10, x1 - x0 - 2 * padding))
    heights = [draw.textbbox((0, 0), line or "国", font=fnt)[3] for line in lines]
    total_h = sum(heights) + max(0, len(lines) - 1) * line_gap
    y = y0 + (y1 - y0 - total_h) / 2
    for line, h in zip(lines, heights):
        bbox = draw.textbbox((0, 0), line, font=fnt)
        w = bbox[2] - bbox[0]
        draw.text((x0 + (x1 - x0 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def rounded_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fill: str,
    outline: str = NAVY,
    text_color: str = WHITE,
    size: int = 28,
    bold: bool = True,
    radius: int = 16,
    width: int = 3,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=rgb(fill), outline=rgb(outline), width=width)
    draw_centered_text(draw, box, text, font(size, bold), rgb(text_color))


def diamond(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    width: int,
    height: int,
    text: str,
    fill: str = PALE_ORANGE,
    outline: str = ORANGE,
    size: int = 25,
) -> tuple[int, int, int, int]:
    cx, cy = center
    pts = [(cx, cy - height // 2), (cx + width // 2, cy), (cx, cy + height // 2), (cx - width // 2, cy)]
    draw.polygon(pts, fill=rgb(fill), outline=rgb(outline))
    draw.line(pts + [pts[0]], fill=rgb(outline), width=4, joint="curve")
    box = (cx - width // 3, cy - height // 3, cx + width // 3, cy + height // 3)
    draw_centered_text(draw, box, text, font(size, True), rgb(INK), padding=0)
    return (cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str = MID_GREY,
    width: int = 5,
    label: str | None = None,
    label_offset: tuple[int, int] = (0, -28),
) -> None:
    draw.line([start, end], fill=rgb(color), width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head = 18
    a1 = angle + math.pi * 0.82
    a2 = angle - math.pi * 0.82
    p1 = (end[0] + head * math.cos(a1), end[1] + head * math.sin(a1))
    p2 = (end[0] + head * math.cos(a2), end[1] + head * math.sin(a2))
    draw.polygon([end, p1, p2], fill=rgb(color))
    if label:
        bbox = draw.textbbox((0, 0), label, font=font(22, True))
        lx = (start[0] + end[0]) / 2 - (bbox[2] - bbox[0]) / 2 + label_offset[0]
        ly = (start[1] + end[1]) / 2 + label_offset[1]
        draw.rounded_rectangle((lx - 8, ly - 4, lx + bbox[2] - bbox[0] + 8, ly + bbox[3] - bbox[1] + 5), 6, fill=rgb(WHITE))
        draw.text((lx, ly), label, font=font(22, True), fill=rgb(color))


def diagram_title(draw: ImageDraw.ImageDraw, canvas_width: int, title: str, subtitle: str | None = None) -> None:
    draw.text((60, 38), title, font=font(42, True), fill=rgb(NAVY))
    draw.line((60, 98, canvas_width - 60, 98), fill=rgb(BLUE), width=5)
    if subtitle:
        draw.text((60, 112), subtitle, font=font(22), fill=rgb(MID_GREY))


def image_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def architecture_diagram() -> bytes:
    img = Image.new("RGB", (1800, 1120), rgb(WHITE))
    d = ImageDraw.Draw(img)
    diagram_title(d, img.width, "BM + PBL 总体架构", "启动控制链与升级执行链相互独立，通过固定分区和持久状态协同")

    rounded_box(d, (60, 245, 335, 405), "整车 / 诊断仪\nOTA 平台", PALE_BLUE, BLUE, INK, 29)
    rounded_box(d, (455, 165, 835, 420), "PBL\n诊断通信与升级执行\nUDS / ImageM\nFlashPort", TEAL, TEAL, WHITE, 28)
    rounded_box(d, (455, 515, 835, 745), "BM\n初始化 / 生命周期\n安全启动 / 目标选择 / 交接", NAVY, NAVY, WHITE, 25)

    d.rounded_rectangle((1030, 155, 1730, 745), radius=18, fill=rgb(WHITE), outline=rgb(MID_GREY), width=4)
    d.text((1060, 180), "外部 Flash 镜像与数据", font=font(29, True), fill=rgb(NAVY))
    rounded_box(d, (1060, 245, 1360, 355), "PBL  0x020000", PALE_BLUE, BLUE, INK, 24)
    rounded_box(d, (1400, 245, 1700, 355), "FBL  0x050000", PALE_ORANGE, ORANGE, INK, 24)
    rounded_box(d, (1060, 395, 1360, 505), "CustApp  0x090000", PALE_GREEN, GREEN, INK, 23)
    rounded_box(d, (1400, 395, 1700, 505), "ProductionApp\n0x190000", PALE_GREEN, GREEN, INK, 23)
    rounded_box(d, (1060, 555, 1700, 700), "HSM / 数据分区 / 安全数据\n由白名单或专用接口维护", LIGHT_GREY, MID_GREY, INK, 24, False)

    arrow(d, (335, 325), (455, 325), BLUE)
    d.text((335, 280), "CAN FD / UDS", font=font(17, True), fill=rgb(BLUE))
    arrow(d, (835, 285), (1030, 285), TEAL)
    d.text((845, 235), "擦除 / 下载 / 校验", font=font(20, True), fill=rgb(TEAL))
    arrow(d, (835, 630), (1030, 630), NAVY)
    d.text((850, 580), "选择 / 加载 / 跳转", font=font(20, True), fill=rgb(NAVY))

    d.text((60, 850), "共享平台与可信状态", font=font(30, True), fill=rgb(NAVY))
    shared = [
        ("SoC / Cortex-R5\n向量、时钟、RAM、IPC", BLUE),
        ("Fls / Flash Driver\n外部 Flash 访问", TEAL),
        ("NvM / Fee\nvalid 与重编程状态", GREEN),
        ("HSM / Security\n生命周期、Hash、签名", ORANGE),
        ("共享 RAM\nLC + CRC8 / 错误记录", MID_GREY),
    ]
    x = 60
    widths = [325, 305, 305, 325, 330]
    for (label, color), w in zip(shared, widths):
        rounded_box(d, (x, 900, x + w, 1050), label, LIGHT_GREY, color, INK, 24, False, 10, 3)
        x += w + 18
    return image_bytes(img)


def bm_flow_diagram() -> bytes:
    img = Image.new("RGB", (1600, 2120), rgb(WHITE))
    d = ImageDraw.Draw(img)
    diagram_title(d, img.width, "BM 启动设计流程", "当前 ELF 基线的路径优先级与失败边界")
    cx = 600

    boxes = [
        ((420, 150, 780, 250), "上电 / 复位进入 BM", NAVY),
        ((360, 320, 840, 460), "BootM_Init\nSoC、Flash、NvM、CAN、安全 Flash", BLUE),
        ((360, 530, 840, 670), "安全基础初始化 + 早期 CAN 窗口\n接收 FORCEJUMP", TEAL),
    ]
    for box, text, color in boxes:
        rounded_box(d, box, text, color, color, WHITE, 29)
    arrow(d, (cx, 250), (cx, 320), NAVY)
    arrow(d, (cx, 460), (cx, 530), NAVY)

    lc = diamond(d, (cx, 800), 600, 220, "生命周期门通过？")
    arrow(d, (cx, 670), (cx, lc[1]), NAVY)
    rounded_box(d, (1030, 705, 1490, 890), "安全错误态\n停留 BM，不执行未验证目标", PALE_RED, RED, RED, 27)
    arrow(d, (lc[2], 800), (1030, 800), RED)
    d.text((825, 755), "否且无 FORCE", font=font(20, True), fill=rgb(RED))
    d.text((910, 545), "OnBoard / Customizing：比较\n0x3E2000 前 128 字节 magic\n失败时仅 FORCE 1/2 可旁路", font=font(21), fill=rgb(MID_GREY))

    rounded_box(
        d,
        (205, 1000, 995, 1360),
        "Boot_Logic 启动选择优先级\n\n1. FORCE：1→FBL，2→PBL\n   跳过 valid，但不跳过安全检查；失败无回退\n2. 重编程请求：FBL / PBL\n   检查 valid + 安全；失败固定尝试 CustApp\n3. 普通启动：App → FBL → PBL\n   每个候选均检查 valid + 安全",
        PALE_BLUE,
        BLUE,
        INK,
        24,
        False,
    )
    arrow(d, (cx, lc[3]), (cx, 1000), GREEN)
    d.text((640, 935), "通过 / 合法 FORCE", font=font(20, True), fill=rgb(GREEN))

    selected = diamond(d, (cx, 1515), 520, 190, "获得可启动目标？", PALE_GREEN, GREEN, 26)
    arrow(d, (cx, 1360), (cx, selected[1]), NAVY)
    rounded_box(d, (1050, 1425, 1490, 1605), "无可启动目标\n记录错误并停留 BM", PALE_RED, RED, RED, 25)
    arrow(d, (selected[2], 1515), (1050, 1515), RED)
    d.text((900, 1470), "否", font=font(21, True), fill=rgb(RED))

    rounded_box(d, (90, 1740, 650, 1940), "FBL / PBL 交接\n安全装载后复制 0x400 字节向量\n0x1021E000 → 0x00000000\nBLX 0", PALE_ORANGE, ORANGE, INK, 24, False)
    rounded_box(d, (760, 1740, 1320, 1940), "App 交接\n解析 AppImage / RPRC\n加载多核镜像并跳转 entryPoint", PALE_GREEN, GREEN, INK, 24, False)
    arrow(d, (cx, selected[3]), (370, 1740), ORANGE)
    arrow(d, (cx, selected[3]), (1040, 1740), GREEN)
    d.text((300, 1660), "imageId 1/2", font=font(20, True), fill=rgb(ORANGE))
    d.text((865, 1660), "imageId 0", font=font(20, True), fill=rgb(GREEN))
    rounded_box(d, (430, 2020, 980, 2090), "目标软件运行；异常返回视为启动失败", LIGHT_GREY, MID_GREY, INK, 22, False, 8)
    arrow(d, (370, 1940), (650, 2020), ORANGE)
    arrow(d, (1040, 1940), (760, 2020), GREEN)
    return image_bytes(img)


def pbl_flow_diagram() -> bytes:
    img = Image.new("RGB", (1600, 2300), rgb(WHITE))
    d = ImageDraw.Draw(img)
    diagram_title(d, img.width, "PBL 升级设计流程", "典型 UDS 事务；Flash job、校验和 NvM 提交均按异步状态机推进")
    cx = 610
    x0, x1 = 260, 960
    y = 155
    steps = [
        ("进入 PBL\nEcuM / OS / CAN / DCM 初始化", NAVY, 135),
        ("UDS 会话与 SecurityAccess\n建立授权上下文", BLUE, 135),
        ("RoutineControl 0xFF00 擦除\n白名单 / 范围检查\nCustApp 擦除前先提交 invalid=0x55", ORANGE, 165),
        ("RequestDownload\n建立 ImageContext，返回最大块长 0x0FFF", TEAL, 145),
        ("TransferData\n按 0x100 页缓存并异步写 Flash", TEAL, 145),
        ("RequestTransferExit\n最后一页补 0x00 并完成异步写入", TEAL, 145),
        ("下载镜像校验\nCRC32 + 按安全策略启用的 SHA-512 / 签名", BLUE, 165),
    ]
    prev_bottom = None
    for text, color, h in steps:
        box = (x0, y, x1, y + h)
        rounded_box(d, box, text, color, color, WHITE, 27)
        if prev_bottom is not None:
            arrow(d, (cx, prev_bottom), (cx, y), NAVY)
        prev_bottom = y + h
        y += h + 70

    result = diamond(d, (cx, 1780), 580, 190, "校验全部通过？", PALE_GREEN, GREEN, 27)
    arrow(d, (cx, prev_bottom), (cx, result[1]), NAVY)
    rounded_box(d, (1030, 1685, 1510, 1880), "失败\n保持 / 写回 invalid\n返回明确错误，不启动半写镜像", PALE_RED, RED, RED, 25)
    arrow(d, (result[2], 1780), (1030, 1780), RED)
    d.text((920, 1735), "否", font=font(21, True), fill=rgb(RED))
    rounded_box(d, (260, 1985, 960, 2135), "成功提交\nCustApp valid=0xAA → NvM/Fee 持久化\n→ 受控复位", GREEN, GREEN, WHITE, 25)
    arrow(d, (cx, result[3]), (cx, 1985), GREEN)
    d.text((640, 1915), "是", font=font(21, True), fill=rgb(GREEN))

    rounded_box(d, (1040, 500, 1510, 1160), "全过程保护规则\n\n• 仅允许九个 LogBlock\n• 请求不得跨分区\n• 任一时刻仅一个 Flash job\n• pending 不得覆盖 context / 缓冲区\n• 擦除、写入、校验或 NvM 失败均不得置 valid\n• 断电后必须保持可恢复状态", LIGHT_GREY, MID_GREY, INK, 23, False)
    d.text((70, 2225), "说明：完整服务顺序、会话权限、NRC 和时序以冻结后的 ODX/诊断矩阵为准。", font=font(20), fill=rgb(MID_GREY))
    return image_bytes(img)


def function_block_diagram() -> bytes:
    img = Image.new("RGB", (1800, 1330), rgb(WHITE))
    d = ImageDraw.Draw(img)
    diagram_title(d, img.width, "功能块与责任边界", "供应商内部模块可重构，但对外接口、状态迁移和保护边界必须保持")

    d.text((70, 155), "BM 启动域", font=font(31, True), fill=rgb(NAVY))
    d.text((660, 155), "PBL 升级域", font=font(31, True), fill=rgb(TEAL))
    d.text((1250, 155), "共享基础软件 / 硬件域", font=font(31, True), fill=rgb(ORANGE))

    bm_blocks = [
        ("Reset / BootM_Init", BLUE),
        ("Early CAN FORCEJUMP", BLUE),
        ("Lifecycle + Magic Gate", NAVY),
        ("Boot_Logic Target Selection", NAVY),
        ("SecBoot + Error Record", ORANGE),
        ("AppImage / RPRC Loader", GREEN),
        ("Vector Relocation / Handover", GREEN),
    ]
    pbl_blocks = [
        ("EcuM / OS Scheduler", TEAL),
        ("CAN / CanTp / PduR / DCM", TEAL),
        ("SWDL Diagnostic Adapter", BLUE),
        ("ImageM Context + Whitelist", BLUE),
        ("FlashPort Async Jobs", ORANGE),
        ("CRC / Hash / Signature Verify", ORANGE),
        ("Valid / Reprogram Commit", GREEN),
    ]
    shared_blocks = [
        ("Cortex-R5 / Clock / RAM / IPC", BLUE),
        ("Fls + External Flash", TEAL),
        ("NvM / Fee Physical Banks", GREEN),
        ("HSM / Key Slots / Lifecycle", ORANGE),
        ("Shared LC + CRC8 / Error RAM", MID_GREY),
        ("Watchdog / Reset / Diagnostics", RED),
    ]

    def column(x: int, blocks: list[tuple[str, str]], width: int = 480) -> None:
        y = 220
        for label, color in blocks:
            rounded_box(d, (x, y, x + width, y + 115), label, LIGHT_GREY, color, INK, 25, False, 9, 3)
            y += 135

    column(70, bm_blocks)
    column(660, pbl_blocks)
    column(1250, shared_blocks, 480)

    rounded_box(d, (70, 1190, 1730, 1280), "禁止绕过的边界：DCM/SWDL 不得直接任意写 Flash；BM 不得跳转未通过 valid/安全决策的目标；PBL 不得提交未完整验证的镜像。", PALE_RED, RED, RED, 25, True, 10)
    return image_bytes(img)


def memory_map_diagram() -> bytes:
    img = Image.new("RGB", (1800, 2130), rgb(WHITE))
    d = ImageDraw.Draw(img)
    diagram_title(d, img.width, "4 MiB 外部 Flash 内存布局", "示意图不按长度比例绘制；地址边界和所有者以标注为准")

    panels = [
        (
            60,
            "可执行镜像与数据区  [0x000000, 0x340000)",
            [
                ("0x000000-0x020000", "BM", "ImageM 可下载", NAVY),
                ("0x020000-0x050000", "PBL / PlatformBoot", "ImageM 可下载", BLUE),
                ("0x050000-0x090000", "FBL / CustBoot", "ImageM 可下载", ORANGE),
                ("0x090000-0x190000", "CustApp", "ImageM 可下载", GREEN),
                ("0x190000-0x290000", "ProductionApp", "ImageM 可下载", GREEN),
                ("0x290000-0x2D0000", "Reserved", "禁止", MID_GREY),
                ("0x2D0000-0x310000", "HSM Image", "ImageM 可下载", ORANGE),
                ("0x310000-0x320000", "WeifuData", "ImageM 可下载", TEAL),
                ("0x320000-0x330000", "CustData", "ImageM 可下载", TEAL),
                ("0x330000-0x340000", "ClibData", "ImageM 可下载", TEAL),
            ],
        ),
        (
            920,
            "NVM、安全与保留区  [0x340000, 0x400000)",
            [
                ("0x340000-0x350000", "ProductionSW / App NVM", "ImageM 禁止", RED),
                ("0x350000-0x390000", "Customer App NVM / Fee Bank 0", "Fee 管理", GREEN),
                ("0x390000-0x3D0000", "Customer App NVM / Fee Bank 1", "Fee 管理", GREEN),
                ("0x3D0000-0x3E0000", "Reserved / Undefined", "禁止", MID_GREY),
                ("0x3E0000-0x3E1000", "Lifecycle / Security Data", "专用安全路径", ORANGE),
                ("0x3E1000-0x3E2000", "Security Key Data", "专用安全路径", ORANGE),
                ("0x3E2000-0x3E3000", "Lifecycle Magic", "DID FC00 专用", BLUE),
                ("0x3E3000-0x3E4000", "Fast App Selection", "DID FC01 专用", BLUE),
                ("0x3E4000-0x3F0000", "Reserved", "当前无入口", MID_GREY),
                ("0x3F0000-0x400000", "Future Reserved", "当前无入口", MID_GREY),
            ],
        ),
    ]

    for x, title, rows in panels:
        d.text((x, 150), title, font=font(27, True), fill=rgb(NAVY))
        y = 215
        for address, label, access, color in rows:
            d.rounded_rectangle((x, y, x + 820, y + 145), radius=9, fill=rgb(LIGHT_GREY), outline=rgb(color), width=4)
            d.rectangle((x, y, x + 24, y + 145), fill=rgb(color))
            d.text((x + 45, y + 20), address, font=font(23, True), fill=rgb(color))
            d.text((x + 45, y + 63), label, font=font(25, True), fill=rgb(INK))
            ab = d.textbbox((0, 0), access, font=font(21))
            d.text((x + 790 - (ab[2] - ab[0]), y + 105), access, font=font(21), fill=rgb(MID_GREY))
            y += 158

    rounded_box(
        d,
        (60, 1880, 1740, 2070),
        "NVM 保护结论\n正常 CustApp / ProductionApp 镜像擦除不直接进入 0x340000-0x370000。\nCustApp valid 更新会触发 Fee 事务，可能在 0x350000 起的物理 bank 内编程、回收或迁移；验收应检查逻辑 NvM 数据保持，而不是要求整区原始字节不变。",
        PALE_RED,
        RED,
        INK,
        25,
        False,
        12,
    )
    return image_bytes(img)


def run_xml(text: str, *, bold: bool = False, italic: bool = False, color: str | None = None, size: int | None = None) -> str:
    props: list[str] = [
        '<w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="Microsoft YaHei"/>',
    ]
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if size:
        props.append(f'<w:sz w:val="{size * 2}"/><w:szCs w:val="{size * 2}"/>')
    chunks = text.split("\n")
    content: list[str] = []
    for index, chunk in enumerate(chunks):
        if index:
            content.append("<w:br/>")
        content.append(f'<w:t xml:space="preserve">{escape(chunk)}</w:t>')
    return f"<w:r><w:rPr>{''.join(props)}</w:rPr>{''.join(content)}</w:r>"


class DocxBuilder:
    def __init__(self) -> None:
        self.body: list[str] = []
        self.images: list[tuple[str, bytes, str]] = []
        self.rels: list[tuple[str, str, str]] = []
        self.next_rel = 6
        self.next_doc_pr = 1

    def paragraph(
        self,
        text: str = "",
        *,
        style: str | None = None,
        align: str | None = None,
        bold: bool = False,
        italic: bool = False,
        color: str | None = None,
        size: int | None = None,
        before: int | None = None,
        after: int | None = 120,
        keep_next: bool = False,
        page_break_before: bool = False,
        left: int | None = None,
        first_line: int | None = None,
        line: int | None = 330,
    ) -> None:
        ppr: list[str] = []
        if style:
            ppr.append(f'<w:pStyle w:val="{style}"/>')
        if align:
            ppr.append(f'<w:jc w:val="{align}"/>')
        if keep_next:
            ppr.append("<w:keepNext/>")
        if page_break_before:
            ppr.append("<w:pageBreakBefore/>")
        spacing_attrs = []
        if before is not None:
            spacing_attrs.append(f'w:before="{before}"')
        if after is not None:
            spacing_attrs.append(f'w:after="{after}"')
        if line is not None:
            spacing_attrs.extend([f'w:line="{line}"', 'w:lineRule="auto"'])
        if spacing_attrs:
            ppr.append(f"<w:spacing {' '.join(spacing_attrs)}/>")
        indent_attrs = []
        if left is not None:
            indent_attrs.append(f'w:left="{left}"')
        if first_line is not None:
            indent_attrs.append(f'w:firstLine="{first_line}"')
        if indent_attrs:
            ppr.append(f"<w:ind {' '.join(indent_attrs)}/>")
        self.body.append(
            f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{run_xml(text, bold=bold, italic=italic, color=color, size=size)}</w:p>"
        )

    def rich_paragraph(
        self,
        runs: list[dict[str, object]],
        *,
        style: str | None = None,
        align: str | None = None,
        after: int = 120,
        line: int = 330,
    ) -> None:
        ppr = []
        if style:
            ppr.append(f'<w:pStyle w:val="{style}"/>')
        if align:
            ppr.append(f'<w:jc w:val="{align}"/>')
        ppr.append(f'<w:spacing w:after="{after}" w:line="{line}" w:lineRule="auto"/>')
        rendered = "".join(run_xml(**run) for run in runs)
        self.body.append(f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{rendered}</w:p>")

    def heading(self, text: str, level: int = 1, *, page_break: bool = False) -> None:
        self.paragraph(text, style=f"Heading{level}", keep_next=True, page_break_before=page_break, after=140)

    def bullet(self, text: str, *, level: int = 0) -> None:
        prefix = "• " if level == 0 else "– "
        self.paragraph(prefix + text, left=360 + level * 360, first_line=-240, after=65, line=300)

    def numbered(self, number: str, text: str) -> None:
        self.rich_paragraph(
            [
                {"text": f"{number}  ", "bold": True, "color": BLUE},
                {"text": text},
            ],
            after=80,
            line=310,
        )

    def page_break(self) -> None:
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def note(self, title: str, text: str, *, fill: str = PALE_BLUE, border: str = BLUE) -> None:
        self.table([[title + "\n" + text]], widths=[10000], header=False, fills=[[fill]], colors=[[INK]], border=border)
        self.paragraph("", after=40, line=200)

    def table(
        self,
        rows: list[list[str]],
        *,
        widths: list[int] | None = None,
        header: bool = True,
        fills: list[list[str | None]] | None = None,
        colors: list[list[str | None]] | None = None,
        border: str = LINE_GREY,
        font_size: int = 9,
    ) -> None:
        if not rows:
            return
        columns = len(rows[0])
        widths = widths or [int(10000 / columns)] * columns
        table_parts = [
            "<w:tbl>",
            "<w:tblPr>",
            '<w:tblW w:w="10000" w:type="dxa"/>',
            '<w:tblLayout w:type="fixed"/>',
            f'<w:tblBorders><w:top w:val="single" w:sz="6" w:color="{border}"/>'
            f'<w:left w:val="single" w:sz="6" w:color="{border}"/>'
            f'<w:bottom w:val="single" w:sz="6" w:color="{border}"/>'
            f'<w:right w:val="single" w:sz="6" w:color="{border}"/>'
            f'<w:insideH w:val="single" w:sz="4" w:color="{border}"/>'
            f'<w:insideV w:val="single" w:sz="4" w:color="{border}"/></w:tblBorders>',
            '<w:tblCellMar><w:top w:w="100" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="100" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar>',
            "</w:tblPr>",
            "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>",
        ]
        for row_index, row in enumerate(rows):
            table_parts.append("<w:tr>")
            if row_index == 0 and header:
                table_parts.append("<w:trPr><w:tblHeader/></w:trPr>")
            for col_index, value in enumerate(row):
                fill = NAVY if header and row_index == 0 else (LIGHT_GREY if row_index % 2 == 0 else WHITE)
                if fills and row_index < len(fills) and col_index < len(fills[row_index]) and fills[row_index][col_index]:
                    fill = str(fills[row_index][col_index])
                text_color = WHITE if header and row_index == 0 else INK
                if colors and row_index < len(colors) and col_index < len(colors[row_index]) and colors[row_index][col_index]:
                    text_color = str(colors[row_index][col_index])
                cell_p = []
                for line_index, line_value in enumerate(str(value).split("\n")):
                    ppr = '<w:pPr><w:spacing w:after="0" w:line="260" w:lineRule="auto"/></w:pPr>'
                    cell_p.append(
                        f"<w:p>{ppr}{run_xml(line_value, bold=(header and row_index == 0) or line_index == 0 and len(str(value).splitlines()) > 1, color=text_color, size=font_size)}</w:p>"
                    )
                table_parts.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{widths[col_index]}" w:type="dxa"/><w:shd w:fill="{fill}"/></w:tcPr>{"".join(cell_p)}</w:tc>'
                )
            table_parts.append("</w:tr>")
        table_parts.append("</w:tbl>")
        self.body.append("".join(table_parts))
        self.paragraph("", after=30, line=180)

    def add_image(self, name: str, data: bytes, *, width_cm: float, caption: str) -> None:
        with Image.open(io.BytesIO(data)) as image:
            width_px, height_px = image.size
        height_cm = width_cm * height_px / width_px
        cx = int(width_cm * 360000)
        cy = int(height_cm * 360000)
        rid = f"rId{self.next_rel}"
        self.next_rel += 1
        filename = f"image{len(self.images) + 1}.png"
        self.images.append((filename, data, "image/png"))
        self.rels.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", f"media/{filename}"))
        doc_pr = self.next_doc_pr
        self.next_doc_pr += 1
        drawing = f"""
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="80" w:after="80"/></w:pPr><w:r><w:drawing>
<wp:inline distT="0" distB="0" distL="0" distR="0">
  <wp:extent cx="{cx}" cy="{cy}"/>
  <wp:effectExtent l="0" t="0" r="0" b="0"/>
  <wp:docPr id="{doc_pr}" name="{escape(name)}" descr="{escape(caption)}"/>
  <wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
  <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
    <pic:pic>
      <pic:nvPicPr><pic:cNvPr id="0" name="{escape(filename)}"/><pic:cNvPicPr/></pic:nvPicPr>
      <pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
      <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
    </pic:pic>
  </a:graphicData></a:graphic>
</wp:inline></w:drawing></w:r></w:p>
"""
        self.body.append(drawing)
        self.paragraph(caption, style="Caption", align="center", color=MID_GREY, size=9, after=160, line=260)

    def toc(self) -> None:
        self.body.append(
            """
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/><w:spacing w:after="160"/></w:pPr><w:r><w:t>目录</w:t></w:r></w:p>
<w:p><w:pPr><w:spacing w:after="80"/></w:pPr>
  <w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>
  <w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>
  <w:r><w:fldChar w:fldCharType="separate"/></w:r>
  <w:r><w:t>打开 Word 后选择目录并更新域。</w:t></w:r>
  <w:r><w:fldChar w:fldCharType="end"/></w:r>
</w:p>
"""
        )

    def build(self, output: Path) -> None:
        document = document_xml("".join(self.body))
        rels = document_rels_xml(self.rels)
        content_types = content_types_xml(self.images)
        parts: dict[str, bytes] = {
            "[Content_Types].xml": content_types.encode("utf-8"),
            "_rels/.rels": root_rels_xml().encode("utf-8"),
            "docProps/core.xml": core_xml().encode("utf-8"),
            "docProps/app.xml": app_xml().encode("utf-8"),
            "word/document.xml": document.encode("utf-8"),
            "word/_rels/document.xml.rels": rels.encode("utf-8"),
            "word/styles.xml": styles_xml().encode("utf-8"),
            "word/settings.xml": settings_xml().encode("utf-8"),
            "word/header1.xml": header_xml().encode("utf-8"),
            "word/header2.xml": first_header_xml().encode("utf-8"),
            "word/footer1.xml": footer_xml().encode("utf-8"),
        }
        for filename, data, _ in self.images:
            parts[f"word/media/{filename}"] = data
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in parts.items():
                archive.writestr(name, data)


def document_xml(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
<w:body>
{body}
<w:sectPr>
  <w:headerReference w:type="default" r:id="rId3"/>
  <w:headerReference w:type="first" r:id="rId4"/>
  <w:footerReference w:type="default" r:id="rId5"/>
  <w:titlePg/>
  <w:pgSz w:w="11906" w:h="16838"/>
  <w:pgMar w:top="1020" w:right="1020" w:bottom="1134" w:left="1020" w:header="480" w:footer="480" w:gutter="0"/>
  <w:cols w:space="720"/>
  <w:docGrid w:linePitch="312"/>
</w:sectPr>
</w:body></w:document>"""


def styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="Microsoft YaHei"/><w:color w:val="{INK}"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="330" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:before="180" w:after="160"/></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="54"/><w:szCs w:val="54"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="100"/></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/><w:color w:val="{BLUE}"/><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:uiPriority w:val="9"/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="300" w:after="140"/><w:outlineLvl w:val="0"/><w:pBdr><w:bottom w:val="single" w:sz="10" w:color="{BLUE}" w:space="5"/></w:pBdr></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:uiPriority w:val="9"/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="220" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="{BLUE}"/><w:sz w:val="27"/><w:szCs w:val="27"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:uiPriority w:val="9"/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="160" w:after="80"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="{TEAL}"/><w:sz w:val="23"/><w:szCs w:val="23"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="140"/></w:pPr><w:rPr><w:i/><w:color w:val="{MID_GREY}"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="TOCHeading"><w:name w:val="TOC Heading"/><w:basedOn w:val="Heading1"/><w:next w:val="Normal"/><w:qFormat/></w:style>
</w:styles>"""


def settings_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:updateFields w:val="true"/>
  <w:defaultTabStop w:val="720"/>
  <w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def document_rels_xml(extra: list[tuple[str, str, str]]) -> str:
    fixed = [
        ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"),
        ("rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings", "settings.xml"),
        ("rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header", "header1.xml"),
        ("rId4", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header", "header2.xml"),
        ("rId5", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer", "footer1.xml"),
    ]
    rows = "".join(f'<Relationship Id="{rid}" Type="{typ}" Target="{target}"/>' for rid, typ, target in fixed + extra)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rows}</Relationships>'


def content_types_xml(images: list[tuple[str, bytes, str]]) -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/header2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def header_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" w:color="{LINE_GREY}"/></w:pBdr><w:spacing w:after="40"/></w:pPr>{run_xml('CR60 Light BYD Bootloader 供应商总体设计', bold=True, color=NAVY, size=9)}</w:p></w:hdr>"""


def first_header_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p/></w:hdr>"""


def footer_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/><w:pBdr><w:top w:val="single" w:sz="4" w:space="4" w:color="{LINE_GREY}"/></w:pBdr></w:pPr>{run_xml('内部/供应商受控资料  |  第 ', color=MID_GREY, size=8)}<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>{run_xml(' 页', color=MID_GREY, size=8)}</w:p></w:ftr>"""


def core_xml() -> str:
    created = f"{date.today().isoformat()}T00:00:00Z"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>CR60 Light BYD Bootloader（BM + PBL）供应商总体架构与设计要求</dc:title>
  <dc:subject>供应商 BM/PBL 开发总体设计输入</dc:subject>
  <dc:creator>项目组</dc:creator>
  <cp:keywords>Bootloader; BM; PBL; UDS; Flash; NVM; Supplier</cp:keywords>
  <dc:description>由无源码 ELF 静态逆向详细设计文档提炼的总体设计版。</dc:description>
  <cp:revision>1</cp:revision>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application><AppVersion>16.0000</AppVersion><Company>Project Team</Company>
</Properties>"""


def validate_source() -> str:
    if not SOURCE_MD.exists():
        raise FileNotFoundError(SOURCE_MD)
    raw = SOURCE_MD.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    required = [
        "## 1. 总体架构",
        "### 3.6 普通启动优先级",
        "### 4.3 OTA/UDS 主流程",
        "### 2.4 外部 Flash 分区与保护边界",
        "## 14. 接口冻结与供应商交付物",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"Source document is missing required sections: {missing}")
    return hashlib.sha256(raw).hexdigest().upper()


def add_document_content(doc: DocxBuilder, source_sha: str, figures: dict[str, bytes]) -> None:
    # Cover
    doc.paragraph("CR60 LIGHT BYD", align="center", bold=True, color=BLUE, size=13, before=700, after=160)
    doc.paragraph("BOOTLOADER（BM + PBL）", style="Title", after=100)
    doc.paragraph("供应商总体架构与设计要求", style="Subtitle", after=220)
    doc.paragraph("总体设计版", align="center", bold=True, color=WHITE, size=14, before=100, after=180)
    # A compact title band implemented as a one-cell table.
    doc.table([["用于供应商方案设计、开发启动与接口冻结"]], widths=[10000], header=False, fills=[[NAVY]], colors=[[WHITE]], border=NAVY, font_size=13)
    doc.paragraph("", before=560, after=20, line=180)
    doc.table(
        [
            ["文档版本", "V1.0"],
            ["编制日期", "2026-07-20"],
            ["详细设计基线", "Bootloader_BM_PBL_Detailed_Design_and_Technical_Requirements.md V3.1"],
            ["适用对象", "BM / PBL 软件供应商、系统工程、测试与安全评审人员"],
            ["资料等级", "内部/供应商受控资料"],
        ],
        widths=[2700, 7300],
        header=False,
        fills=[[PALE_BLUE, WHITE], [PALE_BLUE, WHITE], [PALE_BLUE, WHITE], [PALE_BLUE, WHITE], [PALE_BLUE, WHITE]],
        font_size=10,
    )
    doc.paragraph("本文件是总体设计输入，不替代详细设计、诊断规范、镜像格式规范、HSM 配置和目标板验证。", align="center", italic=True, color=RED, size=10, before=160)
    doc.page_break()

    # Document control
    doc.heading("文档控制", 1)
    doc.heading("修订记录", 2)
    doc.table(
        [
            ["版本", "日期", "修改内容", "状态"],
            ["V1.0", "2026-07-20", "从 V3.1 详细逆向设计中提炼总体架构、设计流程、功能块、内存布局和供应商最低要求。", "初版"],
        ],
        widths=[1200, 1600, 5700, 1500],
    )
    doc.heading("分析基线", 2)
    doc.table(
        [
            ["基线项", "SHA-256 / 说明"],
            ["D_CR60_Light_BM.elf", "CB02B2FCD702BE6A2F6999F56202E0B58EC15BC2689EF3AE3FE497054624E5C3"],
            ["D_CR60_Light_PBL.elf", "BB8FDA704106300380FC4916807B089E21AFD1CFF97A817629F745B3B69DE300"],
            ["详细设计 Markdown", source_sha],
            ["静态证据目录", "BM_PBL_Reverse_Engineering_Evidence/"],
        ],
        widths=[2800, 7200],
        font_size=9,
    )
    doc.note(
        "使用边界",
        "本文将当前 ELF 能直接确认的高层行为作为兼容基线，同时将供应商必须补充的安全增强写为技术要求。仅凭本总体设计可以开展架构和方案设计，但不足以宣称实现与当前 ELF 完全等效；编码前必须冻结第 9 节接口，并以详细设计及差分测试为准。",
        fill=PALE_ORANGE,
        border=ORANGE,
    )
    doc.page_break()
    doc.toc()
    doc.page_break()

    # 1
    doc.heading("1. 文档目的与范围", 1)
    doc.paragraph("本文向供应商定义 CR60 Light BYD Bootloader 的总体架构与主要设计约束。Bootloader 由 Boot Manager（BM）和 Platform/Primary Bootloader（PBL）组成，并与现有 FBL、CustApp、ProductionApp、HSM、安全数据和 NvM/Fee 协同工作。")
    doc.heading("1.1 本文覆盖", 2)
    for item in [
        "BM、PBL 的职责边界和总体软件分层。",
        "BM 的启动目标、选择优先级、生命周期门和交接方式。",
        "PBL 的 UDS 升级主流程、Flash/NvM 提交原则和地址保护边界。",
        "4 MiB 外部 Flash 分区、共享状态和关键外部接口。",
        "供应商开发的最低技术要求、交付物和验收框架。",
    ]:
        doc.bullet(item)
    doc.heading("1.2 本文暂不展开", 2)
    for item in [
        "每个函数、结构体、局部状态码和反汇编指令级实现。",
        "完整 UDS 服务矩阵、NRC、P2/P2*/S3 时序和 SecurityAccess 算法。",
        "安全容器每个字段、签名覆盖范围、HSM key slot 和证书内容。",
        "芯片 Flash 物理扇区几何、Fee 逻辑块映射和所有掉电时序点。",
    ]:
        doc.bullet(item)
    doc.note("配套详细资料", "上述内容由 V3.1 详细设计文档、ELF 证据包、ODX/PDX、镜像格式规范、Flash/HSM 数据手册和目标板测试共同冻结。")

    # 2
    doc.heading("2. 系统上下文与术语", 1, page_break=True)
    doc.table(
        [
            ["术语", "含义", "当前固定地址 / 说明"],
            ["BM", "Boot Manager，启动决策与安全交接模块", "入口 0x00020000；运行代码主要位于内部 RAM 映射"],
            ["PBL / pfboot", "Platform/Primary Bootloader，UDS/OTA 刷写执行模块", "外部 Flash 0x020000"],
            ["FBL / custboot", "客户/功能 Bootloader", "外部 Flash 0x050000"],
            ["CustApp", "客户应用镜像", "外部 Flash 0x090000"],
            ["ProductionApp", "量产应用镜像", "外部 Flash 0x190000"],
            ["ImageM", "镜像下载上下文、白名单、校验与状态管理", "PBL 核心抽象"],
            ["Fee/NvM", "非易失逻辑块与物理 bank 管理", "Fee banks: 0x350000-0x3D0000"],
            ["HSSE/HSM", "硬件安全模块与量产安全设备类型", "生命周期、Hash、签名、解密与 key 管理"],
        ],
        widths=[1800, 4300, 3900],
        font_size=9,
    )
    doc.add_image("overall_architecture", figures["architecture"], width_cm=17.2, caption="图 1  BM + PBL 总体架构")
    doc.paragraph("系统包含两条核心控制链：")
    doc.numbered("A.", "启动控制链：复位进入 BM，BM 获取持久状态和安全状态，选择目标镜像，完成验证、加载和交接。")
    doc.numbered("B.", "升级执行链：诊断请求进入 PBL，PBL 通过白名单、异步 Flash job 和校验状态机完成镜像更新，最后提交 valid 状态。")

    # 3
    doc.heading("3. 总体设计原则", 1, page_break=True)
    principles = [
        ("职责分离", "BM 不承担 UDS 数据下载；PBL 不替代 BM 的最终启动决策。"),
        ("固定分区", "镜像地址、NVM、安全数据和保留区必须由统一链接/配置源生成，BM 与 PBL 配置不得漂移。"),
        ("先验证后启动", "valid 仅表示允许尝试；所有实际启动目标仍必须经过统一安全决策入口。"),
        ("先失效后升级", "CustApp 擦除前先持久化 invalid，完整校验成功后才恢复 valid。"),
        ("单一异步作业", "任一时刻只允许一个受控 Flash job；pending 状态不得被新请求覆盖。"),
        ("地址最小授权", "请求必须完整位于一个白名单分区，页写和扇区擦除后的物理影响也不得越界。"),
        ("故障可恢复", "断电、超时、通信中断、安全失败和 NvM 失败不得导致半写镜像被启动。"),
        ("行为可追溯", "当前 ELF 等效行为、安全增强和待确认项必须分别记录并纳入差分测试。"),
    ]
    doc.table([["原则", "设计要求"]] + [[a, b] for a, b in principles], widths=[2200, 7800], font_size=9)
    doc.add_image("functional_blocks", figures["blocks"], width_cm=17.2, caption="图 2  BM、PBL 与共享平台的功能块和责任边界")

    # 4 BM
    doc.heading("4. BM 总体设计", 1, page_break=True)
    doc.heading("4.1 BM 主要职责", 2)
    for item in [
        "初始化 CPU/SoC、Flash、NvM、CAN、IPC 和安全基础模块。",
        "读取 App/FBL/PBL valid、重编程请求、快速 App 选择和生命周期状态。",
        "在上电早期窗口接收 FBL/PBL FORCEJUMP 帧。",
        "按固定优先级选择 App、FBL 或 PBL，并记录安全启动结果。",
        "对目标执行安全决策；加载 AppImage/RPRC 或重定位 Bootloader 向量后交接。",
        "无合法目标或安全初始化失败时停留在 BM 安全错误态。",
    ]:
        doc.bullet(item)
    doc.heading("4.2 启动目标", 2)
    doc.table(
        [
            ["imageId", "目标", "起始地址", "valid 规则", "交接方式"],
            ["0", "CustApp / ProductionApp", "0x090000 / 0x190000", "Application_Valid_Flag != 0x55", "AppImage/RPRC 多核加载后跳 entryPoint"],
            ["1", "FBL / custboot", "0x050000", "0xAAAAAAAA", "向量搬移后 BLX 0"],
            ["2", "PBL / pfboot", "0x020000", "0xAAAAAAAA", "向量搬移后 BLX 0"],
        ],
        widths=[1000, 2300, 2000, 2400, 2300],
        font_size=9,
    )
    doc.heading("4.3 启动决策优先级", 2)
    doc.table(
        [
            ["优先级", "触发条件", "目标", "valid 检查", "失败处理"],
            ["1", "早期 CAN StayInBootFlag=1/2", "1→FBL；2→PBL", "绕过目标 valid", "安全检查失败后直接留在 BM，不回退"],
            ["2", "FBL/PBL 重编程 magic", "请求的 FBL 或 PBL", "必须为 0xAAAAAAAA", "目标不可用时仅固定尝试 CustApp 0x090000"],
            ["3", "无强制、无有效重编程请求", "App → FBL → PBL", "逐个检查", "当前候选失败后尝试下一个，耗尽后留在 BM"],
        ],
        widths=[1000, 2600, 2200, 1900, 2300],
        font_size=9,
    )
    doc.note(
        "生命周期门",
        "仅 OnBoard 和 Customizing 生命周期比较 0x3E2000 前 128 字节 magic。magic 失败且没有合法 FORCEJUMP 时不得进入启动选择；FORCEJUMP 只允许旁路该门和目标 valid，不得旁路目标安全检查。",
        fill=PALE_ORANGE,
        border=ORANGE,
    )
    doc.page_break()
    doc.add_image("bm_boot_flow", figures["bm_flow"], width_cm=14.0, caption="图 3  BM 启动选择、验证与交接流程")
    doc.heading("4.4 安全启动与交接要求", 2)
    for item in [
        "所有目标使用统一安全决策入口；HSSE 量产生命周期按策略强制 Hash、签名和可选解密。",
        "安全初始化、镜像加载、Hash、签名和解密失败必须区分记录，并保持 fail-closed。",
        "FBL/PBL 交接前将 RAM 0x1021E000 起的 0x400 字节向量复制到 0x00000000，然后直接 BLX 0。",
        "App 必须兼容现有 AppImage/RPRC 格式和量产 golden images，同时增加长度、偏移、地址、溢出和重叠检查。",
    ]:
        doc.bullet(item)

    # 5 PBL
    doc.heading("5. PBL 总体设计", 1, page_break=True)
    doc.heading("5.1 PBL 主要职责", 2)
    for item in [
        "运行 EcuM/OS 周期任务并维持 CAN FD、CanTp、PduR、DCM 和网络管理。",
        "处理擦除、RequestDownload、TransferData、TransferExit 和校验相关 UDS 回调。",
        "通过 ImageM 建立下载上下文、执行九块白名单和写权限检查。",
        "通过 FlashPort/Fls 执行异步分块擦除、256 字节页缓存写入和末页收尾。",
        "执行 CRC32，并按安全策略执行 SHA-512 和签名验证。",
        "CustApp 擦除前提交 invalid=0x55，验证通过后提交 valid=0xAA。",
    ]:
        doc.bullet(item)
    doc.heading("5.2 调度模型", 2)
    doc.table(
        [
            ["执行上下文", "主要内容", "设计约束"],
            ["1 ms task", "CAN/DCM/CanTp、安全访问延时", "不得被长 Flash/HSM 操作阻塞"],
            ["10 ms task", "BootM、CanSM、ComM、EcuM、NvM、安全 Flash", "持续推进持久化和网络状态"],
            ["Background task", "ImageM 校验、FlashPort job、TransferExit、兼容性 job", "异步状态可查询，超时/取消可恢复"],
        ],
        widths=[1900, 3800, 4300],
        font_size=9,
    )
    doc.page_break()
    doc.add_image("pbl_upgrade_flow", figures["pbl_flow"], width_cm=13.8, caption="图 4  PBL 典型 UDS 升级事务和 valid 提交流程")
    doc.heading("5.3 升级状态与关键约束", 2)
    doc.table(
        [
            ["阶段", "主要动作", "失败原则"],
            ["授权/打开", "检查会话、安全等级、地址、长度和单块包含关系", "拒绝并保持原状态"],
            ["失效", "CustApp block 2 写 0x55 并确认持久化", "未确认成功不得开始擦除"],
            ["擦除", "每次最大 0x10000，异步轮询", "保持 invalid，关闭上下文"],
            ["接收/写入", "按 0x100 页缓存；TransferExit 收尾", "不得越下载窗口或覆盖 pending job"],
            ["校验", "CRC32 + 安全门控的 SHA-512/签名", "任一失败不得提交 valid"],
            ["提交/复位", "CustApp 写 0xAA，清重编程请求，确认 NvM 后复位", "持久化失败时保持恢复模式"],
        ],
        widths=[1500, 5300, 3200],
        font_size=9,
    )
    doc.heading("5.4 当前接口基线", 2)
    doc.table(
        [
            ["接口", "当前基线"],
            ["RequestDownload 最大块长度", "0x0FFF（4095 字节）"],
            ["Flash 页写", "0x100 字节；最后一页以 0x00 补齐"],
            ["Flash 擦除分块", "单次最大 0x10000 字节"],
            ["Routine 0xFF00", "目标区域擦除"],
            ["Routine 0x0212", "异步下载校验接口"],
            ["Routine 0x0205", "当前仅异步检查 App valid，并返回 0/5；不是完整版本兼容性检查"],
            ["DID FC00 / FC01", "分别专用于 0x3E2000 / 0x3E3000 扇区，不得扩展为任意地址写接口"],
        ],
        widths=[3000, 7000],
        font_size=9,
    )

    # 6 memory
    doc.heading("6. 外部 Flash 与 NVM 布局", 1, page_break=True)
    doc.add_image("external_flash_map", figures["memory"], width_cm=16.8, caption="图 5  4 MiB 外部 Flash 分区与访问边界")
    doc.heading("6.1 PBL 普通下载白名单", 2)
    doc.table(
        [
            ["imageId", "分区", "半开地址区间", "长度"],
            ["0", "BM", "[0x000000, 0x020000)", "0x020000"],
            ["2", "PBL", "[0x020000, 0x050000)", "0x030000"],
            ["1", "FBL", "[0x050000, 0x090000)", "0x040000"],
            ["3", "CustApp", "[0x090000, 0x190000)", "0x100000"],
            ["4", "ProductionApp", "[0x190000, 0x290000)", "0x100000"],
            ["7", "HSM", "[0x2D0000, 0x310000)", "0x040000"],
            ["8", "WeifuData", "[0x310000, 0x320000)", "0x010000"],
            ["5", "CustData", "[0x320000, 0x330000)", "0x010000"],
            ["6", "ClibData", "[0x330000, 0x340000)", "0x010000"],
        ],
        widths=[1200, 2500, 4000, 2300],
        font_size=9,
    )
    doc.heading("6.2 NVM 保护要求", 2)
    doc.note(
        "准确结论",
        "正常 CustApp/ProductionApp 的 ImageM 镜像擦除不会直接进入 0x340000-0x370000。CustApp 的 valid 更新会触发 Fee/NvM 事务，因此 0x350000 起的 Fee 物理 bank 可能发生页写、垃圾回收或 bank 迁移；这不应导致其他 App 逻辑 NvM block 丢失。",
        fill=PALE_RED,
        border=RED,
    )
    for item in [
        "ImageM/FlashPort 必须拒绝对 [0x340000, 0x3D0000) 的直接下载、擦除和越界页写。",
        "BM 与 PBL 必须使用完全一致的 Fee bank 配置：[0x350000,0x390000) 和 [0x390000,0x3D0000)。",
        "验收同时检查 Fls 物理 trace 与 NvM 逻辑读回；Fee 元数据变化不能直接判定为 NVM 数据被破坏。",
        "必须结合真实 Flash 扇区几何证明擦除单元不跨分区，并覆盖 Fee 回收和逐时间点掉电测试。",
    ]:
        doc.bullet(item)

    # 7 interfaces
    doc.heading("7. BM/PBL 关键接口与数据合同", 1, page_break=True)
    doc.heading("7.1 启动与共享状态", 2)
    doc.table(
        [
            ["接口/状态", "地址或值", "合同"],
            ["FBL valid word", "0x08F000 / 0xAAAAAAAA", "BM 仅在精确匹配时把 FBL 视为有效"],
            ["PBL valid word", "0x04F000 / 0xAAAAAAAA", "BM 仅在精确匹配时把 PBL 视为有效"],
            ["Application valid", "0xAA valid；0x55 invalid", "BM 当前按 !=0x55 允许尝试；PBL CustApp 按 0x55/0xAA 提交"],
            ["快速 App 选择", "0x3E3000，CUAP/PDAP", "选择 CustApp 0x090000 或 ProductionApp 0x190000"],
            ["Lifecycle 共享 RAM", "0x102DFF0C，4 字节", "{ecuLC,hsmMain,hsmSub,crc8}；CRC8 覆盖前三字节"],
            ["Lifecycle magic", "0x3E2000 前 128 字节", "仅 OnBoard/Customizing 启动门使用"],
            ["重编程请求", "FBL: 0x10021002/0x10821082\nPBL: 0x10061006/0x10861086", "优先进入对应 Bootloader；目标不可用时按 BM 固定规则回退"],
        ],
        widths=[2300, 3500, 4200],
        font_size=8,
    )
    doc.heading("7.2 早期 CAN 强制跳转", 2)
    doc.table(
        [
            ["CAN ID", "16 字节 payload", "结果"],
            ["0x190C8532", "02 10 82 46 4F 52 43 45 4A 55 4D 50 A5 B6 C7 D8", "StayInBootFlag=1，FBL"],
            ["0x190C8532", "02 10 60 46 4F 52 43 45 4A 55 4D 50 A5 B6 C7 D8", "StayInBootFlag=2，PBL"],
        ],
        widths=[2000, 5500, 2500],
        font_size=8,
    )
    doc.bullet("新实现必须先检查 DLC/长度至少为 16，再比较完整 payload；合法帧行为保持与当前基线一致。")
    doc.bullet("强制帧仅在 BM 早期窗口生效；真实时间窗口须在目标硬件测量后冻结。")
    doc.heading("7.3 Lifecycle CRC8", 2)
    doc.table(
        [
            ["参数", "值"],
            ["算法等价", "CRC-8/SAE-J1850"],
            ["Polynomial", "0x1D"],
            ["Init / XorOut", "0xFF / 0xFF"],
            ["RefIn / RefOut", "false / false"],
            ["覆盖范围", "0x102DFF0C 起前三字节；结果写偏移 +3"],
        ],
        widths=[3000, 7000],
        font_size=9,
    )

    # 8 requirements
    doc.heading("8. 供应商最低技术要求", 1, page_break=True)
    requirements = [
        ("ARCH-01", "实现 BM/PBL 分层，禁止诊断层和业务层绕过 ImageM/安全决策直接访问任意 Flash。"),
        ("BOOT-01", "保持目标地址、三层启动优先级、valid 规则、重编程映射和 CAN FORCEJUMP 行为。"),
        ("BOOT-02", "无合法目标、安全初始化失败或镜像验证失败时保持 fail-closed，不执行未验证地址。"),
        ("SEC-01", "量产生命周期下强制安全启动；密钥不进入普通软件交付物，HSM 故障可追溯。"),
        ("DL-01", "仅允许九个 LogBlock；请求、页写和物理擦除单元都不得跨越授权边界。"),
        ("DL-02", "erase/write/write-exit/verifier 任一 pending 时，新请求不得覆盖 context、job、缓冲或结果指针。"),
        ("NVM-01", "CustApp 擦除前确认 invalid 持久化，校验成功后确认 valid 持久化；失败不得继续依赖动作。"),
        ("NVM-02", "Fee 操作不得丢失非目标逻辑 NvM block；BM/PBL Fee 配置必须一致。"),
        ("ROB-01", "所有外部长度、地址加法、页/扇区对齐和镜像头字段必须检查溢出、越界与重叠。"),
        ("ROB-02", "所有 Flash/HSM/NvM pending 必须具备超时、取消或安全复位恢复方案。"),
        ("PWR-01", "擦除、每页写、TransferExit、验证和 valid 写回各关键点断电后均可安全恢复。"),
        ("COMP-01", "当前量产镜像、烧录包、签名工具、UDS 客户端和 CAN 行为保持兼容；有意差异须批准。"),
        ("QUAL-01", "提供可复现构建、MISRA/CERT-C 静态分析、覆盖率、WCET、栈水位和依赖清单。"),
    ]
    doc.table([["ID", "强制要求"]] + [[rid, text] for rid, text in requirements], widths=[1500, 8500], font_size=9)
    doc.note(
        "当前缺陷与安全增强",
        "详细设计中已识别 lifecycle 返回值忽略、CRC-invalid fallback、并发 context/job 覆盖、TransferData 子窗口未收敛、NvM 最终结果未确认等异常路径。供应商应修复，但必须把修复列为经批准的安全增强，不得宣称这些拒绝行为已由当前 ELF 实现。",
        fill=PALE_ORANGE,
        border=ORANGE,
    )

    # 9 freeze
    doc.heading("9. 编码前接口冻结清单", 1, page_break=True)
    freeze_items = [
        "完整 4 MiB Flash 分区、真实物理扇区/页几何、所有者和写保护策略。",
        "BM/PBL/FBL/App/HSM 镜像格式、链接地址、入口、头字段、padding、Hash/签名覆盖范围。",
        "AppImage/RPRC CPU 表、加载地址、PLL/时钟、核释放顺序及超时。",
        "NvM block 2/3 布局、默认值、冗余/CRC、Fee 全部逻辑 block 映射、回收与迁移原子性。",
        "完整 UDS 服务、会话/安全矩阵、DID/RID 格式、NRC、P2/P2*/S3 和 CanTp 参数。",
        "HSM 生命周期、key slot、签名/解密算法、SecurityAccess 和证书更新流程。",
        "CUAP/PDAP 快速选择策略、FC00/FC01 权限和 CustApp/ProductionApp 发布策略。",
        "Watchdog、复位原因、错误日志、超时阈值和现场恢复策略。",
    ]
    for idx, item in enumerate(freeze_items, 1):
        doc.numbered(f"{idx}.", item)
    doc.note("门槛", "以上接口没有形成双方签字版本前，供应商可以开展架构原型，但不应冻结详细设计或进入量产代码实现。", fill=PALE_RED, border=RED)

    # 10 deliverables
    doc.heading("10. 供应商交付物与验收", 1, page_break=True)
    doc.heading("10.1 强制交付物", 2)
    deliverables = [
        "Bootloader 软件架构、BM/PBL 详细设计、状态机、时序图和接口数据字典。",
        "全部源码、生成配置、链接脚本、构建脚本、固定工具版本和可复现构建说明。",
        "ELF、HEX/BIN、map、符号、反汇编、SHA-256 清单和量产烧录包。",
        "镜像打包/签名/验签工具及版本化格式规范；密钥按独立安全流程管理。",
        "单元、集成、HIL、诊断一致性、掉电、模糊、安全和性能测试报告。",
        "MISRA/CERT-C、静态分析、deviation、代码覆盖率、栈/WCET/CPU 负载和开源清单。",
        "需求到设计、代码和测试的双向追溯矩阵。",
        "与当前 ELF 的同输入差分报告，以及每项有意行为差异的客户批准记录。",
    ]
    for item in deliverables:
        doc.bullet(item)
    doc.heading("10.2 最低验收场景", 2)
    doc.table(
        [
            ["类别", "至少覆盖"],
            ["BM 启动", "普通 App→FBL→PBL、四种重编程 magic、两种 FORCEJUMP、valid/安全失败、magic/lifecycle 矩阵"],
            ["PBL 升级", "九分区边界、合法/非法 RequestDownload、跨页/末页、擦写故障、CRC/Hash/签名篡改"],
            ["NVM/Fee", "逻辑块保持、强制垃圾回收/bank 迁移、block 2/3 最终结果、0x340000 边界 trace"],
            ["断电恢复", "擦除、每页写、TransferExit、校验、invalid/valid、清重编程请求的逐时间点断电"],
            ["安全", "错 key、错 Hash、错签名、截断、回滚、短 CAN 帧、越界/溢出、并发 job 和 HSM 超时"],
            ["兼容性", "当前全部量产升级包、烧录工具、诊断脚本和启动目标与当前 ELF 对比"],
        ],
        widths=[1800, 8200],
        font_size=9,
    )
    doc.heading("10.3 接受准则", 2)
    for item in [
        "除批准差异外，启动目标、UDS 响应、NRC、pending 行为、CAN 接口和持久状态一致。",
        "任一未完整验证的镜像都不能被提交 valid 或由 BM 启动。",
        "ImageM 不直接擦写 NVM；Fee 事务保持全部非目标逻辑数据。",
        "所有 TBC 关闭，零个未批准兼容差异，零个开放安全高危/严重缺陷。",
        "客户环境可独立复现构建、烧录、升级、差分测试和故障恢复。",
    ]:
        doc.bullet(item)

    # 11 conclusion
    doc.heading("11. 结论与后续工作", 1, page_break=True)
    doc.paragraph("本文件足以支持供应商开展 BM/PBL 总体方案、模块划分、接口评审和项目估算。为了开发出与当前 BM/PBL 功能一致且异常路径更安全的量产实现，供应商仍需以 V3.1 详细设计为行为基线，并完成第 9 节接口冻结。")
    doc.note(
        "最终等效判据",
        "不是代码结构相似，也不是仅通过正常升级；而是在同一 ECU/HIL 上对当前 ELF 与供应商 ELF 施加相同输入，比较启动目标、CAN/UDS、Flash/NvM、共享状态、安全结果和所有关键掉电点。",
        fill=PALE_GREEN,
        border=GREEN,
    )
    doc.heading("后续文档层级", 2)
    doc.table(
        [
            ["阶段", "文档/活动", "输出"],
            ["当前", "本总体设计评审", "架构、职责、主流程、内存与最低要求一致"],
            ["接口冻结", "诊断、镜像、Flash/NvM、HSM、时序专题评审", "签字版接口冻结清单"],
            ["详细设计", "供应商 BM/PBL 详细设计与当前 V3.1 对照", "状态机、接口、异常路径和差异矩阵"],
            ["实现验证", "单元/集成/HIL/安全/掉电/差分", "可复现证据和量产接受报告"],
        ],
        widths=[1800, 4500, 3700],
        font_size=9,
    )
    doc.paragraph("— 文档结束 —", align="center", bold=True, color=MID_GREY, size=10, before=400, after=0)


def validate_docx(path: Path, expected_source_sha: str) -> None:
    if not path.exists() or path.stat().st_size < 100_000:
        raise RuntimeError(f"DOCX output missing or unexpectedly small: {path}")
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt DOCX ZIP member: {bad}")
        names = set(archive.namelist())
        required = {
            "[Content_Types].xml",
            "word/document.xml",
            "word/styles.xml",
            "word/_rels/document.xml.rels",
            "word/media/image1.png",
            "word/media/image5.png",
        }
        missing = required - names
        if missing:
            raise RuntimeError(f"DOCX missing parts: {sorted(missing)}")
        document = archive.read("word/document.xml").decode("utf-8", errors="strict")
        for text in [
            "供应商总体架构与设计要求",
            "BM 总体设计",
            "PBL 总体设计",
            "外部 Flash 与 NVM 布局",
            "最终等效判据",
            expected_source_sha,
        ]:
            if escape(text) not in document:
                raise RuntimeError(f"Expected text missing from DOCX: {text}")
        if "\ufffd" in document:
            raise RuntimeError("Replacement character found in document.xml")
        media = [name for name in names if name.startswith("word/media/")]
        if len(media) != 5:
            raise RuntimeError(f"Expected 5 embedded diagrams, found {len(media)}")
        for name in media:
            with Image.open(io.BytesIO(archive.read(name))) as image:
                image.verify()


def main() -> None:
    if not FONT_REGULAR.exists() or not FONT_BOLD.exists():
        raise FileNotFoundError("Required Microsoft YaHei fonts are unavailable")
    source_sha = validate_source()
    figures = {
        "architecture": architecture_diagram(),
        "bm_flow": bm_flow_diagram(),
        "pbl_flow": pbl_flow_diagram(),
        "blocks": function_block_diagram(),
        "memory": memory_map_diagram(),
    }
    doc = DocxBuilder()
    add_document_content(doc, source_sha, figures)
    doc.build(OUTPUT_DOCX)
    validate_docx(OUTPUT_DOCX, source_sha)
    print(f"OUTPUT={OUTPUT_DOCX}")
    print(f"SIZE={OUTPUT_DOCX.stat().st_size}")
    print(f"SHA256={hashlib.sha256(OUTPUT_DOCX.read_bytes()).hexdigest().upper()}")
    print(f"SOURCE_SHA256={source_sha}")
    print("FIGURES=5")


if __name__ == "__main__":
    main()
