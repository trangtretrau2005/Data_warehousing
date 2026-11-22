"""Verify saved evidence, WAV cache, links and the actual prepared application."""

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote,urlsplit
import wave
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

import numpy as np
from PIL import Image
from streamlit.testing.v1 import AppTest

from coffee_dw.baseline_study import sha,write_json
from coffee_dw.demo import DEMO_DIR,load_demo_bundle


def verify(output=ROOT/"experiments/briefing/results"):
    output=Path(output)
    manifest=json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path=output/item["path"]
        assert path.stat().st_size==item["bytes"] and sha(path)==item["sha256"],path
    for path in [output/"report.html",*output.rglob("*.md")]:
        content=path.read_text(encoding="utf-8")
        links=re.findall(r'''(?:src|href)=["']([^"']+)["']''',content) if path.suffix==".html" else re.findall(r"\]\(([^)]+)\)",content)
        for link in links:
            parsed=urlsplit(link)
            if not parsed.scheme and parsed.path:
                assert (path.parent/unquote(parsed.path)).exists(),(path,link)
    for item in manifest["figures"]:
        image=Image.open(output/(item["path"]+".png"))
        assert image.width>2000 and image.height>1000
        assert all(abs(value-300)<1 for value in image.info["dpi"])
    index=json.loads((output/"audio_index.json").read_text(encoding="utf-8"))
    durations=[]
    for item in index["references"]:
        path=Path(index["cache_directory"]).parent/item["file"]
        assert sha(path)==item["sha256"]
        with wave.open(str(path),"rb") as stream:
            assert stream.getnchannels()==1 and stream.getsampwidth()==2
            pcm=np.frombuffer(stream.readframes(stream.getnframes()),dtype="<i2").astype(float)
            assert np.sqrt(np.mean(pcm**2))>1
            durations.append(len(pcm)/stream.getframerate())
    path=Path(manifest["published_bundle"])
    bundle=load_demo_bundle(path)
    assert sha(path)==manifest["bundle_sha256"]
    assert json.loads((output/"bundle_snapshot.json").read_text(encoding="utf-8"))==bundle
    app=AppTest.from_file(str(ROOT/"apps/forecast_demo/app.py"),default_timeout=30).run()
    assert not app.exception and not app.warning
    assert app.selectbox[0].value=="West" and app.selectbox[1].value=="2014-01-01" and app.selectbox[2].value=="moving_average_3"
    assert app.metric[0].value=="11.593,0"
    tests={}
    for name in ("pytest","frontend"):
        report=DEMO_DIR/f"qa_v3_{name}.xml"
        if report.is_file():
            root=ET.parse(report).getroot()
            cases=list(root.iter("testcase"))
            totals={"tests":len(cases),"failures":sum(c.find("failure") is not None for c in cases),
                    "errors":sum(c.find("error") is not None for c in cases)}
            assert totals["tests"]>0
            assert totals["failures"]==0 and totals["errors"]==0
            tests[name]=totals
    result={"artifacts_verified":len(manifest["files"]),"figures":manifest["figure_count"],
        "source_unchanged":manifest["source_sha256"]==manifest["source_sha256_after"],
        "links_valid":True,"png_dpi":300,"audio_references":len(durations),"audio_unique_files":manifest["audio_unique_files"],
        "audio_duration_min":min(durations) if durations else None,"audio_duration_max":max(durations) if durations else None,
        "prepared_app":"AppTest passed; default West/2014-01/MA3; no exception/warning",
        "test_reports":tests,"browser_visual_audio_acceptance":"not_verified_host_unavailable"}
    write_json(DEMO_DIR/"qa_v3.json",result)
    return result


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"experiments/briefing/results")
    args=parser.parse_args()
    print(json.dumps(verify(args.output),ensure_ascii=False,indent=2))
