"""Local, bounded demo: warehouse forecasts + exact explanations + cached speech."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

# Streamlit executes entrypoints outside Python package context.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import render_presenter

from coffee_dw.config import DB_PATH, ROOT
from coffee_dw.demo import DEMO_DIR, load_demo_bundle, monthly_fingerprint, report_fingerprint, number_vi
from coffee_dw.forecast import monthly_sales
from coffee_dw.warehouse import read_detail
from coffee_dw.briefing import case_markdown


@st.cache_data(show_spinner=False)
def read_bundle(path: str, modified_ns: int):
    return load_demo_bundle(path)


@st.cache_data(show_spinner=False)
def warehouse_signature(path: str, modified_ns: int):
    detail = read_detail(path)
    return monthly_fingerprint(monthly_sales(detail)), report_fingerprint(detail)


def main():
    st.set_page_config(page_title="Coffee Lab · Dự báo có giải thích", page_icon="☕", layout="wide")
    st.markdown("<style>" + Path(__file__).with_name("app.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
    path = DEMO_DIR / "bundle.json"
    if not path.is_file():
        st.info("Demo chưa có dữ liệu đã chuẩn bị. Chạy lệnh bên dưới rồi tải lại trang.")
        st.code('python -m coffee_dw.cli demo\npython scripts/prepare_forecast_demo.py --voice --download-voice')
        st.stop()
    try:
        bundle = read_bundle(str(path), path.stat().st_mtime_ns)
        if not Path(DB_PATH).is_file():
            raise FileNotFoundError("Kho cục bộ chưa tồn tại. Chạy python -m coffee_dw.cli demo.")
        if warehouse_signature(str(DB_PATH), Path(DB_PATH).stat().st_mtime_ns) != (bundle["dataset"]["monthly_sha256"], bundle["dataset"].get("report_sha256")):
            st.warning("Kho đã thay đổi so với gói thuyết minh. Tạo lại gói demo để biểu đồ và lời đọc khớp dữ liệu mới.")
            st.code("python scripts/prepare_forecast_demo.py --voice")
            st.stop()
    except (ValueError, OSError, KeyError) as exc:
        st.error(f"Không đọc được gói demo: {exc}")
        st.stop()

    with st.sidebar:
        st.markdown('<div style="font-size:25px;font-weight:700;letter-spacing:-1px;margin:7px 0 3px">☕ coffee lab<span style="color:#729266">.</span></div><div style="font-size:10px;letter-spacing:1.7px;color:#8a8274;margin-bottom:30px">FORECAST EXPLAINER / PROTOTYPE</div>', unsafe_allow_html=True)
        st.caption("CHỌN PHẠM VI BÁO CÁO")
        market = st.selectbox("Thị trường", bundle["markets"], index=3)
        target = st.selectbox("Tháng dự báo", bundle["targets"], index=len(bundle["targets"])-1, format_func=lambda s: pd.Timestamp(s).strftime("%m/%Y"))
        methods = list(bundle["methods"])
        method = st.selectbox("Phương pháp", methods, index=methods.index(bundle["selected_method"]),
                              format_func=lambda s: bundle["methods"][s]+(" · Đã chọn" if s==bundle["selected_method"] else " · Đối chứng"))
        st.caption("Mặc định là phương pháp đã chốt bằng validation. Có thể chọn đối chứng để so cách tính.")
        st.divider()
        st.markdown("**Phương pháp chọn trên validation**")
        st.write(bundle["methods"][bundle["selected_method"]])
        st.caption("Chọn bằng MAE gộp 4 Market, kỳ 04–09/2013. Giữ nguyên lựa chọn trước test.")
        st.divider()
        st.markdown("**Một mạch báo cáo**")
        st.caption("Nhìn lại thị trường → hiểu dự kiến tháng tới → xác định điều cần kiểm tra.\n\nBấm nghe báo cáo hoặc tự chọn từng phần.")
        st.caption("Dữ liệu tháng 2012–2013 · đơn vị nguồn. Nhân vật minh họa và giọng TTS, không phải chatbot tự do.")
        if bundle.get("research"):
            st.caption("Đã đối soát 96 ô tháng–thị trường giữa nghiên cứu và kho SQLite. Bàn giao native của Chi là bước riêng.")

    case = next(c for c in bundle["cases"] if (c["market"], c["forecast_month"], c["method"]) == (market, target, method))
    st.markdown('<div class="demo-kicker">COFFEE LAB · BÁO CÁO ĐIỀU HÀNH THÁNG <span class="demo-pill">DỰ BÁO CÓ KIỂM CHỨNG</span></div><div class="demo-title">Một con số, đầy đủ căn cứ.</div><div class="demo-description">Chọn thị trường → xem dự báo → hiểu cách tính → kiểm chứng bằng lịch sử. Người thuyết trình dẫn bạn qua từng bằng chứng.</div>', unsafe_allow_html=True)
    if method!=bundle["selected_method"]:
        st.info("Bạn đang xem phương pháp đối chứng. Phương pháp được chọn để trình bày là "+bundle["methods"][bundle["selected_method"]]+".")
    cols = st.columns(3)
    cols[0].metric(f"Dự báo {pd.Timestamp(target):%m/%Y} · {market}", number_vi(case["prediction"]))
    change = case["prediction"] - case["last_actual"]
    cols[1].metric("So với tháng vừa kết thúc", ("+" if change >= 0 else "−") + number_vi(abs(change)))
    cols[2].metric("MAE validation tại thị trường", number_vi(case["validation_market"]["MAE"], 2))
    st.caption(f"Dữ liệu chốt đến {pd.Timestamp(case['train_end']):%m/%Y} · {bundle['methods'][method]} · Sai số tham khảo trên 6 kỳ validation, không phải khoảng dự báo.")
    html = render_presenter(case, bundle, DEMO_DIR)
    if hasattr(st, "iframe"):
        st.iframe(html, height="content", alt="Dự báo, biểu đồ đóng góp và người thuyết minh Coffee Lab")
    else:
        import streamlit.components.v1 as components
        components.html(html, height=1700 if bundle.get("research") else 1300, scrolling=True)

    if bundle.get("research"):
        with st.expander("Kết quả nghiên cứu đã chốt: 7 cấu hình và quyết định lựa chọn"):
            research=bundle["research"]
            st.write(f"Đã thử {research['candidate_count']} cấu hình; MAE validation tốt nhất {number_vi(research['validation_mae'],2)}. Cải thiện so cấu hình cơ sở {number_vi(research['gain_vs_previous_pct'],2)}%.")
            st.dataframe(pd.DataFrame(research["leaderboard"]),hide_index=True)
            st.caption("Chọn bằng validation 04–09/2013. Test đã được xem ở bước trước, vì vậy vòng mở rộng là thăm dò; không tuyên bố kiểm định mù mới.")

    with st.expander("Dữ liệu nào là thật, dữ liệu nào được tạo thêm?"):
        st.markdown("**Nguồn thật:** Coffee.csv có 4.248 dòng, tổng hợp thành 96 ô Market–tháng. Không tạo thêm doanh số giả.\n\n**Dữ liệu dẫn xuất:** 48 dự báo/giải thích = 4 Market × 4 kỳ × 3 phương pháp; các phần đóng góp, lời thuyết minh theo mẫu và WAV Piper.\n\n**Nghiên cứu:** EDA, thí nghiệm cơ sở và thử 7 cấu hình đã có kết quả lưu riêng. Chưa nghiệm thu với người dùng/SQL Server, chưa có bằng chứng nhân quả.")
        st.dataframe(pd.DataFrame(case["explanation"]["features"]), hide_index=True)
        st.caption(f"Mức nền: {number_vi(case['explanation']['base_value'], 4)} · Sai lệch tái dựng: {case['explanation']['reconstruction_error']:.3g}. Độ trễ có tương quan; cách phân chia đóng góp phụ thuộc mức tham chiếu và mô hình.")
        st.markdown("**So sánh phương pháp trên 24 dự báo validation của toàn chuỗi**")
        st.dataframe(pd.DataFrame(bundle["comparison"]), hide_index=True)
        st.code(f"monthly_sha256: {bundle['dataset']['monthly_sha256']}\nsource_sha256: {bundle['dataset']['source_sha256']}\nvoice: {bundle['voice']['status']}")
    with st.expander("Tải dữ liệu để xem hoặc đưa vào báo cáo"):
        if case.get("story"):
            st.download_button("Tải báo cáo đúng bộ lọc",case_markdown(case,bundle),case["id"]+".md","text/markdown")
            st.download_button("Tải bảng kiểm chứng đúng bộ lọc",pd.DataFrame(case["story"]["validation_history"]).to_csv(index=False).encode("utf-8-sig"),case["id"]+"_validation.csv","text/csv")
        for filename, label in [("case_summary.csv", "Tải bảng dự báo"), ("contributions.csv", "Tải bảng đóng góp"), ("narration.csv", "Tải lời thuyết minh")]:
            artifact = DEMO_DIR / filename
            if artifact.is_file():
                st.download_button(label, artifact.read_bytes(), filename, "text/csv")
    st.caption("Prototype của Trang · Dự báo, phân rã cộng tính và thuyết minh theo mẫu · main được giữ nguyên.")


if __name__ == "__main__":
    main()
