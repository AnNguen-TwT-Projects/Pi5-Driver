# -*- coding: utf-8 -*-
"""Tạo báo cáo cuối kỳ (Word) cho project LCD2004 + 4 nút trên Pi5.
Chạy trong WSL:  python3 make_report.py   -> Report_LCD2004_Pi5_v2.docx
Sau đó chạy update_fields.ps1 trên Windows để Word điền mục lục, số trang.
"""
import os
import re
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "fig")
OUT = os.path.join(HERE, "Report_LCD2004_Pi5_v2.docx")

FONT = "Times New Roman"
MONO = "Consolas"
BODY_PT = 13
HEADER_TEXT = ("Project Topic 2 – Linux Device Driver for an LCD2004 "
               "and Four Push Buttons on Raspberry Pi 5")

doc = Document()

# ---------------------------------------------------------------- styles

def set_font(style_or_run, name=FONT, size=None, bold=None, italic=None, color=None):
    f = style_or_run.font
    f.name = name
    if size is not None:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color is not None:
        f.color.rgb = color
    el = style_or_run.element if hasattr(style_or_run, "element") else style_or_run._element
    rpr = el.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), name)
    # Bỏ font theo theme (Calibri Light của Heading), nếu không Word bỏ qua font đã đặt
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(a)) is not None:
            del rfonts.attrib[qn(a)]


st = doc.styles
normal = st["Normal"]
set_font(normal, size=BODY_PT)
pf = normal.paragraph_format
pf.line_spacing = 1.3
pf.space_after = Pt(6)
pf.space_before = Pt(0)
pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

BLACK = RGBColor(0, 0, 0)
for name, size, align, before, after, italic in (
        ("Heading 1", 15, WD_ALIGN_PARAGRAPH.CENTER, 0, 18, False),
        ("Heading 2", 13.5, WD_ALIGN_PARAGRAPH.LEFT, 12, 6, False),
        ("Heading 3", 13, WD_ALIGN_PARAGRAPH.LEFT, 10, 4, True)):
    s = st[name]
    set_font(s, size=size, bold=True, italic=italic, color=BLACK)
    s.paragraph_format.alignment = align
    s.paragraph_format.space_before = Pt(before)
    s.paragraph_format.space_after = Pt(after)
    s.paragraph_format.line_spacing = 1.15
    s.paragraph_format.keep_with_next = True

cap = st["Caption"]
set_font(cap, size=12, bold=False, italic=True, color=BLACK)
cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap.paragraph_format.space_before = Pt(4)
cap.paragraph_format.space_after = Pt(10)

for lst in ("List Bullet", "List Number"):
    s = st[lst]
    set_font(s, size=BODY_PT)
    s.paragraph_format.space_after = Pt(3)
    s.paragraph_format.line_spacing = 1.3

code = st.add_style("CodeBlock", 1)
code.base_style = normal
set_font(code, name=MONO, size=9.5)
code.paragraph_format.line_spacing = 1.0
code.paragraph_format.space_after = Pt(0)
code.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
code.paragraph_format.left_indent = Cm(0.3)

tbl_text = st.add_style("TableText", 1)
tbl_text.base_style = normal
set_font(tbl_text, size=11.5)
tbl_text.paragraph_format.line_spacing = 1.05
tbl_text.paragraph_format.space_after = Pt(2)
tbl_text.paragraph_format.space_before = Pt(2)
tbl_text.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

# ---------------------------------------------------------------- helpers

TOKEN = re.compile(r"(\*\*.+?\*\*|`.+?`|\*.+?\*)")


