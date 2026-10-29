"""
Edited! - FFmpeg cutter: 9:16 framing, optional hook zoom, styled timed subtitles
(optional free local speech-to-text via faster-whisper), optional progress bar. No headline box.
"""
import os
import re
import json
import shutil
import subprocess
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_NAME = "font.ttf"


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def get_video_info(video_path: str) -> dict:
    if not shutil.which("ffprobe"):
        return {"duration": 60.0, "width": 1920, "height": 1080}
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(res.stdout)
        duration = float(data.get("format", {}).get("duration", 60.0))
        width, height = 1920, 1080
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                width = int(s.get("width", 1920))
                height = int(s.get("height", 1080))
                break
        return {"duration": duration, "width": width, "height": height}
    except Exception as e:
        print(f"[Cutter] Error getting video info: {e}")
        return {"duration": 60.0, "width": 1920, "height": 1080}


def _clean(text: str, limit: int = 250) -> str:
    return re.sub(r"[^\w\s!?.\-#&$']", "", text or "", flags=re.UNICODE).strip()[:limit]


STYLES = {
    "bold_yellow": dict(fontcolor="0xFFE600", fontsize=60, borderw=6, bordercolor="black", box=""),
    "clean_white": dict(fontcolor="white", fontsize=50, borderw=3, bordercolor="black@0.75", box=""),
    "dark_box": dict(fontcolor="white", fontsize=48, borderw=0, bordercolor="black", box=":box=1:boxcolor=black@0.7:boxborderw=16"),
    "neon_green": dict(fontcolor="0x39FF14", fontsize=58, borderw=5, bordercolor="black", box=""),
    "hot_pink": dict(fontcolor="0xFF3FA4", fontsize=58, borderw=5, bordercolor="white", box=""),
    "orange_box": dict(fontcolor="white", fontsize=52, borderw=0, bordercolor="black", box=":box=1:boxcolor=0xFF4D2E@0.95:boxborderw=18"),
}
SIZES = {"small": 0.8, "medium": 1.0, "large": 1.3}
POSITIONS = {"bottom": "h*0.74", "middle": "(h-text_h)/2", "top": "h*0.16"}


def transcribe_words(video_path: str, start: float, end: float) -> list:
    """Free local speech-to-text. Returns [(start, end, word)] relative to the clip, or [] if unavailable."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[Cutter] faster-whisper not installed; using the typed subtitle text instead.")
        return []
    tmp = os.path.join(BASE_DIR, f"_audio_{uuid.uuid4().hex[:8]}.wav")
    subprocess.run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-i", video_path, "-t", f"{end - start:.2f}",
                    "-vn", "-ac", "1", "-ar", "16000", tmp], capture_output=True)
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = model.transcribe(tmp, word_timestamps=True)
        return [(w.start, w.end, w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()]
    except Exception as e:
        print(f"[Cutter] Transcription failed: {e}")
        return []
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def subtitle_filters(text, duration, style="bold_yellow", font="", words=None, size="medium",
                     position="bottom", uppercase=True, per_chunk=3) -> list:
    if style == "none":
        return []
    n = max(1, int(per_chunk))
    timed = []
    if words:
        for i in range(0, len(words), n):
            g = words[i:i + n]
            timed.append((g[0][0], g[-1][1], " ".join(w[2] for w in g)))
    else:
        toks = (text or "").split()
        chunks = [" ".join(toks[i:i + n]) for i in range(0, len(toks), n)]
        if not chunks:
            return []
        step = min(2.5, max(0.6, duration / len(chunks)))
        timed = [(k * step, min(duration, (k + 1) * step), ch) for k, ch in enumerate(chunks) if k * step < duration]
    s = STYLES.get(style, STYLES["bold_yellow"])
    fs = int(s["fontsize"] * SIZES.get(size, 1.0))
    y = POSITIONS.get(position, POSITIONS["bottom"])
    out = []
    for t0, t1, ch in timed:
        ch = _clean(ch, 80)
        if uppercase:
            ch = ch.upper()
        esc = ch.replace("'", "").replace(":", r"\:").replace(",", r"\,")
        if not esc:
            continue
        out.append(f"drawtext=text='{esc}'{font}:expansion=none:fontcolor={s['fontcolor']}:fontsize={fs}:"
                   f"borderw={s['borderw']}:bordercolor={s['bordercolor']}{s['box']}:x=(w-text_w)/2:y={y}:"
                   f"enable='between(t,{t0:.2f},{max(t1, t0 + 0.3):.2f})'")
    return out


def cut_vertical_clip(input_path, output_path, start_time, end_time, crop_mode="crop_9_16",
                      caption_text="", subtitle_style="bold_yellow", enable_zoom=True,
                      enable_progress_bar=True, auto_subtitles=False, subtitle_size="medium",
                      subtitle_position="bottom", uppercase=True, words_per_chunk=3, **_ignored) -> bool:
    if not check_ffmpeg():
        raise RuntimeError("FFmpeg is not installed or not in system PATH.")
    start_time, end_time = float(start_time), float(end_time)
    duration = max(1.0, end_time - start_time)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    font = f":fontfile={FONT_NAME}" if os.path.exists(os.path.join(BASE_DIR, FONT_NAME)) else ""

    if crop_mode == "blur_pad":
        base = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
                "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    elif crop_mode == "raw":
        base = None
    else:
        base = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"

    filters = []
    if base:
        filters.append(base)
        if enable_zoom:
            filters.append("scale=eval=frame:w='if(lte(t,2.5),1242,1080)':h='if(lte(t,2.5),2208,1920)'")
            filters.append("crop=1080:1920:(iw-1080)/2:(ih-1920)/2")
    words = transcribe_words(os.path.abspath(input_path), start_time, start_time + duration) \
        if auto_subtitles and subtitle_style != "none" else []
    filters += subtitle_filters(_clean(caption_text), duration, subtitle_style, font, words,
                                subtitle_size, subtitle_position, uppercase, words_per_chunk)
    if base and enable_progress_bar:
        filters.append(f"drawbox=x=0:y=1906:w='1080*t/{duration:.2f}':h=14:color=0xFF4D2E:t=fill")

    cmd = ["ffmpeg", "-y", "-ss", f"{start_time:.2f}", "-i", os.path.abspath(input_path), "-t", f"{duration:.2f}"]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", os.path.abspath(output_path)]
    print(f"[Cutter] Rendering: zoom={enable_zoom} style={subtitle_style} synced={bool(words)}")
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
    if res.returncode != 0:
        print(f"[Cutter] FFmpeg Error: {res.stderr[-800:]}")
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0
