#!/usr/bin/env python3
"""Turn "loopUrl" entries in videos.json into small preview loops.

For a video with "loopUrl" (for example a Vimeo animated thumbnail GIF),
downloads the file, converts it to a small muted MP4 in assets/loops/,
sets "loop" to that file and removes "loopUrl". Needs ffmpeg.
Problems are printed and never stop the build.
"""
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOOPS = ROOT / "assets" / "loops"
VIDEOS_FILE = ROOT / "videos.json"


def convert(url, target):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site build)"})
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source"
        with urllib.request.urlopen(request, timeout=120) as response, open(source, "wb") as handle:
            handle.write(response.read())
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(source),
            "-vf", "scale='trunc(min(960,iw)/2)*2':-2:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-movflags", "+faststart", "-an", str(target),
        ], capture_output=True, text=True, timeout=600)
        if result.returncode or not target.exists() or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            raise RuntimeError((result.stderr or "ffmpeg failed").strip().splitlines()[-1][:200])


def main():
    videos = json.loads(VIDEOS_FILE.read_text(encoding="utf-8"))
    LOOPS.mkdir(parents=True, exist_ok=True)
    changed = False
    for video in videos:
        url = video.get("loopUrl")
        if not url:
            continue
        name = f"{video['id']}.mp4"
        try:
            convert(url, LOOPS / name)
        except Exception as error:
            print(f"FAILED {video['title']}: {error}")
            continue
        old = video.get("loop")
        if old and old != name:
            (LOOPS / old).unlink(missing_ok=True)
        video["loop"] = name
        del video["loopUrl"]
        changed = True
        print(f"OK {video['title']}: {name} ({(LOOPS / name).stat().st_size // 1024} KB)")
    if changed:
        lines = ["  " + json.dumps(video, ensure_ascii=False) for video in videos]
        VIDEOS_FILE.write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
