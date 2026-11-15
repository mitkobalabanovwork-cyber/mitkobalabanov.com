#!/usr/bin/env python3
"""Create short muted preview loops for the videos in videos.json.

For every video without a loop, asks the Vimeo API for a small rendition of
the video, takes a few seconds from the middle and saves a small MP4 in
assets/loops/. To pick the moment yourself, add "loopAt": <second> to the
video in videos.json.

Needs ffmpeg and a Vimeo personal access token (scopes: public, private,
video_files) in the VIMEO_TOKEN environment variable. Failures are written
to loops-status.json and never stop the build.
"""
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOOPS = ROOT / "assets" / "loops"
VIDEOS_FILE = ROOT / "videos.json"
STATUS_FILE = ROOT / "loops-status.json"
TOKEN = os.environ.get("VIMEO_TOKEN", "").strip()
LENGTH = 5


def clean(text):
    """Last line of a message, without any (signed) URLs."""
    lines = [line for line in str(text).splitlines() if line.strip()]
    return re.sub(r"https?://\S+", "<url>", lines[-1] if lines else "unknown error")[:240]


def api(path):
    request = urllib.request.Request("https://api.vimeo.com" + path, headers={
        "Authorization": "bearer " + TOKEN,
        "Accept": "application/vnd.vimeo.*+json;version=3.4",
    })
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            body = json.load(error)
        except Exception:
            body = {}
        return error.code, body
    except Exception as error:
        return 0, {"error": str(error)}


def pick_source(data):
    """Smallest progressive rendition that is at least 360px tall, else HLS."""
    found = []
    for item in data.get("files") or []:
        if item.get("link") and item.get("quality") in ("sd", "hd", "mobile"):
            found.append((item.get("height") or 0, item["link"]))
    for item in (data.get("play") or {}).get("progressive") or []:
        if item.get("link"):
            found.append((item.get("height") or 0, item["link"]))
    for item in data.get("download") or []:
        if item.get("link") and item.get("quality") != "source":
            found.append((item.get("height") or 0, item["link"]))
    good = sorted(entry for entry in found if entry[0] >= 360)
    if good:
        return good[0][1]
    if found:
        return sorted(found, reverse=True)[0][1]
    for item in data.get("files") or []:
        if item.get("link") and item.get("quality") == "hls":
            return item["link"]
    hls = ((data.get("play") or {}).get("hls") or {}).get("link")
    return hls or None


def encode(link, start, target):
    try:
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(LENGTH), "-i", link,
            "-vf", "scale=640:-2:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-movflags", "+faststart", "-an", str(target),
        ], capture_output=True, text=True, timeout=600)
    except Exception as error:
        target.unlink(missing_ok=True)
        return "encode: " + clean(error)
    if result.returncode or not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        return "encode: " + clean(result.stderr or result.stdout)
    return ""


def make(video, start, target):
    code, data = api(f"/videos/{video['id']}?fields=duration,files,download,play")
    if code != 200:
        return None, f"api {code}: " + clean(data.get("developer_message") or data.get("error") or "no details")
    if start is None:
        start = max(0, int(data.get("duration") or 0) // 2 - LENGTH // 2)
    link = pick_source(data)
    if not link:
        keys = ",".join(key for key in ("files", "download", "play") if data.get(key)) or "none"
        return None, f"no video files in the API answer (fields present: {keys})"
    return start, encode(link, start, target)


def main():
    videos = json.loads(VIDEOS_FILE.read_text(encoding="utf-8"))
    LOOPS.mkdir(parents=True, exist_ok=True)
    status = {}
    todo = []
    for video in videos:
        if "loopAt" in video:
            start = max(0, int(video["loopAt"]))
            name = f"{video['id']}_{start}s.mp4"
        elif video.get("loop") and (LOOPS / video["loop"]).exists():
            continue
        else:
            start, name = None, f"{video['id']}.mp4"
        if video.get("loop") == name and (LOOPS / name).exists():
            continue
        todo.append((video, start, name))

    if todo and not TOKEN:
        status["_token"] = "VIMEO_TOKEN secret not found"
    elif todo:
        code, who = api("/oauth/verify?fields=scope,user.account")
        status["_token"] = {"status": code, "scope": who.get("scope"), "account": (who.get("user") or {}).get("account")}
        for video, start, name in todo:
            used, error = make(video, start, LOOPS / name)
            if error:
                status[video["id"]] = error
                print(f"FAILED {video['title']}: {error}")
            else:
                video["loop"] = name
                status[video["id"]] = f"ok, from {used}s"
                print(f"OK {video['title']}: {name} from {used}s")

    lines = ["  " + json.dumps(video, ensure_ascii=False) for video in videos]
    VIDEOS_FILE.write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")
    if status:
        STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    made = sum(1 for value in status.values() if isinstance(value, str) and value.startswith("ok"))
    print(f"{made} made, {len(todo) - made} not made")


if __name__ == "__main__":
    main()
