"""Verify research, generate narrated cases, archive evidence, publish locally."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
os.environ.setdefault("MPLCONFIGDIR",str(ROOT/".tmp/matplotlib"))

from coffee_dw.baseline_study import sha,utc,write_json,write_table
from coffee_dw.briefing import TUNING_DIR,build_briefing,case_markdown
from coffee_dw.briefing_report import write_reports
from coffee_dw.config import DB_PATH,SOURCE_PATH
from coffee_dw.demo import DEMO_DIR,load_demo_bundle,save_demo_bundle


def run(db=DB_PATH,research_dir=TUNING_DIR,output=ROOT/"experiments/briefing/results",publish_dir=DEMO_DIR,*,voice=False,download_voice=False,render=True):
    output,publish_dir=Path(output),Path(publish_dir)
    output.mkdir(parents=True,exist_ok=True)
    source_before=sha(SOURCE_PATH)
    bundle,tables=build_briefing(db,research_dir)
    for name,table in tables.items():
        write_table(output,name+".csv",table)
    print("Bước 1: 96 ô kho–nghiên cứu đã khớp; 48 case qua kiểm tra origin.",flush=True)
    for case in bundle["cases"]:
        if case["story"]["is_selected"]:
            path=output/"02_story/cases"/case["id"]
            write_json(path.with_suffix(".json"),case)
            path.with_suffix(".md").write_text(case_markdown(case,bundle),encoding="utf-8")
    print("Bước 2: đã lưu 16 hồ sơ MA3, công thức và lời đọc theo ba phần.",flush=True)
    previous=publish_dir/"bundle.json"
    backup=output/"00_previous_bundle.json"
    if previous.is_file() and not backup.exists():
        shutil.copy2(previous,backup)
    if voice:
        from coffee_dw.voice import synthesize_bundle
        def progress(done,total):
            if done%12==0 or done==total:
                print(f"Giọng đọc: {done}/{total} đoạn.",flush=True)
        synthesize_bundle(bundle,publish_dir,download=download_voice,progress=progress)
    figures=write_reports(bundle,tables,output,render=render)
    spec=importlib.util.spec_from_file_location("briefing_presenter_render",ROOT/"apps/forecast_demo/render.py")
    renderer=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    preview=next(case for case in bundle["cases"] if case["market"]=="West" and case["forecast_month"]=="2014-01-01" and case["story"]["is_selected"])
    (output/"preview_west_201401.html").write_text(renderer.render_presenter(preview,bundle,publish_dir),encoding="utf-8")
    # Archive immutable evidence before updating the live bundle. Content-hashed
    # audio stays in the live cache and is indexed by checksum below.
    write_json(output/"bundle_snapshot.json",bundle)
    audio=[]
    for case in bundle["cases"]:
        for chapter in case["chapters"]:
            if chapter.get("audio_file"):
                path=publish_dir/chapter["audio_file"]
                with wave.open(str(path),"rb") as wav:
                    duration=wav.getnframes()/wav.getframerate()
                    if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or duration<=.1:
                        raise ValueError("WAV không đúng định dạng.")
                audio.append({"case":case["id"],"chapter":chapter["id"],"file":chapter["audio_file"],
                              "seconds":duration,"sha256":sha(path)})
    write_json(output/"audio_index.json",{"cache_directory":str((publish_dir/"audio").resolve()),"references":audio})
    if sha(SOURCE_PATH)!=source_before:
        raise RuntimeError("Nguồn bị thay đổi trong khi chuẩn bị.")
    path=save_demo_bundle(bundle,publish_dir)
    load_demo_bundle(path)
    print("Bước 3: đã công bố bundle thuyết trình có nghiên cứu vào demo.",flush=True)
    files=sorted(p for p in output.rglob("*") if p.is_file() and p.name!="manifest.json")
    result={"created_at_utc":utc(),"source_sha256":source_before,"source_sha256_after":sha(SOURCE_PATH),
        "research_manifest_sha256":bundle["research"]["manifest_sha256"],"bundle_sha256":sha(path),
        "published_bundle":str(path.resolve()),"cases":48,"selected_cases":16,"reconciled_cells":96,
        "figure_count":len(figures),"figures":figures,"audio_references":len(audio),
        "audio_unique_files":len({x["file"] for x in audio}),"voice_status":bundle["voice"]["status"],
        "browser_visual_audio_acceptance":"not_verified_host_unavailable",
        "code_sha256":{name:sha(ROOT/name) for name in ["src/coffee_dw/briefing.py","src/coffee_dw/briefing_report.py","src/coffee_dw/demo.py","src/coffee_dw/voice.py",
            "experiments/briefing/run.py","apps/forecast_demo/app.py","apps/forecast_demo/render.py","apps/forecast_demo/presenter.html","apps/forecast_demo/presenter.css"]},
        "files":[{"path":p.relative_to(output).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in files]}
    write_json(output/"manifest.json",result)
    return result


def main():
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="Bước tiếp theo: tích hợp nghiên cứu vào bài thuyết trình có kiểm chứng.")
    parser.add_argument("--db",type=Path,default=DB_PATH)
    parser.add_argument("--research",type=Path,default=TUNING_DIR)
    parser.add_argument("--output",type=Path,default=ROOT/"experiments/briefing/results")
    parser.add_argument("--publish",type=Path,default=DEMO_DIR)
    parser.add_argument("--voice",action="store_true")
    parser.add_argument("--download-voice",action="store_true",help="Tải giọng Piper công khai nếu máy chưa có")
    args=parser.parse_args()
    result=run(args.db,args.research,args.output,args.publish,voice=args.voice,download_voice=args.download_voice)
    print(f"Hoàn tất: {result['figure_count']} bộ hình; {result['audio_references']} tham chiếu âm thanh.",flush=True)
    print(f"Báo cáo: {args.output.resolve()/'report.html'}",flush=True)


if __name__=="__main__":
    main()
