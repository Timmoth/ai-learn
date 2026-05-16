# ai-learn

AI-generated learning material — written lessons and accompanying audio narration — published as a static site at [ai-learn.timmoth.com](https://ai-learn.timmoth.com).

Lessons are researched and written by [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) (or [opencode](https://opencode.ai)) driven by a small Python runner. Audio is rendered by a self-hosted [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) server.

## Layout

```
lessons.json              manifest: title, description, topics, tags, timestamps
courses.json              groupings of lessons into ordered sequences
tts_dictionary.json       word/acronym → phonetic spelling, applied at TTS time

lessons/<slug>/           generated per-lesson content
  ├── lesson.md           written article
  ├── script.md           narration-tuned version (TTS-friendly)
  ├── audio.mp3           rendered audio
  └── meta.json           revision, sources, summary

runner/
  ├── generate.py         interactive entry point
  ├── build.py            static site generator → dist/
  ├── backends.py         shells out to claude-code / opencode
  ├── tts.py              Kokoro TTS + dictionary substitution + ffmpeg
  ├── manifest.py         JSON I/O
  ├── config.json         backend, TTS, and site configuration
  ├── prompts/            templates fed to the CLI backend
  └── templates/          home.html + lesson.html (Tailwind via CDN)

dist/                     static site output (gitignored / publishable)
static/                   optional pass-through dir (CNAME, favicons, …)
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Requires `claude` (or `opencode`) on PATH for content generation, and `ffmpeg` on PATH for audio transcoding. The TTS server URL and voice are set in `runner/config.json` (or via `TTS_URL` / `TTS_VOICE` env vars).

## Usage

```bash
python -m runner.generate
```

Opens an interactive menu:

| Action | What it does |
| --- | --- |
| Generate or update a lesson | Pick a lesson; if no content exists, research + write from scratch; otherwise prompt for `refresh / add / remove / modify`. Audio is rendered automatically on success. |
| Render audio for a lesson | Re-run TTS on an existing `script.md` (useful after editing the dictionary or switching voice). |
| Build static site | Render `dist/` from `lessons.json` + per-lesson files. Also runs as `python -m runner.build`. |
| Create a new lesson | Free-text description → backend produces structured JSON → appended to `lessons.json`. No content yet. |
| Delete a lesson | Removes the manifest entry, strips references from courses, and `rm -rf`s the lesson directory. |
| Manage TTS dictionary | Add/update an entry (backend suggests phonetic spelling, editable before save) or remove one. |

## How content gets generated

The runner is an orchestrator — it doesn't write lessons itself. For each task it renders a prompt template from `runner/prompts/` and shells out to `claude -p` (or `opencode`). The backend does the research (`WebSearch`, `WebFetch`), writes `lesson.md`, `script.md`, and `meta.json` into `lessons/<slug>/`, and the runner verifies the output and updates `updated_at` in `lessons.json`.

Switch backends by changing `active_backend` in `runner/config.json`.

## TTS pipeline

1. Read `lessons/<slug>/script.md`
2. Strip residual markdown (fences, headings, links, emphasis)
3. Apply `tts_dictionary.json` as case-insensitive word-boundary find/replace **in memory only** — `script.md` is never modified
4. POST to the Kokoro server, receive FLAC
5. Transcode to MP3 with ffmpeg → `lessons/<slug>/audio.mp3`

## Static site

`python -m runner.build` regenerates `dist/`:

- `index.html` lists all lessons with `lesson.md` present
- `lessons/<slug>/index.html` per lesson (markdown rendered via Pygments-highlighted code blocks, HTML5 audio player)
- `sitemap.xml`, `robots.txt`, `.nojekyll`
- Anything under `static/` is copied verbatim into `dist/` (put `CNAME`, favicons, etc. there)

Tailwind is loaded from the Play CDN; dark mode persists via `localStorage`.

## Publishing

GitHub Pages from `dist/` (either committed to a publishing branch or pushed via a GitHub Action). Site root is `ai-learn.timmoth.com` — change `site.url` in `runner/config.json` if you fork.
