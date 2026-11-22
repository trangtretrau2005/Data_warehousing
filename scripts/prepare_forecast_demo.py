"""Prepare real forecast/explanation/narration artifacts for the bounded demo."""

import argparse
from pathlib import Path
import sys

from coffee_dw.config import DB_PATH
from coffee_dw.demo import DEMO_DIR, build_demo_bundle, save_demo_bundle


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=DEMO_DIR)
    parser.add_argument("--voice", action="store_true", help="Generate cached Vietnamese WAV with local Piper")
    parser.add_argument("--download-voice", action="store_true", help="Download public Piper model on first use")
    args = parser.parse_args()
    bundle = build_demo_bundle(args.db)
    print(f"Đã tạo {len(bundle['cases'])} trường hợp, 16 bộ lọc × 3 phương pháp.", flush=True)
    if args.voice:
        from coffee_dw.voice import synthesize_bundle

        def progress(done, total):
            if done % 12 == 0 or done == total:
                print(f"Đã chuẩn bị giọng đọc {done}/{total} đoạn.", flush=True)

        synthesize_bundle(bundle, args.output, download=args.download_voice, progress=progress)
    # Publish only after all requested audio is ready; keep the previous bundle
    # usable if synthesis is interrupted.
    path = save_demo_bundle(bundle, args.output)
    print(f"Kết quả: {path}")
    print("Mở demo: python -m streamlit run apps/forecast_demo/app.py --server.port 8502")


if __name__ == "__main__":
    main()
