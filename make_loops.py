#!/usr/bin/env python3
"""Create short muted preview loops for the videos in videos.json.

For every video without a loop, takes a few seconds from the middle of the
video on Vimeo and saves a small MP4 in assets/loops/. To pick the moment
yourself, add "loopAt": <second> to the video in videos.json.

Needs yt-dlp and ffmpeg. Failures are reported, never fatal.
"""
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOOPS = ROOT / "assets" / "loops"
VIDEOS_FILE = ROOT / "videos.json"
STATUS_FILE = ROOT / "loops-status.json"
LENGTH = 5


def seconds(iso):
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not match:
        return 0
    hours, minutes, secs = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + secs


def run(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    except Exception as error:  # timeout, missing tool
        return 1, str(error)
    return result.returncode, (result.stderr or result.stdout or "").strip()


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else "unknown error")[:300]


def make(video, start, target):
    url = f"https://player.vimeo.com/video/{video['id']}?h={video['hash']}"
    with tempfile.TemporaryDirectory() as tmp:
        code, output = run([
            "yt-dlp", "--no-playlist", "--no-warnings", "--referer", "https://mitkobalabanov.com/",
            "-f", "bv*[height<=540]/bv*[height<=720]/b[height<=720]/bv*/b",
            "--download-sections", f"*{start}-{start + LENGTH + 1}",
            "-o", str(Path(tmp) / "clip.%(ext)s"), url,
        ])
        clips = [path for path in Path(tmp).glob("clip.*") if path.stat().st_size > 0]
        if code or not clips:
            return "download: " + last_line(output)
        code, output = run([
            "ffmpeg", "-v", "error", "-y", "-i", str(clips[0]), "-t", str(LENGTH),
            "-vf", "scale=640:-2:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-movflags", "+faststart", "-an", str(target),
        ])
        if code or not target.exists() or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            return "encode: " + last_line(output)
    return ""


def main():
    videos = json.loads(VIDEOS_FILE.read_text(encoding="utf-8"))
    LOOPS.mkdir(parents=True, exist_ok=True)
    status = {}
    for video in videos:
        duration = seconds(video.get("duration"))
        if "loopAt" in video:
            start = max(0, int(video["loopAt"]))
            name = f"{video['id']}_{start}s.mp4"
        elif video.get("loop") and (LOOPS / video["loop"]).exists():
            continue
        else:
            start = max(0, duration // 2 - LENGTH // 2)
            name = f"{video['id']}.mp4"
        if video.get("loop") == name and (LOOPS / name).exists():
            continue
        error = make(video, start, LOOPS / name)
        if error:
            status[video["id"]] = error
            print(f"FAILED {video['title']}: {error}")
        else:
            video["loop"] = name
            status[video["id"]] = f"ok, from {start}s"
            print(f"OK {video['title']}: {name} from {start}s")
    lines = ["  " + json.dumps(video, ensure_ascii=False) for video in videos]
    VIDEOS_FILE.write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")
    if status:
        STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(1 for v in status.values() if v.startswith('ok'))} made, "
          f"{sum(1 for v in status.values() if not v.startswith('ok'))} failed")


if __name__ == "__main__":
    main()
