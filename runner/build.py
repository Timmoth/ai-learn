from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
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

LESSON_CARD = """<a href="lessons/{{slug}}/" class="block p-5 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600 transition">
        <h2 class="text-base font-medium mb-1">{{title}}</h2>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">{{description}}</p>
        <div class="flex flex-wrap gap-1.5">{{tag_chips}}</div>
      </a>"""

TAG_CHIP = '<span class="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">{{tag}}</span>'

AUDIO_SECTION = """<div class="mb-10 p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
      <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-500 mb-2">Listen</p>
      <audio controls preload="metadata" class="w-full">
        <source src="audio.mp3" type="audio/mpeg">
        Your browser does not support audio playback.
      </audio>
    </div>"""


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


def tag_chips(tags: list[str]) -> str:
    return "".join(render(TAG_CHIP, {"tag": html.escape(t)}) for t in tags)


def lesson_has_material(slug: str) -> bool:
    return (LESSONS_DIR / slug / "lesson.md").exists()


def github_profile_url(repo_url: str) -> str | None:
    m = re.match(r"https?://github\.com/([^/]+)", repo_url)
    return f"https://github.com/{m.group(1)}" if m else None


def footer_html(site: dict) -> str:
    author = html.escape(site["author"])
    author_url = html.escape(site["author_url"])
    github_url = html.escape(site["github_url"])
    return (
        '<footer class="border-t border-gray-200 dark:border-gray-800 mt-20">\n'
        '    <div class="max-w-3xl mx-auto px-6 py-6 text-sm text-gray-600 dark:text-gray-500">\n'
        f'      Architected by <a href="{author_url}" rel="me author" class="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 underline-offset-2 hover:underline">{author}</a> — '
        f'<a href="{github_url}" rel="external" class="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 underline-offset-2 hover:underline">GitHub</a>\n'
        '    </div>\n'
        '  </footer>'
    )


def home_json_ld(site: dict) -> str:
    profile = github_profile_url(site["github_url"])
    same_as = [profile] if profile else []
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site["title"],
        "url": site["url"],
        "description": site["description"],
        "author": {
            "@type": "Person",
            "name": site["author"],
            "url": site["author_url"],
            **({"sameAs": same_as} if same_as else {}),
        },
    }
    return f'<script type="application/ld+json">{json.dumps(data, separators=(",", ":"))}</script>'


def lesson_json_ld(lesson: dict, site: dict, audio_url: str | None) -> str:
    profile = github_profile_url(site["github_url"])
    same_as = [profile] if profile else []
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
        "author": {
            "@type": "Person",
            "name": site["author"],
            "url": site["author_url"],
            **({"sameAs": same_as} if same_as else {}),
        },
        "publisher": {
            "@type": "Person",
            "name": site["author"],
            "url": site["author_url"],
        },
    }
    if audio_url:
        data["audio"] = {
            "@type": "AudioObject",
            "contentUrl": audio_url,
            "encodingFormat": "audio/mpeg",
        }
    return f'<script type="application/ld+json">{json.dumps(data, separators=(",", ":"))}</script>'


def build_lesson_page(lesson: dict, md: markdown.Markdown, site: dict, footer: str) -> None:
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

    page = render(load_template("lesson.html"), {
        "site_title": html.escape(site["title"]),
        "title": html.escape(lesson["title"]),
        "description": html.escape(lesson.get("description", "")),
        "canonical_url": html.escape(canonical),
        "author_url": html.escape(site["author_url"]),
        "tag_chips": tag_chips(lesson.get("tags", [])),
        "audio_section": audio_section,
        "lesson_html": lesson_html,
        "highlight_css": HIGHLIGHT_CSS,
        "json_ld": lesson_json_ld(lesson, site, audio_url),
        "footer": footer,
    })
    (out_dir / "index.html").write_text(page)


def build_home(lessons: list[dict], site: dict, footer: str) -> None:
    if lessons:
        cards = "\n      ".join(
            render(LESSON_CARD, {
                "slug": l["slug"],
                "title": html.escape(l["title"]),
                "description": html.escape(l.get("description", "")),
                "tag_chips": tag_chips(l.get("tags", [])),
            })
            for l in lessons
        )
    else:
        cards = '<p class="text-gray-600 dark:text-gray-400">No lessons published yet.</p>'

    canonical = f"{site['url']}/"
    page = render(load_template("home.html"), {
        "site_title": html.escape(site["title"]),
        "site_description": html.escape(site["description"]),
        "canonical_url": html.escape(canonical),
        "author_url": html.escape(site["author_url"]),
        "lesson_cards": cards,
        "json_ld": home_json_ld(site),
        "footer": footer,
    })
    (DIST_DIR / "index.html").write_text(page)


def build_sitemap(lessons: list[dict], site: dict) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [(f"{site['url']}/", today, "weekly", "1.0")]
    for l in lessons:
        lastmod = (l.get("updated_at") or "")[:10] or today
        urls.append((f"{site['url']}/lessons/{l['slug']}/", lastmod, "monthly", "0.8"))

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
    publishable.sort(key=lambda l: l["title"].lower())

    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "codehilite"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
        },
    )

    footer = footer_html(site)

    print(f"Building {len(publishable)} lesson page(s)...")
    for lesson in publishable:
        build_lesson_page(lesson, md, site, footer)
        print(f"  lesson   {lesson['slug']}")

    build_home(publishable, site, footer)
    print("  home     index.html")

    build_sitemap(publishable, site)
    print("  sitemap  sitemap.xml")

    build_robots(site)
    print("  robots   robots.txt")

    (DIST_DIR / ".nojekyll").touch()
    print("  pages    .nojekyll")

    if copy_static_passthrough():
        print("  static   static/ → dist/")

    skipped = len(lessons) - len(publishable)
    if skipped:
        print(f"  skipped  {skipped} lesson(s) without lesson.md")

    print(f"\nBuilt site → {DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
