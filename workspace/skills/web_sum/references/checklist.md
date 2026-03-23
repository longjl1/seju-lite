# Web Summary Checklist

## Mode A: News Summary

### Input Checks
- Confirm article URL is reachable.
- Identify publish date and event date (if different).
- Note source type (official media, blog, community post).

### Extract
- What happened (1 sentence).
- Who is involved.
- When and where it happened.
- Why it matters.
- What is confirmed vs what is unconfirmed.

### Risk Flags
- Title/content mismatch.
- Missing date/time context.
- One-sided claims without evidence.
- Outdated article treated as breaking news.

### Output Template
- Summary: 2-4 sentences.
- Key Points: 3-6 bullets.
- Uncertainties: 1-3 bullets.
- Sources: URL list.

## Mode B: Product/Docs Summary

### Input Checks
- Confirm official docs URL (prefer vendor docs first).
- Identify document version/date.
- Identify target user role (beginner/dev/admin).

### Extract
- Product/document purpose.
- Core features and limits.
- Required setup/prerequisites.
- Pricing/plan differences (if present).
- Breaking changes / migration notes (if present).

### Risk Flags
- Version mismatch.
- Deprecated APIs/features.
- Implicit limits not highlighted (quota, rate limits, region constraints).
- Security/privacy caveats omitted.

### Output Template
- Summary: 2-4 sentences.
- Key Points: 5-8 bullets.
- Important Details: limits, dates, versions.
- Action Items: next steps for user.
- Sources: URL list.

## General Quality Bar
- Do not invent facts.
- Keep quotes short; prefer paraphrase.
- Preserve numbers and dates exactly.
- Clearly separate facts from inference.
- If fetch fails, state failure and continue with available sources.
