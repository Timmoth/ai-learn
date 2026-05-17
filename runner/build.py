from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

from . import manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_DIR = Path(__file__).resolve().parent
LESSONS_DIR = REPO_ROOT / "lessons"
DIST_DIR = REPO_ROOT / "dist"
STATIC_DIR = REPO_ROOT / "static"
TEMPLATES_DIR = RUNNER_DIR / "templates"
LESSONS_PATH = REPO_ROOT / "lessons.json"
CONFIG_PATH = RUNNER_DIR / "config.json"
TAILWIND_INPUT = RUNNER_DIR / "styles.css"

PODCAST_EPISODE_AUTHOR = "Tim Jones / Claude / Kokoro"
RELATED_LIMIT = 3
WORDS_PER_MINUTE = 200

LESSON_CARD = """<a href="{{root_rel}}lessons/{{slug}}/" class="block p-5 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600 transition">
        <h2 class="text-base font-medium mb-1">{{title}}</h2>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">{{description}}</p>
        <p class="text-xs text-gray-500 dark:text-gray-500 mb-3">{{card_meta}}</p>
        <div class="flex flex-wrap gap-1.5">{{tag_chips}}</div>
      </a>"""

TAG_CHIP_LINK = '<a href="{{root_rel}}tags/{{slug}}/" class="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition">{{tag}}</a>'

TAG_CHIP_SPAN = '<span class="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">{{tag}}</span>'

AUDIO_SECTION = """<div class="mb-10 p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
      <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-500 mb-2">Listen</p>
      <audio controls preload="metadata" class="w-full">
        <source src="audio.mp3" type="audio/mpeg">
        Your browser does not support audio playback.
      </audio>
    </div>"""

RELATED_SECTION = """<section class="mt-16 pt-8 border-t border-gray-200 dark:border-gray-800">
      <h2 class="text-sm uppercase tracking-wide text-gray-500 dark:text-gray-500 mb-4">Related lessons</h2>
      <div class="space-y-3">{{related_cards}}</div>
    </section>"""


def _highlight_css() -> str:
    light = HtmlFormatter(style="default").get_style_defs(".highlight")
    dark = HtmlFormatter(style="monokai").get_style_defs(".dark .highlight")
    overrides = """
.highlight {
  background-color: #f6f8fa;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  overflow-x: auto;
  font-size: 0.875rem;
  line-height: 1.55;
  margin: 1.25rem 0;
}
.dark .highlight {
  background-color: #0d1117;
  border-color: #30363d;
}
.highlight pre {
  background-color: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  margin: 0 !important;
  border: 0 !important;
}
.highlight code {
  background-color: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  font-size: inherit !important;
}
.highlight code::before, .highlight code::after { content: none !important; }
"""
    return f"{light}\n{dark}\n{overrides}"


HIGHLIGHT_CSS = _highlight_css()


def render(template: str, vars: dict) -> str:
    for key, value in vars.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def load_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text()


def slugify_tag(tag: str) -> str:
    s = tag.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def tag_chips(tags: list[str], root_rel: str = "", linked: bool = True) -> str:
    template = TAG_CHIP_LINK if linked else TAG_CHIP_SPAN
    return "".join(
        render(template, {
            "root_rel": root_rel,
            "slug": slugify_tag(t),
            "tag": html.escape(t),
        })
        for t in tags
    )


def lesson_has_material(slug: str) -> bool:
    return (LESSONS_DIR / slug / "lesson.md").exists()


def github_profile_url(repo_url: str) -> str | None:
    m = re.match(r"https?://github\.com/([^/]+)", repo_url)
    return f"https://github.com/{m.group(1)}" if m else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def format_date_human(dt: datetime | None) -> str:
    if not dt:
        return ""
    return f"{dt.day} {dt.strftime('%b %Y')}"


def read_time_minutes(text: str) -> int:
    words = len(re.findall(r"\b\w[\w'-]*\b", text))
    return max(1, round(words / WORDS_PER_MINUTE))


def audio_duration_seconds(path: Path) -> int | None:
    try:
        from mutagen.mp3 import MP3
        return int(round(MP3(str(path)).info.length))
    except Exception:
        return None