def add_runs(par, text, size=None):
    """Chữ thường; **đậm**, *nghiêng*, `code`."""
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**"):
            r = par.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`"):
            r = par.add_run(part[1:-1])
            set_font(r, name=MONO, size=(size or BODY_PT) - 2)
            continue
        elif part.startswith("*"):
            r = par.add_run(part[1:-1])
            r.italic = True
        else:
            r = par.add_run(part)
        if size:
            r.font.size = Pt(size)
    return par


def P(text, style=None, align=None, size=None, indent_first=False):
    par = doc.add_paragraph(style=style)
    add_runs(par, text, size)
    if align is not None:
        par.alignment = align
    if indent_first:
        par.paragraph_format.first_line_indent = Cm(0)
    return par


def B(text):
    return P(text, style="List Bullet")


def N(text):
    return P(text, style="List Number")


NEXT_PB = [False]   # True: tiêu đề kế tiếp bắt đầu trang mới


def take_page_break(par):
    """Sang trang bằng page_break_before (không tạo đoạn trống có thể rơi
    sang trang mới và sinh ra một trang trắng)."""
    if NEXT_PB[0]:
        par.paragraph_format.page_break_before = True
        NEXT_PB[0] = False
    return par


def H1(text):
    return take_page_break(doc.add_heading(text, level=1))


def H2(text):
    return doc.add_heading(text, level=2)


def H3(text):
    return doc.add_heading(text, level=3)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def add_field(par, instr, placeholder=""):
    def fld(t):
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), t)
        r = OxmlElement("w:r")
        r.append(e)
        return r
    par._p.append(fld("begin"))
    r = OxmlElement("w:r")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = " %s " % instr
    r.append(it)
    par._p.append(r)
    par._p.append(fld("separate"))
    run = par.add_run(placeholder)
    par._p.append(fld("end"))
    return run


def shade(el_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    el_pr.append(shd)


def p_border(par, sides=("top", "left", "bottom", "right"), color="A6A6A6", sz=6, space=4):
    ppr = par._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    for s in sides:
        e = OxmlElement("w:" + s)
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:space"), str(space))
        e.set(qn("w:color"), color)
        bdr.append(e)
    ppr.append(bdr)


fig_no = [0]
tab_no = [0]
lst_no = [0]


def caption(kind, text, counter):
    counter[0] += 1
    par = doc.add_paragraph(style="Caption")
    par.add_run(kind + " ")
    add_field(par, "SEQ %s \\* ARABIC" % kind, str(counter[0]))
    par.add_run(". " + text)
    return par


def FIGURE(fname, width_cm, text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.keep_with_next = True
    par.paragraph_format.space_before = Pt(6)
    par.add_run().add_picture(os.path.join(FIG, fname), width=Cm(width_cm))
    caption("Figure", text, fig_no)


def PHOTO(what, text, height_cm=6.0):
    """Ô giữ chỗ để nhóm dán ảnh thật."""
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.keep_with_next = True
    par.paragraph_format.space_before = Pt(6)
    par.paragraph_format.space_after = Pt(0)
    lines = int(height_cm / 0.75)
    r = par.add_run("[INSERT PHOTO: %s]" % what)
    r.italic = True
    r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    for _ in range(lines):
        r.add_break()
    p_border(par, color="808080", sz=8, space=8)
    ppr = par._p.get_or_add_pPr()
    shade(ppr, "F2F2F2")
    caption("Figure", text, fig_no)


def CODE(text, title=None):
    if title:
        lst_no[0] += 1
        t = doc.add_paragraph(style="Caption")
        t.alignment = WD_ALIGN_PARAGRAPH.LEFT
        t.paragraph_format.space_after = Pt(2)
        t.paragraph_format.keep_with_next = True
        t.add_run("Listing %d. %s" % (lst_no[0], title))
    lines = text.strip("\n").split("\n")
    for i, line in enumerate(lines):
        par = doc.add_paragraph(style="CodeBlock")
        par.add_run(line if line else " ")
        ppr = par._p.get_or_add_pPr()
        shade(ppr, "F3F3F3")
        if i < len(lines) - 1:
            par.paragraph_format.keep_with_next = True
        if i == 0:
            par.paragraph_format.space_before = Pt(2)
    doc.paragraphs[-1].paragraph_format.space_after = Pt(10)


def cell_text(cell, text, bold=False, align=None, size=None):
    cell.text = ""
    par = cell.paragraphs[0]
    par.style = doc.styles["TableText"]
    add_runs(par, text, size)
    if bold:
        for r in par.runs:
            r.bold = True
    if align is not None:
        par.alignment = align


def table_borders(table, inner_h=True):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side, val, sz in (("top", "single", 10), ("bottom", "single", 10),
                          ("left", "nil", 0), ("right", "nil", 0),
                          ("insideH", "single" if inner_h else "nil", 4),
                          ("insideV", "nil", 0)):
        e = OxmlElement("w:" + side)
        e.set(qn("w:val"), val)
        if sz:
            e.set(qn("w:sz"), str(sz))
            e.set(qn("w:space"), "0")
            e.set(qn("w:color"), "000000" if side in ("top", "bottom") else "A6A6A6")
        borders.append(e)
    tbl_pr.append(borders)


def set_widths(table, widths):
    """Độ rộng cột phải đặt ở cả tblGrid (LibreOffice, Google Docs đọc chỗ này)
    lẫn từng ô (Word đọc chỗ này), và khóa bố cục cố định."""
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(int(sum(widths) * 567)))
    for j, w in enumerate(widths):
        table.columns[j].width = Cm(w)
    for row in table.rows:
        for j, w in enumerate(widths):
            row.cells[j].width = Cm(w)


def TABLE(caption_text, headers, rows, widths, grid=False, center_cols=()):
    if caption_text:
        caption("Table", caption_text, tab_no).paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if grid:
        t.style = doc.styles["Table Grid"]
    else:
        table_borders(t)
    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]
        cell_text(c, h, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER if j in center_cols else None)
        shade(c._tc.get_or_add_tcPr(), "E7E6E6")
    # lặp lại hàng tiêu đề khi bảng sang trang
    trpr = t.rows[0]._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    trpr.append(e)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell_text(t.rows[i + 1].cells[j], v,
                      align=WD_ALIGN_PARAGRAPH.CENTER if j in center_cols else None)
    set_widths(t, widths)
    after = doc.add_paragraph()
    after.paragraph_format.space_after = Pt(4)
    after.paragraph_format.line_spacing = 0.8
    return t


def sect_xml(section, page_fmt=None, start=None, border=False):
    """Đặt kiểu số trang và viền trang cho đúng MỘT section.
    add_section() chép sectPr của section trước, nên xóa thuộc tính cũ trước khi đặt.
    """
    sp = section._sectPr
    for tag in ("w:pgBorders", "w:pgNumType"):
        for old in sp.findall(qn(tag)):
            sp.remove(old)
    if page_fmt:
        pg = OxmlElement("w:pgNumType")
        pg.set(qn("w:fmt"), page_fmt)
        if start is not None:
            pg.set(qn("w:start"), str(start))
        # Thứ tự trong sectPr: ... pgMar, pgBorders, pgNumType, cols ...
        cols = sp.find(qn("w:cols"))
        if cols is not None:
            cols.addprevious(pg)
        else:
            sp.append(pg)
    if border:
        b = OxmlElement("w:pgBorders")
        b.set(qn("w:offsetFrom"), "page")
        for side in ("top", "left", "bottom", "right"):
            e = OxmlElement("w:" + side)
            e.set(qn("w:val"), "thinThickSmallGap")
            e.set(qn("w:sz"), "24")
            e.set(qn("w:space"), "24")
            e.set(qn("w:color"), "1F3864")
            b.append(e)
        # pgBorders phải đứng trước pgNumType và cols trong sectPr
        pgmar = sp.find(qn("w:pgMar"))
        pgmar.addnext(b)


def footer_page_number(section):
    section.footer.is_linked_to_previous = False
    par = section.footer.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(par, "PAGE", "1")


def setup_margins(section):
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.0)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(1.0)


# ================================================================ COVER
s0 = doc.sections[0]
setup_margins(s0)
sect_xml(s0, border=True)


def cover_line(text, size=13, bold=False, italic=False, before=0, after=0, color=None):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(before)
    par.paragraph_format.space_after = Pt(after)
    par.paragraph_format.line_spacing = 1.15
    r = par.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    if color:
        r.font.color.rgb = color
    return par


cover_line("HO CHI MINH CITY UNIVERSITY OF TECHNOLOGY AND ENGINEERING", 12, True, before=6)
cover_line("FACULTY OF ADVANCED EDUCATION", 12, True)
cover_line("――――――――", 12, True, after=10)
lp = doc.add_paragraph()
lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
lp.add_run().add_picture(os.path.join(FIG, "logo.png"), width=Cm(3.6))
cover_line("COURSE REPORT", 16, True, before=14)
cover_line("Subject: Embedded Systems", 13)
cover_line("First semester, academic year 2026–2027", 13, italic=True, after=16)
cover_line("PROJECT TOPIC 2: EMBEDDED LINUX SYSTEM DEVELOPMENT", 13.5, True)
cover_line("LINUX DEVICE DRIVER FOR AN LCD2004 DISPLAY", 17, True,
           before=6, color=RGBColor(0x1F, 0x38, 0x64))
cover_line("AND FOUR PUSH BUTTONS ON RASPBERRY PI 5", 17, True, after=22,
           color=RGBColor(0x1F, 0x38, 0x64))

MEMBERS = [
    # (họ tên có dấu, MSSV, phân công ngắn)
    ("Nguyễn Phước An", "24119007",
     "Device Tree overlay, Makefiles, loading the driver, building the driver into the kernel"),
    ("Đặng Đình Mạnh", "24119055",
     "LCD control over I2C (PCF8574, HD44780), LCD wiring"),
    ("Nguyễn Hoàng Nam", "24119062",
     "Button handling: interrupts, debouncing, event queue; button wiring"),
    ("Võ Minh Tâm", "24119082",
     "Device file /dev/lcd2004 (write, ioctl, read), test programs and demo"),
]

info = doc.add_table(rows=2 + len(MEMBERS), cols=3)
info.alignment = WD_TABLE_ALIGNMENT.CENTER
info_rows = [("Supervisor:", "Assoc. Prof. Dr. Trương Ngọc Sơn", ""),
             ("Class code:", "261EMSY435664E_01FIE", "")]
info_rows += [("Members:" if i == 0 else "", n, sid) for i, (n, sid, _) in enumerate(MEMBERS)]
for i, (a, b, c) in enumerate(info_rows):
    for j, v in enumerate((a, b, c)):
        cell = info.rows[i].cells[j]
        cell.text = ""
        par = cell.paragraphs[0]
        par.paragraph_format.space_after = Pt(2)
        par.paragraph_format.line_spacing = 1.15
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = par.add_run(v)
        r.font.size = Pt(13)
        r.bold = (j == 0)
        if i == 2:
            par.paragraph_format.space_before = Pt(12)
set_widths(info, (3.0, 8.2, 2.8))

cover_line("Ho Chi Minh City, October 2026", 13, italic=True, before=40)

# ================================================================ FRONT MATTER
s1 = doc.add_section(WD_SECTION.NEW_PAGE)
setup_margins(s1)
s1.header.is_linked_to_previous = False
footer_page_number(s1)
sect_xml(s1, page_fmt="lowerRoman", start=1)

H1("LIST OF CONTRIBUTING MEMBERS")
cover_line("SEMESTER I, ACADEMIC YEAR: 2026–2027", 13, True, after=2)
cover_line("GROUP: ......", 13, True, after=6)
P("**Topic:** Linux device driver for an LCD2004 display and four push buttons on "
  "Raspberry Pi 5 (Project Topic 2: Embedded Linux System Development).")
TABLE(None,
      ["Full name", "Student ID", "Assigned tasks", "Completion (%)"],
      [[n, sid, task, "100"] for n, sid, task in MEMBERS],
      [3.7, 2.3, 7.3, 2.7], grid=True, center_cols=(1, 3))

P("Lecturer’s comments:", align=WD_ALIGN_PARAGRAPH.LEFT)
for _ in range(5):
    P("." * 118, align=WD_ALIGN_PARAGRAPH.LEFT, size=11)
P("Ho Chi Minh City, ....../....../2026", align=WD_ALIGN_PARAGRAPH.RIGHT).runs[0].italic = True
P("Lecturer", align=WD_ALIGN_PARAGRAPH.RIGHT).runs[0].bold = True
NEXT_PB[0] = True


def front_title(text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_after = Pt(12)
    r = par.add_run(text)
    r.bold = True
    r.font.size = Pt(15)
    return take_page_break(par)


front_title("TABLE OF CONTENTS")
toc = doc.add_paragraph()
add_field(toc, 'TOC \\o "1-3" \\h \\z \\u', "Right-click and choose Update Field to build the table of contents.")
NEXT_PB[0] = True

H1("LIST OF FIGURES")
lof = doc.add_paragraph()
add_field(lof, 'TOC \\h \\z \\c "Figure"', "Update field to build the list of figures.")
NEXT_PB[0] = True

H1("LIST OF TABLES")
lot = doc.add_paragraph()
add_field(lot, 'TOC \\h \\z \\c "Table"', "Update field to build the list of tables.")
NEXT_PB[0] = True

H1("LIST OF ABBREVIATIONS")
abbr = [
    ("API", "Application Programming Interface"),
    ("BCM", "Broadcom pin numbering of the Raspberry Pi GPIO header"),
    ("DDRAM", "Display Data RAM of the HD44780 controller"),
    ("DT / DTS / DTBO", "Device Tree / Device Tree Source / Device Tree Blob Overlay"),
    ("GPIO", "General-Purpose Input/Output"),
    ("I2C", "Inter-Integrated Circuit, a two-wire serial bus"),
    ("IRQ", "Interrupt Request"),
    ("ISR", "Interrupt Service Routine"),
    ("kfifo", "Kernel first-in first-out ring buffer"),
    ("LCD", "Liquid Crystal Display"),
    ("OS", "Operating System"),
    ("RP1", "Raspberry Pi I/O controller chip of the Raspberry Pi 5"),
    ("SCL / SDA", "Serial Clock / Serial Data lines of I2C"),
    ("SMBus", "System Management Bus, a subset of I2C"),
    ("SoC", "System on Chip"),
    ("SSH", "Secure Shell"),
    ("WSL", "Windows Subsystem for Linux"),
]
t = doc.add_table(rows=1 + len(abbr), cols=2)
t.alignment = WD_TABLE_ALIGNMENT.CENTER
table_borders(t, inner_h=False)
cell_text(t.rows[0].cells[0], "Abbreviation", bold=True)
cell_text(t.rows[0].cells[1], "Meaning", bold=True)
for i, (a, m) in enumerate(abbr):
    cell_text(t.rows[i + 1].cells[0], a)
    cell_text(t.rows[i + 1].cells[1], m)
set_widths(t, (4.0, 12.0))

# ================================================================ MAIN BODY
s2 = doc.add_section(WD_SECTION.NEW_PAGE)
setup_margins(s2)
sect_xml(s2, page_fmt="decimal", start=1)
s2.header.is_linked_to_previous = False
hp = s2.header.paragraphs[0]
hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
hr = hp.add_run(HEADER_TEXT)
hr.italic = True
hr.font.size = Pt(11)
p_border(hp, sides=("bottom",), color="000000", sz=6, space=1)
s2.footer.is_linked_to_previous = False
footer_page_number(s2)

# ---------------------------------------------------------------- INTRODUCTION
H1("INTRODUCTION")
P("This report describes a Linux driver for a 20×4 character LCD (LCD2004) and "
  "four push buttons on a Raspberry Pi 5. It is Project Topic 2 (Embedded Linux System "
  "Development) of the course Embedded Systems.")
P("The driver controls the LCD over I2C and reads the buttons with interrupts. "
  "Programs use both devices through one file: `/dev/lcd2004`. The driver works in "
  "two forms: as a module (`.ko`) and built into the kernel.")

H2("1. Project overview")
P("On a microcontroller, the program drives the LCD and reads the buttons directly. "
  "On Linux this is not allowed: normal programs cannot touch the hardware. They must "
  "go through a driver in the kernel. The driver handles the hardware details and gives "
  "programs simple file operations: `open`, `read`, `write`, `ioctl` and `poll`.")
P("The assignment asks for a driver for an LCD or a 7-segment display together with "
  "push buttons, plus test programs and a demo where the buttons control the display. "
  "Our group chose the LCD and buttons. The hardware is a Raspberry Pi 5, an LCD2004 "
  "with a PCF8574 I2C board, a BSS138 level shifter and a board with four buttons.")

H2("2. System objectives")
B("Show text on all four rows of the LCD.")
B("Read four buttons with interrupts. One press gives exactly one event.")
B("Give programs one device file, `/dev/lcd2004`: `write()` prints text, `ioctl()` "
  "clears the screen, moves the cursor and turns the backlight on or off, `read()` "
  "and `poll()` wait for buttons.")
B("Describe the I2C address and button pins in a Device Tree overlay, not in the code.")
B("Build the driver as a module and load it (“meets requirements” level).")
B("Build the same driver into the kernel (“good” level).")
B("Write two test programs and one demo program.")
B("Protect the 3.3 V pins of the Raspberry Pi from the 5 V LCD board.")

H2("3. Scope")
P("The project covers the circuit, the driver, the Device Tree overlay, building the "
  "module and the kernel, three user programs and the tests on real hardware. The "
  "driver shows normal ASCII characters only (no Vietnamese accents), supports one LCD "
  "and exactly four buttons. Scrolling text is done by the demo program, not by the "
  "driver. Everything was tested on one Raspberry Pi 5 (4 GB) with Raspberry Pi OS "
  "64-bit and kernel 6.18.")

H2("4. Related work")
H3("4.1. Course laboratory guide")
P("The lab guide of the course (exercises 2.1–2.5) [2] writes drivers for an LED, "
  "a button and an LCD1602 on a Raspberry Pi 4. It uses older kernel functions: fixed "
  "GPIO numbers, a fixed I2C address in the code, and debouncing inside the interrupt "
  "handler. It is easy to follow but does not move well to the Raspberry Pi 5.")
H3("4.2. Drivers in the Linux kernel")
P("Linux already has a general HD44780 LCD driver [14] and a general button driver "
  "called `gpio-keys` [15]. They work well, but the LCD and the buttons become two "
  "separate devices, and the LCD is controlled with special escape codes.")
H3("4.3. User-space libraries")
P("Many hobby projects control the LCD from a normal program (for example a Python "
  "library writing to `/dev/i2c-1`). No driver is needed, so this does not meet the "
  "assignment. Also, two programs cannot share the LCD safely.")
H3("4.4. Comparison")
P("Table 1 compares these ways with our project.")
TABLE("Comparison of related approaches",
      ["Approach", "Display", "Buttons", "How programs use it"],
      [["Course lab guide [2]", "LCD1602, address fixed in code",
        "1 button, debounce in the interrupt handler", "`read()` returns a status text"],
       ["Kernel `hd44780` + `gpio-keys` [14], [15]", "General LCD driver",
        "Separate input driver", "Escape codes, input events"],
       ["User-space library", "Program writes to `/dev/i2c-1`", "Program checks the pins in a loop",
        "Library calls, no driver"],
       ["**This project**", "LCD2004, address in Device Tree",
        "4 buttons, interrupt + debounce, event queue",
        "One file: `write`, `ioctl`, `read`, `poll`"]],
      [3.6, 4.2, 4.0, 4.2])
P("Our driver uses the modern kernel style but keeps the LCD and the buttons in one "
  "small driver, so every member can explain the whole path from a button press to a "
  "character on the screen.")

H2("5. Practical significance")
P("The project shows the full chain of an embedded Linux product: circuit, Device "
  "Tree, driver, kernel build and programs. The same steps work for other small I2C "
  "or GPIO devices such as sensors or relays. The built-in kernel shows how a product "
  "can have its device working right after boot. The parts are cheap, and the source "
  "code is public [17].")

# ---------------------------------------------------------------- CHAPTER 1
NEXT_PB[0] = True
H1("CHAPTER 1: THEORETICAL BACKGROUND AND HARDWARE")
H2("1.1. Mapping to the assignment requirements")
P("Table 2 shows each requirement and where it is answered.")
TABLE("Assignment requirements and solutions",
      ["Requirement", "Solution", "Section"],
      [["Driver for an LCD with push buttons",
        "Driver `lcd2004_btn`: LCD2004 over I2C, four buttons with interrupts", "2.2–2.7"],
       ["Driver as a module, installed (meets requirements)",
        "`lcd2004_btn.ko`, loaded with `insmod` (tests HW-2, HW-7)", "3.3, 4.2"],
       ["Driver built into the kernel (good)",
        "Kernel `6.18.57-v8-16k-lcd` with the driver inside (test HW-8)", "2.9, 3.4, 4.3"],
       ["Test programs", "`lcd_test` (LCD) and `button_test` (buttons)", "2.8, 4.2"],
       ["Demo: buttons as input, LCD as output", "`demo`: greeting, member list, member details", "2.8"],
       ["Run on an embedded board", "Raspberry Pi 5, Raspberry Pi OS 64-bit", "1.3"]],
      [5.0, 8.4, 2.6], center_cols=(2,))

H2("1.2. Theoretical background")
H3("1.2.1. Kernel module and built-in driver")
P("A driver can be used in two ways:")
B("**Module (`.ko`):** a separate file. It is loaded with `insmod` and removed with "
  "`rmmod`. It must be built for the exact kernel version that is running.")
B("**Built-in:** the driver is part of the kernel file. It starts during boot and "
  "cannot be removed.")
P("The choice is made in the kernel settings (Kconfig): `=m` gives a module, `=y` "
  "gives a built-in driver. Our code uses the macro `module_i2c_driver()`, which works "
  "in both cases, so the code did not change at all.")

H3("1.2.2. Device files and misc devices")
P("Programs talk to a driver through a file in `/dev`. The driver gives the kernel a "
  "list of functions (`read`, `write`, `ioctl`, `poll`) to call when a program uses "
  "that file. The usual way to create the file takes four steps. A *misc device* does "
  "it in one call, `misc_register()`. Our driver uses it to create `/dev/lcd2004`.")

H3("1.2.3. I2C bus and PCF8574")
P("I2C uses two wires: SDA (data) and SCL (clock). Each device on the bus has an "
  "address. The Raspberry Pi is the master and starts every transfer [5].")
P("The PCF8574 is a small chip that turns I2C into 8 output pins [4]. When the Pi "
  "writes one byte, the 8 bits appear on the 8 pins P0–P7. On the LCD board these "
  "pins are wired to the LCD as in Table 3. Our board uses address 0x27. Some boards "
  "use 0x3F, so the address can be changed in the overlay.")
TABLE("PCF8574 pins and LCD signals",
      ["PCF8574 pin", "LCD signal", "Meaning"],
      [["P0", "RS", "0 = command, 1 = character"],
       ["P1", "RW", "Always 0 (we only write)"],
       ["P2", "E", "Enable: a pulse tells the LCD to read the data"],
       ["P3", "Backlight", "1 = backlight on"],
       ["P4–P7", "D4–D7", "4 data bits"]],
      [3.0, 3.0, 10.0], center_cols=(0, 1))

H3("1.2.4. HD44780 in 4-bit mode")
P("The HD44780 is the controller chip inside the LCD [3]. The PCF8574 has only 8 pins, "
  "so only 4 data lines are used. Each byte is sent in two halves (high 4 bits, then low "
  "4 bits). Each half is taken by the LCD when E goes from 1 to 0.")
P("At power-on, the datasheet asks for a fixed start-up order: wait 40 ms, send 0x3 "
  "three times, then 0x2 to enter 4-bit mode. After that, normal commands can be sent "
  "(Table 4).")
TABLE("HD44780 commands used by the driver",
      ["Code", "Command", "Meaning"],
      [["0x28", "Function set", "4-bit mode, 2 lines, 5×8 font"],
       ["0x08", "Display off", "Turn the display off during start-up"],
       ["0x01", "Clear display", "Clear the screen (takes about 1.5 ms)"],
       ["0x06", "Entry mode", "Move the cursor right after each character"],
       ["0x0C", "Display on", "Display on, no cursor"],
       ["0x80 + address", "Set address", "Move the cursor to a row and column"]],
      [2.8, 3.6, 9.6], center_cols=(0,))
P("The rows of an LCD2004 are not in order in memory. Row 0 starts at address 0x00, "
  "row 1 at 0x40, row 2 at 0x14 and row 3 at 0x54. So after row 0 the LCD jumps to "
  "row 2. To avoid this, the driver sets the address itself at the start of each row.")
P("Speed: one I2C write takes about 0.2 ms, and one character needs 4 writes, so about "
  "0.9 ms per character. A full screen (80 characters) takes about 75 ms. This is fast "
  "enough for text that moves every 200 ms.")

H3("1.2.5. GPIO, interrupts and debouncing")
P("The driver gets the button pins from the Device Tree with `devm_gpiod_get_array()` "
  "[10]. The pins are marked *active-low*: a pressed button pulls the pin to 0 V, but the "
  "driver reads 1. Each pin has an interrupt on both edges, so the driver knows when a "
  "button is pressed and when it is released.")
P("A button contact *bounces*: for a few milliseconds it opens and closes many times. "
  "Without care, one press would look like many presses. Our fix: every edge restarts a "
  "30 ms timer. The pin is read only after 30 ms with no new edge. An event is made only "
  "when the button changes from released to pressed.")

H3("1.2.6. Delayed work, kfifo, wait queue and poll")
B("**Delayed work:** an interrupt handler must be very short. So it only starts a "
  "timer; the real work runs later in a kernel thread.")
B("**kfifo:** a small queue (16 bytes) that stores button events until a program "
  "reads them. A spinlock protects it because two CPU cores can use it at once.")
B("**Wait queue:** when a program calls `read()` and there is no event, it sleeps. "
  "A new event wakes it up. No CPU time is wasted.")
B("**poll:** lets a program wait for a button *or* a timeout in one call.")

H3("1.2.7. Device Tree and overlays")
P("On ARM boards the kernel does not find devices by itself. It reads a list of "
  "devices called the Device Tree [9]. Each entry has a `compatible` name (which driver "
  "to use), an address and other data such as pins. An *overlay* is a small addition to "
  "this list. The Raspberry Pi loads it at boot when `config.txt` has a `dtoverlay=` "
  "line. When the kernel finds our entry, it calls the driver’s `probe()` function.")

H2("1.3. Hardware and components")
H3("1.3.1. Bill of materials")
TABLE("Components",
      ["Component", "Qty", "Notes"],
      [["Raspberry Pi 5 (4 GB) with 5 V/5 A power supply", "1", "Raspberry Pi OS 64-bit"],
       ["LCD2004 with PCF8574 I2C board", "1", "5 V supply, address 0x27"],
       ["4-channel level shifter (BSS138)", "1", "2 channels used for SDA and SCL"],
       ["Button board (pins V, 1, 2, 3, 4, G)", "1", "4 buttons, common ground"],
       ["Breadboard and jumper wires", "1 set", "Short I2C wires (under 20 cm)"],
       ["Multimeter", "1", "Check wiring before power-on"]],
      [6.6, 1.4, 8.0], center_cols=(1,))

H3("1.3.2. Raspberry Pi 5 and RP1")
P("On the Raspberry Pi 5, the GPIO and I2C pins are controlled by a separate chip "
  "called RP1 [6], [7]. This has two effects:")
B("Old tutorials that write directly to hardware registers do not work. Our driver only "
  "uses kernel functions.")
B("The pin number “17” in old code is not the real kernel number on the "
  "Pi 5. Our driver takes the pins from the Device Tree, so this problem does not happen.")

H3("1.3.3. Pin assignment")
TABLE("Raspberry Pi 5 pins used in the project",
      ["Pin", "Name", "Connected to"],
      [["1", "3V3", "LV of the level shifter"],
       ["2", "5V", "VCC of the LCD board and HV of the level shifter"],
       ["3", "GPIO2 (SDA)", "LV1 → HV1 → SDA of the LCD board"],
       ["5", "GPIO3 (SCL)", "LV2 → HV2 → SCL of the LCD board"],
       ["6", "GND", "GND of the LCD and the level shifter"],
       ["9", "GND", "G of the button board"],
       ["11", "GPIO17", "Button 1"],
       ["13", "GPIO27", "Button 2"],
       ["15", "GPIO22", "Button 3"],
       ["16", "GPIO23", "Button 4"],
       ["17", "3V3", "V of the button board"]],
      [2.0, 3.4, 10.6], center_cols=(0,))
FIGURE("pi5-gpio-header.png", 11.0,
       "Raspberry Pi 40-pin GPIO header (source: Raspberry Pi Ltd documentation [6])")

H3("1.3.4. Wiring diagram")
P("Figure 2 shows the full circuit. Each button connects its pin to ground when "
  "pressed. When released, the pin is kept at 3.3 V by an internal pull-up resistor.")
FIGURE("wiring-lcd2004-4-buttons.png", 15.5,
       "Wiring of the Raspberry Pi 5, level shifter, LCD board and buttons")

H3("1.3.5. Voltage protection")
P("Raspberry Pi pins accept only 3.3 V. The LCD board runs at 5 V and pulls SDA and "
  "SCL up to 5 V. If we connect it directly, the bus voltage is about:")
P("V = 3.3 + (5 − 3.3) × 1.8 / (1.8 + 4.7) ≈ 3.77 V",
  align=WD_ALIGN_PARAGRAPH.CENTER).runs[0].italic = True
P("(1.8 kΩ is the pull-up on the Pi, 4.7 kΩ is a typical pull-up on the LCD "
  "board.) This is too high. The BSS138 level shifter keeps the Pi side at 3.3 V and "
  "the LCD side at 5 V [16]. The buttons use only 3.3 V.")

# ---------------------------------------------------------------- CHAPTER 2
NEXT_PB[0] = True
H1("CHAPTER 2: SYSTEM DESIGN")
H2("2.1. System block diagram")
P("Figure 3 shows the system in four parts: programs, device file, kernel and hardware. "
  "Programs only see `/dev/lcd2004`. The driver uses the kernel I2C functions for the "
  "LCD and the GPIO functions for the buttons. The overlay tells the kernel where the "
  "devices are.")
FIGURE("block.png", 14.0, "System block diagram")

H2("2.2. Driver structure")
P("The driver is one C file, `driver/lcd2004_btn.c` (about 560 lines). It is split into "
  "parts (Table 7). Each part only calls the part below it, so each part is easy to "
  "explain.")
TABLE("Parts of the driver",
      ["Part", "Job", "Main functions"],
      [["1. I2C", "Send one byte to the PCF8574", "`pcf_write()`"],
       ["2. HD44780", "Start-up, send commands and characters, move the cursor",
        "`lcd_init()`, `lcd_cmd()`, `lcd_putc()`, `lcd_goto()`"],
       ["3. Linux interface", "Functions of the device file",
        "`lcd_write()`, `lcd_ioctl()`, `lcd_read()`, `lcd_poll()`"],
       ["Buttons", "Interrupt, debounce, event queue", "`btn_isr()`, `btn_debounce()`"],
       ["Start / stop", "Set up and remove the device", "`lcd_probe()`, `lcd_remove()`"]],
      [3.0, 6.5, 6.5])
P("All data of the device is kept in one structure, `struct lcd2004`. There are no "
  "global variables.")

H2("2.3. Device Tree overlay")
P("The overlay `dts/lcd2004-btn-overlay.dts` does two things: it sets the four button "
  "pins as inputs with pull-up, and it adds the LCD to the I2C bus with address 0x27 "
  "and the list of button pins. The parameter `addr` allows another address, for "
  "example `dtoverlay=lcd2004-btn,addr=0x3f`.")
CODE(r'''
lcd: lcd2004@27 {
    compatible = "twt,lcd2004-btn";   /* matches the driver */
    reg = <0x27>;                     /* I2C address */
    pinctrl-names = "default";
    pinctrl-0 = <&lcd_btn_pins>;      /* inputs with pull-up */
    /* button 1..4; flag 1 = active-low */
    button-gpios = <&gpio 17 1>, <&gpio 27 1>,
                   <&gpio 22 1>, <&gpio 23 1>;
    status = "okay";
};''', "LCD entry in the Device Tree overlay")

H2("2.4. Interface for programs")
P("The file `include/lcd2004_ioctl.h` is shared by the driver and the programs, so both "
  "use the same command numbers and button codes. Table 8 lists what programs can do.")
TABLE("Operations of /dev/lcd2004",
      ["Operation", "What it does"],
      [["`write()`", "Prints text. `\\n` goes to the next row. A full row continues on the next row."],
       ["`ioctl(LCD_IOC_CLEAR)`", "Clears the screen"],
       ["`ioctl(LCD_IOC_SET_CURSOR)`", "Moves the cursor to (row 0–3, column 0–19)"],
       ["`ioctl(LCD_IOC_BACKLIGHT)`", "0 = backlight off, 1 = on"],
       ["`read()`", "Returns `'1'`–`'4'` for each button press. Waits if there is none."],
       ["`poll()`", "Tells the program when a button event is ready"]],
      [5.6, 10.4])
CODE(r'''
struct lcd_pos { __u8 row; __u8 col; };

#define LCD_IOC_CLEAR      _IO('L', 0)
#define LCD_IOC_SET_CURSOR _IOW('L', 1, struct lcd_pos)
#define LCD_IOC_BACKLIGHT  _IOW('L', 2, int)

#define LCD_BTN_1 '1'   /* GPIO17 */
#define LCD_BTN_2 '2'   /* GPIO27 */
#define LCD_BTN_3 '3'   /* GPIO22 */
#define LCD_BTN_4 '4'   /* GPIO23 */''', "Main definitions in lcd2004_ioctl.h")

H2("2.5. Button event path")
P("Figure 4 shows what happens when a button is pressed:")
N("Each edge on the pin calls the interrupt handler. It only restarts a 30 ms timer.")
N("When the button stops bouncing, the timer ends and the debounce function reads the pin.")
N("If the button is newly pressed, its code (`'1'`–`'4'`) is put into the queue.")
N("A program waiting in `read()` or `poll()` wakes up and gets the code.")
FIGURE("button.png", 7.6, "Path of a button event")

H2("2.6. Sharing and locking")
P("Two programs can use the LCD at the same time, and button events can arrive while a "
  "program reads. Table 9 shows how the shared data is protected.")
TABLE("Shared data and locks",
      ["Data", "Used by", "Protection"],
      [["LCD and cursor position", "`write()`, `ioctl()`",
        "Mutex: one program writes at a time, texts do not mix"],
       ["Event queue (`kfifo`)", "Debounce function, `read()`", "Spinlock (very short lock)"],
       ["Pressed flag of a button", "Only that button’s debounce function", "No lock needed"]],
      [4.6, 5.0, 6.4])
P("The LCD uses a mutex because I2C writes can sleep. The queue uses a spinlock "
  "because its operations are very short.")

H2("2.7. Start-up (probe) and removal")
P("When the kernel finds the overlay entry, it calls `lcd_probe()` (Figure 5). The LCD "
  "is tested first, so a wiring error shows up early. The queue is prepared before the "
  "interrupts are turned on. The device file is created last, when everything is ready.")
FIGURE("probe.png", 11.0, "Steps of lcd_probe()")
P("Memory, pins and interrupts are freed by the kernel automatically (`devm_*` "
  "functions). Before removal, `lcd_btns_stop()` turns off the interrupts and waits for "
  "pending work, so nothing runs on freed memory. `rmmod` is refused while a program "
  "still has `/dev/lcd2004` open.")

H2("2.8. Test and demo programs")
TABLE("User programs",
      ["Program", "What it does", "Pass when"],
      [["`lcd_test`", "Prints on 4 rows, clears, moves the cursor, toggles the backlight, "
        "tries wrong values", "It prints `ALL PASS`"],
       ["`button_test`", "Prints `NUT 1`…`NUT 4` with the time for each press",
        "One line per press"],
       ["`demo`", "Buttons control what the LCD shows (Figure 6)", "All steps work as designed"]],
      [3.1, 8.1, 4.8])
P("The demo has four states (Figure 6):")
B("**XIN_CHAO:** “Xin Chao” scrolls on the screen. Any button goes to the member list.")
B("**DSTV:** shows the list “1 2 3 4”. Button *k* selects member *k*.")
B("**SCROLL:** the name and student ID of member *k* scroll once.")
B("**INFO:** name and ID stay on the screen for 10 seconds, then the list comes back.")
FIGURE("demo.png", 15.5, "States of the demo program")
P("The program uses one `poll()` loop, no threads. It waits for a button for at most "
  "200 ms. If no button comes, it moves the text one step. Only the changed row is "
  "redrawn, so the screen does not flicker.")

H2("2.9. Built-in kernel design")
P("For the “good” level, the driver is added to the kernel source in "
  "`drivers/auxdisplay/` (the folder for LCD drivers). The kernel is built on the "
  "Raspberry Pi 5 from the branch that matches the running kernel (`rpi-6.18.y`) [8]. "
  "Figure 7 shows the steps done by `tools/build-builtin.sh`.")
FIGURE("builtin.png", 16.0, "Steps to build the driver into the kernel")
P("Safety: the new kernel has its own name, `kernel_lcd.img`, and is chosen by one line "
  "`kernel=kernel_lcd.img` in `config.txt`. Deleting this line brings back the old "
  "kernel. The kernel modules must still be installed, because the I2C controller of "
  "the Pi 5 is itself a module. The overlay is still needed: it tells the kernel where "
  "the device is.")
TABLE("Module and built-in",
      ["", "Module", "Built-in"],
      [["Where is the driver", "`lcd2004_btn.ko` file", "Inside `kernel_lcd.img`"],
       ["How it starts", "`sudo insmod` after each boot", "By itself at boot"],
       ["`lsmod`", "Shows `lcd2004_btn`", "Shows nothing"],
       ["Remove", "`rmmod`", "Not possible"],
       ["After a code change", "Rebuild the module (seconds)", "Rebuild the kernel and reboot"]],
      [4.2, 5.6, 6.2])

# ---------------------------------------------------------------- CHAPTER 3
NEXT_PB[0] = True
H1("CHAPTER 3: IMPLEMENTATION AND SOURCE CODE")
H2("3.1. Development environment")
TABLE("Development tools",
      ["Tool", "Use"],
      [["Raspberry Pi OS 64-bit, kernel 6.18", "Build and run the driver, the programs and the kernel"],
       ["`raspberrypi-kernel-headers`, `device-tree-compiler`, `i2c-tools`",
        "Build the module, compile the overlay, find the I2C address"],
       ["Windows 11 + WSL2 Ubuntu 24.04 + ARM64 compiler", "Check that the code compiles before testing on the Pi"],
       ["VS Code, SSH, `tmux`", "Edit code, work on the Pi remotely, keep long builds running"],
       ["Git and GitHub", "Save versions and share code [17]"]],
      [7.0, 9.0])

H2("3.2. Hardware assembly")
P("The circuit was built with the Pi unplugged: level shifter first, then power and "
  "ground, then I2C, then the buttons. Before power-on, the buttons and the power lines "
  "were checked with a multimeter, and every wire was compared with Table 6.")
PHOTO("the assembled circuit: Raspberry Pi 5, level shifter, LCD2004 and button board",
      "The assembled hardware", 7.0)

H2("3.3. Building and loading the module")
CODE(r'''
# Overlay (once)
dtc -@ -I dts -O dtb -o lcd2004-btn.dtbo dts/lcd2004-btn-overlay.dts
sudo cp lcd2004-btn.dtbo /boot/firmware/overlays/
#   add to /boot/firmware/config.txt:  dtparam=i2c_arm=on
#                                      dtoverlay=lcd2004-btn
sudo reboot
i2cdetect -y 1                  # HW-1: address 27 must appear

# Driver and programs
make -C driver                  # -> lcd2004_btn.ko
sudo insmod driver/lcd2004_btn.ko
make -C app                     # -> lcd_test, button_test, demo
sudo rmmod lcd2004_btn          # HW-7: remove, then load again''', "Commands for the module")

H2("3.4. Building the driver into the kernel")
P("The script `tools/build-builtin.sh` runs on the Pi and does all steps of Figure 7: "
  "download the kernel source, copy the driver into `drivers/auxdisplay/`, add the "
  "Kconfig entry (Listing 4) and one Makefile line, turn the driver on (`=y`), build, "
  "install the modules and copy the new kernel. The option `--check` stops before the "
  "build to test the setup quickly. The script does not change `config.txt`; this is "
  "done by hand so everyone knows how to go back.")
CODE(r'''
config LCD2004_BTN
	tristate "LCD2004 (PCF8574 I2C) + 4 buttons for Raspberry Pi 5"
	depends on I2C && GPIOLIB && OF
	help
	  HD44780 20x4 character LCD behind a PCF8574 I2C backpack, plus
	  4 push buttons. Creates /dev/lcd2004 (write, ioctl, read, poll).''',
     "Kconfig entry added to drivers/auxdisplay/Kconfig")
P("`tristate` means the driver can be a module (`m`) or built-in (`y`). The full build "
  "took about 70 minutes on the 4 GB Pi 5. It was run inside `tmux`, so a lost SSH "
  "connection did not stop it.")

H2("3.5. Source code")
P("The code below is taken from `driver/lcd2004_btn.c` and `app/demo.c`. Comments are "
  "translated into English.")
H3("3.5.1. Sending data to the LCD")
CODE(r'''
static int pcf_write(struct lcd2004 *lcd, u8 data)
{
	return i2c_smbus_write_byte(lcd->client, data | lcd->backlight);
}

/* Send 4 bits with an E pulse so that the LCD reads them */
static int lcd_write4(struct lcd2004 *lcd, u8 nibble, u8 rs)
{
	u8 data = (nibble << 4) | rs;          /* 4 bits on P4..P7 */
	int ret;

	ret = pcf_write(lcd, data | LCD_EN);   /* E = 1 */
	if (ret)
		return ret;
	udelay(1);
	ret = pcf_write(lcd, data);            /* E = 0: LCD reads the data */
	if (ret)
		return ret;
	udelay(50);                            /* wait for the LCD */
	return 0;
}

/* One byte = high 4 bits, then low 4 bits */
static int lcd_send(struct lcd2004 *lcd, u8 byte, u8 rs)
{
	int ret = lcd_write4(lcd, byte >> 4, rs);
	if (ret)
		return ret;
	return lcd_write4(lcd, byte & 0x0F, rs);
}''', "Sending a byte to the LCD")
P("`pcf_write()` always adds the backlight bit, so the backlight never turns off by "
  "mistake. `lcd_write4()` sets the 4 bits and makes the E pulse. `lcd_send()` sends a "
  "byte in two halves. `lcd_goto()` moves the cursor using the row addresses "
  "`{0x00, 0x40, 0x14, 0x54}`.")

H3("3.5.2. write()")
CODE(r'''
mutex_lock(&lcd->lock);                   /* one writer at a time */
while (done < count) {
	n = min_t(size_t, count - done, sizeof(buf));     /* 80 bytes at a time */
	if (copy_from_user(buf, ubuf + done, n)) { ret = -EFAULT; goto out; }
	for (i = 0; i < n; i++) {
		err = 0;
		if (buf[i] == '\n') {
			err = lcd_newline(lcd);
		} else if (buf[i] >= 0x20 && buf[i] <= 0x7E) {
			if (lcd->col >= LCD_COLS)      /* row full: next row */
				err = lcd_newline(lcd);
			if (!err)
				err = lcd_putc(lcd, buf[i]);
		} else {
			continue;                      /* skip other bytes */
		}
		if (err) { ret = -EIO; goto out; }
	}
	done += n;
}
out:
mutex_unlock(&lcd->lock);''', "Main loop of lcd_write()")
P("Text is copied from the program 80 bytes at a time. A full row moves to the next "
  "row only when another character comes. Without this, `echo` of exactly 20 "
  "characters would skip one row (once for the full row, once for `\\n`).")

H3("3.5.3. ioctl()")
P("`lcd_ioctl()` first copies and checks the value from the program. A wrong row or "
  "column gives `EINVAL`, an unknown command gives `ENOTTY`. Only then does it lock the "
  "LCD and send the command. This keeps the lock short.")

H3("3.5.4. Interrupt and debouncing")
CODE(r'''
static irqreturn_t btn_isr(int irq, void *data)
{
	struct lcd_btn *btn = data;

	/* each edge restarts the 30 ms timer */
	mod_delayed_work(system_wq, &btn->work, msecs_to_jiffies(DEBOUNCE_MS));
	return IRQ_HANDLED;
}

static void btn_debounce(struct work_struct *w)
{
	struct lcd_btn *btn = container_of(to_delayed_work(w), struct lcd_btn, work);
	struct lcd2004 *lcd = btn->lcd;
	int v = gpiod_get_value_cansleep(btn->gpio);   /* 1 = pressed */

	if (v < 0)
		return;
	if (v && !btn->pressed) {                   /* new press */
		btn->pressed = true;
		if (kfifo_in_spinlocked(&lcd->events, &btn->code, 1, &lcd->fifo_lock))
			wake_up_interruptible(&lcd->wq);    /* wake the reader */
	} else if (!v) {
		btn->pressed = false;                   /* released: no event */
	}
}''', "Interrupt handler and debounce function")
P("The interrupt handler does almost nothing, which is how it should be. The debounce "
  "function makes one event per press. If the queue is full (16 events), new presses "
  "are dropped.")

H3("3.5.5. read() and poll()")
CODE(r'''
while (1) {
	n = kfifo_out_spinlocked(&lcd->events, tmp,
				 min_t(size_t, count, sizeof(tmp)), &lcd->fifo_lock);
	if (n)
		break;                              /* got events */
	if (file->f_flags & O_NONBLOCK)
		return -EAGAIN;                     /* do not wait */
	if (wait_event_interruptible(lcd->wq, !kfifo_is_empty(&lcd->events)))
		return -ERESTARTSYS;                /* Ctrl+C */
}
if (copy_to_user(ubuf, tmp, n))
	return -EFAULT;
return n;

/* poll(): ready when the queue is not empty */
poll_wait(file, &lcd->wq, pt);
return kfifo_is_empty(&lcd->events) ? 0 : EPOLLIN | EPOLLRDNORM;''', "lcd_read() and lcd_poll()")
P("`read()` sleeps until there is an event, so it uses no CPU while waiting. Ctrl+C "
  "stops the wait, so the test programs can exit cleanly.")

H3("3.5.6. probe() and remove()")
P("`lcd_probe()` follows Figure 5. It checks that the LCD answers on I2C, starts the "
  "LCD and shows a welcome screen (“LCD2004 driver OK”). This screen proves "
  "the driver works even before any program runs. Then it gets the 4 button pins, "
  "turns on their interrupts and creates `/dev/lcd2004`. `lcd_remove()` stops the "
  "buttons, removes the device file and turns off the backlight.")

H3("3.5.7. Demo main loop")
CODE(r'''
while (!stop && !err) {
	/* member list: wait for a button forever; other states: 200 ms */
	r = poll(&pfd, 1, d.state == DSTV ? -1 : TICK_MS);
	if (r < 0) {
		if (errno == EINTR)
			continue;                     /* Ctrl+C */
		err = 1;
	} else if (r == 0) {
		err = on_tick(&d) != 0;           /* no button: move the text */
	} else {
		n = read(d.fd, buf, sizeof(buf)); /* one byte per press */
		for (i = 0; i < n && !err; i++)
			err = on_key(&d, buf[i]) != 0;
	}
}''', "Main loop of the demo (shortened)")
P("`on_key()` handles a button and `on_tick()` moves the scrolling text. When the user "
  "presses Ctrl+C, the program clears the LCD and exits.")

# ---------------------------------------------------------------- CHAPTER 4
NEXT_PB[0] = True
H1("CHAPTER 4: TESTING AND EVALUATION")
H2("4.1. Test method")
P("A driver cannot be tested on the laptop, so we tested on the real board in eight "
  "steps, HW-1 to HW-8. Each step has a clear pass rule. We moved to the next step only "
  "after the current one passed, so any error points to one part.")

H2("4.2. Results with the module")
TABLE("Test steps and results",
      ["Test", "Pass rule", "Result"],
      [["HW-1", "`i2cdetect -y 1` shows the LCD address", "Passed (0x27)"],
       ["HW-2", "`insmod` works, `/dev/lcd2004` exists, welcome screen shows", "Passed"],
       ["HW-3", "`echo \"Hello\" > /dev/lcd2004` shows the text", "Passed"],
       ["HW-4", "`lcd_test` prints `ALL PASS`", "Passed"],
       ["HW-5", "`button_test`: all 4 buttons work, one event per press", "Passed"],
       ["HW-6", "`demo` works as in Figure 6", "Passed"],
       ["HW-7", "`rmmod` then `insmod` again without error", "Passed"],
       ["HW-8", "Built-in kernel: `/dev/lcd2004` exists without `insmod`", "Passed (4.3)"]],
      [1.6, 10.8, 3.6], center_cols=(0,))
