"""Optional offline Vietnamese narration. Download weights once; cache by text."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
import urllib.request
import wave

from coffee_dw.config import ROOT

VOICE_NAME = "vi_VN-vais1000-medium"
VOICE_DIR = ROOT / "data" / "models" / "piper"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium"


def prepare_voice(model_dir: Path = VOICE_DIR, download: bool = False) -> Path:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        path = model_dir / f"{VOICE_NAME}{suffix}"
        if path.exists():
            continue
        if not download:
            raise FileNotFoundError("Chưa có giọng Piper. Chạy prepare_forecast_demo.py --voice --download-voice")
        temporary = path.with_name(path.name + ".part")
        urllib.request.urlretrieve(f"{VOICE_URL}/{path.name}", temporary)
        temporary.replace(path)
    card = model_dir / "MODEL_CARD.txt"
    if download and not card.exists():
        urllib.request.urlretrieve(f"{VOICE_URL}/MODEL_CARD", card)
    return model_dir / f"{VOICE_NAME}.onnx"


def synthesize_bundle(bundle: dict, output_dir: Path, download: bool = False,
                      model_dir: Path = VOICE_DIR, progress=None) -> None:
    try:
        from piper import PiperVoice, SynthesisConfig
    except ImportError as exc:
        raise RuntimeError('Cài giọng đọc bằng python -m pip install -e ".[voice]"') from exc
    model_path = prepare_voice(model_dir, download)
    # espeak-ng's Windows C runtime cannot open a data path with Vietnamese
    # characters. The ONNX model stays in the project; copy only bundled
    # phonemizer resources into an ASCII user-temp path when required.
    import piper
    espeak_path = Path(piper.__file__).parent / "espeak-ng-data"
    if os.name == "nt" and not str(espeak_path).isascii():
        portable = Path(tempfile.gettempdir()) / "coffee_dw_piper" / "espeak-ng-data"
        if not str(portable).isascii():
            raise RuntimeError("Piper cần thư mục TEMP có đường dẫn ASCII trên Windows.")
        if not (portable / "phontab").is_file():
            shutil.copytree(espeak_path, portable, dirs_exist_ok=True)
        espeak_path = portable
    # Keep offline synthesis from exhausting CPU threads alongside Streamlit.
    import onnxruntime
    from piper.config import PiperConfig
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    voice = PiperVoice(
        config=PiperConfig.from_dict(json.loads(Path(str(model_path) + ".json").read_text(encoding="utf-8"))),
        session=onnxruntime.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"]),
        espeak_data_dir=espeak_path, download_dir=Path(model_dir),
    )
    folder = Path(output_dir) / "audio"
    folder.mkdir(parents=True, exist_ok=True)
    total = len(bundle["cases"]) * 3
    completed = 0
    for case in bundle["cases"]:
        for chapter in case["chapters"]:
            digest = hashlib.sha256((VOICE_NAME + "|v2-sentence-pauses-1.18|" + chapter["text"]).encode("utf-8")).hexdigest()[:24]
            path = folder / f"{digest}.wav"
            if not path.exists():
                temporary = path.with_suffix(".part.wav")
                # Explicit pauses avoid joined sentences; each paragraph is a new breath.
                # The voice's learned prosody is retained; no claim of human emotion.
                with wave.open(str(temporary), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(voice.config.sample_rate)
                    for paragraph in chapter["text"].split("\n\n"):
                        sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
                        for sentence in sentences:
                            if not sentence:
                                continue
                            for chunk in voice.synthesize(sentence, syn_config=SynthesisConfig(length_scale=1.18)):
                                wav_file.writeframes(chunk.audio_int16_bytes)
                            wav_file.writeframes(b"\x00\x00" * int(voice.config.sample_rate * .42))
                        wav_file.writeframes(b"\x00\x00" * int(voice.config.sample_rate * .40))
                temporary.replace(path)
            with wave.open(str(path), "rb") as wav_file:
                duration = wav_file.getnframes() / wav_file.getframerate()
                if duration <= .1:
                    raise RuntimeError(f"Audio không hợp lệ: {path.name}")
            chapter.update(audio_file=f"audio/{path.name}", audio_seconds=round(duration, 3))
            completed += 1
            if progress:
                progress(completed, total)
    bundle["voice"] = {"status": "ready", "engine": "Piper local", "voice": VOICE_NAME,
                       "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                       "source": VOICE_URL, "chapter_count": total,
                       "pacing": {"length_scale": 1.18, "sentence_pause_seconds": .42, "paragraph_extra_seconds": .40},
                       "note": "Nhân vật minh họa và TTS; không phải người thật hoặc LLM trò chuyện."}