def format_hms(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def listen_minutes(seconds: int) -> int:
    return max(1, round(seconds / 60))


def card_meta(lesson: dict) -> str:
    parts = []
    updated = parse_iso(lesson.get("updated_at"))
    if updated:
        iso_date = updated.date().isoformat()
        parts.append(f'<time datetime="{iso_date}">{html.escape(format_date_human(updated))}</time>')
    rt = lesson.get("_read_time_minutes")
    if rt:
        parts.append(f"{rt} min read")
    dur = lesson.get("_audio_duration_seconds")
    if dur:
        parts.append(f"{listen_minutes(dur)} min listen")
    return " · ".join(parts)


def lesson_meta_line(lesson: dict) -> str:
    parts = []
    created = parse_iso(lesson.get("created_at"))
    updated = parse_iso(lesson.get("updated_at"))
    if created:
        parts.append(
            f'Published <time datetime="{created.date().isoformat()}">{html.escape(format_date_human(created))}</time>'
        )
    if updated and (not created or updated.date() != created.date()):
        parts.append(
            f'Updated <time datetime="{updated.date().isoformat()}">{html.escape(format_date_human(updated))}</time>'
        )
    rt = lesson.get("_read_time_minutes")
    if rt:
        parts.append(f"{rt} min read")
    dur = lesson.get("_audio_duration_seconds")
    if dur:
        parts.append(f"{listen_minutes(dur)} min listen")
    return " · ".join(parts)


def lesson_byline(site: dict) -> str:
    author = html.escape(site["author"])
    author_url = html.escape(site["author_url"])
    return (
        f'Requested by <a href="{author_url}" rel="author" class="underline-offset-2 hover:underline">{author}</a>, '
        'written by <span class="text-gray-700 dark:text-gray-300">Claude</span>, '
        'narrated by <span class="text-gray-700 dark:text-gray-300">Kokoro</span>'
    )


def footer_html(site: dict) -> str:
    author = html.escape(site["author"])
    author_url = html.escape(site["author_url"])
    github_url = html.escape(site["github_url"])
    return (
        '<footer class="border-t border-gray-200 dark:border-gray-800 mt-20">\n'
        '    <div class="max-w-3xl mx-auto px-6 py-6 text-sm text-gray-600 dark:text-gray-500">\n'
        f'      Architected by <a href="{author_url}" rel="me author" class="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 underline-offset-2 hover:underline">{author}</a>, Built by AI — '
        f'<a href="{github_url}" rel="external" class="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 underline-offset-2 hover:underline">GitHub</a>\n'
        '    </div>\n'
        '  </footer>'
    )


def person_same_as(site: dict) -> list[str]:
    same = list(site.get("same_as") or [])
    profile = github_profile_url(site["github_url"])
    if profile and profile not in same:
        same.append(profile)
    return same


def person_node(site: dict, with_id: bool = True) -> dict:
    node: dict = {
        "@type": "Person",
        "name": site["author"],
        "url": site["author_url"],
    }
    if with_id:
        node["@id"] = f"{site['author_url'].rstrip('/')}/#person"
    same = person_same_as(site)
    if same:
        node["sameAs"] = same
    return node


def home_website_json_ld(site: dict) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{site['url'].rstrip('/')}/#website",
        "name": site["title"],
        "url": site["url"],
        "description": site["description"],
        "inLanguage": "en",
        "author": {"@id": f"{site['author_url'].rstrip('/')}/#person"},
    }
    return f'<script type="application/ld+json">{json.dumps(data, separators=(",", ":"))}</script>'


def home_person_json_ld(site: dict) -> str:
    data = {"@context": "https://schema.org", **person_node(site)}
    return f'<script type="application/ld+json">{json.dumps(data, separators=(",", ":"))}</script>'


def lesson_json_ld(lesson: dict, site: dict, audio_url: str | None) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "LearningResource",
        "name": lesson["title"],
        "headline": lesson["title"],
        "description": lesson.get("description", ""),
        "url": f"{site['url']}/lessons/{lesson['slug']}/",
        "inLanguage": "en",
        "keywords": ", ".join(lesson.get("tags", [])),
        "datePublished": (lesson.get("created_at") or "")[:10],
        "dateModified": (lesson.get("updated_at") or "")[:10],
        "author": person_node(site),
        "publisher": person_node(site, with_id=False),
    }
    if audio_url:
        audio = {
            "@type": "AudioObject",
            "contentUrl": audio_url,
            "encodingFormat": "audio/mpeg",
        }
        dur = lesson.get("_audio_duration_seconds")
        if dur:
            audio["duration"] = f"PT{dur}S"
        data["audio"] = audio
    return f'<script type="application/ld+json">{json.dumps(data, separators=(",", ":"))}</script>'


