#!/usr/bin/env python3
"""Apply the local WF Word template to the latest BM/PBL supplier HLD."""

from __future__ import annotations

import copy
import hashlib
import posixpath
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "模板.docx"
SOURCE = ROOT / "Bootloader_BM_PBL_Supplier_High_Level_Design_20260720.docx"
OUTPUT = ROOT / "Bootloader_BM_PBL_Supplier_High_Level_Design_WF.docx"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

TITLE = "Bootloader BM/PBL 总体架构与设计要求"
HEADER_TITLE = "BM/PBL Design Specification  BM/PBL 总体设计规范"
BODY_WIDTH_TWIPS = 9170
MAX_IMAGE_WIDTH_EMU = 5_580_000  # 15.5 cm, within the template text area.
HEADING_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*(?:[.、])?\s+")


def qn(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def parse_xml(data: bytes) -> etree._Element:
    return etree.fromstring(data)


def xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        standalone=True,
    )


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def element_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def ensure_ppr(paragraph: etree._Element) -> etree._Element:
    ppr = paragraph.find(qn("w", "pPr"))
    if ppr is None:
        ppr = etree.Element(qn("w", "pPr"))
        paragraph.insert(0, ppr)
    return ppr


def set_pstyle(paragraph: etree._Element, style_id: str) -> None:
    ppr = ensure_ppr(paragraph)
    pstyle = ppr.find(qn("w", "pStyle"))
    if pstyle is None:
        pstyle = etree.Element(qn("w", "pStyle"))
        ppr.insert(0, pstyle)
    pstyle.set(qn("w", "val"), style_id)


def get_pstyle(paragraph: etree._Element) -> str:
    pstyle = paragraph.find("./w:pPr/w:pStyle", namespaces=NS)
    return pstyle.get(qn("w", "val"), "") if pstyle is not None else ""


def set_paragraph_text(paragraph: etree._Element, text: str) -> None:
    text_nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if text_nodes:
        text_nodes[0].text = text
        if text[:1].isspace() or text[-1:].isspace():
            text_nodes[0].set(XML_SPACE, "preserve")
        else:
            text_nodes[0].attrib.pop(XML_SPACE, None)
        for node in text_nodes[1:]:
            node.text = ""
        return

    run = etree.SubElement(paragraph, qn("w", "r"))
    text_node = etree.SubElement(run, qn("w", "t"))
    text_node.text = text


def replace_exact_paragraphs(
    root: etree._Element, replacements: dict[str, str]
) -> dict[str, int]:
    counts = {old: 0 for old in replacements}
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        current = paragraph_text(paragraph).strip()
        if current in replacements:
            set_paragraph_text(paragraph, replacements[current])
            counts[current] += 1
    return counts


def adapt_cover(document_root: etree._Element) -> None:
    body = document_root.find("w:body", namespaces=NS)
    cover = body.find("w:tbl", namespaces=NS)
    replacements = {
        "软件合格性测试流程": TITLE,
        "王君亦": "待填写",
        "张晓峰": "待填写",
        "王永强": "待填写",
        "软件测试工程师": "待填写",
        "项目管理高级工程师": "待填写",
        "WFSS副总经理": "待填写",
        "2026/6/3": "待签署",
    }
    counts = replace_exact_paragraphs(cover, replacements)
    expected = {
        "软件合格性测试流程": 1,
        "王君亦": 1,
        "张晓峰": 1,
        "王永强": 1,
        "软件测试工程师": 1,
        "项目管理高级工程师": 1,
        "WFSS副总经理": 1,
        "2026/6/3": 3,
    }
    if counts != expected:
        raise RuntimeError(f"WF cover structure changed unexpectedly: {counts}")


def set_cell_text(cell: etree._Element, text: str) -> None:
    paragraph = cell.find("w:p", namespaces=NS)
    if paragraph is None:
        paragraph = etree.SubElement(cell, qn("w", "p"))
    set_paragraph_text(paragraph, text)


