"""Cut the shots to the narration, add transitions, colour grade, subtitles and ducked music."""
import math
import random
from pathlib import Path

from .ff import ffmpeg

W, H, FPS = 1920, 1080, 30
MAX_SHOT = 6.5
BATCH = 24
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


def plan_shots(sentences, total: float):
    """Split the timeline into shots: each sentence gets 1+ shots, never longer than MAX_SHOT."""
    shots = []
    for i, s in enumerate(sentences):
        start = 0.0 if i == 0 else s["start"] - 0.15
        end = total if i == len(sentences) - 1 else sentences[i + 1]["start"] - 0.15
        n = max(1, math.ceil((end - start) / MAX_SHOT))
        step = (end - start) / n
        for k in range(n):
            shots.append({"start": start + k * step, "end": start + (k + 1) * step,
                          "query": s.get("visual", ""), "sentence": i})
    return shots


def _kenburns(dur: float) -> str:
    frames = max(1, round(dur * FPS))
    mode = random.choice(["in", "out", "left", "right"])
    z = {"in": f"1+0.13*on/{frames}", "out": f"1.13-0.13*on/{frames}"}.get(mode, "1.1")
    if mode == "left":
        x = f"(iw-iw/zoom)*(1-on/{frames})"
    elif mode == "right":
        x = f"(iw-iw/zoom)*on/{frames}"
    else:
        x = "(iw-iw/zoom)/2"
    return (f"zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)/2':d=1:s={W}x{H}:fps={FPS}")


def render_shot(shot, out: Path, grade: str):
    dur = shot["len"]
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}"
    if shot.get("kind") == "image":
        big = out.with_suffix(".still.jpg")   # scale once, not per frame
        ffmpeg(["-i", str(shot["src"]), "-vf", f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
                f"crop={W * 2}:{H * 2}", "-q:v", "2", "-frames:v", "1", str(big)])
        inp = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(big)]
        vf = _kenburns(dur)
    elif shot.get("kind") in ("video", "film"):
        loop = [] if str(shot["src"]).startswith("http") else ["-stream_loop", "-1"]
        inp = [*loop, "-ss", f"{shot['offset']:.2f}", "-i", str(shot["src"]), "-t", f"{dur:.3f}"]
        vf = cover
    else:   # nothing found: dark moving texture so the video never breaks
        inp = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"color=c=0x15120f:s={W}x{H}:r={FPS}"]
        vf = "noise=alls=25:allf=t,gblur=sigma=6"
    vf += f",{grade},setsar=1,format=yuv420p"
    ffmpeg([*inp, "-vf", vf, "-frames:v", str(max(1, round(dur * FPS))), "-an", *ENC, "-r", str(FPS), str(out)])


def _xfade_batch(files, shots, out: Path):
    if len(files) == 1:
        ffmpeg(["-i", str(files[0]), "-c", "copy", str(out)])
        return
    inputs = []
    for f in files:
        inputs += ["-i", str(f)]
    parts, prev, acc = [], "[0:v]", 0.0
    for k in range(1, len(files)):
        acc += shots[k - 1]["own"]
        lab = f"[x{k}]"
        sh = shots[k - 1]
        parts.append(f"{prev}[{k}:v]xfade=transition={sh['trans']}:duration={sh['td']:.3f}:offset={acc:.3f}{lab}")
        prev = lab
    ffmpeg([*inputs, "-filter_complex", ";".join(parts), "-map", prev, *ENC, str(out)])


def ass_time(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(sentences, path: Path, font: str, words_per_line: int = 7):
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Sub,{font},62,&H00F2F2F2,&H00FFFFFF,&H00000000,&H7F000000,-1,0,0,0,100,100,0.5,0,1,3.2,1.5,2,"
        "140,140,95,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for s in sentences:
        words = s["text"].split()
        n = max(1, math.ceil(len(words) / words_per_line))
        size = math.ceil(len(words) / n)
        chunks = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
        total_chars = sum(len(c) for c in chunks) or 1
        t = s["start"]
        span = s["end"] - s["start"]
        for c in chunks:
            d = span * len(c) / total_chars
            text = c.replace("{", "(").replace("}", ")")
            lines.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + d)},Sub,,0,0,0,,{text}")
            t += d
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(shots, theme, work: Path, narration: Path, total: float, music: Path | None,
          out: Path, subtitles: bool = True, sentences=None):
    seg_dir = work / "segments"
    seg_dir.mkdir(exist_ok=True)
    # transition plan: td = overlap with the next shot (0 for a hard cut and for batch ends)
    for i, sh in enumerate(shots):
        sh["own"] = sh["end"] - sh["start"]
        last_in_batch = (i % BATCH == BATCH - 1) or i == len(shots) - 1
        cut = random.random() < theme["hard_cut_ratio"]
        sh["trans"] = random.choice(theme["transitions"])
        sh["td"] = 0.0 if last_in_batch else (1 / FPS if cut else (0.9 if sh["trans"] == "fadeblack" else 0.6))
        if sh["td"] and sh["td"] < 0.1:
            sh["trans"] = "fade"
        sh["len"] = sh["own"] + sh["td"]

    files = []
    for i, sh in enumerate(shots):
        f = seg_dir / f"s{i:04d}.mp4"
        render_shot(sh, f, theme["grade"])
        files.append(f)
        print(f"  sahne {i + 1}/{len(shots)}  {sh.get('kind', 'boş'):5s} {sh['own']:.1f}s  {sh['query'][:40]}")

    batch_files = []
    for b in range(0, len(files), BATCH):
        bf = work / f"batch{b // BATCH:03d}.mp4"
        _xfade_batch(files[b:b + BATCH], shots[b:b + BATCH], bf)
        batch_files.append(bf)
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{p.name}'\n" for p in batch_files), encoding="utf-8")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", concat.name, "-c", "copy", "video_only.mp4"], cwd=work)

    vf = "null"
    if subtitles and sentences:
        write_ass(sentences, work / "subs.ass", theme.get("subtitle_font", "Georgia"))
        vf = "ass=subs.ass"
    vf += f",fade=t=in:st=0:d=0.8,fade=t=out:st={max(0, total - 1.2):.2f}:d=1.2"

    inputs = ["-i", "video_only.mp4", "-i", str(narration.resolve())]
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]
        af = (f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{total:.2f},volume=0.28,"
              f"afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
              f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[v][sc];"
              f"[m][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[duck];"
              f"[v][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-15:TP=-1.5[a]")
    else:
        af = "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-15:TP=-1.5[a]"
    ffmpeg([*inputs, "-filter_complex", f"[0:v]{vf}[vout];{af}", "-map", "[vout]", "-map", "[a]",
            *ENC, "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart",
            str(out.resolve())], cwd=work)
