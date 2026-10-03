"""Text to speech, one WAV per sentence so every sentence has an exact start and end.

Engines:
  kokoro  open source (Apache-2.0), runs on CPU, very natural English. Default for English.
  edge    edge-tts, free Microsoft neural voices (needs internet, no key). Default for Turkish.
  piper   open source, fully offline, CPU; Turkish voice is tr_TR-dfki-medium (more robotic).
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

SR = 24000
KOKORO_FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
KOKORO_LANG = {"en": "en-us", "gb": "en-gb", "es": "es", "fr": "fr-fr", "it": "it", "pt": "pt-br"}


def _download(url: str, dest: Path):
    print(f"  indiriliyor: {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)


def _to_sr(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return audio.astype(np.float32)
    x = np.linspace(0, len(audio), int(len(audio) * SR / sr), endpoint=False)
    return np.interp(x, np.arange(len(audio)), audio).astype(np.float32)


class Kokoro:
    def __init__(self, models_dir: Path, voice: str, lang: str, speed: float):
        from kokoro_onnx import Kokoro as K
        for name, url in KOKORO_FILES.items():
            if not (models_dir / name).exists():
                _download(url, models_dir / name)
        self.k = K(str(models_dir / "kokoro-v1.0.onnx"), str(models_dir / "voices-v1.0.bin"))
        self.voice, self.lang, self.speed = voice, KOKORO_LANG.get(lang, "en-us"), speed

    def say(self, text: str) -> np.ndarray:
        audio, sr = self.k.create(text, voice=self.voice, speed=self.speed, lang=self.lang)
        return _to_sr(audio, sr)


class Edge:
    def __init__(self, voice: str, speed: float, work: Path):
        self.voice, self.work = voice, work
        pct = int(round((speed - 1) * 100))
        self.rate = f"{pct:+d}%"

    def say(self, text: str) -> np.ndarray:
        import edge_tts
        out = self.work / "_edge.mp3"
        asyncio.run(edge_tts.Communicate(text, self.voice, rate=self.rate).save(str(out)))
        wav = self.work / "_edge.wav"
        from .ff import ffmpeg
        ffmpeg(["-i", str(out), "-ac", "1", "-ar", str(SR), str(wav)])
        audio, _ = sf.read(wav, dtype="float32")
        return audio


class Piper:
    def __init__(self, voice: str, models_dir: Path, speed: float, work: Path):
        self.voice, self.dir, self.work = voice, models_dir / "piper", work
        self.dir.mkdir(parents=True, exist_ok=True)
        if not (self.dir / f"{voice}.onnx").exists():
            subprocess.run([sys.executable, "-m", "piper.download_voices", "--data-dir", str(self.dir), voice],
                           check=True)
        self.length_scale = 1 / speed

    def say(self, text: str) -> np.ndarray:
        wav = self.work / "_piper.wav"
        subprocess.run([sys.executable, "-m", "piper", "-m", str(self.dir / f"{self.voice}.onnx"),
                        "--length-scale", str(self.length_scale), "-f", str(wav), "--", text],
                       check=True, capture_output=True)
        audio, sr = sf.read(wav, dtype="float32")
        return _to_sr(audio, sr)


def make_engine(name: str, voice: str, lang: str, speed: float, models_dir: Path, work: Path):
    if name == "kokoro":
        return Kokoro(models_dir, voice, lang, speed)
    if name == "edge":
        return Edge(voice, speed, work)
    if name == "piper":
        return Piper(voice, models_dir, speed, work)
    raise SystemExit(f"bilinmeyen ses motoru: {name}")


def narrate(engine, sentences: list, out_wav: Path, gap: float = 0.38, lead: float = 0.6, tail: float = 1.6):
    """Synthesize every sentence, join them with short pauses and record each sentence's span."""
    parts = [np.zeros(int(lead * SR), np.float32)]
    t = lead
    for i, s in enumerate(sentences):
        audio = engine.say(s["text"])
        # trim leading/trailing near-silence so pauses stay even
        idx = np.where(np.abs(audio) > 0.01)[0]
        if len(idx):
            audio = audio[max(0, idx[0] - 600): idx[-1] + 1200]
        dur = len(audio) / SR
        s["start"], s["end"] = t, t + dur
        pause = gap * (2.2 if s["text"].rstrip().endswith(("?", "!")) or i % 6 == 5 else 1)
        parts += [audio, np.zeros(int(pause * SR), np.float32)]
        t += dur + pause
        print(f"  ses {i + 1}/{len(sentences)}  {dur:4.1f}s")
    parts.append(np.zeros(int(tail * SR), np.float32))
    full = np.concatenate(parts)
    peak = np.max(np.abs(full)) or 1
    sf.write(out_wav, full / peak * 0.89, SR)
    return len(full) / SR