def adapt_header(header_root: etree._Element) -> None:
    title_replaced = False
    for paragraph in header_root.xpath(".//w:p", namespaces=NS):
        if paragraph_text(paragraph).strip() == "Software Test Procedure 软件合格性测试流程":
            set_paragraph_text(paragraph, HEADER_TITLE)
            title_replaced = True
            break
    if not title_replaced:
        raise RuntimeError("WF header title cell was not found")

    cells = header_root.xpath(".//w:tc", namespaces=NS)
    number_cell_set = False
    for index, cell in enumerate(cells[:-1]):
        if "Document number" in element_text(cell):
            set_cell_text(cells[index + 1], "TBD")
            number_cell_set = True
            break
    if not number_cell_set:
        raise RuntimeError("WF document number cell was not found")


def add_unnumbered_heading_style(
    styles_root: etree._Element,
    base_style_id: str,
    style_id: str,
    style_name: str,
) -> None:
    existing = styles_root.xpath(
        f'./w:style[@w:styleId="{style_id}"]', namespaces=NS
    )
    if existing:
        return
    base = styles_root.xpath(
        f'./w:style[@w:styleId="{base_style_id}"]', namespaces=NS
    )
    if len(base) != 1:
        raise RuntimeError(f"Template heading style {base_style_id!r} is unavailable")

    style = copy.deepcopy(base[0])
    style.set(qn("w", "styleId"), style_id)
    style.set(qn("w", "customStyle"), "1")
    name = style.find(qn("w", "name"))
    name.set(qn("w", "val"), style_name)
    link = style.find(qn("w", "link"))
    if link is not None:
        style.remove(link)
    for num_pr in style.xpath("./w:pPr/w:numPr", namespaces=NS):
        num_pr.getparent().remove(num_pr)
    styles_root.append(style)


def create_fresh_toc(template_sdt: etree._Element) -> etree._Element:
    sdt = copy.deepcopy(template_sdt)
    content = sdt.find(qn("w", "sdtContent"))
    template_paragraphs = content.findall(qn("w", "p"))
    if len(template_paragraphs) < 2:
        raise RuntimeError("WF TOC content control does not contain its expected paragraphs")

    title_paragraph = copy.deepcopy(template_paragraphs[0])
    field_paragraph = copy.deepcopy(template_paragraphs[1])
    for child in list(field_paragraph):
        if child.tag != qn("w", "pPr"):
            field_paragraph.remove(child)

    begin_run = etree.SubElement(field_paragraph, qn("w", "r"))
    begin = etree.SubElement(begin_run, qn("w", "fldChar"))
    begin.set(qn("w", "fldCharType"), "begin")
    begin.set(qn("w", "dirty"), "true")

    instruction_run = etree.SubElement(field_paragraph, qn("w", "r"))
    instruction = etree.SubElement(instruction_run, qn("w", "instrText"))
    instruction.set(XML_SPACE, "preserve")
    instruction.text = ' TOC \\o "1-3" \\h \\z \\u '

    separate_run = etree.SubElement(field_paragraph, qn("w", "r"))
    separate = etree.SubElement(separate_run, qn("w", "fldChar"))
    separate.set(qn("w", "fldCharType"), "separate")

    result_run = etree.SubElement(field_paragraph, qn("w", "r"))
    result = etree.SubElement(result_run, qn("w", "t"))
    result.text = "目录将在打开文档时自动更新"

    end_run = etree.SubElement(field_paragraph, qn("w", "r"))
    end = etree.SubElement(end_run, qn("w", "fldChar"))
    end.set(qn("w", "fldCharType"), "end")

    for child in list(content):
        content.remove(child)
    content.append(title_paragraph)
    content.append(field_paragraph)
    return sdt


def update_settings(settings_root: etree._Element) -> None:
    update = settings_root.find(qn("w", "updateFields"))
    if update is None:
        update = etree.SubElement(settings_root, qn("w", "updateFields"))
    update.set(qn("w", "val"), "true")


def clear_direct_paragraph_format(paragraph: etree._Element) -> None:
    ppr = ensure_ppr(paragraph)
    removable = {
        "contextualSpacing",
        "ind",
        "jc",
        "keepLines",
        "keepNext",
        "numPr",
        "outlineLvl",
        "pageBreakBefore",
        "spacing",
        "widowControl",
    }
    for child in list(ppr):
        if etree.QName(child).localname in removable:
            ppr.remove(child)


def remove_direct_run_format(paragraph: etree._Element) -> None:
    for run_properties in paragraph.xpath(".//w:r/w:rPr", namespaces=NS):
        run_properties.getparent().remove(run_properties)


