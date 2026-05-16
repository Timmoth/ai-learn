You are rewriting the narration script for an existing technical lesson.

Do NOT do new research.
Work only from the existing lesson.md.
Do NOT add facts, tools, commands, products, caveats, or examples that are not already present in lesson.md.

Lesson metadata:
- Slug: $slug
- Title: $title
- Description: $description

Repo root: $repo_root
Lesson directory, relative to repo root: $lesson_dir

Your task:

1. Read `$lesson_dir/lesson.md`.

2. Rewrite `$lesson_dir/script.md` as a natural spoken narration for an audio lesson.

The script must cover the same concepts as lesson.md, but it should sound like a calm, clear technical instructor speaking to one listener.

Style requirements:

- Use normal, natural English.
- Write acronyms and technical terms normally: `YAML`, `API`, `QEMU`, `Kubernetes`, `nginx`, `SSH`, and so on.
- Do NOT spell terms phonetically. Do not write things like "yamel", "ay pee eye", or "kee moo". A runtime TTS dictionary handles pronunciation later.
- Do not use markdown headings, bullet lists, tables, footnotes, blockquotes, emphasis markers, or ASCII diagrams.
- Write in short paragraphs.
- Prefer short, speakable sentences.
- Avoid long textbook-style paragraphs.
- Avoid overly formal phrases like "it is important to note that", "as previously mentioned", or "in conclusion".
- Use natural transitions such as "Now", "So", "Next", "The key idea is", and "Here is the mental model".
- Keep the tone confident, practical, and conversational.
- Do not make it chatty, jokey, salesy, or dramatic.
- Do not mention that this is a rewrite.

Technical content requirements:

- Preserve the meaning and depth of lesson.md.
- Keep the important technical distinctions, warnings, and failure modes.
- Keep important command names, file paths, config keys, resource names, and tool names when they matter.
- Replace fenced code blocks with short spoken explanations of what the code does.
- Keep short inline command references as normal text, for example `apt install`, `kubectl get pods`, or `cloud-init status`.
- Avoid reading large code blocks, YAML blocks, JSON blocks, or config files verbatim.
- When a code example is central to the lesson, summarize the important fields or steps in prose.
- Avoid bare URLs. Describe the resource instead, if needed.
- Do not invent examples that are not supported by lesson.md.

Audio narration requirements:

- Optimise for listening, not reading.
- Add small recap sentences after dense concepts.
- Break complex ideas into multiple short sentences.
- Use occasional signposting so the listener knows where they are in the lesson.
- Make the opening direct and useful.
- Make the ending a short practical recap.
- Avoid phrases like "in this article", "the section below", "as shown above", or "see the following table".
- Avoid too many numbered phrases like "first, second, third" unless the sequence truly matters.
- Do not include stage directions, SSML, pronunciation notes, or audio production notes.

Output file requirements:

- Write the final narration script to `$lesson_dir/script.md`.
- The script should be plain text or simple markdown paragraphs only.
- Do not include a title heading unless lesson.md itself requires one for clarity.
- Do not include front matter.

3. Update `$lesson_dir/meta.json`:

- Bump `"revision"` by 1.
- Update `"generated_at"` to the current ISO8601 UTC time.

4. Do not modify `$lesson_dir/lesson.md`.

5. Do not modify any files outside `$lesson_dir/`.

Before finishing, check your work:

- Confirm that `$lesson_dir/script.md` exists.
- Confirm that the script contains no fenced code blocks.
- Confirm that the script contains no markdown tables.
- Confirm that the script contains no bullet lists.
- Confirm that obvious acronyms remain written normally, not phonetically.
- Confirm that `$lesson_dir/meta.json` has an incremented revision and updated generated_at timestamp.