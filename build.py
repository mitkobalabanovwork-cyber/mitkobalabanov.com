#!/usr/bin/env python3
"""Build the static site into ./dist from videos.json and site.json.

Standard library only:  python3 build.py
"""
import datetime
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
VIDEOS = json.loads((ROOT / "videos.json").read_text(encoding="utf-8"))
YEAR = datetime.date.today().year
HAS_PORTRAIT = (ROOT / "assets" / "portrait.jpg").exists()
FONTS = "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@600;700;800;900&display=swap"


def E(value):
    return html.escape(str(value), quote=True)


def thumb(video, size="960x540"):
    return f"https://i.vimeocdn.com/video/{video['thumb']}-d_{size}?region=us"


def absolute(path=""):
    return SITE["url"].rstrip("/") + "/" + path


def default_image():
    return absolute("assets/portrait.jpg") if HAS_PORTRAIT else thumb(VIDEOS[0], "1920x1080")


def json_ld(data):
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def layout(*, depth, path, title, description, body, active="", image="", head="", main_class=""):
    root = "../" * depth or "./"

    def nav(label, href):
        current = ' aria-current="page"' if label == active else ""
        return f'<a href="{href}"{current}>{label}</a>'

    social = "\n".join(f'<a href="{E(href)}" rel="noopener">{E(label)}</a>' for label, href in SITE["social"].items())
    image = image or default_image()
    main_attr = f' class="{main_class}"' if main_class else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(description)}">
