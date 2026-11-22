"""Render scientific figures and a Vietnamese report from measured native runs."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

from coffee_dw.config import ROOT
from coffee_dw.exploration_plots import configure, NAVY, TEAL, GRID, INK, MUTED

LABELS = {"TN08_read": "TN08 · đọc tổng hợp", "TN08_insert": "TN08 · INSERT + duy trì view",
          "TN09_month": "TN09 · một tháng", "TN09_all": "TN09 · toàn bộ 24 tháng",
          "TN10_narrow": "TN10 · lát cắt hẹp", "TN10_broad": "TN10 · toàn bộ bảng"}


def save(fig, folder, stem, note):
    fig.text(.06, .025, note, fontsize=11, color=MUTED, va="bottom")
    folder.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(folder / f"{stem}.{suffix}", dpi=300, bbox_inches="tight", pad_inches=.2)
    plt.close(fig)


def panels(summary, column, title, unit, folder, stem, row_count=2124000):
    order = list(summary.experiment.drop_duplicates())
    fig, axes = plt.subplots(3, 2, figsize=(11.2, 10.5), squeeze=False)
    fig.subplots_adjust(left=.1, right=.97, top=.86, bottom=.13, hspace=.7, wspace=.35)
    fig.suptitle(title, x=.06, y=.97, ha="left", fontsize=22, weight="bold")
    fig.text(.06, .91, f"SQL Server Express · {row_count:,} dòng · N = 15 lượt / phương án", fontsize=14, color=MUTED)
    for axis, experiment in zip(axes.flat, order):
        data = summary.loc[summary.experiment.eq(experiment)].sort_values("variant")
        values = data[column].to_numpy()
        bars = axis.bar(data.variant, values, color=[NAVY, TEAL], width=.52, zorder=3)
        axis.bar_label(bars, labels=[f"{v:,.1f}" for v in values], padding=5, fontsize=13)
        axis.set_title(LABELS.get(experiment, experiment), loc="left", fontsize=16, pad=14)
        axis.set_ylabel(unit)
        axis.set_ylim(0, max(1, values.max()) * 1.35)
        axis.grid(axis="y", color=GRID); axis.set_axisbelow(True)
    save(fig, folder, stem, "Nguồn: actual plans · Cùng MAXDOP 1, MAX_GRANT_PERCENT=1 · Warm cache, máy dùng chung.\nA/B đổi ý nghĩa theo TN; xem bảng phương án trong báo cáo. Thời gian server có độ phân giải ms.")


def render(folder):
    configure()
    summary = pd.read_csv(folder / "benchmark_summary.csv")
    raw = pd.read_csv(folder / "benchmark_runs.csv")
    env = json.loads((folder / "environment.json").read_text(encoding="utf-8"))
    if env.get("status") != "measured":
        raise ValueError("Native benchmark must finish before publishing a report")
    measured = raw.loc[~raw.warmup]
    if len(measured) != 180 or len(raw) != 216:
        raise ValueError("Expected six pairs, 3 warm-up + 15 measured per variant")
    row_count = env["copies"] * 4248
    panels(summary, "median_ms", "Thời gian server: kết quả phụ thuộc workload", "Median elapsed (ms)", folder / "figures", "01_elapsed", row_count)
    panels(summary, "median_logical_reads", "Số đọc logic từ các actual runtime counters", "Median logical reads (trang 8 KB)", folder / "figures", "02_logical_reads", row_count)
    meanings = pd.DataFrame([
        ["TN08_read", "GROUP BY trên bảng gốc; EXPAND VIEWS", "Indexed view; NOEXPAND"],
        ["TN08_insert", "INSERT 4.248 dòng vào WriteA không view", "INSERT cùng batch vào WriteB có indexed view"],
        ["TN09_month", "Heap không partition, 10/2012", "Heap RANGE RIGHT, 10/2012"],
        ["TN09_all", "Heap không partition, 24 tháng", "Heap RANGE RIGHT, 24 tháng"],
        ["TN10_narrow", "Heap không NCI, 719/Amaretto 01–03/2012", "Có covering NCI, cùng lát cắt"],
        ["TN10_broad", "Heap không NCI, toàn bảng", "Có covering NCI, toàn bảng"],
    ], columns=["experiment", "A", "B"])
    meanings.to_csv(folder / "variant_dictionary.csv", index=False)
    sections = ["# Kết quả TN07–TN10 trên SQL Server thật", "",
        "Ngày thực hiện: 19/11/2026. Đây là benchmark trên máy phát triển dùng chung, không phải SLA sản xuất.", "",
        f"Engine: {env['engine'][0]['ProductVersion']} — {env['engine'][0]['Edition']}. "
        f"Database biệt lập: `{env['database']}`. Nguồn bất biến: `{env['source_sha256']}`.", "",
        "## Dữ liệu và giao thức", "",
        f"{env['copies']} bản sao của nguồn 4.248 dòng tạo {row_count:,} dòng/bảng bench, Sales = {env['copies'] * 819811:,}. "
        "Đây chỉ là dữ liệu tải; không đưa vào mô hình dự báo. `table_totals.csv` và `except_two_way.csv` "
        "lưu đối soát tổng và đa tập theo grain (COUNT_BIG, SUM) bằng EXCEPT hai chiều trước/sau đo.", "",
        "Mỗi cặp có 3 warm-up/phương án, 15 lượt đo/phương án, thứ tự AB ở vòng lẻ và BA ở vòng chẵn. "
        "Không flush cache. Cả A/B dùng MAXDOP 1, MAX_GRANT_PERCENT=1 tại query. "
        "Lần đối soát đầu gặp RESOURCE_SEMAPHORE; đã hủy đúng session của runner rồi áp giới hạn query, "
        "không đổi cấu hình server. Giới hạn này cũng là điều kiện thực nghiệm, không khái quát thành hiệu năng mặc định.", "",
        "Mọi lượt lưu actual `.sqlplan` và Messages IO/TIME. `elapsed_ms`/`cpu_ms` lấy QueryTimeStats; "
        "logical_reads cộng ActualLogicalReads trên runtime operators/threads. Client elapsed lưu riêng và gồm truyền kết quả/plan. "
        "Các bước INSERT nằm trong transaction rồi ROLLBACK; server time là statement INSERT, không gồm thời gian rollback; "
        "client elapsed có gồm rollback. Không gọi phép đo này là tốc độ commit hoặc throughput.", "",
        "## Phương án", "", meanings.to_csv(index=False), "## Kết quả", "", summary.to_csv(index=False), "",
        "![Median server elapsed](figures/01_elapsed.png)", "", "![Median logical reads](figures/02_logical_reads.png)", "",
        "## Nhận xét theo workload", ""]
    for experiment, group in summary.groupby("experiment", sort=False):
        a = group.loc[group.variant.eq("A")].iloc[0]
        b = group.loc[group.variant.eq("B")].iloc[0]
        sections.append(f"- **{experiment}:** median elapsed A/B = {a.median_ms:g}/{b.median_ms:g} ms; "
                        f"p95 = {a.p95_ms:g}/{b.p95_ms:g} ms; median logical reads = "
                        f"{a.median_logical_reads:g}/{b.median_logical_reads:g}. "
                        + ("Có giá trị 0 ms: sát độ phân giải, không tính speedup vô hạn." if min(a.median_ms, b.median_ms) == 0 else "Kết luận chỉ áp dụng dữ liệu, cache và giới hạn query đã ghi."))
    plan_info = json.loads((folder / "actual_plan_summary.json").read_text(encoding="utf-8"))
    native_checks = []
    for exp in ("TN09_month", "TN09_all"):
        items = [r for r in plan_info if r["experiment"] == exp and r["variant"] == "B" and not r["warmup"]]
        counts = sorted({access["count"] for r in items for access in r["partitions_accessed"]})
        native_checks.append({"experiment": exp, "observed_partition_counts": counts})
        sections.append(f"- `{exp}` phương án B: actual plan ghi số partition truy cập {counts}.")
    write = summary.loc[summary.experiment.eq("TN08_insert")]
    sections += ["", "## Giới hạn và tài sản", "",
        "- Partition lưu trên cùng PRIMARY; không phải thử nghiệm phân bố I/O qua nhiều đĩa.",
        "- NCI là covering index; nếu không có Lookup trong actual plan thì không tự thêm hay tuyên bố đã thấy Lookup.",
        "- Dung lượng theo object/index ở `storage.csv`; trang 8 KB khác với logical read counters.",
        "- Bộ số đo gồm 216 actual plans (36 lượt/cặp × 6 cặp), 180 lượt chính; mỗi lượt có checksum kết quả A/B.",
        "- p95 dùng pandas quantile(0.95), nội suy tuyến tính; N=15 mỗi ô. Có instrumentation overhead và tải nền.",
        "- Không thay bằng chứng SSIS/SSAS hoặc thử người dùng bằng benchmark này.", ""]
    (folder / "analysis.md").write_text("\n".join(sections), encoding="utf-8")
    body = "<h1>Kết quả TN07–TN10: SQL Server thật</h1><p>19/11/2026 · N=15/phương án · máy dùng chung · giới hạn query như analysis.md</p>"
    body += "<h2>Phương án</h2>" + meanings.to_html(index=False)
    body += "<h2>Kết quả</h2>" + summary.to_html(index=False, float_format=lambda x: f"{x:,.2f}")
    for name in ("01_elapsed", "02_logical_reads"):
        body += f'<img src="figures/{name}.png" alt="Kết quả benchmark" style="width:100%;max-width:1100px">'
    body += "<h2>Diễn giải và giới hạn</h2><pre style='white-space:pre-wrap'>" + html.escape("\n".join(sections[sections.index("## Nhận xét theo workload"):])) + "</pre>"
    (folder / "report.html").write_text("<!doctype html><html lang='vi'><meta charset='utf-8'><title>TN07–TN10</title><style>body{font:18px 'Times New Roman',serif;color:#18324e;margin:40px auto;max-width:1200px}table{border-collapse:collapse;width:100%;font-size:15px}td,th{border:1px solid #ccd8e3;padding:8px;text-align:left}th{background:#eaf0f5}</style>" + body + "</html>", encoding="utf-8")
    write_json = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    write_json(folder / "native_checks.json", native_checks)
    sources = [ROOT / "scripts" / name for name in ("run_native_benchmarks.py", "run_native_hru.py", "summarize_benchmarks.py", "render_native_report.py")]
    sources += list((ROOT / "sql/sqlserver").glob("0[1-8]_*.sql"))
    sources += [ROOT / "src/coffee_dw" / name for name in ("source.py", "sqlserver.py")]
    write_json(folder / "reproducibility.json", {
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "note": "Code hashes captured at publication from the working tree; commit alone does not identify uncommitted work.",
        "inputs": [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]})
    if (folder / "hru/benchmark_summary.csv").exists():
        render_hru(folder / "hru")
    inventory = [{"path": str(p.relative_to(folder)).replace("\\", "/"), "bytes": p.stat().st_size,
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.rglob("*"))
                 if p.is_file() and p.name != "artifact_manifest.json"]
    write_json(folder / "artifact_manifest.json", inventory)
    print(f"Published report + 2 figure sets, verified inventory of {len(inventory)} measured artifacts")


def render_hru(folder):
    summary = pd.read_csv(folder / "benchmark_summary.csv")
    protocol = json.loads((folder / "protocol.json").read_text(encoding="utf-8"))
    cuboids = pd.read_csv(folder / "cuboids.csv")
    rounds = pd.read_csv(folder / "hru_rounds.csv")
    mapping = pd.read_csv(folder / "workload_mapping.csv")
    panels(summary, "median_ms", "HRU: replay workload qua các cuboid đã chọn", "Median elapsed (ms)", folder / "figures", "01_hru_elapsed", protocol["base_benchmark_rows"])
    positions = {"MRP": (.5,.88), "MR": (.16,.63), "MP": (.5,.63), "RP": (.84,.63),
                 "M": (.16,.35), "R": (.5,.35), "P": (.84,.35), "ALL": (.5,.1)}
    costs = dict(zip(cuboids.cuboid, cuboids.group_rows))
    chosen = set(protocol["selected_views"])
    fig, axis = plt.subplots(figsize=(11.2, 8.2))
    fig.subplots_adjust(left=.04,right=.96,top=.83,bottom=.13)
    fig.suptitle("Lattice HRU: cardinality đo thật, ngân sách giả định", x=.06,y=.97,ha="left",fontsize=22,weight="bold")
    fig.text(.06,.9,f"Đã chọn {protocol['selected_group_rows']}/300 group-row · màu xanh: được dùng trong replay",fontsize=14,color=MUTED)
    for high, (x,y) in positions.items():
        high_set = set(high) if high != "ALL" else set()
        for low,(a,b) in positions.items():
            low_set = set(low) if low != "ALL" else set()
            if len(high_set) == len(low_set)+1 and low_set.issubset(high_set):
                axis.annotate("",xy=(a,b+.035),xytext=(x,y-.035),arrowprops={"arrowstyle":"->","color":"#B6C5D4","lw":1.3},zorder=1)
    for node,(x,y) in positions.items():
        axis.text(x,y,f"{node}\n{costs[node]:,} dòng",ha="center",va="center",fontsize=16,
                  color="white" if node in chosen else INK,
                  bbox={"boxstyle":"round,pad=.55","facecolor":TEAL if node in chosen else "#EEF3F7","edgecolor":TEAL if node in chosen else "#B6C5D4"},zorder=3)
    axis.set_xlim(0,1); axis.set_ylim(0,1); axis.axis("off")
    save(fig,folder/"figures","02_hru_lattice","Nguồn: cuboid cardinality thực trong SQL Server · M: tháng, R: Market, P: Product.\nNgân sách 300 group-row và trọng số workload là giả định; không phải byte hay latency.")
    content = ["# TN13 HRU: kiểm chứng trên SQL Server", "",
        "Ngày 19/11/2026. Các cuboid là bảng tổng hợp thường trong bench; không tự cập nhật như indexed view.", "",
        "## Lựa chọn mô hình chi phí", "", rounds.to_csv(index=False), "",
        f"Đã chọn {protocol['selected_group_rows']}/300 group-row. Mô hình dùng base {protocol['base_source_rows']} dòng nguồn; "
        f"replay vật lý dùng {protocol['base_benchmark_rows']:,} dòng nhân tải. Cardinality cuboid không đổi khi nhân bản.", "",
        "![Lattice](figures/02_hru_lattice.png)", "", "## Mapping workload", "", mapping.to_csv(index=False), "",
        "A đọc base, B đọc ancestor nhỏ nhất trong các cuboid được chọn; MP không có ancestor đã chọn thì B quay về base. "
        "Các candidate không được chọn vẫn được tạo để khảo sát cardinality/storage nhưng không phục vụ B.", "",
        "## Số đo SQL", "", summary.to_csv(index=False), "", "![Replay](figures/01_hru_elapsed.png)", "",
        "Mỗi query/variant 3 warm-up +15 measured, AB/BA, actual plan và checksum kết quả. "
        "Weights là giả định; không coi greedy bảo đảm tối ưu toàn cục, không so lợi ích group-row trực tiếp với ms/byte. "
        "Không có đo maintenance/refresh cho các cuboid HRU. Chênh nhỏ/0ms hoặc tải nền không đủ kết luận speedup.", ""]
    (folder / "analysis.md").write_text("\n".join(content),encoding="utf-8")
    body = "<h1>TN13 HRU — SQL Server</h1><h2>Lựa chọn</h2>"+rounds.to_html(index=False)+"<h2>Workload</h2>"+mapping.to_html(index=False)+"<h2>Số đo</h2>"+summary.to_html(index=False)
    body += '<img src="figures/02_hru_lattice.png" style="width:100%"><img src="figures/01_hru_elapsed.png" style="width:100%">'
    body += "<p>Ngân sách/trọng số giả định; ordinary aggregate tables; không đo refresh/maintenance HRU. N=15/variant; máy Express dùng chung.</p>"
    (folder / "report.html").write_text("<!doctype html><html lang='vi'><meta charset='utf-8'><title>TN13 HRU</title><style>body{font:18px 'Times New Roman';margin:40px auto;max-width:1150px}table{border-collapse:collapse;font-size:14px}td,th{border:1px solid #ccd8e3;padding:7px}</style>"+body+"</html>",encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    render(parser.parse_args().folder)
