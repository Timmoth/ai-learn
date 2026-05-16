from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def _http_post_bytes(url: str, payload: dict, timeout: float) -> bytes:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def load_dictionary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_dictionary(path: Path, dictionary: dict[str, str]) -> None:
    ordered = dict(sorted(dictionary.items(), key=lambda kv: kv[0].lower()))
    path.write_text(json.dumps(ordered, indent=2) + "\n")


def apply_dictionary(text: str, dictionary: dict[str, str]) -> str:
    if not dictionary:
        return text
    lookup = {k.lower(): v for k, v in dictionary.items()}
    keys = sorted(lookup.keys(), key=len, reverse=True)
    pattern = r"(?<!\w)(" + "|".join(re.escape(k) for k in keys) + r")(?!\w)"
    regex = re.compile(pattern, re.IGNORECASE)
    return regex.sub(lambda m: lookup[m.group(0).lower()], text)


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def synthesize(
    script_path: Path,
    audio_path: Path,
    config: dict,
    dict_path: Path | None = None,
) -> None:
    """Render script_path → audio_path.mp3 via the configured TTS server."""
    tts = config.get("tts", {})
    if not tts.get("enabled", True):
        print("TTS disabled in config; skipping audio render.")
        return

    url = os.environ.get("TTS_URL") or tts.get("url", "http://localhost:8880/v1")
    voice = os.environ.get("TTS_VOICE") or tts.get("voice", "am_eric")
    model = tts.get("model", "kokoro")
    speed = tts.get("speed", 1.0)
    response_format = tts.get("response_format", "flac").lower()
    normalization_options = tts.get("normalization_options")
    timeout = tts.get("timeout_seconds", 600)

    needs_transcode = response_format != "mp3"
    if needs_transcode and shutil.which("ffmpeg") is None:
        raise RuntimeError(
            f"ffmpeg not found on PATH; required to transcode {response_format} → MP3."
        )

    text = _strip_markdown(script_path.read_text(encoding="utf-8"))
    if not text:
        raise RuntimeError(f"{script_path} is empty after stripping markdown.")

    if dict_path is not None:
        dictionary = load_dictionary(dict_path)
        if dictionary:
            text = apply_dictionary(text, dictionary)
            print(f"  applied TTS dictionary ({len(dictionary)} entries)")

    print(
        f"  TTS  {url}  voice={voice}  format={response_format}  "
        f"speed={speed}  ({len(text)} chars)"
    )

    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": response_format,
        "speed": speed,
        "stream": False,
    }
    if normalization_options is not None:
        payload["normalization_options"] = normalization_options

    try:
        audio_bytes = _http_post_bytes(f"{url}/audio/speech", payload, timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"TTS HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"TTS request failed: {e.reason}") from e

    if not audio_bytes:
        raise RuntimeError("TTS server returned an empty response.")

    audio_path.parent.mkdir(parents=True, exist_ok=True)

    if not needs_transcode:
        audio_path.write_bytes(audio_bytes)
    else:
        intermediate = audio_path.with_suffix(f".{response_format}")
        intermediate.write_bytes(audio_bytes)
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(intermediate),
                    "-c:a", "libmp3lame", "-q:a", "0",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")
        finally:
            try:
                intermediate.unlink()
            except FileNotFoundError:
                pass

    size_mb = audio_path.stat().st_size / 1024 / 1024
    print(f"  wrote {audio_path}  ({size_mb:.1f} MB)")
