#!/usr/bin/env python3
"""Add new public Vimeo videos to videos.json.

Looks at the videos in the Vimeo account behind VIMEO_TOKEN. Every video that
is public ("Anyone can see this video"), can be embedded and is not in
videos.json yet is added at the top of the list. Videos already in the list
are never changed or removed, so manual edits (titles, credits, order, loops)
are safe.

A short summary is written to sync-status.json. Problems never stop the build.
"""
import datetime
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIDEOS_FILE = ROOT / "videos.json"
STATUS_FILE = ROOT / "sync-status.json"
TOKEN = os.environ.get("VIMEO_TOKEN", "").strip()
FIELDS = ("uri,name,description,link,player_embed_url,duration,width,height,created_time,release_time,"
          "privacy.view,privacy.embed,pictures.base_link")


def api(path):
    url = path if path.startswith("http") else "https://api.vimeo.com" + path
    request = urllib.request.Request(url, headers={
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


def account_videos():
    path = f"/me/videos?per_page=100&sort=date&direction=desc&fields={FIELDS}"
    videos = []
    for _ in range(50):
        code, data = api(path)
        if code != 200:
            message = str(data.get("developer_message") or data.get("error") or "no details")[:200]
            return None, f"api {code}: {message}"
        videos += data.get("data") or []
        path = (data.get("paging") or {}).get("next")
        if not path:
            break
    return videos, ""


def credits(description, title):
    """Turn "Role: Name" style lines of a Vimeo description into [role, name] pairs."""
    description = (description or "").strip()
    if not description or description == title.strip():
        return []
    pairs = []
    for line in description.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(" / ")] if line.count(":") > 1 else [line]
        for part in parts:
            match = (re.match(r"^([^:]{2,30}):\s*(.+)$", part) or re.match(r"^(\S[^.]{1,12})\.\s+(.+)$", part)
                     or re.match(r"^(.{2,20}?)___(.+)$", part) or re.match(r"^(.{2,20}?)\s+-\s+(.+)$", part))
            pairs.append([match.group(1).strip(), match.group(2).strip()] if match else ["", part])
    return pairs


def iso_duration(total):
    total = int(total or 0)
    hours, minutes, secs = total // 3600, total // 60 % 60, total % 60
    return "PT" + (f"{hours}H" if hours else "") + (f"{minutes}M" if minutes else "") + (f"{secs}S" if secs or not total else "")


def entry(video):
    """videos.json entry for a Vimeo API video, or None if something essential is missing."""
    found = re.search(r"/videos/(\d+)", video.get("uri") or "")
    thumb = re.search(r"/video/([^_?/]+)", ((video.get("pictures") or {}).get("base_link") or ""))
    if not found or not thumb:
        return None
    video_id = found.group(1)
    thumb_key = thumb.group(1)[:-2] if thumb.group(1).endswith("-d") else thumb.group(1)
    hash_match = (re.search(r"[?&]h=([0-9a-f]+)", video.get("player_embed_url") or "")
                  or re.search(rf"vimeo\.com/{video_id}/([0-9a-f]+)", video.get("link") or ""))
    created = video.get("release_time") or video.get("created_time") or ""
    title = (video.get("name") or "").strip() or video_id
    return {
        "id": video_id,
        "hash": hash_match.group(1) if hash_match else "",
        "title": title,
        "year": int(created[:4]) if created[:4].isdigit() else datetime.date.today().year,
        "thumb": thumb_key,
        "width": int(video.get("width") or 1920),
        "height": int(video.get("height") or 1080),
        "uploaded": created,
        "duration": iso_duration(video.get("duration")),
        "credits": credits(video.get("description"), title),
    }


def main():
    videos = json.loads(VIDEOS_FILE.read_text(encoding="utf-8"))
    known = {video["id"] for video in videos}
    status = {}
    added = []
    if not TOKEN:
        status["error"] = "VIMEO_TOKEN secret not found"
    else:
        account, error = account_videos()
        if account is None:
            status["error"] = error
        else:
            by_privacy = {}
            in_account = set()
            for video in account:
                view = (video.get("privacy") or {}).get("view") or "unknown"
                by_privacy[view] = by_privacy.get(view, 0) + 1
                found = re.search(r"/videos/(\d+)", video.get("uri") or "")
                if found:
                    in_account.add(found.group(1))
                if view != "anybody" or (video.get("privacy") or {}).get("embed") == "private":
                    continue
                item = entry(video)
                if item and item["id"] not in known:
                    added.append(item)
                    known.add(item["id"])
            status["videos_in_account"] = len(account)
            status["by_privacy"] = dict(sorted(by_privacy.items()))
            status["on_site_and_in_account"] = len({video["id"] for video in videos} & in_account)
            status["on_site_but_not_in_account"] = sorted({video["id"] for video in videos} - in_account)
            status["last_added"] = [f"{item['id']} {item['title']}" for item in added]

    if added:
        videos = added + videos
        lines = ["  " + json.dumps(video, ensure_ascii=False) for video in videos]
        VIDEOS_FILE.write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")
    if not added and STATUS_FILE.exists():
        try:
            status["last_added"] = json.loads(STATUS_FILE.read_text(encoding="utf-8")).get("last_added", [])
        except Exception:
            pass
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"changed={'true' if added else 'false'}\n")
    print(f"{len(added)} new video(s) added" + (f"; problem: {status['error']}" if "error" in status else ""))


if __name__ == "__main__":
    main()