def set_run_format(
    run: etree._Element,
    size_half_points: int,
    *,
    color: str | None = None,
    bold: bool | None = None,
) -> None:
    rpr = run.find(qn("w", "rPr"))
    if rpr is None:
        rpr = etree.Element(qn("w", "rPr"))
        run.insert(0, rpr)

    for old in rpr.findall(qn("w", "rFonts")):
        rpr.remove(old)
    fonts = etree.Element(qn("w", "rFonts"))
    fonts.set(qn("w", "ascii"), "Times New Roman")
    fonts.set(qn("w", "hAnsi"), "Times New Roman")
    fonts.set(qn("w", "eastAsia"), "宋体")
    fonts.set(qn("w", "cs"), "Times New Roman")
    rpr.insert(0, fonts)

    for tag in ("sz", "szCs", "lang"):
        for old in rpr.findall(qn("w", tag)):
            rpr.remove(old)
    size = etree.SubElement(rpr, qn("w", "sz"))
    size.set(qn("w", "val"), str(size_half_points))
    size_cs = etree.SubElement(rpr, qn("w", "szCs"))
    size_cs.set(qn("w", "val"), str(size_half_points))
    language = etree.SubElement(rpr, qn("w", "lang"))
    language.set(qn("w", "val"), "zh-CN")

    if color is not None:
        for old in rpr.findall(qn("w", "color")):
            rpr.remove(old)
        color_element = etree.Element(qn("w", "color"))
        color_element.set(qn("w", "val"), color)
        insert_at = max(1, len(rpr) - 3)
        rpr.insert(insert_at, color_element)

    if bold is not None:
        for tag in ("b", "bCs"):
            old = rpr.find(qn("w", tag))
            if bold and old is None:
                marker = etree.Element(qn("w", tag))
                rpr.insert(1, marker)
            elif not bold and old is not None:
                rpr.remove(old)


def set_paragraph_layout(
    paragraph: etree._Element,
    *,
    alignment: str,
    after: int,
    line: int,
    left: int | None = None,
    hanging: int | None = None,
) -> None:
    ppr = ensure_ppr(paragraph)
    for tag in ("spacing", "jc", "ind"):
        for old in ppr.findall(qn("w", tag)):
            ppr.remove(old)

    spacing = etree.SubElement(ppr, qn("w", "spacing"))
    spacing.set(qn("w", "after"), str(after))
    spacing.set(qn("w", "line"), str(line))
    spacing.set(qn("w", "lineRule"), "auto")
    justify = etree.SubElement(ppr, qn("w", "jc"))
    justify.set(qn("w", "val"), alignment)
    if left is not None or hanging is not None:
        indent = etree.SubElement(ppr, qn("w", "ind"))
        if left is not None:
            indent.set(qn("w", "left"), str(left))
        if hanging is not None:
            indent.set(qn("w", "hanging"), str(hanging))


def normalize_body_paragraph(paragraph: etree._Element) -> None:
    style = get_pstyle(paragraph)
    text = paragraph_text(paragraph).strip()
    if style in {"1", "2", "3"}:
        match = HEADING_PREFIX.match(text)
        if match:
            set_paragraph_text(paragraph, text[match.end() :])
        elif style == "1":
            set_pstyle(paragraph, "WFHeading1U")
        elif style == "2":
            set_pstyle(paragraph, "WFHeading2U")
        else:
            set_pstyle(paragraph, "WFHeading3U")
        clear_direct_paragraph_format(paragraph)
        remove_direct_run_format(paragraph)
        return

    if style == "a5":
        set_pstyle(paragraph, "a4")
        clear_direct_paragraph_format(paragraph)
        remove_direct_run_format(paragraph)
        return

    has_drawing = bool(paragraph.xpath(".//w:drawing", namespaces=NS))
    if has_drawing:
        set_paragraph_layout(paragraph, alignment="center", after=60, line=240)
    elif not text:
        set_paragraph_layout(paragraph, alignment="left", after=0, line=240)
    elif text.startswith("•"):
        set_paragraph_layout(
            paragraph,
            alignment="both",
            after=40,
            line=312,
            left=420,
            hanging=240,
        )
    elif re.match(r"^\d+\.\s+", text):
        set_paragraph_layout(
            paragraph,
            alignment="both",
            after=40,
            line=312,
            left=420,
            hanging=360,
        )
    else:
        set_paragraph_layout(paragraph, alignment="both", after=80, line=312)

    for run in paragraph.xpath(".//w:r", namespaces=NS):
        set_run_format(run, 21)