P("All eight steps passed on the Raspberry Pi 5 (HW-8 on 21 October 2026). "
  "`button_test` printed one line per press, so the 30 ms debounce works.")
PHOTO("LCD showing the welcome screen after insmod (or after boot)",
      "Welcome screen from lcd_probe()", 5.5)
PHOTO("LCD during lcd_test, and the terminal showing ALL PASS",
      "lcd_test result", 5.5)
PHOTO("demo screens: member list “1 2 3 4” and one member’s details",
      "Demo controlled by the buttons", 5.5)

H2("4.3. Results with the built-in kernel")
P("After switching to `kernel_lcd.img` and rebooting, without `insmod`:")
TABLE("Checks of the built-in driver (HW-8)",
      ["Check", "Result", "Meaning"],
      [["Look at the LCD", "Welcome screen shows by itself", "Driver starts at boot"],
       ["`uname -r`", "`6.18.57-v8-16k-lcd`", "Our kernel is running"],
       ["`lsmod | grep lcd2004`", "Nothing", "Driver is not a module"],
       ["`grep lcd2004 .../modules.builtin`", "`kernel/drivers/auxdisplay/lcd2004_btn.ko`",
        "Driver is inside the kernel"],
       ["`ls /dev/lcd2004`", "File exists", "Device file was created"],
       ["`lcd_test`, `button_test`, `demo`", "Same as with the module", "Programs need no change"]],
      [5.2, 5.6, 5.2])