<meta name="author" content="{E(SITE['name'])}">
<link rel="canonical" href="{E(absolute(path))}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{E(SITE['name'])}, {E(SITE['role'])}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(description)}">
<meta property="og:url" content="{E(absolute(path))}">
<meta property="og:image" content="{E(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ff5a1f">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}assets/style.css">
{head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<a class="brand" href="{root}">
<span class="brand-name">{E(SITE['name'])}</span>
<span class="small">{E(SITE['tagline'])}</span>
</a>
<nav class="nav" aria-label="Main">
{nav('Work', root)}
{nav('About', root + 'about/')}
{nav('Contact', root + 'contact/')}
<a href="{E(SITE['social']['Instagram'])}" rel="noopener">Instagram</a>
</nav>
</header>
<main id="main"{main_attr}>
{body}
</main>
<footer class="site-footer">
<span>© {YEAR} {E(SITE['name'])}</span>
<div class="site-footer-links">
{social}
</div>
</footer>
<script src="{root}assets/site.js" defer></script>
</body>
</html>
"""


def tile(video, root, eager=False, extra_class=""):
    if video.get("loop"):
        media = (f'<video autoplay muted loop playsinline preload="metadata" poster="{E(thumb(video))}" aria-hidden="true">'
                 f'<source src="{root}assets/loops/{E(video["loop"])}" type="video/mp4"></video>')
    else:
        loading = "eager" if eager else "lazy"
        media = f'<img src="{E(thumb(video))}" alt="" width="960" height="540" loading="{loading}" decoding="async">'
    cls = "tile" + (" " + extra_class if extra_class else "")
    return (f'<a class="{cls}" href="{root}videos/{E(video["id"])}/">\n{media}\n'
            f'<span class="tile-label">{E(video["title"])}</span>\n</a>')


def hello(extra_class="", style=""):
    cls = "hello" + (" " + extra_class if extra_class else "")
    style_attr = f' style="{style}"' if style else ""
    return f"""<section class="{cls}" id="contact"{style_attr}>
<p class="small">{E(SITE['contactLabel'])}</p>
<div class="hello-row">
<h2 class="giant">Say hello,</h2>
<div class="hello-contact">
<a class="hello-mail u" href="mailto:{E(SITE['email'])}">{E(SITE['email'])}</a>
<a class="link" href="tel:{E(SITE['phone'].replace(' ', ''))}">{E(SITE['phone'])} · {E(SITE['city'])}</a>
</div>
</div>
</section>"""


def write(path, text):
    target = DIST / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_home():
    count = len(VIDEOS)

    def span(cols):
        rest = (cols - count % cols) % cols
        return rest if rest >= 2 else cols

    tiles = "\n".join(
        tile(v, "./", eager=i < 8, extra_class="tile--wide2" if i == count - 1 and count % 2 else "")
        for i, v in enumerate(VIDEOS)
    )
    body = f"""<h1 class="sr-only">{E(SITE['name'])}, {E(SITE['role'])} — selected work</h1>
<div class="wall">
{tiles}
{hello('hello--tile', f'--s4: {span(4)}; --s3: {span(3)}')}
</div>"""
    person = {
        "@context": "https://schema.org", "@type": "Person", "name": SITE["name"], "jobTitle": SITE["role"],
        "description": SITE["description"], "url": SITE["url"], "email": SITE["email"],
        "sameAs": list(SITE["social"].values()),
    }
    write("index.html", layout(
        depth=0, path="", active="Work", body=body, head=json_ld(person),
        title=f"{SITE['name']}, {SITE['role']} (Sofia, Bulgaria)", description=SITE["description"],
    ))


def build_videos():
    count = len(VIDEOS)
    for index, video in enumerate(VIDEOS):
        root = "../../"
        pairs = "".join(f"<div><dt>{E(role)}</dt><dd>{E(name)}</dd></div>\n" for role, name in video["credits"] if role)
        notes = "".join(f"<p>{E(text)}</p>\n" for role, text in video["credits"] if not role)
        notes = f'<div class="credit-notes">\n{notes}</div>' if notes else ""
        more = "\n".join(tile(VIDEOS[(index + k) % count], root) for k in range(1, 5))
        embed = f"https://player.vimeo.com/video/{video['id']}?h={video['hash']}&title=0&byline=0&portrait=0"
        body = f"""<div class="player" style="--ar: {video['width']} / {video['height']}">
<iframe src="{E(embed)}" title="{E(video['title'])}" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>
</div>
<section class="video-info">
<h1 class="giant video-title">{E(video['title'])}</h1>
<div class="video-credits">
<dl class="credits">
<div><dt>Year</dt><dd>{E(video['year'])}</dd></div>
{pairs}</dl>
{notes}
</div>
</section>
<section class="more">
<div class="more-head">
<h2 class="small">More work</h2>
<a class="link u" href="{root}">All work</a>
</div>
<div class="wall">
{more}
</div>
</section>"""
        description = f"Watch {video['title']}, edited by {SITE['name']}."
        data = {
            "@context": "https://schema.org", "@type": "VideoObject", "name": video["title"], "description": description,
            "thumbnailUrl": thumb(video, "1920x1080"), "embedUrl": embed.split("&")[0],
        }
        if video.get("uploaded"):
            data["uploadDate"] = video["uploaded"]
        if video.get("duration"):
            data["duration"] = video["duration"]
        write(f"videos/{video['id']}/index.html", layout(
            depth=2, path=f"videos/{video['id']}/", active="Work", body=body, head=json_ld(data),
            title=f"{video['title']} — edited by {SITE['name']}", description=description,
            image=thumb(video, "1920x1080"),
        ))


def build_about():
    def credit_list(label, items):
        rows = []
        for title, meta, notes in items:
            lines = "".join(f"\n<span class=\"film-note\">{E(note)}</span>" for note in notes)
            rows.append(f'<li>\n<div class="film-row"><span class="film-title">{E(title)}</span>'
                        f'<span class="small">{E(meta)}</span></div>{lines}\n</li>')
        return f'<div class="film-col">\n<h3 class="small">{E(label)}</h3>\n<ul class="film-list">\n' + "\n".join(rows) + "\n</ul>\n</div>"

    bio = "\n".join(f"<span>{E(line)}</span>" for line in SITE["bio"])
    portrait = ('<img class="portrait" src="../assets/portrait.jpg" alt="Portrait of ' + E(SITE["name"]) + '" loading="lazy">'
                if HAS_PORTRAIT else "")
    lists = "\n".join(credit_list(label, items) for label, items in SITE["filmography"].items())
    body = f"""<section class="about-intro">
<div class="about-text">
<p class="small">{E(SITE['role'])}</p>
<h1 class="about-bio">
{bio}
</h1>
</div>
{portrait}
</section>
<section class="filmography">
<h2 class="giant">Selected filmography</h2>
<div class="film-cols">
{lists}
</div>
</section>
{hello()}"""
    write("about/index.html", layout(
        depth=1, path="about/", active="About", body=body,
        title=f"About — {SITE['name']}, {SITE['role']} in Sofia",
        description=f"About {SITE['name']}, {SITE['role'].lower()} based in Sofia, Bulgaria — selected filmography.",
    ))


def build_contact():
    body = f"""<p class="small">Get in touch</p>
<div class="contact-main">
<h1 class="giant">Say hello,</h1>
<a class="contact-mail" href="mailto:{E(SITE['email'])}">{E(SITE['email'])}</a>
</div>
<div class="contact-details">
<a class="link contact-phone" href="tel:{E(SITE['phone'].replace(' ', ''))}">{E(SITE['phone'])}</a>
<span class="link">{E(SITE['location'])}</span>
<span>{E(SITE['contactNote'])}</span>
</div>"""
    write("contact/index.html", layout(
        depth=1, path="contact/", active="Contact", body=body, main_class="contact-page",
        title=f"Contact — {SITE['name']}, {SITE['role']}", description=f"Contact {SITE['name']}. {SITE['contactNote']}",
    ))


def build_extras():
    write("404.html", f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found — {E(SITE['name'])}</title>
<meta name="robots" content="noindex">
<style>
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;justify-content:center;gap:24px;padding:24px;background:#ff5a1f;color:#0b0b0a;font-family:'Helvetica Neue',Arial,sans-serif}}
h1{{margin:0;font-size:clamp(64px,15vw,232px);font-weight:900;line-height:.84;letter-spacing:-.045em;text-transform:uppercase}}
a{{color:inherit;font-size:20px;font-weight:800;text-underline-offset:4px}}
</style>
</head>
<body>
<h1>Cut.</h1>
<a href="/">This page does not exist — back to all work</a>
</body>
</html>
""")
    pages = ["", "about/", "contact/"] + [f"videos/{v['id']}/" for v in VIDEOS]
    urls = "\n".join(f"<url><loc>{E(absolute(p))}</loc></url>" for p in pages)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {absolute('sitemap.xml')}\n")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "assets", DIST / "assets")
    build_home()
    build_videos()
    build_about()
    build_contact()
    build_extras()
    print(f"Built {len(VIDEOS)} video pages into {DIST}")


if __name__ == "__main__":
    main()