def ensure_table_property(table_properties: etree._Element, local: str) -> etree._Element:
    element = table_properties.find(qn("w", local))
    if element is None:
        element = etree.SubElement(table_properties, qn("w", local))
    return element


def set_cell_shading(cell: etree._Element, fill: str) -> None:
    tcpr = cell.find(qn("w", "tcPr"))
    if tcpr is None:
        tcpr = etree.Element(qn("w", "tcPr"))
        cell.insert(0, tcpr)
    shading = tcpr.find(qn("w", "shd"))
    if shading is None:
        shading = etree.SubElement(tcpr, qn("w", "shd"))
    shading.set(qn("w", "val"), "clear")
    shading.set(qn("w", "color"), "auto")
    shading.set(qn("w", "fill"), fill)


def set_table_borders(table_properties: etree._Element) -> None:
    borders = ensure_table_property(table_properties, "tblBorders")
    for local in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = borders.find(qn("w", local))
        if border is None:
            border = etree.SubElement(borders, qn("w", local))
        border.set(qn("w", "val"), "single")
        border.set(qn("w", "sz"), "4")
        border.set(qn("w", "space"), "0")
        border.set(qn("w", "color"), "808080")


def normalize_table(table: etree._Element) -> None:
    table_properties = table.find(qn("w", "tblPr"))
    if table_properties is None:
        table_properties = etree.Element(qn("w", "tblPr"))
        table.insert(0, table_properties)

    table_width = ensure_table_property(table_properties, "tblW")
    table_width.set(qn("w", "type"), "dxa")
    table_width.set(qn("w", "w"), str(BODY_WIDTH_TWIPS))
    table_indent = ensure_table_property(table_properties, "tblInd")
    table_indent.set(qn("w", "type"), "dxa")
    table_indent.set(qn("w", "w"), "0")
    layout = ensure_table_property(table_properties, "tblLayout")
    layout.set(qn("w", "type"), "fixed")
    set_table_borders(table_properties)

    margins = ensure_table_property(table_properties, "tblCellMar")
    for local, value in (("top", 50), ("left", 80), ("bottom", 50), ("right", 80)):
        margin = margins.find(qn("w", local))
        if margin is None:
            margin = etree.SubElement(margins, qn("w", local))
        margin.set(qn("w", "type"), "dxa")
        margin.set(qn("w", "w"), str(value))

    grid_columns = table.xpath("./w:tblGrid/w:gridCol", namespaces=NS)
    old_widths = [int(col.get(qn("w", "w"), "0")) for col in grid_columns]
    old_total = sum(old_widths)
    factor = BODY_WIDTH_TWIPS / old_total if old_total else 1.0
    if old_total:
        scaled = [max(120, round(width * factor)) for width in old_widths]
        scaled[-1] += BODY_WIDTH_TWIPS - sum(scaled)
        for column, width in zip(grid_columns, scaled):
            column.set(qn("w", "w"), str(width))
        for width_element in table.xpath(".//w:tcPr/w:tcW", namespaces=NS):
            if width_element.get(qn("w", "type"), "dxa") != "dxa":
                continue
            old_width = int(width_element.get(qn("w", "w"), "0"))
            if old_width > 0:
                width_element.set(qn("w", "w"), str(max(120, round(old_width * factor))))

    rows = table.findall(qn("w", "tr"))
    is_callout = len(rows) == 1
    for row_index, row in enumerate(rows):
        trpr = row.find(qn("w", "trPr"))
        if trpr is None:
            trpr = etree.Element(qn("w", "trPr"))
            row.insert(0, trpr)
        if trpr.find(qn("w", "cantSplit")) is None:
            etree.SubElement(trpr, qn("w", "cantSplit"))
        if row_index == 0 and not is_callout and trpr.find(qn("w", "tblHeader")) is None:
            etree.SubElement(trpr, qn("w", "tblHeader"))

        for cell in row.findall(qn("w", "tc")):
            tcpr = cell.find(qn("w", "tcPr"))
            if tcpr is None:
                tcpr = etree.Element(qn("w", "tcPr"))
                cell.insert(0, tcpr)
            vertical = tcpr.find(qn("w", "vAlign"))
            if vertical is None:
                vertical = etree.SubElement(tcpr, qn("w", "vAlign"))
            vertical.set(qn("w", "val"), "center")

            header_cell = row_index == 0 and not is_callout
            if header_cell:
                set_cell_shading(cell, "0070C0")
            elif is_callout:
                set_cell_shading(cell, "D9EAF7")

            for paragraph in cell.xpath(".//w:p", namespaces=NS):
                set_paragraph_layout(
                    paragraph,
                    alignment="center" if header_cell else "left",
                    after=0,
                    line=240,
                )
                for run in paragraph.xpath(".//w:r", namespaces=NS):
                    set_run_format(
                        run,
                        18,
                        color="FFFFFF" if header_cell else "000000",
                        bold=True if header_cell else None,
                    )