PHOTO("terminal output of uname -r, lsmod, modules.builtin and ls /dev/lcd2004 on the built-in kernel",
      "Terminal output of the HW-8 checks", 6.0)

H2("4.4. Comparison with the course lab guide")
TABLE("Our choices compared with the lab guide",
      ["Topic", "Lab guide [2]", "This project", "Why"],
      [["Button pins", "Fixed number `gpio_request(17)`", "Pins from Device Tree",
        "Numbers differ on the Pi 5"],
       ["I2C address", "Fixed in the code", "In the overlay", "Change address without rebuilding"],
       ["Device file", "4 steps (`cdev`, `class_create`)", "`misc_register()`", "Simpler"],
       ["Interrupt", "All work in the handler", "Handler only starts a timer",
        "Handler stays short"],
       ["Button events", "`read()` returns a text", "Queue, `read()`, `poll()`",
        "No lost presses, no busy waiting"]],
      [2.8, 4.4, 4.2, 4.6])

H2("4.5. Overall assessment")
P("Both levels of the assignment were reached. The driver works as a module and inside "
  "the kernel, with the same code. The test programs check the LCD and the buttons "
  "separately, and the demo shows the buttons controlling the LCD. The circuit protects "
  "the Pi from 5 V, and the old kernel can always be restored.")

