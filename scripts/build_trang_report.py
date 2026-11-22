"""Build a printable HTML report from the versioned Trang chapters, using stdlib only."""

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "docs/trang/chapter06_forecasting.md", ROOT / "docs/trang/chapter07_deployment.md",
           ROOT / "docs/trang/research_findings.md"]
FIGURES = {
    "6.3": ("experiments/baseline/results/02_protocol/figures/01_rolling_origin.png", "Lịch dự báo một bước với quá khứ mở rộng"),
    "6.5": ("experiments/tuning/results/02_validation/figures/01_ranking.png", "So sánh MAE validation giữa các cấu hình"),
    "6.6": ("results/trang_forecast_review/figures/01_ma3_nine_origins.png", "Thực tế và MA3: sáu kỳ validation, ba kỳ test; mỗi điểm dự báo trước một tháng"),
    "6.7": ("experiments/briefing/results/02_story/figures/west_201401_moving_average_3.png", "Dự báo và công thức MA3 cho West tháng 01 năm 2014"),
    "Kết quả native ngày 19 tháng 11 năm 2026": ("results/native_trang/20261119/figures/01_elapsed.png", "Median và p95 elapsed của các đối chứng SQL Server"),
    "TN13 mở rộng HRU và kiểm chứng SQL": ("results/native_trang/20261119/hru/figures/02_hru_lattice.png", "Lattice cuboid và phương án HRU theo ngân sách giả định"),
}


def inline(text: str, source: Path, output: Path) -> str:
    value = html.escape(text)
    def link(match):
        label, target = match.groups()
        if not target.startswith(("https://", "http://", "#")):
            target = Path(os.path.relpath(source.parent / html.unescape(target), output.parent)).as_posix()
        return f'<a href="{html.escape(target, quote=True)}">{label}</a>'
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", link, value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)


def convert(source: Path, output: Path) -> str:
    lines = source.read_text(encoding="utf-8").splitlines()
    blocks, index, figures = [], 0, []
    def add_figures():
        for path, caption in figures:
            if not path.exists():
                raise FileNotFoundError(path)
            relative = Path(os.path.relpath(path, output.parent)).as_posix()
            blocks.append(f'<figure><img src="{html.escape(relative)}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>')
        figures.clear()
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("#"):
            add_figures()
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            blocks.append(f"<h{level}>{inline(text, source, output)}</h{level}>")
            key = text.split()[0]
            figure = FIGURES.get(text) or FIGURES.get(key)
            if figure:
                path, caption = figure
                figures.append((ROOT / path, caption))
            index += 1
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [v.strip() for v in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", v) for v in cells):
                    rows.append(cells)
                index += 1
            blocks.append("<div class='table-wrap'><table>")
            for row_index, cells in enumerate(rows):
                cell = "th" if row_index == 0 else "td"
                if row_index == 0:
                    blocks.append("<thead>")
                elif row_index == 1:
                    blocks.append("<tbody>")
                blocks.append("<tr>" + "".join(f"<{cell}>{inline(v, source, output)}</{cell}>" for v in cells) + "</tr>")
                if row_index == 0:
                    blocks.append("</thead>")
            blocks.append("</tbody></table></div>")
        elif line.startswith("- "):
            blocks.append("<ul>")
            while index < len(lines) and lines[index].strip().startswith("- "):
                blocks.append("<li>" + inline(lines[index].strip()[2:], source, output) + "</li>")
                index += 1
            blocks.append("</ul>")
        else:
            paragraph = [line]
            index += 1
            while index < len(lines) and lines[index].strip() and not lines[index].strip().startswith(("#", "|", "- ")):
                paragraph.append(lines[index].strip())
                index += 1
            blocks.append("<p>" + inline(" ".join(paragraph), source, output) + "</p>")
    add_figures()
    return "\n".join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/trang_completion/report_trang.html")
    args = parser.parse_args()
    output = args.output.resolve()
    body = "\n".join(f"<article>{convert(source, output)}</article>" for source in SOURCES)
    content = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Dự báo và triển khai Coffee DW</title>
<style>body{font-family:'Times New Roman',serif;color:#111;background:#eee;margin:0;line-height:1.5;font-size:18px}
main{max-width:1000px;margin:24px auto;padding:40px 54px;background:white}h1,h2{color:#000;line-height:1.25}h1{font-size:29px;margin-top:0}h2{font-size:23px;margin:30px 0 12px}
p{margin:10px 0;text-align:justify}a{color:#164d78;text-underline-offset:2px}table{border-collapse:collapse;width:100%;font-size:16px;margin:16px 0}th,td{border:1px solid #d9d9d9;padding:9px 11px;vertical-align:top}th{background:#e7eef4;text-align:left;color:black}tr:nth-child(even){background:#f8fafc}thead{display:table-header-group}tr{break-inside:avoid}figure{margin:24px 0;break-inside:avoid}figure img{max-width:100%;height:auto}figcaption{font-size:16px;text-align:center;font-style:italic;margin:8px}code{font-size:.87em;overflow-wrap:anywhere}article+article{margin-top:56px;padding-top:20px}article:last-child table{font-size:15px}.note{font-size:16px;color:#444}button{font-size:16px;padding:7px 16px}
@media print{@page{size:A4;margin:20mm}body{background:white;font-size:12pt}main{margin:0;padding:0;max-width:none}.no-print{display:none}h1{font-size:19pt}h2{font-size:15pt;break-after:avoid}p{widows:3;orphans:3}table{font-size:10pt}article+article{break-before:page;margin:0;padding:0}a{color:black}figure img{max-height:210mm;object-fit:contain}}
</style></head><body><main><div class="no-print"><button onclick="window.print()">In hoặc lưu PDF</button>
<p class="note">Coffee DW · Phần Trang · Cập nhật 19/11/2026. Nội dung có thể chỉnh sửa trong các tệp Markdown đi kèm.</p></div>""" + body + "</main></body></html>"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "sources": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES},
                "html_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "scope": "Printable HTML; not a rendered or verified DOCX"}
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
