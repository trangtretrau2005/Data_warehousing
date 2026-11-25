"""Build the visually verified Chapter 5 and 6 handoff document.

The generated report separates verified warehouse/OLAP evidence from web and
model experiments that remain under development. It does not overwrite the
two original Word documents in docs/.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports"
ASSET_DIR = OUT_DIR / "chi_trang_assets"
OUTPUT = OUT_DIR / "Chuong_5_6_Chi_Trang.docx"

NAVY = "17324D"
GREEN = "285F50"
GOLD = "B77C28"
RED = "A8483E"
PALE_BLUE = "EAF1F6"
PALE_GREEN = "EAF3EE"
PALE_GOLD = "F7F0E4"
LIGHT = "F4F6F7"
GRID = "D9D9D9"
BLACK = "000000"
MUTED = "55646F"

ARIAL = Path(r"C:\Windows\Fonts\arial.ttf")
ARIAL_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(ARIAL_BOLD if bold else ARIAL), size)


def rounded(draw, xy, fill, outline=None, radius=24, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw, xy, text, fnt, fill, max_width=None, line_gap=6):
    x0, y0, x1, y1 = xy
    words = text.split()
    lines, current = [], ""
    if max_width is None:
        max_width = x1 - x0 - 20
    for word in words:
        trial = (current + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    heights = [draw.textbbox((0, 0), line, font=fnt)[3] for line in lines]
    total = sum(heights) + line_gap * max(0, len(lines) - 1)
    y = y0 + (y1 - y0 - total) / 2
    for line, h in zip(lines, heights, strict=True):
        box = draw.textbbox((0, 0), line, font=fnt)
        draw.text((x0 + (x1 - x0 - (box[2] - box[0])) / 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def arrow(draw, start, end, color=GREEN, width=8):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 18
    for delta in (2.55, -2.55):
        point = (end[0] + length * math.cos(angle + delta), end[1] + length * math.sin(angle + delta))
        draw.line([end, point], fill=color, width=width)


def save_diagrams():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Architecture and evidence boundary.
    img = Image.new("RGB", (1400, 650), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 35), "TỪ DỮ LIỆU ĐẾN QUYẾT ĐỊNH", font=font(34, True), fill="#17324D")
    d.text((55, 85), "Đường liền là phần đã có bằng chứng đối soát; đường nét đứt là lớp thử nghiệm.", font=font(22), fill="#55646F")
    stages = [
        ("Nguồn", "Coffee.csv\n4.248 dòng"),
        ("ETL và kho", "SSIS · mô hình sao\naudit và reject"),
        ("Mart và OLAP", "96 ô Market-tháng\nSSAS · MDX"),
        ("Phân tích", "Drill-down quý\nSQL đối chứng"),
        ("Thử nghiệm", "Cube 3D · Gemini\nForecast · Linear"),
    ]
    xs = [50, 315, 580, 845, 1110]
    for i, ((title, sub), x) in enumerate(zip(stages, xs, strict=True)):
        fill = "#EAF3EE" if i < 4 else "#F7F0E4"
        outline = "#285F50" if i < 4 else "#B77C28"
        rounded(d, (x, 185, x + 225, 380), fill, outline, 26, 4)
        center_text(d, (x + 12, 205, x + 213, 265), title, font(25, True), "#17324D")
        center_text(d, (x + 14, 270, x + 211, 355), sub, font(20), "#465A63")
        if i < len(stages) - 1:
            if i == 3:
                for xx in range(x + 230, xs[i + 1] - 10, 18):
                    d.line([(xx, 282), (min(xx + 10, xs[i + 1] - 10), 282)], fill="#B77C28", width=6)
                arrow(d, (xs[i + 1] - 28, 282), (xs[i + 1] - 10, 282), "#B77C28", 6)
            else:
                arrow(d, (x + 230, 282), (xs[i + 1] - 10, 282), "#285F50", 6)
    d.line([(700, 445), (700, 610)], fill="#D8DEDE", width=3)
    center_text(d, (65, 455, 660, 490), "CÓ THỂ KHẲNG ĐỊNH", font(20, True), "#285F50")
    center_text(d, (65, 500, 660, 595), "Grain, KPI, tổng mart, ETL, SSAS/MDX\nvà phép phân rã số học đã được kiểm tra.", font(21), "#17324D")
    center_text(d, (740, 455, 1335, 490), "KHÔNG NÊN KHẲNG ĐỊNH", font(20, True), "#A8483E")
    center_text(d, (740, 500, 1335, 595), "AI chính xác, Cube 3D ổn định tuyệt đối\nhoặc mô hình đủ tốt để ra quyết định thật.", font(21), "#17324D")
    img.save(ASSET_DIR / "architecture_status.png")

    # 2. One-port navigation map.
    img = Image.new("RGB", (1400, 520), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 35), "MỘT CỔNG 8504 · MỘT LỘ TRÌNH TRÌNH BÀY", font=font(32, True), fill="#17324D")
    labels = [
        ("01", "Giải thích\nchênh lệch", "Phần chính", GREEN),
        ("02", "Cube 3D", "Beta", "6C62C7"),
        ("03", "Truy vấn và\nkiểm chứng", "Builder ổn định\nGemini thử nghiệm", NAVY),
        ("04", "Mô hình", "Nghiên cứu\nđang phát triển", GOLD),
    ]
    xs = [55, 390, 725, 1060]
    for i, ((num, title, status, color), x) in enumerate(zip(labels, xs, strict=True)):
        rounded(d, (x, 135, x + 275, 390), "#F8F9F7", f"#{color}", 28, 4)
        d.ellipse((x + 22, 157, x + 82, 217), fill=f"#{color}")
        center_text(d, (x + 22, 157, x + 82, 217), num, font(20, True), "white")
        center_text(d, (x + 25, 225, x + 250, 300), title, font(25, True), "#17324D")
        center_text(d, (x + 28, 310, x + 247, 370), status, font(18), f"#{color}")
        if i < 3:
            arrow(d, (x + 280, 265), (xs[i + 1] - 10, 265), "#9AA9A1", 5)
    d.text((55, 445), "Bắt đầu bằng số liệu đã đối soát. Chỉ mở phần beta khi môi trường demo sẵn sàng.", font=font(22), fill="#55646F")
    img.save(ASSET_DIR / "link_roadmap.png")

    # 3. Mart grains.
    img = Image.new("RGB", (1400, 620), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 35), "BA MART · BA MỨC PHỤC VỤ", font=font(32, True), fill="#17324D")
    items = [
        ("vw_Detail", "4.248 dòng", "Tháng × AreaCode × Product", "State và dữ liệu chi tiết"),
        ("vw_MarketProductPeriod", "1.008 ô", "Tháng × Market × Product", "Đóng góp theo sản phẩm"),
        ("vw_MarketPeriod", "96 ô", "Tháng × Market", "KPI và đầu vào forecast"),
    ]
    widths = [1180, 930, 680]
    for i, ((name, count, grain, use), w) in enumerate(zip(items, widths, strict=True)):
        x = 110 + (1180 - w) / 2
        y = 145 + i * 140
        rounded(d, (x, y, x + w, y + 110), ["#EAF1F6", "#EAF3EE", "#F7F0E4"][i], ["#17324D", "#285F50", "#B77C28"][i], 20, 3)
        d.text((x + 24, y + 18), name, font=font(23, True), fill="#17324D")
        d.text((x + 390, y + 18), count, font=font(23, True), fill="#A8483E")
        d.text((x + 24, y + 62), grain, font=font(19), fill="#465A63")
        d.text((x + w - 360, y + 62), use, font=font(19), fill="#465A63")
    img.save(ASSET_DIR / "mart_grains.png")

    # 4. Market performance chart.
    img = Image.new("RGB", (1400, 760), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 30), "HIỆU QUẢ TOÀN CHUỖI THEO MARKET", font=font(32, True), fill="#17324D")
    markets = ["Central", "East", "South", "West"]
    sales = [265045, 178576, 103926, 272264]
    budgets = [250360, 157900, 98200, 239700]
    profits = [93852, 59217, 32478, 73996]
    maxv = max(sales) * 1.1
    plot_x0, plot_x1 = 230, 1320
    y0 = 150
    for i, market in enumerate(markets):
        y = y0 + i * 125
        d.text((55, y + 18), market, font=font(23, True), fill="#17324D")
        for j, (value, color, label) in enumerate(((sales[i], "#285F50", "Sales"), (budgets[i], "#8CB5A5", "Budget"))):
            yy = y + j * 38
            width = (plot_x1 - plot_x0) * value / maxv
            d.rounded_rectangle((plot_x0, yy, plot_x0 + width, yy + 26), 8, fill=color)
            d.text((plot_x0 + width + 12, yy - 1), f"{value:,}".replace(",", "."), font=font(18, True), fill="#17324D")
        d.text((1040, y + 67), f"Profit {profits[i]:,}".replace(",", "."), font=font(18), fill="#8A5A20")
    d.rectangle((55, 690, 85, 712), fill="#285F50"); d.text((98, 687), "Sales", font=font(18), fill="#465A63")
    d.rectangle((220, 690, 250, 712), fill="#8CB5A5"); d.text((263, 687), "BudgetSales", font=font(18), fill="#465A63")
    img.save(ASSET_DIR / "market_performance.png")

    # 5. Fan-out illustration.
    img = Image.new("RGB", (1400, 500), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 30), "VÌ SAO PHẢI TỔNG HỢP TRƯỚC KHI JOIN", font=font(31, True), fill="#17324D")
    boxes = [
        (80, "Budget đúng", "9.460", GREEN),
        (475, "Số dòng chi tiết", "56", NAVY),
        (870, "Budget bị nhân sai", "529.760", RED),
    ]
    for x, title, value, color in boxes:
        rounded(d, (x, 145, x + 340, 360), "#F8F9F7", f"#{color}", 26, 4)
        center_text(d, (x + 20, 165, x + 320, 230), title, font(22, True), "#17324D")
        center_text(d, (x + 20, 235, x + 320, 330), value, font(42, True), f"#{color}")
    d.text((430, 238), "×", font=font(50, True), fill="#55646F")
    d.text((825, 238), "=", font=font(50, True), fill="#55646F")
    d.text((180, 420), "Quy tắc: aggregate Actual và Budget về cùng MonthStart × Market, sau đó mới JOIN 1–1.", font=font(22, True), fill="#17324D")
    img.save(ASSET_DIR / "fanout.png")

    # 6. Cube hierarchies.
    img = Image.new("RGB", (1400, 650), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 30), "BA CHIỀU PHÂN TÍCH TRONG SSAS", font=font(32, True), fill="#17324D")
    columns = [
        ("Thời gian", ["Year", "Quarter", "Month"], NAVY),
        ("Địa lý", ["Market", "State", "AreaCode"], GREEN),
        ("Sản phẩm", ["Product Line", "Product Type", "Product"], GOLD),
    ]
    for i, (title, levels, color) in enumerate(columns):
        x = 80 + i * 445
        d.text((x + 80, 110), title, font=font(26, True), fill=f"#{color}")
        for j, level in enumerate(levels):
            y = 180 + j * 120
            rounded(d, (x, y, x + 350, y + 75), "#F8F9F7", f"#{color}", 18, 3)
            center_text(d, (x + 10, y + 8, x + 340, y + 67), level, font(22, True), "#17324D")
            if j < 2:
                arrow(d, (x + 175, y + 78), (x + 175, y + 112), f"#{color}", 5)
    d.text((55, 575), "Drill-down đi từ cấp tổng quát xuống cấp chi tiết; roll-up đi theo chiều ngược lại.", font=font(22), fill="#55646F")
    img.save(ASSET_DIR / "cube_hierarchies.png")

    # 7. South Q3 decomposition.
    img = Image.new("RGB", (1400, 760), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 30), "CÂU CHUYỆN SOUTH Q3 2013", font=font(32, True), fill="#17324D")
    levels = [
        ("Quý", "South Q3", "+374", GREEN, 90),
        ("Tháng", "08/2013", "-9", RED, 340),
        ("Nhóm", "Coffee", "-373", RED, 590),
        ("Sản phẩm", "Colombian", "-268", RED, 840),
        ("Địa bàn", "State", "Drill tiếp", NAVY, 1090),
    ]
    for i, (kind, name, gap, color, x) in enumerate(levels):
        rounded(d, (x, 180, x + 220, 410), "#F8F9F7", f"#{color}", 24, 4)
        center_text(d, (x + 12, 195, x + 208, 245), kind, font(18, True), f"#{color}")
        center_text(d, (x + 12, 255, x + 208, 325), name, font(23, True), "#17324D")
        center_text(d, (x + 12, 330, x + 208, 390), gap, font(29, True), f"#{color}")
        if i < len(levels) - 1:
            arrow(d, (x + 225, 295), (levels[i + 1][4] - 10, 295), "#9AA9A1", 5)
    d.text((90, 500), "16 - 9 + 367 = 374", font=font(25, True), fill="#285F50")
    d.text((505, 500), "-373 + 48 + 316 = -9", font=font(25, True), fill="#285F50")
    d.text((945, 500), "-268 - 105 = -373", font=font(25, True), fill="#285F50")
    d.text((90, 610), "Kết luận đúng: Colombian đóng góp lớn vào phần hụt của Coffee. Chưa đủ dữ liệu để kết luận nguyên nhân kinh doanh.", font=font(22), fill="#17324D")
    img.save(ASSET_DIR / "south_story.png")

    # 8. Query safety boundary.
    img = Image.new("RGB", (1400, 620), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 30), "QUERY STUDIO · PHẦN ỔN ĐỊNH VÀ PHẦN THỬ NGHIỆM", font=font(30, True), fill="#17324D")
    boxes = [
        (55, "Bộ chọn truy vấn", "SUM · AVG · bộ lọc\nallowlist · parameter binding", GREEN, "ỔN ĐỊNH KHI DEMO"),
        (530, "Gemini Text to SQL", "Model đề xuất SELECT\nkhông có quyền chạy trực tiếp", GOLD, "ĐANG PHÁT TRIỂN"),
        (1005, "Backend kiểm tra", "AST · nguồn · cột · hàm\nkết nối chỉ đọc", NAVY, "HÀNG RÀO BẮT BUỘC"),
    ]
    for x, title, body, color, status in boxes:
        rounded(d, (x, 150, x + 350, 420), "#F8F9F7", f"#{color}", 25, 4)
        center_text(d, (x + 18, 175, x + 332, 230), title, font(23, True), "#17324D")
        center_text(d, (x + 20, 245, x + 330, 335), body, font(19), "#465A63")
        center_text(d, (x + 20, 350, x + 330, 400), status, font(17, True), f"#{color}")
    arrow(d, (410, 285), (520, 285), "#9AA9A1", 5)
    arrow(d, (885, 285), (995, 285), "#9AA9A1", 5)
    d.text((55, 515), "Nếu Gemini sai hoặc hết quota, bộ chọn truy vấn vẫn hoạt động độc lập. Khi bảo vệ nên dùng bộ chọn làm luồng chính.", font=font(22), fill="#55646F")
    img.save(ASSET_DIR / "query_boundary.png")

    # 9. Linear scatter plots generated from the immutable source snapshot.
    raw = pd.read_csv(ROOT / "data" / "raw" / "Coffee.csv")
    raw["MonthStart"] = pd.to_datetime(raw["Date"], unit="D", origin="1899-12-30")
    monthly = raw.groupby(["Market", "MonthStart"], as_index=False)[["Marketing", "Sales"]].sum()
    img = Image.new("RGB", (1400, 900), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 25), "LINEAR MARKETING VÀ SALES · THỬ NGHIỆM", font=font(31, True), fill="#17324D")
    for idx, market in enumerate(sorted(monthly["Market"].unique())):
        col, row = idx % 2, idx // 2
        x0, y0 = 70 + col * 670, 110 + row * 370
        w, h = 580, 285
        group = monthly.loc[monthly["Market"].eq(market)].sort_values("MonthStart")
        train = group.iloc[:18]
        coef, intercept = np.polyfit(train["Marketing"], train["Sales"], 1)
        xmin, xmax = group["Marketing"].min(), group["Marketing"].max()
        ymin, ymax = group["Sales"].min(), group["Sales"].max()
        px = lambda value: x0 + 55 + (value - xmin) / max(1, xmax - xmin) * (w - 85)
        py = lambda value: y0 + h - 42 - (value - ymin) / max(1, ymax - ymin) * (h - 80)
        d.rectangle((x0, y0, x0 + w, y0 + h), outline="#D9D9D9", width=2)
        d.text((x0 + 18, y0 + 12), market, font=font(22, True), fill="#17324D")
        for i, point in group.reset_index(drop=True).iterrows():
            color = "#527BC0" if i < 18 else "#DB8956"
            x, y = px(point["Marketing"]), py(point["Sales"])
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color, outline="white", width=1)
        d.line((px(xmin), py(intercept + coef * xmin), px(xmax), py(intercept + coef * xmax)), fill="#285F50", width=4)
        d.text((x0 + 18, y0 + h - 28), "Marketing", font=font(15), fill="#55646F")
        d.text((x0 + w - 190, y0 + 14), f"Sales = {intercept:.0f} + {coef:.2f} × Marketing", font=font(15), fill="#55646F")
    d.ellipse((950, 846, 964, 860), fill="#527BC0"); d.text((975, 840), "Train 18 tháng", font=font(17), fill="#55646F")
    d.ellipse((1140, 846, 1154, 860), fill="#DB8956"); d.text((1165, 840), "Test 6 tháng", font=font(17), fill="#55646F")
    img.save(ASSET_DIR / "linear_scatter.png")


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_border(cell, color=GRID, size="6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top=90, start=100, bottom=90, end=100):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_run_font(run, name="Arial", size=10.2, bold=None, color=BLACK):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def add_hyperlink(paragraph, text, url, color="1D5D78"):
    relationship_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color_node = OxmlElement("w:color")
    color_node.set(qn("w:val"), color)
    props.append(color_node)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    run.append(props)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


class Report:
    def __init__(self):
        self.doc = Document()
        section = self.doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.56)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.68)
        section.right_margin = Inches(0.68)
        section.header_distance = Inches(0.25)
        section.footer_distance = Inches(0.25)
        self.figure_no = 0
        self.table_no = 0
        self._styles()
        self._header_footer()

    def _styles(self):
        styles = self.doc.styles
        normal = styles["Normal"]
        normal.font.name = "Arial"
        normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        normal.font.size = Pt(10.2)
        normal.font.color.rgb = RGBColor.from_string(BLACK)
        normal.paragraph_format.line_spacing = 1.12
        normal.paragraph_format.space_after = Pt(4.5)
        for name, size in (("Title", 25), ("Subtitle", 13), ("Heading 1", 17), ("Heading 2", 13), ("Heading 3", 11)):
            style = styles[name]
            style.font.name = "Arial"
            style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
            style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
            style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
            style.font.size = Pt(size)
            style.font.bold = name != "Subtitle"
            style.font.color.rgb = RGBColor.from_string(BLACK)
            style.paragraph_format.space_before = Pt(5)
            style.paragraph_format.space_after = Pt(6)
            style.paragraph_format.keep_with_next = True
        styles["Title"].paragraph_format.space_before = Pt(40)
        styles["Title"].paragraph_format.space_after = Pt(12)
        # Keep the required built-in Title style, but remove Word's decorative
        # bottom border so the cover has no horizontal-rule decoration.
        title_ppr = styles["Title"].element.get_or_add_pPr()
        title_border = title_ppr.find(qn("w:pBdr"))
        if title_border is not None:
            title_ppr.remove(title_border)

    def _header_footer(self):
        section = self.doc.sections[0]
        header = section.header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run("COFFEE DW   |   CHƯƠNG 5 VÀ CHƯƠNG 6")
        set_run_font(r, size=8.3, bold=True, color=MUTED)
        footer = section.footer
        table = footer.add_table(rows=1, cols=2, width=Inches(7.1))
        table.autofit = False
        table.columns[0].width = Inches(6.3)
        table.columns[1].width = Inches(0.8)
        left = table.cell(0, 0).paragraphs[0]
        left.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = left.add_run("Phần Chi và Trang   ·   Tách rõ bằng chứng đã xác nhận và tính năng đang phát triển")
        set_run_font(r, size=7.8, color=MUTED)
        right = table.cell(0, 1).paragraphs[0]
        right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = right.add_run("Trang ")
        set_run_font(r, size=7.8, color=MUTED)
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        right._p.append(fld)
        for cell in table.rows[0].cells:
            cell._tc.get_or_add_tcPr().append(OxmlElement("w:tcBorders"))

    def page_break(self):
        self.doc.add_page_break()

    def title(self, text, subtitle=None):
        p = self.doc.add_paragraph(style="Title")
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.add_run(text)
        if subtitle:
            p2 = self.doc.add_paragraph(style="Subtitle")
            p2.add_run(subtitle)

    def page_heading(self, number, title, deck=None):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(number.upper())
        set_run_font(r, size=8.5, bold=True, color=GREEN)
        h = self.doc.add_paragraph(title, style="Heading 1")
        if deck:
            p2 = self.doc.add_paragraph(deck)
            p2.paragraph_format.space_after = Pt(8)
            for r in p2.runs:
                set_run_font(r, size=10.5, color=MUTED)
        return h

    def paragraph(self, text, bold_lead=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=4.5):
        p = self.doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        if bold_lead and text.startswith(bold_lead):
            lead, rest = bold_lead, text[len(bold_lead):]
            r = p.add_run(lead)
            set_run_font(r, bold=True)
            r = p.add_run(rest)
            set_run_font(r)
        else:
            r = p.add_run(text)
            set_run_font(r)
        return p

    def bullets(self, items, compact=True):
        for item in items:
            p = self.doc.add_paragraph(style="List Bullet")
            p.paragraph_format.left_indent = Inches(0.22)
            p.paragraph_format.first_line_indent = Inches(-0.15)
            p.paragraph_format.space_after = Pt(2 if compact else 4)
            r = p.add_run(item)
            set_run_font(r, size=9.8)

    def table(self, headers, rows, widths=None, caption=None, font_size=8.8, alignments=None):
        if caption:
            self.table_no += 1
            p = self.doc.add_paragraph()
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(3)
            r = p.add_run(f"Bảng {self.table_no}. {caption}")
            set_run_font(r, size=9.3, bold=True, color=NAVY)
        table = self.doc.add_table(rows=1, cols=len(headers))
        table.autofit = False
        table.alignment = 1
        repeat_table_header(table.rows[0])
        for idx, header in enumerate(headers):
            cell = table.rows[0].cells[idx]
            cell.text = str(header)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_shading(cell, NAVY)
            set_cell_border(cell)
            set_cell_margins(cell)
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(0)
                for r in p.runs:
                    set_run_font(r, size=font_size, bold=True, color="FFFFFF")
        for row_idx, values in enumerate(rows):
            cells = table.add_row().cells
            for col_idx, value in enumerate(values):
                cell = cells[col_idx]
                cell.text = str(value)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                set_cell_border(cell)
                set_cell_margins(cell)
                if row_idx % 2:
                    set_cell_shading(cell, PALE_BLUE)
                alignment = (alignments[col_idx] if alignments else (WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER))
                for p in cell.paragraphs:
                    p.alignment = alignment
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.03
                    for r in p.runs:
                        set_run_font(r, size=font_size)
        if widths:
            for row in table.rows:
                for idx, width in enumerate(widths):
                    row.cells[idx].width = Inches(width)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(0)
        return table

    def figure(self, path, caption, width=6.9):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(path), width=Inches(width))
        self.figure_no += 1
        c = self.doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_after = Pt(5)
        r = c.add_run(f"Hình {self.figure_no}. {caption}")
        set_run_font(r, size=8.8, bold=True, color=MUTED)

    def hyperlink_line(self, label, url, note):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(label + "  ")
        set_run_font(r, size=10, bold=True, color=NAVY)
        add_hyperlink(p, url, url)
        r = p.add_run("  " + note)
        set_run_font(r, size=9.5, color=MUTED)

    def save(self):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.doc.save(OUTPUT)


def build_report():
    save_diagrams()
    r = Report()

    # Page 1 — cover.
    r.title("Xây dựng kho dữ liệu và hệ thống phân tích đa chiều cho Coffee Chains", "Chương 5 Phân tích đa chiều và Chương 6 Thử nghiệm dự báo doanh số")
    r.paragraph("Phần thực hiện của Chi và Trang", align=WD_ALIGN_PARAGRAPH.LEFT)
    r.figure(ASSET_DIR / "architecture_status.png", "Ranh giới giữa phần đã có bằng chứng và lớp chức năng đang phát triển", 6.8)
    r.paragraph("Bản tổng hợp kỹ thuật ngày 23 tháng 11 năm 2026. Tài liệu dùng để ghép báo cáo và chuẩn bị bảo vệ; không ghi đè tài liệu Word gốc.", align=WD_ALIGN_PARAGRAPH.LEFT)

    # Page 2 — opening conclusion and status.
    r.page_break(); r.page_heading("Phạm vi", "Kết luận chính và mức độ có thể khẳng định", "Hệ thống mạnh nhất ở tính đúng và khả năng truy vết của dữ liệu. Các giao diện mới và mô hình được giữ đúng vai trò thử nghiệm.")
    r.paragraph("Kết luận chính. Đề tài đã xây dựng được chuỗi nguồn CSV, ETL, mô hình sao, mart và SSAS để phân tích hiệu quả kinh doanh theo thời gian, địa lý và sản phẩm. Số liệu nguồn, SQL và MDX có bằng chứng đối soát. Đây là phần nên đặt ở trung tâm khi viết và bảo vệ.", "Kết luận chính.")
    r.paragraph("Ranh giới trình bày. Drill-down quý là phép phân rã số học từ mart và có thể dùng làm câu chuyện chính. Cube 3D, Gemini, forecast và Linear Regression là các tính năng nghiên cứu đang phát triển. Các phần này được trình bày với metric và giới hạn thật, không được gọi là hệ thống dự báo chính xác hoặc chức năng sẵn sàng vận hành.", "Ranh giới trình bày.")
    r.table(
        ["Thành phần", "Trạng thái", "Cách nói khi bảo vệ"],
        [
            ["ETL SSIS, audit và reject", "Đã có bằng chứng native", "Nêu package, batch và kết quả kiểm tra"],
            ["Mart và KPI", "Đã đối soát", "Có thể khẳng định số tổng và grain"],
            ["SSAS và MDX", "Đã đối soát 17/17", "Dùng làm bằng chứng OLAP"],
            ["Drill-down quý", "Đã kiểm số học", "Dùng làm luồng demo chính"],
            ["Cube 3D", "Beta đang phát triển", "Chỉ mở khi môi trường ổn định"],
            ["Gemini Text to SQL", "Thử nghiệm", "Luôn kiểm tra lại SQL và kết quả"],
            ["Forecast và Linear", "Nghiên cứu", "Trình bày metric, không cam kết quyết định"],
            ["Nghiệm thu người dùng", "Chưa thực hiện", "Không tuyên bố đã dễ dùng hoặc tiết kiệm thời gian"],
        ],
        [2.15, 1.55, 3.25],
        "Ma trận trạng thái của các thành phần trong đề tài",
        8.5,
    )

    # Page 3 — links and reading map.
    r.page_break(); r.page_heading("Tổ chức", "Một cổng và một lộ trình liên kết", "Các link được sắp xếp theo câu chuyện phân tích thay vì theo thời điểm phát triển chức năng.")
    r.figure(ASSET_DIR / "link_roadmap.png", "Thứ tự thống nhất của bốn trang trên cổng 8504", 6.9)
    r.hyperlink_line("01 Giải thích chênh lệch", "http://127.0.0.1:8504/quarter.html", "Luồng chính và dễ kiểm chứng nhất")
    r.hyperlink_line("02 Cube 3D beta", "http://127.0.0.1:8504/", "Trực quan hóa đang phát triển")
    r.hyperlink_line("03 Truy vấn và kiểm chứng", "http://127.0.0.1:8504/query.html", "Ưu tiên bộ chọn; Gemini chỉ là thử nghiệm")
    r.hyperlink_line("04 Mô hình thử nghiệm", "http://127.0.0.1:8504/linear.html", "Đọc metric và giới hạn, không dùng để cam kết")
    r.paragraph("Thứ tự demo đề xuất. Bắt đầu bằng South Q3/2013, xác định tháng 08/2013 và Colombian, sau đó dùng SQL hoặc SSAS để kiểm chứng con số. Cube 3D chỉ mở như hình minh họa bổ sung. Phần mô hình được trình bày sau cùng để tránh làm người nghe hiểu sai rằng AI là trọng tâm của đề tài.", "Thứ tự demo đề xuất.")

    # Page 4 — Chapter 5 opener.
    r.page_break(); r.page_heading("Chương 5", "Phân tích đa chiều và kết quả kinh doanh", "Chương của Chi tập trung vào mart, SSAS, các phép toán OLAP và khả năng giữ đúng tổng khi thay đổi góc nhìn.")
    r.paragraph("Mục tiêu chương. Chương 5 biến dữ liệu đã được ETL ở chương 4 thành các cấu trúc phục vụ phân tích. Người dùng có thể xem doanh số, ngân sách, lợi nhuận và chênh lệch theo năm, quý, tháng, Market, State, nhóm sản phẩm và sản phẩm. Mỗi kết quả phải đối chiếu được với SQL ở cùng kỳ và cùng bộ lọc.", "Mục tiêu chương.")
    r.paragraph("Đóng góp chính. Ba mart công bố grain rõ ràng; SSAS cung cấp ba chiều dùng chung và các phân cấp tự nhiên; bộ truy vấn MDX minh họa slice, dice, drill-down, roll-up và pivot. Inventory được xử lý như số đo bán cộng, còn tỷ lệ ngân sách được tính từ hai tổng thay vì lấy trung bình tỷ lệ từng dòng.", "Đóng góp chính.")
    r.table(
        ["Câu hỏi quản trị", "Cấu trúc trả lời", "Bằng chứng"],
        [
            ["Market nào vượt hoặc hụt kế hoạch?", "vw_MarketPeriod", "96 ô đối soát"],
            ["Sản phẩm nào tạo chênh lệch?", "vw_MarketProductPeriod", "1.008 ô đối soát"],
            ["State nào đóng góp cho sản phẩm?", "vw_Detail", "4.248 nhóm chi tiết"],
            ["Tổng có giữ nguyên khi drill?", "SSAS hierarchy và MDX", "17/17 MDX khớp SQL"],
        ],
        [2.35, 2.15, 2.45],
        "Câu hỏi trung tâm của chương 5",
    )
    r.figure(ROOT / "results" / "native_build_20261120" / "ui" / "ssas_dsv_final.png", "Data Source View của mô hình sao được dùng cho SSAS", 6.1)

    # Page 5 — marts.
    r.page_break(); r.page_heading("5.1", "Data Mart và độ hạt phục vụ", "Mỗi mart giải quyết một mức phân tích; việc đổi grain được thực hiện bằng phép tổng hợp có kiểm soát.")
    r.figure(ASSET_DIR / "mart_grains.png", "Ba mart và phạm vi sử dụng", 6.8)
    r.table(
        ["Mart", "Grain", "Số dòng", "Mục đích"],
        [
            ["mart.vw_Detail", "Tháng × AreaCode × Product", "4.248", "State, AreaCode và 11 số đo"],
            ["mart.vw_MarketProductPeriod", "Tháng × Market × Product", "1.008", "Đóng góp Gap theo sản phẩm"],
            ["mart.vw_MarketPeriod", "Tháng × Market", "96", "KPI, dashboard và đầu vào nghiên cứu"],
        ],
        [1.75, 2.25, 0.75, 2.2],
        "Hợp đồng độ hạt của ba mart",
        8.5,
    )
    r.paragraph("Ý nghĩa. Grain cho biết một dòng đại diện cho điều gì. Vì nguồn đã tổng hợp theo tháng, một dòng không phải là một đơn hàng. Mọi phép COUNT chỉ được gọi là số ô dữ liệu hoặc số nhóm fact; không được diễn giải thành số giao dịch hay số khách hàng.", "Ý nghĩa.")

    # Page 6 — KPI contracts.
    r.page_break(); r.page_heading("5.2", "Quy tắc KPI và phép cộng an toàn", "KPI được tính lại trên cùng phạm vi lọc, không lấy trung bình các tỷ lệ con và không cộng tồn kho xuyên thời gian.")
    r.table(
        ["KPI", "Công thức", "Quy tắc đọc"],
        [
            ["Sales", "SUM(Sales)", "Doanh số thực tế trong cùng filter"],
            ["BudgetSales", "SUM(BudgetSales)", "Mục tiêu doanh số trong cùng filter"],
            ["Gap", "SUM(Sales) - SUM(BudgetSales)", "Âm là hụt, dương là vượt"],
            ["BudgetAchievement", "SUM(Sales) / SUM(BudgetSales)", "Budget bằng 0 trả thiếu"],
            ["ProfitMargin", "SUM(Profit) / SUM(Sales)", "Sales bằng 0 trả thiếu"],
            ["Inventory", "SUM tại kỳ cuối được chọn", "Không SUM xuyên nhiều tháng"],
        ],
        [1.45, 2.65, 2.85],
        "Các KPI và điều kiện tổng hợp",
        8.7,
    )
    r.paragraph("Ví dụ tỷ lệ. Nếu hai sản phẩm có tỷ lệ đạt ngân sách khác nhau, hệ thống không lấy trung bình hai tỷ lệ đó. Hệ thống cộng Sales, cộng BudgetSales rồi mới chia. Cách này bảo đảm tỷ lệ của cấp Market phản ánh đúng trọng số ngân sách của từng sản phẩm.", "Ví dụ tỷ lệ.")
    r.paragraph("Ví dụ Inventory. Khi người dùng chọn 01/2013 đến 12/2013, Inventory chỉ được lấy ở kỳ cuối 12/2013 trước khi cộng theo Market. Quy tắc này được công bố vì nguồn không cung cấp metadata đầy đủ để xác định chính sách tồn kho nghiệp vụ phức tạp hơn.", "Ví dụ Inventory.")
    r.bullets([
        "Giữ số âm của Profit và Inventory; không tự đổi thành 0.",
        "Ô thiếu giữ là thiếu; không tạo tổ hợp không tồn tại trong nguồn.",
        "Tên cột và định nghĩa KPI được dùng thống nhất ở SQL, SSAS và web.",
        "Đơn vị tiền không được nguồn công bố nên báo cáo giữ nguyên đơn vị nguồn.",
    ])

    # Page 7 — performance.
    r.page_break(); r.page_heading("5.3", "Kết quả kinh doanh toàn chuỗi", "Bốn Market đều vượt ngân sách khi gộp 24 tháng, nhưng drill-down theo kỳ vẫn phát hiện các lát cắt hụt.")
    r.figure(ASSET_DIR / "market_performance.png", "Sales và BudgetSales toàn kỳ theo Market", 6.8)
    r.table(
        ["Market", "Sales", "Budget", "Gap", "Profit", "Đạt NS"],
        [
            ["Central", "265.045", "250.360", "+14.685", "93.852", "105,87%"],
            ["East", "178.576", "157.900", "+20.676", "59.217", "113,09%"],
            ["South", "103.926", "98.200", "+5.726", "32.478", "105,83%"],
            ["West", "272.264", "239.700", "+32.564", "73.996", "113,59%"],
            ["Toàn chuỗi", "819.811", "746.160", "+73.651", "259.543", "109,87%"],
        ],
        [1.15, 1.15, 1.15, 1.0, 1.1, 1.0],
        "Tổng hợp hiệu quả kinh doanh 01/2012 đến 12/2013",
        8.4,
    )
    r.paragraph("Nhận xét. West dẫn đầu Sales và Gap, nhưng Central tạo Profit cao nhất. Một Market có Sales cao chưa chắc có biên lợi nhuận cao nhất. Quan trọng hơn, tổng 24 tháng đều dương không loại trừ tháng hoặc sản phẩm đang hụt kế hoạch; vì vậy cần OLAP và drill-down.", "Nhận xét.")

    # Page 8 — fan-out.
    r.page_break(); r.page_heading("5.4", "Drill across và lỗi nhân bản ngân sách", "Hai nguồn số liệu chỉ được nối sau khi cùng được tổng hợp về MonthStart × Market.")
    r.figure(ASSET_DIR / "fanout.png", "Minh họa lỗi fan-out tại West 01/2012", 6.8)
    r.paragraph("Ca kiểm chứng. West 01/2012 có BudgetSales đúng bằng 9.460 và 56 dòng chi tiết. Nếu nối budget cấp Market-tháng vào fact chi tiết rồi mới SUM, toàn bộ 9.460 bị lặp 56 lần thành 529.760. Trên toàn nguồn, tổng budget có thể bị phóng đại hơn 48 lần.", "Ca kiểm chứng.")
    r.figure(ROOT / "results" / "TN05" / "chi_2026-11-15" / "TN05_join.png", "Minh chứng TN05 về phép nối hai tập đã tổng hợp", 5.7)
    r.paragraph("Quy tắc bắt buộc. Actual và Budget phải được aggregate độc lập về cùng grain, sau đó JOIN 1–1. FULL OUTER JOIN giữ được cả nhóm chỉ có actual và nhóm chỉ có kế hoạch; giá trị thiếu không được đổi thành 0 nếu chưa có bằng chứng nghiệp vụ.", "Quy tắc bắt buộc.")

    # Page 9 — SSAS structure.
    r.page_break(); r.page_heading("5.5", "Thiết kế Cube SSAS Multidimensional", "Cube dùng một measure group Fact Sales Performance và ba chiều Date, Location, Product.")
    r.figure(ROOT / "results" / "native_build_20261120" / "ui" / "ssas_cube_structure.png", "Cấu trúc cube Coffee Performance trong SSDT", 6.8)
    r.table(
        ["Thành phần", "Khóa nối", "Vai trò"],
        [
            ["Dim Date", "DateKey", "Năm, quý và tháng"],
            ["Dim Location", "LocationKey", "Market, State và AreaCode"],
            ["Dim Product", "ProductKey", "Product Line, Type và Product"],
            ["Fact Sales Performance", "Ba khóa chiều", "11 số đo actual, budget và chi phí"],
        ],
        [1.7, 1.4, 3.6],
        "Dimension Usage và vai trò của các bảng",
    )
    r.paragraph("Quan hệ. Cả ba chiều nối với measure group bằng quan hệ Regular tại khóa hạt lá. Khóa Quarter chứa Year và Month dùng DateKey để tháng 01/2012 không bị gộp với 01/2013. Đây là điều kiện để slice và roll-up đúng qua nhiều năm.", "Quan hệ.")

    # Page 10 — hierarchies.
    r.page_break(); r.page_heading("5.6", "Phân cấp và số đo trong Cube", "Phân cấp giúp người dùng đi từ kết quả tổng quát xuống đúng cấp chi tiết mà vẫn giữ tổng.")
    r.figure(ASSET_DIR / "cube_hierarchies.png", "Ba đường phân cấp chính trong SSAS", 6.8)
    r.table(
        ["Loại số đo", "Ví dụ", "Cách tổng hợp"],
        [
            ["Cộng được", "Sales, BudgetSales, Profit", "SUM theo thời gian, địa lý và sản phẩm"],
            ["Bán cộng", "Inventory", "Lấy tháng cuối trong ngữ cảnh thời gian"],
            ["Tính toán", "Gap", "Sales - BudgetSales sau tổng hợp"],
            ["Tỷ lệ", "BudgetAchievement", "Sales / BudgetSales; mẫu 0 trả NULL"],
        ],
        [1.25, 2.15, 3.3],
        "Phân loại số đo trong cube",
    )
    r.paragraph("Cách giải thích. Drill-down không tạo ra dữ liệu mới; nó chỉ thay đổi cấp hiển thị. Roll-up cộng các thành viên con trở lại cấp cha. Nếu tổng con không bằng cha thì lỗi có thể nằm ở grain, quan hệ chiều, phép tổng hợp hoặc bộ lọc.", "Cách giải thích.")

    # Page 11 — OLAP operations.
    r.page_break(); r.page_heading("5.7", "Các phép toán OLAP", "Mỗi phép toán được chạy bằng MDX và đối chiếu với SQL ở cùng lát cắt.")
    r.table(
        ["Phép toán", "Câu hỏi", "Ví dụ trong đề tài"],
        [
            ["Slice", "Một thời điểm cụ thể?", "Central 01/2012"],
            ["Drill-down", "Chi tiết bên trong tổng?", "Market xuống 6 State"],
            ["Roll-up", "Tổng các nhánh con?", "6 State về Central"],
            ["Dice", "Một tập thành viên nhiều chiều?", "Coffee tại Central và East"],
            ["Pivot", "Đổi trục có đổi số liệu?", "Hoán đổi hàng và cột"],
        ],
        [1.15, 2.25, 3.3],
        "Ý nghĩa của năm phép toán OLAP",
    )
    r.figure(ROOT / "results" / "native_build_20261120" / "ui" / "ssas_integrated_browser_central_states.png", "Drill-down Central 01/2012 từ Market xuống sáu State", 6.7)
    r.paragraph("Đối soát. Sáu State của Central có Sales lần lượt 1.958, 2.538, 2.029, 1.009, 1.471 và 1.341; tổng bằng 10.346, đúng với cấp Market. Đây là bằng chứng trực tiếp rằng drill-down và roll-up giữ nguyên tổng lát cắt.", "Đối soát.")

    # Page 12 — evidence.
    r.page_break(); r.page_heading("5.8", "Đối soát MDX và SQL", "Kết quả Cube chỉ được chấp nhận khi cùng bộ lọc trả cùng số với SQL nguồn.")
    r.figure(ROOT / "results" / "TN06" / "chi_2026-11-15" / "TN06_mdx_query.png", "Truy vấn MDX dùng để kiểm tra các phép toán OLAP", 6.6)
    r.table(
        ["Nhóm bằng chứng", "Kết quả", "Giới hạn được công bố"],
        [
            ["ProcessFull cube", "Processed", "Theo database biệt lập trên máy Trang"],
            ["MDX so SQL", "17/17 ca khớp", "Cùng kỳ, chiều và measure"],
            ["Pivot ADOMD", "6/6 ô khớp", "Không phải ảnh pivot UI thành công"],
            ["Build project", "0 lỗi, 8 cảnh báo", "Không gọi là 0 cảnh báo"],
            ["Nguồn cuối", "DB SSIS đã đối soát", "Không thay nghiệm thu trên máy Chi"],
        ],
        [2.0, 1.65, 3.05],
        "Tóm tắt bằng chứng native của TN06",
    )
    r.paragraph("Cách nói an toàn. Có thể khẳng định project đã build, process và các ca MDX đã chạy trên môi trường ghi trong biên bản. Không nên suy rộng thành mọi truy vấn đều đúng hoặc cube đã được nghiệm thu trên mọi máy.", "Cách nói an toàn.")

    # Page 13 — South story.
    r.page_break(); r.page_heading("5.9", "Câu chuyện phân tích South Q3 2013", "Một con số dương của cả quý vẫn có thể che một tháng và một nhóm sản phẩm đang hụt kế hoạch.")
    r.figure(ASSET_DIR / "south_story.png", "Chuỗi drill-down từ quý xuống sản phẩm và State", 6.8)
    r.table(
        ["Cấp", "Thành phần", "Sales", "Budget", "Gap"],
        [
            ["Quý", "South Q3/2013", "13.554", "13.180", "+374"],
            ["Tháng", "08/2013", "4.601", "4.610", "-9"],
            ["Nhóm", "Coffee", "—", "—", "-373"],
            ["Sản phẩm", "Colombian", "1.102", "1.370", "-268"],
            ["Sản phẩm", "Decaf Irish Cream", "465", "570", "-105"],
        ],
        [0.85, 2.25, 1.15, 1.15, 0.9],
        "Các mốc chính của ca South",
        8.5,
    )
    r.paragraph("Kết luận đúng. Dashboard xác định Colombian là một đóng góp âm lớn trong Coffee tháng 08/2013. Kết quả không chứng minh nguyên nhân do Marketing, giá, thời tiết hay hoạt động của nhân viên vì nguồn không có các biến này.", "Kết luận đúng.")

    # Page 14 — Cube beta.
    r.page_break(); r.page_heading("5.10", "Cube 3D là lớp trực quan hóa beta", "Trang web đọc mart quan hệ để biểu diễn các ô dữ liệu; nó không thay thế SSAS và chưa được gọi là chức năng ổn định.")
    r.figure(ROOT / "results" / "cube_explorer" / "design_desktop_20261121.jpg", "Giao diện Cube 3D đã được kiểm tra kỹ thuật nhưng vẫn ở trạng thái beta", 5.15)
    r.table(
        ["Có thể trình bày", "Không nên khẳng định"],
        [
            ["Khối biểu diễn Month × Market × Product", "Đây là engine OLAP mới"],
            ["Bộ lọc đọc mart SQL Server chỉ đọc", "Không bao giờ lỗi khi demo"],
            ["Màu thể hiện measure đang chọn", "Thể tích khối là giá trị measure"],
            ["Có test controller và hình học", "Đã nghiệm thu với người dùng thật"],
            ["Có thể mở cùng lát cắt từ truy vấn", "Mọi SELECT đều ánh xạ chính xác sang 3D"],
        ],
        [3.35, 3.35],
        "Ranh giới trình bày Cube 3D",
        8.4,
    )
    r.paragraph("Phương án demo an toàn. Nếu Cube 3D không tải hoặc thao tác xoay khó kiểm soát, quay về trang drill-down quý hoặc bảng SQL. Số liệu chuẩn vẫn nằm ở mart và SSAS; lỗi giao diện không làm thay đổi bằng chứng dữ liệu đã thu.", "Phương án demo an toàn.")

    # Page 15 — Query Studio.
    r.page_break(); r.page_heading("5.11", "Truy vấn và kiểm chứng trên mart", "Query Studio gồm một bộ tạo truy vấn có cấu trúc và một nhánh Gemini đang phát triển.")
    r.figure(ASSET_DIR / "query_boundary.png", "Ranh giới giữa bộ chọn ổn định và Gemini thử nghiệm", 6.8)
    r.table(
        ["Chức năng", "Cơ chế", "Mức dùng khi demo"],
        [
            ["Bộ chọn", "Allowlist identifier và parameter binding", "Nên dùng làm luồng chính"],
            ["Gemini", "Đề xuất SELECT, không chạy trực tiếp", "Chỉ dùng nếu API ổn định"],
            ["AST validator", "Chặn DDL, DML, nguồn và cột lạ", "Luôn bắt buộc"],
            ["Cube context", "Ánh xạ phạm vi tương thích", "Chỉ là liên kết bổ sung"],
        ],
        [1.45, 3.1, 2.15],
        "Hai mức chức năng của Query Studio",
    )
    r.paragraph("Ví dụ an toàn. Khi hỏi năm 2015, hệ thống phải báo ngoài phạm vi vì snapshot chỉ có 2012–2013. Nó không được xóa điều kiện rồi trả tổng toàn kho. Dòng 201 chỉ là guard kỹ thuật để phát hiện truncation và không được hiển thị như logic nghiệp vụ.", "Ví dụ an toàn.")

    # Page 16 — chapter 5 defense.
    r.page_break(); r.page_heading("5.12", "Kết luận chương 5 và cách trả lời khi bảo vệ", "Giá trị lớn nhất của chương 5 là giữ đúng số khi chuyển từ mart sang cube và thay đổi cấp phân tích.")
    r.table(
        ["Câu hỏi có thể gặp", "Câu trả lời ngắn và an toàn"],
        [
            ["Vì sao cần mart?", "Để công bố grain và KPI ổn định cho nhiều consumer."],
            ["Vì sao không JOIN budget trực tiếp?", "Sẽ fan-out; West 01/2012 tăng sai từ 9.460 lên 529.760."],
            ["Cube 3D có phải SSAS không?", "Không. Nó là web đọc mart; SSAS mới là engine OLAP native."],
            ["Drill-down có tìm được nguyên nhân không?", "Nó tìm đóng góp số học; muốn biết nguyên nhân cần thêm biến nghiệp vụ."],
            ["Tại sao Inventory khác Sales?", "Inventory là snapshot bán cộng, chỉ lấy ở kỳ cuối được chọn."],
            ["Bằng chứng cube đúng là gì?", "17/17 MDX khớp SQL và các tổng con khớp tổng cha."],
            ["Nếu giao diện beta lỗi thì sao?", "Dùng bảng SQL, ảnh SSAS và phép đối soát đã lưu."],
        ],
        [2.45, 4.25],
        "Bộ câu hỏi bảo vệ chương 5",
        8.8,
    )
    r.paragraph("Thông điệp kết chương. Chương 5 không chỉ tạo một biểu đồ. Chương này chứng minh dữ liệu có thể được tổng hợp và phân tích theo nhiều chiều mà vẫn truy ngược được về grain, KPI và môi trường chạy cụ thể. Các giao diện web chỉ hỗ trợ người xem tiếp cận kết quả đó.", "Thông điệp kết chương.")

    # Page 17 — Chapter 6 opener.
    r.page_break(); r.page_heading("Chương 6", "Thử nghiệm dự báo doanh số theo thị trường", "Chương của Trang trình bày một nghiên cứu có baseline và đánh giá theo thời gian; chưa phải hệ thống dự báo sẵn sàng vận hành.")
    r.paragraph("Câu hỏi nghiên cứu. Với 24 tháng Sales của mỗi Market, Ridge dùng ba độ trễ có cải thiện so với dự báo bằng tháng trước hoặc trung bình ba tháng hay không? Kết quả không vượt baseline vẫn có giá trị vì nó ngăn hệ thống chọn mô hình phức tạp chỉ vì tên gọi học máy.", "Câu hỏi nghiên cứu.")
    r.table(
        ["Đặc điểm dữ liệu", "Giá trị", "Hệ quả"],
        [
            ["Nguồn chi tiết", "4.248 dòng", "Không phải đơn hàng"],
            ["Grain mô hình", "Market × Month", "96 ô, 24 ô mỗi Market"],
            ["Khoảng thời gian", "01/2012–12/2013", "Chỉ hai chu kỳ năm"],
            ["Target", "SUM(Sales)", "Đơn vị nguồn, không tự gán tiền tệ"],
            ["Actual tương lai", "Không có 01/2014", "Không thể chấm forecast kỳ này"],
            ["Dữ liệu sinh thêm", "0 quan sát", "Không làm đẹp metric bằng synthetic"],
        ],
        [2.0, 2.05, 2.65],
        "Phạm vi dữ liệu của chương 6",
    )
    r.paragraph("Trạng thái. Forecast được xem là thực nghiệm nghiên cứu. Tài liệu có thể khẳng định protocol, các dự báo lịch sử và metric đã được tái lập; không được khẳng định mô hình bảo đảm sai số, thay thế chuyên gia hoặc đưa ra quyết định nhập hàng.", "Trạng thái.")

    # Page 18 — protocol.
    r.page_break(); r.page_heading("6.1", "Thiết kế đánh giá theo thời gian", "Mỗi dự báo chỉ sử dụng actual đã xảy ra trước tháng mục tiêu; dữ liệu không được xáo trộn ngẫu nhiên.")
    r.figure(ROOT / "experiments" / "baseline" / "results" / "02_protocol" / "figures" / "01_rolling_origin.png", "Lịch rolling origin với validation và test tách biệt", 6.7)
    r.table(
        ["Vai trò", "Khoảng thời gian", "Số tháng", "Số dự báo"],
        [
            ["Khởi tạo", "01/2012–03/2013", "15", "Không chấm ngoài mẫu"],
            ["Validation", "04/2013–09/2013", "6", "24 điểm"],
            ["Test", "10/2013–12/2013", "3", "12 điểm"],
            ["Kỳ ngoài nguồn", "01/2014", "1", "4 forecast, chưa có actual"],
        ],
        [1.6, 2.15, 1.0, 1.95],
        "Phân chia dữ liệu của protocol chính",
    )
    r.paragraph("Chống leakage. Dự báo 10/2013 dùng actual đến 09/2013; dự báo 11/2013 có thể dùng actual 10/2013 vì origin đã chuyển sang tháng mới. StandardScaler và Ridge được fit lại chỉ trên quá khứ của từng Market tại từng origin.", "Chống leakage.")

    # Page 19 — models.
    r.page_break(); r.page_heading("6.2", "Baseline và mô hình so sánh", "Mô hình phức tạp chỉ được chọn nếu vượt baseline trên validation đã định trước.")
    r.figure(ROOT / "experiments" / "baseline" / "results" / "02_protocol" / "figures" / "02_method_specifications.png", "Đặc tả ba họ phương pháp trong nghiên cứu cơ sở", 6.5)
    r.table(
        ["Phương pháp", "Feature hoặc quy tắc", "Ý nghĩa"],
        [
            ["Naive", "Sales tháng t-1", "Baseline phản ứng nhanh"],
            ["MA2, MA3, MA6", "Trung bình 2, 3 hoặc 6 tháng", "Làm mượt, không học hệ số"],
            ["Ridge", "lag1, lag2, lag3 + scaler", "Học hệ số có regularization"],
            ["Seasonal naive12", "Sales cùng tháng năm trước", "Đối chứng mùa vụ với lịch sử ngắn"],
            ["SES", "alpha cố định 0,2/0,5/0,8", "Thăm dò sau khi test đã biết"],
        ],
        [1.4, 2.75, 2.55],
        "Các cấu hình đã thử và vai trò",
    )
    r.paragraph("Quy tắc lựa chọn. MAE validation gộp bốn Market là tiêu chí chọn. Test chỉ được dùng để báo cáo sau khi đã chọn; không đổi model vì một cấu hình tình cờ có test tốt hơn. Vòng 11 cấu hình là thăm dò trên test đã biết và không được gọi là kiểm định mù mới.", "Quy tắc lựa chọn.")

    # Page 20 — validation.
    r.page_break(); r.page_heading("6.3", "Kết quả validation và quyết định chọn model", "MA3 có MAE validation thấp nhất trong bảy cấu hình chính; Ridge chưa chứng minh được lợi thế.")
    r.figure(ROOT / "experiments" / "tuning" / "results" / "02_validation" / "figures" / "01_ranking.png", "Xếp hạng cấu hình theo MAE validation", 6.5)
    r.table(
        ["Cấu hình", "MAE validation", "MAE test đã biết", "Chọn"],
        [
            ["MA3", "223,28", "225,22", "Có"],
            ["MA6", "231,31", "152,00", "Không"],
            ["MA2", "244,15", "213,42", "Không"],
            ["Naive", "258,83", "221,75", "Không"],
            ["Ridge alpha=10", "275,22", "200,59", "Không"],
            ["Ridge alpha=1", "292,93", "213,33", "Không"],
            ["Ridge alpha=0,1", "298,87", "215,95", "Không"],
        ],
        [2.1, 1.65, 1.65, 1.0],
        "Bảng lựa chọn theo validation",
        8.2,
    )
    r.paragraph("Giải thích. MA6 có test MAE thấp hơn nhưng không được đổi thành model chính sau khi nhìn test. MA3 giảm 13,74% MAE validation so với Naive. Vòng thử tham số không cải thiện MAE validation so với MA3 ban đầu, vì vậy kết quả trung thực là mô hình đơn giản vẫn phù hợp hơn trên snapshot này.", "Giải thích.")

    # Page 21 — test.
    r.page_break(); r.page_heading("6.4", "Kết quả test và phân tích sai số", "Test gồm ba tháng cho mỗi Market nên chỉ là bằng chứng nhỏ, không phải bảo đảm tổng quát hóa.")
    r.figure(ROOT / "experiments" / "baseline" / "results" / "04_test" / "figures" / "01_actual_forecast.png", "Actual và dự báo của các phương pháp trên ba tháng test", 6.6)
    r.table(
        ["Market", "N", "MAE", "RMSE", "MAPE"],
        [
            ["Central", "3", "259,78", "296,03", "2,35%"],
            ["East", "3", "205,33", "205,67", "2,71%"],
            ["South", "3", "58,11", "61,98", "1,28%"],
            ["West", "3", "377,67", "384,69", "3,27%"],
            ["Toàn bộ", "12", "225,22", "265,41", "2,40%"],
        ],
        [1.4, 0.7, 1.45, 1.45, 1.45],
        "Sai số MA3 trên tập test",
        8.5,
    )
    r.paragraph("Cách đọc. West có sai số tuyệt đối lớn nhất, nhưng mỗi Market chỉ có ba điểm test. MAPE 2,40% không được đổi thành câu 'độ chính xác 97,60%'. MAE cũng không phải khoảng bảo đảm; nó chỉ là trung bình trị tuyệt đối của 12 sai số trong protocol này.", "Cách đọc.")

    # Page 22 — future issue.
    r.page_break(); r.page_heading("6.5", "Dự báo 01/2014 và khả năng giải thích", "Bốn giá trị được phát hành từ lịch sử đến 12/2013; actual 01/2014 không tồn tại trong snapshot.")
    r.figure(ROOT / "experiments" / "briefing" / "results" / "02_story" / "figures" / "west_201401_moving_average_3.png", "Giải thích dự báo MA3 cho West 01/2014", 6.3)
    r.table(
        ["Market", "Forecast 01/2014", "Actual", "Trạng thái"],
        [
            ["Central", "11.174,33", "Chưa có", "Chưa chấm"],
            ["East", "7.585,33", "Chưa có", "Chưa chấm"],
            ["South", "4.537,33", "Chưa có", "Chưa chấm"],
            ["West", "11.593,00", "Chưa có", "Chưa chấm"],
        ],
        [1.45, 1.85, 1.35, 2.05],
        "Dự báo kỳ ngoài nguồn",
    )
    r.paragraph("Ví dụ West. (11.596 + 11.300 + 11.883) / 3 = 11.593. Công thức rõ ràng giúp người nghe kiểm tra được kết quả, nhưng chưa thể gọi dự báo đúng vì không có actual 01/2014 để chấm. Trang demo forecast cũng được xem là prototype đang phát triển.", "Ví dụ West.")

    # Page 23 — linear.
    r.page_break(); r.page_heading("6.6", "Thử nghiệm Linear Marketing và Sales", "Linear Lab kiểm tra quan hệ cùng tháng; nó không phải dự báo tháng tới và không chứng minh nhân quả.")
    r.figure(ASSET_DIR / "linear_scatter.png", "Scatter train và test của bốn Market với đường chỉ fit từ train", 6.7)
    r.table(
        ["Market", "Pearson r", "MAE test", "RMSE", "R² test"],
        [
            ["Central", "0,5623", "325,45", "386,01", "-2,8745"],
            ["East", "0,7234", "274,75", "295,67", "-2,0051"],
            ["South", "0,6205", "187,37", "215,30", "-9,7109"],
            ["West", "0,7206", "333,87", "397,89", "-1,5295"],
        ],
        [1.35, 1.35, 1.35, 1.25, 1.4],
        "Kết quả Linear Regression trên sáu tháng test",
        8.3,
    )
    r.paragraph("Kết luận. Tương quan toàn kỳ dương nhưng R² test âm ở cả bốn Market. Mô hình chưa tổng quát hóa đủ tốt và feature Marketing cùng tháng chưa biết khi dự báo tương lai. Vì vậy Linear Lab chỉ là nghiên cứu đang phát triển, không thay forecast và không tối ưu ngân sách thật.", "Kết luận.")

    # Page 24 — decision and limits.
    r.page_break(); r.page_heading("6.7", "Quyết định mô hình và hướng phát triển", "Giữ forecast và Linear thành hai nghiên cứu tách biệt; không gộp chỉ để tạo một chức năng có vẻ phức tạp hơn.")
    r.table(
        ["Tiêu chí", "Forecast MA3", "Linear Marketing Sales"],
        [
            ["Câu hỏi", "Sales tháng tới?", "Marketing và Sales cùng tháng liên hệ ra sao?"],
            ["Feature", "Sales các tháng trước", "Marketing của chính tháng"],
            ["Protocol", "15 khởi tạo, 6 validation, 3 test", "18 train, 6 test"],
            ["Kết quả", "MAE test 225,22", "R² test âm ở 4 Market"],
            ["Vai trò", "Baseline nghiên cứu chính", "Khảo sát feature và what-if"],
            ["Trạng thái", "Prototype, chưa production", "Đang phát triển, chưa tích hợp"],
        ],
        [1.5, 2.6, 2.6],
        "So sánh hai bài toán mô hình",
        8.5,
    )
    r.paragraph("Không sinh dữ liệu để tăng accuracy. Synthetic có thể hữu ích cho stress test thuật toán, nhưng không tạo thêm bằng chứng về thị trường thật. Với 24 tháng mỗi Market, hướng đúng là thu thêm lịch sử thực và giữ một kỳ đánh giá mới chưa từng được xem.", "Không sinh dữ liệu để tăng accuracy.")
    r.paragraph("Hướng tiếp theo. Có thể thử mô hình theo thời gian dùng Sales lag1/2/3, biến tháng hoặc mùa vụ và Marketing kế hoạch biết trước. Mô hình mới chỉ được tích hợp nếu vượt Naive hoặc MA3 trên validation đã khóa và tiếp tục hợp lý trên test mới.", "Hướng tiếp theo.")
    r.bullets([
        "Theo dõi bốn forecast 01/2014 khi có actual thật.",
        "Không chọn cấu hình theo test đã biết rồi gọi đó là kiểm định độc lập.",
        "Không diễn giải hệ số Linear thành tác động nhân quả.",
        "Không dùng model để ra quyết định nhập hàng khi thiếu biến nghiệp vụ.",
        "Giữ model version, issue month, train end và phạm vi đánh giá trong mọi đầu ra.",
    ], compact=False)

    # Page 25 — integrated handoff.
    r.page_break(); r.page_heading("Kết luận", "Câu chuyện thống nhất của phần Chi và Trang", "Kho dữ liệu đáng tin cậy là nền tảng; phân tích đa chiều là phần chính; giao diện và mô hình là lớp mở rộng có giới hạn.")
    r.paragraph("Thông điệp tổng quát. Phần Chi xây dựng và chứng minh dữ liệu có thể được nạp, tổng hợp và phân tích đúng trên mart và SSAS. Phần Trang sử dụng hợp đồng đó để tạo câu chuyện drill-down, truy vấn kiểm chứng và các nghiên cứu forecast. Hai phần nối nhau bằng grain, KPI và bằng chứng đối soát, không phải bằng một giao diện đơn lẻ.", "Thông điệp tổng quát.")
    r.table(
        ["Thứ tự bảo vệ", "Thao tác", "Điểm cần nói"],
        [
            ["1", "Nêu grain và mô hình sao", "Một dòng không phải đơn hàng"],
            ["2", "Trình bày mart và SSAS", "SQL và MDX giữ cùng tổng"],
            ["3", "Demo South Q3/2013", "Drill từ quý xuống Colombian"],
            ["4", "Mở truy vấn đối chứng", "KPI và filter có thể kiểm tra"],
            ["5", "Nếu ổn mới mở Cube 3D", "Nói rõ beta đang phát triển"],
            ["6", "Trình bày forecast", "Baseline, metric và giới hạn"],
            ["7", "Kết thúc bằng Linear", "Kết quả chưa tốt cũng là phát hiện"],
        ],
        [1.25, 2.4, 3.05],
        "Kịch bản bảo vệ an toàn",
        8.5,
    )
    r.paragraph("Tài sản kiểm chứng chính. Mã và biên bản nằm trong sql/sqlserver, ssis, ssas, results/TN05, results/TN06, results/native_build_20261120, experiments/baseline, experiments/tuning và docs/trang. Khi một chức năng web lỗi, các bảng kết quả, ảnh SSAS và phép đối soát vẫn là bằng chứng thay thế.", "Tài sản kiểm chứng chính.")
    r.paragraph("Kết luận cuối. Đề tài không cần chứng minh AI phức tạp. Giá trị nổi bật là một pipeline kho dữ liệu có thể truy vết, một hệ phân tích đa chiều có đối chứng và một quy trình thử nghiệm mô hình trung thực về giới hạn dữ liệu.", "Kết luận cuối.")

    r.save()
    print(OUTPUT.name)


if __name__ == "__main__":
    build_report()
