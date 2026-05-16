You are producing JSON metadata for a new learning lesson based on a user's free-text description. You are NOT writing lesson content yet — only the metadata entry that will go into lessons.json.

User description:
$description

Output a single JSON object with this exact shape:

{
  "title": "concise lesson title in sentence case",
  "slug": "url-safe-slug-derived-from-title",
  "description": "one-to-two sentence summary of what the lesson covers",
  "topics": ["specific", "subtopics", "this lesson covers"],
  "tags": ["broader", "classification", "labels"]
}

Constraints:
- title: short, clear, sentence case
- slug: lowercase letters, digits, and hyphens only; no spaces or special characters
- description: factual, one to two sentences, plain text
- topics: 3-6 specific concepts taught in the lesson
- tags: 2-5 broader classification labels (domain, difficulty, format, etc.)

Output the JSON object and nothing else. No commentary, no markdown code fences, no leading or trailing text.
