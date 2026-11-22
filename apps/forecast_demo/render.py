"""Render a trusted, local presenter template; embed only validated numeric cases."""

import base64
import json
from pathlib import Path

from plotly.offline import get_plotlyjs


def render_presenter(case: dict, bundle: dict, output_dir: Path) -> str:
    audio = []
    for chapter in case["chapters"]:
        relative = chapter.get("audio_file")
        path = (output_dir / relative).resolve() if relative else None
        if path is not None and not path.is_relative_to(output_dir.resolve()):
            raise ValueError("Audio must stay inside the generated demo directory")
        audio.append("data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
                     if path is not None and path.is_file() else None)
    payload = {"case": case, "audio": audio, "methods": bundle["methods"],
               "selected_method": bundle["selected_method"], "voice": bundle["voice"],
               "research": bundle.get("research")}
    safe_json = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = Path(__file__).with_name("presenter.html").read_text(encoding="utf-8")
    css = Path(__file__).with_name("presenter.css").read_text(encoding="utf-8")
    return template.replace("__PLOTLY_JS__", get_plotlyjs()).replace("__DATA_JSON__", safe_json).replace("__REPORT_CSS__", css)