def scale_drawings(element: etree._Element) -> None:
    for drawing in element.xpath(".//w:drawing", namespaces=NS):
        extent = drawing.find(".//wp:extent", namespaces=NS)
        if extent is None:
            continue
        old_cx = int(extent.get("cx", "0"))
        old_cy = int(extent.get("cy", "0"))
        if old_cx <= MAX_IMAGE_WIDTH_EMU or old_cx == 0:
            continue
        factor = MAX_IMAGE_WIDTH_EMU / old_cx
        new_cx = MAX_IMAGE_WIDTH_EMU
        new_cy = round(old_cy * factor)
        extent.set("cx", str(new_cx))
        extent.set("cy", str(new_cy))
        for graphic_extent in drawing.xpath(".//a:xfrm/a:ext", namespaces=NS):
            graphic_extent.set("cx", str(new_cx))
            graphic_extent.set("cy", str(new_cy))


def normalize_source_element(element: etree._Element) -> None:
    tables: list[etree._Element] = []
    if element.tag == qn("w", "tbl"):
        tables.append(element)
    tables.extend(element.xpath(".//w:tbl", namespaces=NS))
    for table in tables:
        normalize_table(table)

    paragraphs: list[etree._Element] = []
    if element.tag == qn("w", "p"):
        paragraphs.append(element)
    paragraphs.extend(element.xpath(".//w:p", namespaces=NS))
    for paragraph in paragraphs:
        if paragraph.xpath("ancestor::w:tbl", namespaces=NS):
            continue
        normalize_body_paragraph(paragraph)
    scale_drawings(element)


def select_source_content(source_body: etree._Element) -> tuple[list[etree._Element], list[etree._Element]]:
    children = list(source_body)
    control_start = next(
        index
        for index, child in enumerate(children)
        if child.tag == qn("w", "p") and paragraph_text(child).strip() == "文档控制"
    )
    toc_start = next(
        index
        for index, child in enumerate(children)
        if index > control_start
        and child.tag == qn("w", "p")
        and get_pstyle(child) == "TOC"
    )
    main_start = next(
        index
        for index, child in enumerate(children)
        if child.tag == qn("w", "p")
        and "文档目的与范围" in paragraph_text(child)
        and HEADING_PREFIX.match(paragraph_text(child).strip())
    )
    section_index = next(
        index for index, child in enumerate(children) if child.tag == qn("w", "sectPr")
    )
    return children[control_start:toc_start], children[main_start:section_index]


def remap_images(
    elements: list[etree._Element],
    source_relationships: etree._Element,
    template_relationships: etree._Element,
    source_package: dict[str, bytes],
    output_package: dict[str, bytes],
) -> dict[str, str]:
    used_ids = {
        blip.get(qn("r", "embed"))
        for element in elements
        for blip in element.xpath(".//a:blip[@r:embed]", namespaces=NS)
    }
    image_relationships = {
        rel.get("Id"): rel
        for rel in source_relationships
        if rel.get("Type", "").endswith("/image")
    }
    missing = used_ids - image_relationships.keys()
    if missing:
        raise RuntimeError(f"Source image relationships are missing: {sorted(missing)}")

    mapping: dict[str, str] = {}
    for image_index, old_id in enumerate(sorted(used_ids), start=1):
        relationship = image_relationships[old_id]
        target = relationship.get("Target")
        source_part = posixpath.normpath(posixpath.join("word", target))
        suffix = Path(target).suffix.lower() or ".bin"
        new_part = f"word/media/wf_image{image_index}{suffix}"
        new_target = f"media/wf_image{image_index}{suffix}"
        new_id = f"rId{100 + image_index}"
        output_package[new_part] = source_package[source_part]
        new_relationship = etree.SubElement(template_relationships, qn("rel", "Relationship"))
        new_relationship.set("Id", new_id)
        new_relationship.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
        )
        new_relationship.set("Target", new_target)
        mapping[old_id] = new_id

    for element in elements:
        for blip in element.xpath(".//a:blip[@r:embed]", namespaces=NS):
            blip.set(qn("r", "embed"), mapping[blip.get(qn("r", "embed"))])
    return mapping


