You are rewriting the narration script for an existing lesson. Do NOT do new research — work only from the lesson.md that already exists.

Lesson metadata:
- Slug: $slug
- Title: $title
- Description: $description

Repo root: $repo_root
Lesson directory (relative to repo root): $lesson_dir

Steps:

1. Read `$lesson_dir/lesson.md`.

2. Rewrite `$lesson_dir/script.md` as a flowing spoken narration covering the same concepts. Use **normal, natural English**:
   - Write acronyms and technical terms normally (`YAML`, `API`, `QEMU`, `Kubernetes`, `nginx`, `SSH`, etc.). Do NOT spell them phonetically (no "yamel", "ay pee eye", "kee-moo") — a runtime dictionary handles pronunciation before TTS rendering, so leaving them as the normal word is correct.
   - Replace fenced code blocks with short prose explanations of what the code does. Keep short inline references like `apt install` or `kubectl get pods` as normal text.
   - Avoid bare URLs, footnotes, tables, and ASCII diagrams.
   - Strip markdown structure — no headings, no bullet lists, no emphasis markers. Write as flowing prose with natural sentence-level punctuation and short paragraphs.
   - Aim for roughly the same depth as lesson.md, optimised for listening.

3. Update `$lesson_dir/meta.json`:
   - Bump `"revision"` by 1
   - Update `"generated_at"` to the current ISO8601 UTC time

4. Do not modify `lesson.md`. Do not modify any files outside `$lesson_dir/`.
