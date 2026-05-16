You are updating an existing lesson on a public learning site.

Lesson metadata:
- Slug: $slug
- Title: $title
- Description: $description
- Topics: $topics
- Tags: $tags

Repo root: $repo_root
Lesson directory (relative to repo root): $lesson_dir

Update mode: $update_mode
User instructions: $update_details

Do the following:

1. Read the existing files in `$lesson_dir/`: lesson.md, script.md, meta.json.

2. Apply the update according to the mode:
   - refresh: re-check the sources listed in meta.json. If any are outdated or have stronger successors, search the web for fresh material. Update lesson.md and script.md only where content has actually changed or improved. Refresh the sources list in meta.json.
   - add: add the content described in the user instructions. Update both lesson.md and script.md consistently.
   - remove: remove the content described in the user instructions from both lesson.md and script.md.
   - modify: apply the modification described in the user instructions to both lesson.md and script.md.

3. Update `$lesson_dir/meta.json`:
   - Bump "revision" by 1
   - Update "generated_at" to the current ISO8601 UTC time
   - Refresh "sources" if you used new ones
   - Refresh "summary" if the content meaningfully changed

4. Keep lesson.md and script.md in sync — every conceptual change in one should be reflected in the other, subject to the format differences. script.md is flowing narration prose: code blocks replaced with prose explanations, no bare URLs/footnotes/tables, no markdown structure. **Write technical terms and acronyms normally in script.md** (`YAML`, `API`, `QEMU`, `Kubernetes`) — do NOT spell them phonetically; a runtime dictionary handles pronunciation before TTS rendering.

5. Do not modify any files outside `$lesson_dir/`.