def add_png_content_type(content_types: etree._Element) -> None:
    png_defaults = content_types.xpath(
        './ct:Default[translate(@Extension, "PNG", "png")="png"]', namespaces=NS
    )
    if png_defaults:
        return
    default = etree.SubElement(content_types, qn("ct", "Default"))
    default.set("Extension", "png")
    default.set("ContentType", "image/png")


def set_core_property(root: etree._Element, namespace: str, local: str, value: str) -> None:
    tag = f"{{{namespace}}}{local}"
    element = root.find(tag)
    if element is None:
        element = etree.SubElement(root, tag)
    element.text = value


def update_core_properties(core_root: etree._Element) -> None:
    set_core_property(core_root, NS["dc"], "title", TITLE)
    set_core_property(core_root, NS["dc"], "subject", "BM/PBL 供应商总体架构与设计要求")
    modified = core_root.find(qn("dcterms", "modified"))
    if modified is not None:
        modified.text = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )


def build_document() -> None:
    if not TEMPLATE.exists():
        candidates = sorted(ROOT.glob("*.docx"), key=lambda path: path.stat().st_size)
        if not candidates:
            raise FileNotFoundError("No WF Word template was found")
        template_path = candidates[0]
    else:
        template_path = TEMPLATE
    if not SOURCE.exists():
        raise FileNotFoundError(f"Content source is missing: {SOURCE.name}")

    with zipfile.ZipFile(template_path) as archive:
        template_package = {name: archive.read(name) for name in archive.namelist()}
        template_infos = {info.filename: info for info in archive.infolist()}
    with zipfile.ZipFile(SOURCE) as archive:
        source_package = {name: archive.read(name) for name in archive.namelist()}

    output_package = dict(template_package)
    document = parse_xml(template_package["word/document.xml"])
    source_document = parse_xml(source_package["word/document.xml"])
    header = parse_xml(template_package["word/header1.xml"])
    styles = parse_xml(template_package["word/styles.xml"])
    settings = parse_xml(template_package["word/settings.xml"])
    relationships = parse_xml(template_package["word/_rels/document.xml.rels"])
    source_relationships = parse_xml(source_package["word/_rels/document.xml.rels"])
    content_types = parse_xml(template_package["[Content_Types].xml"])
    core_properties = parse_xml(template_package["docProps/core.xml"])

    adapt_cover(document)
    adapt_header(header)
    add_unnumbered_heading_style(styles, "1", "WFHeading1U", "WF Unnumbered Heading 1")
    add_unnumbered_heading_style(styles, "2", "WFHeading2U", "WF Unnumbered Heading 2")
    add_unnumbered_heading_style(styles, "3", "WFHeading3U", "WF Unnumbered Heading 3")
    update_settings(settings)
    add_png_content_type(content_types)
    update_core_properties(core_properties)

    body = document.find("w:body", namespaces=NS)
    original_template_children = list(body)
    template_toc = next(
        child for child in original_template_children if child.tag == qn("w", "sdt")
    )
    section_properties = next(
        child for child in original_template_children if child.tag == qn("w", "sectPr")
    )
    source_body = source_document.find("w:body", namespaces=NS)
    control_source, main_source = select_source_content(source_body)
    control = [copy.deepcopy(element) for element in control_source]
    main = [copy.deepcopy(element) for element in main_source]
    imported = control + main
    for element in imported:
        normalize_source_element(element)

    remap_images(
        imported,
        source_relationships,
        relationships,
        source_package,
        output_package,
    )

    for child in list(body):
        body.remove(child)
    body.append(copy.deepcopy(original_template_children[0]))  # WF cover/signatures.
    body.append(copy.deepcopy(original_template_children[1]))
    body.append(copy.deepcopy(original_template_children[2]))  # Cover page break.
    body.append(create_fresh_toc(template_toc))
    body.append(copy.deepcopy(original_template_children[4]))
    body.append(copy.deepcopy(original_template_children[5]))  # TOC page break.
    for element in control:
        body.append(element)
    body.append(copy.deepcopy(original_template_children[5]))  # Main content starts anew.
    for element in main:
        body.append(element)
    body.append(copy.deepcopy(section_properties))

    output_package["word/document.xml"] = xml_bytes(document)
    output_package["word/header1.xml"] = xml_bytes(header)
    output_package["word/styles.xml"] = xml_bytes(styles)
    output_package["word/settings.xml"] = xml_bytes(settings)
    output_package["word/_rels/document.xml.rels"] = xml_bytes(relationships)
    output_package["[Content_Types].xml"] = xml_bytes(content_types)
    output_package["docProps/core.xml"] = xml_bytes(core_properties)

    temporary = OUTPUT.with_suffix(".tmp.docx")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in template_package:
            info = copy.copy(template_infos[name])
            archive.writestr(info, output_package[name])
        for name in sorted(output_package.keys() - template_package.keys()):
            archive.writestr(name, output_package[name])
    temporary.replace(OUTPUT)


