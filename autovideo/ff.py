"""ffmpeg helpers. Uses ffmpeg from PATH, or the one bundled with the imageio-ffmpeg pip package."""
import re
import shutil
import subprocess


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = ffmpeg_exe()


def ffmpeg(args, cwd=None, check=True):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"ffmpeg hata verdi:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r


def duration(path) -> float:
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def frame_brightness(src, t: float) -> float:
    """Mean luma (0-255) of one frame; used to skip black frames and title cards."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(src),
                        "-frames:v", "1", "-vf", "scale=64:36", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True, timeout=120)
    data = r.stdout
    return sum(data) / len(data) if data else 0.0
