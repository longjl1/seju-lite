# Skill: web_sum

## Purpose
Summarize webpage(s) into clear key points.

## When To Use
- User asks for 网页总结 / TL;DR / 总结链接.
- Input contains one or more URLs.

## Steps
1. Fetch page content.
2. Extract topic, key points, important numbers/dates/limits.
3. If multiple pages, merge overlaps and note conflicts.
4. Output in requested language/style.

## Output Format
- Summary (2-4 sentences)
- Key Points (3-7 bullets)
- Important Details (numbers/dates/limits)
- Open Questions (if any)
- Sources (URL list)

## Constraints
- Do not invent facts.
- If fetch fails, state which URL failed.
- Keep quotes short; prefer paraphrase.
- Use 1-2 emojis per paragraph unless user asks for formal style.