def render_card(lesson: dict, root_rel: str = "") -> str:
    return render(LESSON_CARD, {
        "root_rel": root_rel,
        "slug": lesson["slug"],
        "title": html.escape(lesson["title"]),
        "description": html.escape(lesson.get("description", "")),
        "card_meta": card_meta(lesson),
        "tag_chips": tag_chips(lesson.get("tags", []), root_rel, linked=False),
    })


def render_cards(lessons: list[dict], root_rel: str = "") -> str:
    if not lessons:
        return '<p class="text-gray-600 dark:text-gray-400">No lessons published yet.</p>'
    return "\n      ".join(render_card(l, root_rel) for l in lessons)


def related_lessons(lesson: dict, all_lessons: list[dict]) -> list[dict]:
    own_tags = set(lesson.get("tags", []))
    if not own_tags:
        return []
    scored: list[tuple[int, datetime, dict]] = []
    for other in all_lessons:
        if other["slug"] == lesson["slug"]:
            continue
        overlap = len(own_tags & set(other.get("tags", [])))
        if overlap == 0:
            continue
        updated = parse_iso(other.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        scored.append((overlap, updated, other))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [t[2] for t in scored[:RELATED_LIMIT]]


def related_section_html(lesson: dict, all_lessons: list[dict], root_rel: str) -> str:
    related = related_lessons(lesson, all_lessons)
    if not related:
        return ""
    return render(RELATED_SECTION, {
        "related_cards": "\n        ".join(render_card(l, root_rel) for l in related),
    })


def annotate_lesson(lesson: dict) -> None:
    slug = lesson["slug"]
    src_dir = LESSONS_DIR / slug
    lesson_md = src_dir / "lesson.md"
    if lesson_md.exists():
        lesson["_read_time_minutes"] = read_time_minutes(lesson_md.read_text())
    audio_path = src_dir / "audio.mp3"
    if audio_path.exists():
        dur = audio_duration_seconds(audio_path)
        if dur:
            lesson["_audio_duration_seconds"] = dur
        lesson["_has_audio"] = True


def build_lesson_page(lesson: dict, all_lessons: list[dict], md: markdown.Markdown, site: dict, footer: str) -> None:
    slug = lesson["slug"]
    src_dir = LESSONS_DIR / slug
    out_dir = DIST_DIR / "lessons" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    md.reset()
    lesson_html = md.convert((src_dir / "lesson.md").read_text())

    audio_src = src_dir / "audio.mp3"
    audio_section = ""
    audio_url = None
    if audio_src.exists():
        shutil.copy2(audio_src, out_dir / "audio.mp3")
        audio_section = AUDIO_SECTION
        audio_url = f"{site['url']}/lessons/{slug}/audio.mp3"

    canonical = f"{site['url']}/lessons/{slug}/"
    root_rel = "../../"

    page = render(load_template("lesson.html"), {
        "root_rel": root_rel,
        "site_title": html.escape(site["title"]),
        "title": html.escape(lesson["title"]),
        "description": html.escape(lesson.get("description", "")),
        "canonical_url": html.escape(canonical),
        "author_url": html.escape(site["author_url"]),
        "byline": lesson_byline(site),
        "meta_line": lesson_meta_line(lesson),
        "tag_chips": tag_chips(lesson.get("tags", []), root_rel),
        "audio_section": audio_section,
        "lesson_html": lesson_html,
        "highlight_css": HIGHLIGHT_CSS,
        "json_ld": lesson_json_ld(lesson, site, audio_url),
        "related_section": related_section_html(lesson, all_lessons, root_rel),
        "footer": footer,
    })
    (out_dir / "index.html").write_text(page)


def build_home(lessons: list[dict], site: dict, footer: str) -> None:
    canonical = f"{site['url']}/"
    root_rel = ""
    page = render(load_template("home.html"), {
        "root_rel": root_rel,
        "site_title": html.escape(site["title"]),
        "site_description": html.escape(site["description"]),
        "canonical_url": html.escape(canonical),
        "author_url": html.escape(site["author_url"]),
        "lesson_cards": render_cards(lessons, root_rel),
        "json_ld_website": home_website_json_ld(site),
        "json_ld_person": home_person_json_ld(site),
        "footer": footer,
    })
    (DIST_DIR / "index.html").write_text(page)


def build_tag_pages(lessons: list[dict], site: dict, footer: str) -> list[tuple[str, str]]:
    by_slug: dict[str, dict] = {}
    for lesson in lessons:
        for tag in lesson.get("tags", []):
            slug = slugify_tag(tag)
            if not slug:
                continue
            entry = by_slug.setdefault(slug, {"display": tag, "lessons": []})
            entry["lessons"].append(lesson)

    template = load_template("tag.html")
    written: list[tuple[str, str]] = []
    root_rel = "../../"
    for slug, entry in sorted(by_slug.items()):
        out_dir = DIST_DIR / "tags" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        canonical = f"{site['url']}/tags/{slug}/"
        count = len(entry["lessons"])
        description = f"All {count} lesson{'s' if count != 1 else ''} tagged '{entry['display']}' on {site['title']}."
        page = render(template, {
            "root_rel": root_rel,
            "site_title": html.escape(site["title"]),
            "tag": html.escape(entry["display"]),
            "description": html.escape(description),
            "canonical_url": html.escape(canonical),
            "author_url": html.escape(site["author_url"]),
            "lesson_cards": render_cards(entry["lessons"], root_rel),
            "footer": footer,
        })
        (out_dir / "index.html").write_text(page)
        written.append((slug, canonical))
    return written


def build_sitemap(lessons: list[dict], tag_urls: list[tuple[str, str]], site: dict) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [(f"{site['url']}/", today, "weekly", "1.0")]
    for l in lessons:
        lastmod = (l.get("updated_at") or "")[:10] or today
        urls.append((f"{site['url']}/lessons/{l['slug']}/", lastmod, "monthly", "0.8"))
    for _slug, url in tag_urls:
        urls.append((url, today, "weekly", "0.5"))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, freq, prio in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append(f"    <changefreq>{freq}</changefreq>")
        parts.append(f"    <priority>{prio}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    (DIST_DIR / "sitemap.xml").write_text("\n".join(parts) + "\n")


def build_robots(site: dict) -> None:
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {site['url']}/sitemap.xml\n"
    )
    (DIST_DIR / "robots.txt").write_text(content)


def _xml_escape(text: str) -> str:
    return html.escape(text, quote=True)


def build_podcast_feed(lessons: list[dict], site: dict) -> None:
    audio_lessons = [l for l in lessons if l.get("_has_audio")]
    if not audio_lessons:
        return

    now_rfc822 = format_datetime(datetime.now(timezone.utc))
    site_url = site["url"].rstrip("/")
    feed_url = f"{site_url}/feed.xml"
    image_url = f"{site_url}/podcast-cover.png"

    items: list[str] = []
    for lesson in audio_lessons:
        slug = lesson["slug"]
        title = lesson["title"]
        description = lesson.get("description", "")
        link = f"{site_url}/lessons/{slug}/"
        audio_url = f"{link}audio.mp3"
        audio_path = LESSONS_DIR / slug / "audio.mp3"
        length = audio_path.stat().st_size
        pub_dt = parse_iso(lesson.get("created_at")) or datetime.now(timezone.utc)
        pub_rfc = format_datetime(pub_dt)
        keywords = ", ".join(lesson.get("tags", []))
        duration = lesson.get("_audio_duration_seconds")
        duration_tag = (
            f"\n      <itunes:duration>{format_hms(duration)}</itunes:duration>"
            if duration else ""
        )
        items.append(
            f"""    <item>
      <title>{_xml_escape(title)}</title>
      <description>{_xml_escape(description)}</description>
      <link>{_xml_escape(link)}</link>
      <guid isPermaLink="true">{_xml_escape(link)}</guid>
      <pubDate>{pub_rfc}</pubDate>
      <enclosure url="{_xml_escape(audio_url)}" length="{length}" type="audio/mpeg"/>
      <itunes:author>{_xml_escape(PODCAST_EPISODE_AUTHOR)}</itunes:author>
      <itunes:summary>{_xml_escape(description)}</itunes:summary>
      <itunes:explicit>false</itunes:explicit>
      <itunes:keywords>{_xml_escape(keywords)}</itunes:keywords>{duration_tag}
    </item>"""
        )

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{_xml_escape(site["title"])}</title>
    <link>{_xml_escape(site_url + "/")}</link>
    <atom:link href="{_xml_escape(feed_url)}" rel="self" type="application/rss+xml"/>
    <language>en</language>
    <description>{_xml_escape(site["description"])}</description>
    <copyright>{_xml_escape(site["author"])}</copyright>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
    <managingEditor>noreply@{_xml_escape(site_url.split('//')[-1])} ({_xml_escape(site["author"])})</managingEditor>
    <itunes:author>{_xml_escape(PODCAST_EPISODE_AUTHOR)}</itunes:author>
    <itunes:summary>{_xml_escape(site["description"])}</itunes:summary>
    <itunes:owner>
      <itunes:name>{_xml_escape(site["author"])}</itunes:name>
      <itunes:email>noreply@{_xml_escape(site_url.split('//')[-1])}</itunes:email>
    </itunes:owner>
    <itunes:image href="{_xml_escape(image_url)}"/>
    <itunes:category text="Technology"/>
    <itunes:category text="Education"/>
    <itunes:explicit>false</itunes:explicit>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (DIST_DIR / "feed.xml").write_text(feed)


def _tailwind_binary() -> str:
    candidate = Path(sys.executable).parent / "tailwindcss"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("tailwindcss")
    if found:
        return found
    raise FileNotFoundError(
        "tailwindcss binary not found — install with `pip install pytailwindcss` (it bundles the standalone CLI)"
    )


def build_styles() -> None:
    out = DIST_DIR / "styles.css"
    subprocess.run(
        [_tailwind_binary(), "-i", str(TAILWIND_INPUT), "-o", str(out), "--minify"],
        cwd=REPO_ROOT,
        check=True,
    )


def copy_static_passthrough() -> bool:
    if not STATIC_DIR.exists():
        return False
    for item in STATIC_DIR.iterdir():
        dest = DIST_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    return True


def build() -> int:
    config = manifest.load_json(CONFIG_PATH)
    site = config["site"]

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    lessons = manifest.load_json(LESSONS_PATH).get("lessons", [])
    publishable = [l for l in lessons if lesson_has_material(l["slug"])]
    for l in publishable:
        annotate_lesson(l)
    publishable.sort(
        key=lambda l: parse_iso(l.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "codehilite"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
        },
    )

    footer = footer_html(site)

    print(f"Building {len(publishable)} lesson page(s)...")
    for lesson in publishable:
        build_lesson_page(lesson, publishable, md, site, footer)
        print(f"  lesson   {lesson['slug']}")

    build_home(publishable, site, footer)
    print("  home     index.html")

    tag_urls = build_tag_pages(publishable, site, footer)
    print(f"  tags     {len(tag_urls)} tag page(s)")

    build_sitemap(publishable, tag_urls, site)
    print("  sitemap  sitemap.xml")

    build_robots(site)
    print("  robots   robots.txt")

    build_podcast_feed(publishable, site)
    audio_count = sum(1 for l in publishable if l.get("_has_audio"))
    if audio_count:
        print(f"  podcast  feed.xml ({audio_count} episode{'s' if audio_count != 1 else ''})")

    build_styles()
    print("  tailwind styles.css")

    (DIST_DIR / ".nojekyll").touch()
    print("  pages    .nojekyll")

    if copy_static_passthrough():
        print("  static   static/ → dist/")

    if not (DIST_DIR / "podcast-cover.png").exists() and audio_count:
        print("  WARN     no static/podcast-cover.png — feed.xml references a missing image (Apple Podcasts requires JPG/PNG, min 1400x1400)")

    skipped = len(lessons) - len(publishable)
    if skipped:
        print(f"  skipped  {skipped} lesson(s) without lesson.md")

    print(f"\nBuilt site → {DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
