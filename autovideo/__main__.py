"""Tek komutla video:  python -m autovideo --tema godfather --konu "Apalachin toplantısı" --dakika 3"""
import argparse
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

from .ff import duration
from .footage import Library
from .montage import build, plan_shots
from .script import write_script
from .themes import get_theme
from .tts import make_engine, narrate

ROOT = Path(__file__).resolve().parent.parent
IMG = {".jpg", ".jpeg", ".png", ".webp"}
VID = {".mp4", ".mov", ".webm", ".mkv", ".ogv", ".avi"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:40].strip("-") or "video"


def main():
    ap = argparse.ArgumentParser(description="Konu yaz, video çıksın.")
    ap.add_argument("--tema", "--theme", required=True, help="godfather, sopranos, peaky blinders ya da herhangi bir şey")
    ap.add_argument("--konu", "--topic", help="anlatılacak konu")
    ap.add_argument("--dakika", "--minutes", type=float, default=3)
    ap.add_argument("--dil", "--lang", default="en", help="en (Kokoro sesi) ya da tr (edge-tts)")
    ap.add_argument("--ses-motoru", "--engine", choices=["kokoro", "edge", "piper"])
    ap.add_argument("--ses", "--voice", help="ör. am_onyx, bm_george, tr-TR-AhmetNeural, tr_TR-dfki-medium")
    ap.add_argument("--hiz", "--speed", type=float, default=0.92)
    ap.add_argument("--metin", "--script", help="DeepSeek yerine hazır script.json kullan")
    ap.add_argument("--muzik", "--music", help="müzik dosyası; 'yok' = müziksiz; boş = Commons'tan bul")
    ap.add_argument("--yerel", "--local", help="kendi klip/foto klasörün (bunlar önce kullanılır)")
    ap.add_argument("--sadece-yerel", action="store_true", help="internetten görüntü arama")
    ap.add_argument("--sadece-foto", action="store_true", help="video arama, sadece fotoğraf")
    ap.add_argument("--altyazisiz", action="store_true")
    ap.add_argument("--cikti", "--out", default=str(ROOT / "out"))
    ap.add_argument("--tohum", "--seed", type=int)
    a = ap.parse_args()

    if a.tohum is not None:
        random.seed(a.tohum)
    if not a.konu and not a.metin:
        ap.error("--konu ya da --metin gerekli")
    t0 = time.time()
    theme = get_theme(a.tema)
    work = Path(a.cikti) / f"{datetime.now():%Y%m%d-%H%M}-{slug(a.tema + ' ' + (a.konu or 'metin'))}"
    work.mkdir(parents=True, exist_ok=True)
    print(f"Çalışma klasörü: {work}")

    # 1) script
    if a.metin:
        script = json.loads(Path(a.metin).read_text(encoding="utf-8"))
    else:
        print("1/4 DeepSeek metni yazıyor...")
        script = write_script(theme, a.konu, a.dakika, a.dil)
    (work / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    sentences = script["sentences"]
    print(f"   '{script.get('title', '')}'  {len(sentences)} cümle")

    # 2) voice
    engine_name = a.ses_motoru or ("kokoro" if a.dil in ("en", "gb") else "piper" if a.ses and "_" in a.ses else "edge")
    voice = a.ses or theme["voice"].get(a.dil, "am_onyx")
    print(f"2/4 Seslendirme ({engine_name}, {voice})...")
    engine = make_engine(engine_name, voice, a.dil, a.hiz, ROOT / "models", work)
    narration = work / "narration.wav"
    total = narrate(engine, sentences, narration)
    print(f"   süre {total / 60:.1f} dk")

    # 3) footage
    print("3/4 Telifsiz görüntüler aranıyor...")
    lib = Library(ROOT / "cache", theme, prefer_video=not a.sadece_foto, offline=a.sadece_yerel)
    local = []
    if a.yerel:
        local = [p for p in sorted(Path(a.yerel).rglob("*")) if p.suffix.lower() in IMG | VID]
        random.shuffle(local)
    shots = plan_shots(sentences, total)
    for i, sh in enumerate(shots):
        need = sh["end"] - sh["start"] + 1.0
        if local:
            p = local[i % len(local)]
            sh["kind"] = "image" if p.suffix.lower() in IMG else "video"
            sh["src"] = p
            sh["offset"] = random.uniform(0, max(0.0, duration(p) - need)) if sh["kind"] == "video" else 0.0
            continue
        for attempt in range(3):
            asset = lib.pick(sh["query"])
            if not asset:
                break
            try:
                sh["src"], sh["offset"] = lib.source_for(asset, need)
                sh["kind"] = asset["kind"]
                break
            except Exception as e:
                print(f"   indirilemedi, başkası deneniyor: {e}")
        print(f"   {i + 1}/{len(shots)}  {sh.get('kind', 'boş'):5s}  {sh['query']}")

    music = None
    if a.muzik and a.muzik != "yok":
        music = Path(a.muzik)
    elif not a.muzik and not a.sadece_yerel:
        music = lib.music([script.get("music", "")] + theme["music_queries"])

    # 4) montage
    print("4/4 Montaj...")
    out = work / f"{slug(script.get('title') or a.konu or 'video')}.mp4"
    build(shots, theme, work, narration, total, music, out, subtitles=not a.altyazisiz, sentences=sentences)

    credits = "\n".join(sorted(lib.credits.values()))
    (work / "credits.txt").write_text(credits + "\n", encoding="utf-8")
    voice_credit = {"kokoro": "Voice: Kokoro-82M (Apache-2.0)", "edge": "Voice: Microsoft Edge neural TTS",
                    "piper": "Voice: Piper TTS"}[engine_name]
    (work / "description.txt").write_text(
        f"{script.get('title', '')}\n\n{script.get('description', '')}\n\n"
        f"Footage and music (public domain / Creative Commons):\n{credits}\n{voice_credit}\n", encoding="utf-8")
    print(f"\nHazır: {out}  ({(time.time() - t0) / 60:.1f} dk sürdü)")


if __name__ == "__main__":
    main()