def resolve_relationship_target(rels_name: str, target: str) -> str:
    if rels_name == "_rels/.rels":
        base = ""
    else:
        owner_dir, rels_file = posixpath.split(rels_name)
        base_dir = posixpath.dirname(owner_dir)
        owner_name = rels_file[: -len(".rels")]
        base = posixpath.dirname(posixpath.join(base_dir, owner_name))
    return posixpath.normpath(posixpath.join(base, target.lstrip("/")))


def validate_document() -> dict[str, object]:
    with zipfile.ZipFile(OUTPUT) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"Corrupt ZIP member: {bad_member}")
        names = set(archive.namelist())
        for name in names:
            if name.endswith(".xml") or name.endswith(".rels"):
                parse_xml(archive.read(name))

        for rels_name in (name for name in names if name.endswith(".rels")):
            rels = parse_xml(archive.read(rels_name))
            for relationship in rels:
                if relationship.get("TargetMode") == "External":
                    continue
                target = resolve_relationship_target(rels_name, relationship.get("Target"))
                if target not in names:
                    raise RuntimeError(
                        f"Broken relationship in {rels_name}: {relationship.get('Target')}"
                    )

        document = parse_xml(archive.read("word/document.xml"))
        header = parse_xml(archive.read("word/header1.xml"))
        footer = parse_xml(archive.read("word/footer1.xml"))
        settings = parse_xml(archive.read("word/settings.xml"))
        document_text = element_text(document)
        header_text = element_text(header)
        footer_text = element_text(footer)

        required_document_text = [TITLE, "技术研究院", "☑秘密", "待填写", "待签署"]
        for required in required_document_text:
            if required not in document_text:
                raise RuntimeError(f"Required WF cover text is missing: {required}")
        forbidden = [
            "软件合格性测试流程",
            "王君亦",
            "张晓峰",
            "王永强",
            "软件测试工程师",
            "项目管理高级工程师",
            "WFSS副总经理",
        ]
        for old in forbidden:
            if old in document_text:
                raise RuntimeError(f"Template sample content remains in the document: {old}")
        for required in (
            "Development quality process 研发质量体系流程",
            HEADER_TITLE,
            "Document number文件号",
            "TBD",
            "Version版本",
            "V1.0",
            "Page页次",
        ):
            if required not in header_text:
                raise RuntimeError(f"Required WF header text is missing: {required}")
        if "Template number模板编号: SWE6_PROC_01" not in footer_text:
            raise RuntimeError("WF footer template number is missing")
        if settings.find(qn("w", "updateFields")) is None:
            raise RuntimeError("Automatic field update is not enabled")
        if "\ufffd" in document_text + header_text + footer_text:
            raise RuntimeError("Unicode replacement characters were found")

        section = document.find(".//w:body/w:sectPr", namespaces=NS)
        page_size = section.find(qn("w", "pgSz"))
        margins = section.find(qn("w", "pgMar"))
        expected_page = {"w": "11906", "h": "16838"}
        for key, value in expected_page.items():
            if page_size.get(qn("w", key)) != value:
                raise RuntimeError("WF A4 page size was not preserved")
        expected_margins = {
            "top": "1440",
            "right": "1106",
            "bottom": "1077",
            "left": "1622",
            "header": "851",
            "footer": "851",
        }
        for key, value in expected_margins.items():
            if margins.get(qn("w", key)) != value:
                raise RuntimeError(f"WF page margin {key} was not preserved")

        body = document.find("w:body", namespaces=NS)
        headings = body.xpath(
            './w:p[w:pPr/w:pStyle[@w:val="1" or @w:val="2" or '
            '@w:val="WFHeading1U" or @w:val="WFHeading2U"]]',
            namespaces=NS,
        )
        tables = body.xpath("./w:tbl", namespaces=NS)
        body_images = body.xpath(".//a:blip[@r:embed]", namespaces=NS)
        png_parts = sorted(name for name in names if name.startswith("word/media/wf_image"))
        if len(headings) != 33:
            raise RuntimeError(f"Unexpected heading count: {len(headings)}")
        if len(tables) != 24:
            raise RuntimeError(f"Unexpected table count: {len(tables)}")
        if len(body_images) != 5 or len(png_parts) != 5:
            raise RuntimeError(
                f"Unexpected body image count: embeds={len(body_images)}, parts={len(png_parts)}"
            )
        for drawing_extent in body.xpath(".//wp:extent", namespaces=NS):
            if int(drawing_extent.get("cx", "0")) > MAX_IMAGE_WIDTH_EMU:
                raise RuntimeError("A body diagram exceeds the WF template text width")
        for table in tables[1:]:
            columns = table.xpath("./w:tblGrid/w:gridCol", namespaces=NS)
            if columns and sum(int(column.get(qn("w", "w"), "0")) for column in columns) != BODY_WIDTH_TWIPS:
                raise RuntimeError("An imported table exceeds the WF template text width")
        if "0x340000-0x370000" not in document_text:
            raise RuntimeError("The NVM protection conclusion was lost during migration")
        if "D_CR60_Light_BM.elf" not in document_text or "D_CR60_Light_PBL.elf" not in document_text:
            raise RuntimeError("The ELF analysis baseline was lost during migration")

        with zipfile.ZipFile(SOURCE) as source_archive:
            source_document = parse_xml(source_archive.read("word/document.xml"))
            source_body = source_document.find("w:body", namespaces=NS)
            source_control, source_main = select_source_content(source_body)

            expected_content: list[tuple[str, str]] = []
            for element in source_control + source_main:
                text = element_text(element)
                if element.tag == qn("w", "p") and get_pstyle(element) in {"1", "2", "3"}:
                    text = HEADING_PREFIX.sub("", text)
                if text.strip():
                    expected_content.append((etree.QName(element).localname, text))

            body_children = list(body)
            imported_start = next(
                index
                for index, element in enumerate(body_children)
                if element.tag == qn("w", "p") and get_pstyle(element) == "WFHeading1U"
            )
            actual_content = [
                (etree.QName(element).localname, element_text(element))
                for element in body_children[imported_start:]
                if element.tag != qn("w", "sectPr") and element_text(element).strip()
            ]
            if actual_content != expected_content:
                raise RuntimeError("Technical content changed during WF format migration")

            source_rels = parse_xml(source_archive.read("word/_rels/document.xml.rels"))
            source_image_hashes = sorted(
                hashlib.sha256(
                    source_archive.read(posixpath.normpath(posixpath.join("word", rel.get("Target"))))
                ).digest()
                for rel in source_rels
                if rel.get("Type", "").endswith("/image")
            )
            output_image_hashes = sorted(
                hashlib.sha256(archive.read(part)).digest() for part in png_parts
            )
            if output_image_hashes != source_image_hashes:
                raise RuntimeError("A source diagram changed during WF format migration")

    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest().upper()
    return {
        "output": OUTPUT.name,
        "bytes": OUTPUT.stat().st_size,
        "sha256": digest,
        "headings": 33,
        "tables": 24,
        "body_images": 5,
    }


if __name__ == "__main__":
    build_document()
    result = validate_document()
    for key, value in result.items():
        print(f"{key}: {value}")