H2("4.6. Known limitations")
B("If the queue already has 16 events, new presses are lost.")
B("After an I2C error (for example a loose wire), the cursor position may be wrong; "
  "clear the screen to fix it.")
B("Only ASCII characters are shown; Vietnamese accents are skipped.")
B("Removing the device through sysfs while it is open is not safe (normal `rmmod` is safe).")
B("The built-in driver cannot be removed; any code change needs a kernel rebuild.")

H2("4.7. Difficulties and solutions")
TABLE("Difficulties and solutions",
      ["Difficulty", "Solution"],
      [["LCD board uses 5 V, Pi pins use 3.3 V", "BSS138 level shifter"],
       ["Old GPIO numbers do not work on the Pi 5", "Take the pins from the Device Tree"],
       ["One press gave several events", "30 ms debounce timer"],
       ["`echo` of 20 characters skipped one row", "Go to the next row only when another character comes"],
       ["The Pi runs kernel 6.18, not 6.12", "Script picks the kernel branch from `uname -r`"],
       ["New kernel without modules has no I2C", "Install the modules with a new version name"],
       ["Risk that the Pi does not boot", "Separate `kernel_lcd.img`; delete one line to go back"],
       ["Kernel build takes about 70 minutes", "Run it inside `tmux`"]],
      [7.4, 8.6])

