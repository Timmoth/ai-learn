from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from string import Template

import questionary

from . import backends, build, manifest, tts

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_DIR = Path(__file__).resolve().parent
LESSONS_PATH = REPO_ROOT / "lessons.json"
COURSES_PATH = REPO_ROOT / "courses.json"
LESSONS_DIR = REPO_ROOT / "lessons"
TTS_DICT_PATH = REPO_ROOT / "tts_dictionary.json"


def lesson_dir(slug: str) -> Path:
    return LESSONS_DIR / slug


def has_material(slug: str) -> bool:
    return (lesson_dir(slug) / "lesson.md").exists()


def has_script(slug: str) -> bool:
    return (lesson_dir(slug) / "script.md").exists()


def render_audio(slug: str, config: dict) -> bool:
    script_path = lesson_dir(slug) / "script.md"
    audio_path = lesson_dir(slug) / "audio.mp3"
    if not script_path.exists():
        print(f"No script.md found at {script_path}; skipping audio.")
        return False
    print("\nRendering audio...")
    try:
        tts.synthesize(script_path, audio_path, config, TTS_DICT_PATH)
    except RuntimeError as e:
        print(f"Audio render failed: {e}")
        return False
    return True


def render_prompt(template_name: str, vars: dict) -> str:
    path = RUNNER_DIR / "prompts" / template_name
    return Template(path.read_text()).safe_substitute(vars)


def sanitize_slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def unique_slug(base: str, existing: set[str]) -> str:
    slug = base
    i = 2
    while slug in existing:
        slug = f"{base}-{i}"
        i += 1
    return slug


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in backend output.")
    return json.loads(match.group(0))


