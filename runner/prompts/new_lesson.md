You are generating a new lesson for a public learning site.

Lesson metadata:
- Slug: $slug
- Title: $title
- Description: $description
- Topics: $topics
- Tags: $tags

Repo root: $repo_root
Lesson directory (relative to repo root): $lesson_dir

Do the following:

1. Research the topic. Use WebSearch and WebFetch to gather current, authoritative sources. Prefer primary sources, recent papers, and well-regarded documentation. Capture source URLs as you go.

2. Write the lesson article to `$lesson_dir/lesson.md`. It should be a focused, intuitive explanation matching the description above. Use clear headings, short paragraphs, and code samples where helpful. Assume markdown rendering on a website with code syntax highlighting.

3. Write a narration version to `$lesson_dir/script.md`. This file is fed to a text-to-speech engine, but **write it in normal, natural English** — pronunciation fixes are handled by a separate runtime dictionary that does case-insensitive find/replace before TTS rendering, so:
   - Write acronyms and technical terms normally (`YAML`, `API`, `QEMU`, `Kubernetes`, `nginx`) — do **not** spell them phonetically (no "yamel", "ay pee eye", "kee-moo"). The dictionary handles that.
   - Replace fenced code blocks with prose explanations of what the code does. Keep short inline references (`apt install`, `kubectl get pods`) as normal text.
   - Avoid bare URLs, footnotes, tables, ASCII diagrams, and other things that don't read aloud well.
   - Strip markdown structure (headings, lists, emphasis) — write as flowing prose with natural sentence-level punctuation and short paragraphs.
   - Cover the same concepts as lesson.md, optimised for listening; aim for roughly the same depth but spoken cadence.

4. Write `$lesson_dir/meta.json` with this shape:

   {
     "slug": "$slug",
     "revision": 1,
     "generated_at": "<current ISO8601 UTC timestamp>",
     "sources": [
       {"url": "...", "title": "...", "accessed_at": "<ISO8601 UTC>"}
     ],
     "summary": "<one-paragraph plain-text summary of the lesson>"
   }

5. Do not modify any files outside `$lesson_dir/`.