# ---------------------------------------------------------------- CONCLUSION
NEXT_PB[0] = True
H1("CONCLUSION")
P("We built a Linux driver for an LCD2004 and four push buttons on a Raspberry Pi 5. "
  "The driver controls the LCD over I2C, reads the buttons with interrupts and "
  "debouncing, and gives programs one simple file, `/dev/lcd2004`. The pins and the "
  "address are in a Device Tree overlay. The driver works both as a module and built "
  "into the kernel, so both levels of the assignment are met. All eight hardware tests "
  "passed.")
P("We learned how a driver is linked to hardware through the Device Tree, why "
  "interrupt handlers must be short, how to protect shared data, and how to build and "
  "change the kernel of a board safely.")
P("**Future work:**")
B("Show Vietnamese letters with custom characters.")
B("Detect long presses.")
B("Fix the known limitations.")
B("Use the standard kernel LCD and input frameworks.")

H1("REFERENCES")
refs = [
    "Trương Ngọc Sơn, *Embedded System*, lecture notes, HCMC University of Technology and Education, 2026.",
    "Course laboratory guide, *Linux driver on Raspberry Pi 5* (exercises 2.1–2.5), Embedded Systems course, HCMUTE, 2026.",
    "Hitachi, *HD44780U (LCD-II) Dot Matrix Liquid Crystal Display Controller/Driver*, datasheet.",
    "NXP Semiconductors, *PCF8574; PCF8574A Remote 8-bit I/O expander for I2C-bus with interrupt*, data sheet.",
    "NXP Semiconductors, *UM10204 I2C-bus specification and user manual*.",
    "Raspberry Pi Ltd, *Raspberry Pi hardware documentation*. https://www.raspberrypi.com/documentation/computers/raspberry-pi.html",
    "Raspberry Pi Ltd, *RP1 Peripherals*, datasheet, 2023.",
    "Raspberry Pi Ltd, *The Linux kernel*. https://www.raspberrypi.com/documentation/computers/linux_kernel.html",
    "Raspberry Pi Ltd, *Device Trees, overlays and parameters*. https://www.raspberrypi.com/documentation/computers/configuration.html",
    "The Linux Kernel documentation, *GPIO Descriptor Consumer Interface*.",
    "The Linux Kernel documentation, *Implementing I2C device drivers*.",
    "The Linux Kernel documentation, *Building External Modules* and *Kconfig Language*.",
    "J. Corbet, A. Rubini and G. Kroah-Hartman, *Linux Device Drivers*, 3rd ed., O’Reilly Media, 2005.",
    "Linux kernel source, drivers/auxdisplay/hd44780.c.",
    "Linux kernel source, Documentation/devicetree/bindings/input/gpio-keys.yaml.",
    "NXP Semiconductors, *AN10441 Level shifting techniques in I2C-bus design*, application note.",
    "Project source code: https://github.com/AnNguen-TwT-Projects/Pi5-Driver",
]
for i, r in enumerate(refs, 1):
    par = P("[%d] %s" % (i, r), align=WD_ALIGN_PARAGRAPH.LEFT)
    par.paragraph_format.left_indent = Cm(0.9)
    par.paragraph_format.first_line_indent = Cm(-0.9)
    par.paragraph_format.space_after = Pt(4)

# Đánh dấu tài liệu là Word 2013+ để Word không mở ở "Compatibility Mode"
settings = doc.settings.element
compat = settings.find(qn("w:compat"))
if compat is None:
    compat = OxmlElement("w:compat")
    settings.append(compat)
for cs in compat.findall(qn("w:compatSetting")):
    if cs.get(qn("w:name")) == "compatibilityMode":
        compat.remove(cs)
cs = OxmlElement("w:compatSetting")
cs.set(qn("w:name"), "compatibilityMode")
cs.set(qn("w:uri"), "http://schemas.microsoft.com/office/word")
cs.set(qn("w:val"), "15")
compat.append(cs)

doc.save(OUT)
print("saved", OUT, "figures", fig_no[0], "tables", tab_no[0], "listings", lst_no[0])