def pick_lesson(lessons: list[dict], message: str) -> dict | None:
    if not lessons:
        print("No lessons in lessons.json.")
        return None
    ordered = sorted(lessons, key=lambda l: l["title"].lower())
    choices = []
    for l in ordered:
        marker = "[x]" if has_material(l["slug"]) else "[ ]"
        tags = ", ".join(l.get("tags", []))
        choices.append(
            questionary.Choice(title=f"{marker} {l['title']}  ({tags})", value=l)
        )
    return questionary.select(
        message,
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()


def pick_update_mode() -> tuple[str, str] | None:
    choice = questionary.select(
        "How should this lesson be updated?",
        choices=[
            "refresh   - validate sources, refresh outdated material",
            "add       - add specific content",
            "remove    - remove specific content",
            "modify    - modify specific parts",
        ],
    ).ask()
    if not choice:
        return None
    mode = choice.split()[0]
    details = ""
    if mode != "refresh":
        details = questionary.text("Describe the change:").ask() or ""
    return mode, details


def build_content_prompt(lesson: dict, mode: str | None, details: str) -> str:
    slug = lesson["slug"]
    vars = {
        "slug": slug,
        "title": lesson["title"],
        "description": lesson.get("description", ""),
        "topics": ", ".join(lesson.get("topics", [])),
        "tags": ", ".join(lesson.get("tags", [])),
        "lesson_dir": f"lessons/{slug}",
        "repo_root": str(REPO_ROOT),
        "update_mode": mode or "",
        "update_details": details or "",
    }
    template = "update_lesson.md" if mode else "new_lesson.md"
    return render_prompt(template, vars)


def action_generate(config: dict) -> int:
    data = manifest.load_json(LESSONS_PATH)
    lessons = data.get("lessons", [])
    chosen = pick_lesson(lessons, "Generate / update which lesson?")
    if not chosen:
        return 0

    slug = chosen["slug"]
    print(f"\nSelected: {chosen['title']} ({slug})")

    if has_material(slug):
        update = pick_update_mode()
        if update is None:
            print("Cancelled.")
            return 0
        mode, details = update
        prompt = build_content_prompt(chosen, mode, details)
        verb = f"Updating ({mode})"
    else:
        prompt = build_content_prompt(chosen, None, "")
        verb = "Generating from scratch"

    print(
        f"\n{verb} — this may take a few minutes. "
        "The backend will stream its progress below.\n"
    )
    rc = backends.run_streaming(config, prompt, REPO_ROOT)
    if rc != 0:
        print(f"\nBackend exited with code {rc}.")
        return rc

    chosen["updated_at"] = manifest.now_iso()
    manifest.save_json(LESSONS_PATH, data)

    render_audio(slug, config)

    print("\nDone.")
    return 0


def action_manage_dictionary(config: dict) -> int:
    sub = questionary.select(
        "TTS dictionary — what would you like to do?",
        choices=[
            "Add or update an entry",
            "Remove an entry",
        ],
    ).ask()
    if sub is None:
        return 0
    if sub.startswith("Add"):
        return _dict_add(config)
    return _dict_remove()


def _dict_add(config: dict) -> int:
    word = questionary.text("Word or term to add:").ask()
    if not word or not word.strip():
        print("Cancelled.")
        return 0
    word = word.strip()

    dictionary = tts.load_dictionary(TTS_DICT_PATH)
    if word in dictionary:
        replace = questionary.confirm(
            f"'{word}' is already mapped to '{dictionary[word]}'. Replace?",
            default=False,
        ).ask()
        if not replace:
            print("Cancelled.")
            return 0

    prompt = render_prompt("phonetic_spelling.md", {"word": word})
    print(f"\nAsking backend for phonetic spelling of '{word}'...")
    rc, output = backends.run_capture(config, prompt, REPO_ROOT)
    if rc != 0:
        print(f"Backend exited with code {rc}.\n{output}")
        return rc

    suggestion = output.strip().strip("\"'")
    if "\n" in suggestion:
        lines = [l.strip() for l in suggestion.splitlines() if l.strip()]
        suggestion = lines[-1] if lines else ""
    if not suggestion:
        print("Backend returned empty output.")
        return 1

    phonetic = questionary.text(
        "Phonetic spelling (edit as needed, Enter to save):",
        default=suggestion,
    ).ask()
    if phonetic is None or not phonetic.strip():
        print("Cancelled.")
        return 0

    dictionary[word] = phonetic.strip()
    tts.save_dictionary(TTS_DICT_PATH, dictionary)
    print(f"Saved: '{word}'  →  '{phonetic.strip()}'")
    return 0


def _dict_remove() -> int:
    dictionary = tts.load_dictionary(TTS_DICT_PATH)
    if not dictionary:
        print("Dictionary is empty.")
        return 0

    choices = [
        questionary.Choice(title=f"{k}  →  {dictionary[k]}", value=k)
        for k in sorted(dictionary.keys(), key=lambda s: s.lower())
    ]
    word = questionary.select(
        "Remove which entry?",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()
    if not word:
        return 0

    confirmed = questionary.confirm(
        f"Remove '{word}'  →  '{dictionary[word]}'?",
        default=False,
    ).ask()
    if not confirmed:
        print("Cancelled.")
        return 0

    del dictionary[word]
    tts.save_dictionary(TTS_DICT_PATH, dictionary)
    print(f"Removed '{word}'.")
    return 0


def action_regenerate_script(config: dict) -> int:
    data = manifest.load_json(LESSONS_PATH)
    lessons = data.get("lessons", [])
    with_content = [l for l in lessons if has_material(l["slug"])]
    if not with_content:
        print("No lessons with lesson.md found. Generate a lesson first.")
        return 0

    scope = questionary.select(
        "Regenerate script for which lessons?",
        choices=[
            "A specific lesson",
            f"All lessons with content ({len(with_content)})",
        ],
    ).ask()
    if scope is None:
        return 0

    if scope.startswith("A specific"):
        chosen = pick_lesson(with_content, "Pick a lesson:")
        if not chosen:
            return 0
        targets = [chosen]
    else:
        targets = sorted(with_content, key=lambda l: l["title"].lower())
        confirmed = questionary.confirm(
            f"Regenerate script + audio for all {len(targets)} lesson(s)?",
            default=False,
        ).ask()
        if not confirmed:
            print("Cancelled.")
            return 0

    for lesson in targets:
        slug = lesson["slug"]
        print(f"\n=== {slug} ===")
        prompt = render_prompt("regenerate_script.md", {
            "slug": slug,
            "title": lesson["title"],
            "description": lesson.get("description", ""),
            "lesson_dir": f"lessons/{slug}",
            "repo_root": str(REPO_ROOT),
        })
        rc = backends.run_streaming(config, prompt, REPO_ROOT)
        if rc != 0:
            print(f"Backend failed for {slug} (code {rc}). Continuing.")
            continue

        lesson["updated_at"] = manifest.now_iso()
        manifest.save_json(LESSONS_PATH, data)

        render_audio(slug, config)

    print("\nDone.")
    return 0


def action_render_audio(config: dict) -> int:
    data = manifest.load_json(LESSONS_PATH)
    lessons = data.get("lessons", [])
    with_scripts = [l for l in lessons if has_script(l["slug"])]
    if not with_scripts:
        print("No lessons have a script.md yet — generate a lesson first.")
        return 0

    scope = questionary.select(
        "Render audio for which lessons?",
        choices=[
            "A specific lesson",
            f"All lessons with a script ({len(with_scripts)})",
        ],
    ).ask()
    if scope is None:
        return 0

    if scope.startswith("A specific"):
        chosen = pick_lesson(with_scripts, "Pick a lesson:")
        if not chosen:
            return 0
        targets = [chosen]
    else:
        targets = sorted(with_scripts, key=lambda l: l["title"].lower())
        confirmed = questionary.confirm(
            f"Render audio for all {len(targets)} lesson(s)?",
            default=False,
        ).ask()
        if not confirmed:
            print("Cancelled.")
            return 0

    failures = 0
    for lesson in targets:
        slug = lesson["slug"]
        print(f"\n=== {slug} ===")
        if not render_audio(slug, config):
            failures += 1

    if failures:
        print(f"\nDone with {failures} failure(s).")
        return 1
    print("\nDone.")
    return 0


def action_create(config: dict) -> int:
    description = questionary.text(
        "Describe the lesson you want to create:",
    ).ask()
    if not description or not description.strip():
        print("Cancelled.")
        return 0

    prompt = render_prompt(
        "create_lesson_metadata.md", {"description": description.strip()}
    )

    print("\nGenerating lesson metadata...")
    rc, output = backends.run_capture(config, prompt, REPO_ROOT)
    if rc != 0:
        print(f"Backend exited with code {rc}.\n{output}")
        return rc

    try:
        parsed = extract_json(output)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"\nCould not parse JSON from backend output: {e}")
        print("--- raw output ---")
        print(output)
        return 1

    data = manifest.load_json(LESSONS_PATH)
    lessons = data.setdefault("lessons", [])
    existing_slugs = {l["slug"] for l in lessons}
    base_slug = sanitize_slug(parsed.get("slug") or parsed.get("title", "untitled"))

    now = manifest.now_iso()
    lesson = {
        "slug": unique_slug(base_slug, existing_slugs),
        "title": parsed.get("title", "Untitled"),
        "description": parsed.get("description", ""),
        "topics": parsed.get("topics", []),
        "tags": parsed.get("tags", []),
        "created_at": now,
        "updated_at": now,
    }

    print("\nProposed lesson entry:")
    print(json.dumps(lesson, indent=2))

    if not questionary.confirm("Save this lesson to lessons.json?", default=True).ask():
        print("Cancelled.")
        return 0

    lessons.append(lesson)
    manifest.save_json(LESSONS_PATH, data)
    print(f"\nAdded lesson '{lesson['slug']}'.")
    return 0


def action_delete() -> int:
    data = manifest.load_json(LESSONS_PATH)
    lessons = data.get("lessons", [])
    chosen = pick_lesson(lessons, "Delete which lesson?")
    if not chosen:
        return 0

    slug = chosen["slug"]
    courses_data = manifest.load_json(COURSES_PATH)
    courses = courses_data.get("courses", [])
    affected_courses = [c for c in courses if slug in c.get("lessons", [])]
    ldir = lesson_dir(slug)

    print("\nWill delete:")
    print(f"  - lesson entry: {chosen['title']} ({slug})")
    if ldir.exists():
        file_count = sum(1 for p in ldir.rglob("*") if p.is_file())
        print(f"  - directory: lessons/{slug}/ ({file_count} files)")
    else:
        print(f"  - directory: lessons/{slug}/  (does not exist)")
    if affected_courses:
        names = ", ".join(c["slug"] for c in affected_courses)
        print(f"  - references in courses: {names}")

    if not questionary.confirm("Proceed with deletion?", default=False).ask():
        print("Cancelled.")
        return 0

    data["lessons"] = [l for l in lessons if l["slug"] != slug]
    manifest.save_json(LESSONS_PATH, data)

    if affected_courses:
        now = manifest.now_iso()
        for c in affected_courses:
            c["lessons"] = [s for s in c["lessons"] if s != slug]
            c["updated_at"] = now
        manifest.save_json(COURSES_PATH, courses_data)

    if ldir.exists():
        shutil.rmtree(ldir)

    print(f"\nDeleted lesson '{slug}'.")
    return 0


def main() -> int:
    config = manifest.load_json(RUNNER_DIR / "config.json")
    action = questionary.select(
        "What would you like to do?",
        choices=[
            "Generate or update a lesson",
            "Regenerate script (and audio)",
            "Render audio for a lesson",
            "Build static site",
            "Create a new lesson",
            "Delete a lesson",
            "Manage TTS dictionary",
        ],
    ).ask()
    if action is None:
        return 0
    if action.startswith("Regenerate"):
        return action_regenerate_script(config)
    if action.startswith("Render"):
        return action_render_audio(config)
    if action.startswith("Build"):
        return build.build()
    if action.startswith("Create"):
        return action_create(config)
    if action.startswith("Delete"):
        return action_delete()
    if action.startswith("Manage"):
        return action_manage_dictionary(config)
    return action_generate(config)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
