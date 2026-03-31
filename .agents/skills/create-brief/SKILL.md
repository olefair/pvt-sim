---
name: create-brief
description: >
  Use this skill whenever the user wants a concise but well-researched document
  rendered as a markdown artifact, typically 500-1000 words. Triggers include
  /create-brief, write a brief on, give me a briefing on, short analysis of,
  quick deep dive, summarize the state of, write a one-pager on, or any request
  where the user wants a focused, evidence-based written deliverable that is
  shorter than a full report but more rigorous than a chat response. Also trigger
  when the user says brief or briefing in the context of wanting a document
  output. Do NOT trigger for full research reports or comprehensive analyses
  (use create-artifact for those), quick conversational answers, code edits,
  or file format conversions.
---

# Create Brief — Concise Research Document Skill

## Purpose

Produce a focused, well-sourced markdown artifact in the 500–1000 word range. Same analytical rigor as a full report — just compressed. Every sentence should carry weight.

## When This Skill Applies

- User explicitly requests `/create-brief` or similar trigger phrases
- User asks for a briefing, one-pager, short analysis, or focused summary
- The topic can be adequately addressed in under 1,000 words with proper sourcing

## Workspace Vault Contract

When the current workspace uses the Pete docs vault, read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Use the shared intake and backlink workflow from the last note for `links`,
`related`, lineage fields, body wikilinks, and backlink fallback search. The
brief-specific rules below are deltas, not substitutes.

## Output Format

- Produce one canonical report-family markdown document rather than ad hoc markdown
- Canonical vault path: `docs/reports/briefs/report_<slug>_<YYYY-MM-DD>.md`
- Use the report-family contract from `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`, routing rules from `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`, and the canonical body structure from `docs/templates/template_report-canonical_v1_2026-03-17.md`
- Do **not** use the legacy `brief_<slug>_...` filename pattern; the current canonical filename prefix remains `report_`, with subtype recorded in `report_kind: brief`
- Required frontmatter for vault-native output: `project`, `status`, `report_kind: brief`, `production_mode: generated`, `produced_by: create-brief`, `agent_surface`, `created`, `updated`, `links`, `related`, `external_links`
- Recommended when known: `repos`, `subject`, `supersedes`, `superseded_by`
- Use `status: published` for a finished first-pass deliverable, `status: updated` when revising an existing brief, and `status: draft` only when the user explicitly wants an unfinished draft
- Put governing notes and must-read source notes in `links`, adjacent notes in `related`, preserve lineage in `supersedes` / `superseded_by`, and use body wikilinks so the finished brief improves backlink navigation instead of becoming an orphan
- The body outline must follow the canonical report family:
  - `# Report: <Human Readable Title>`
  - `## Report Type`
  - `## Scope`
  - `## Basis / Inputs`
  - `## Findings / Observations`
  - `## Interpretation`
  - `## Implications / Suggested Follow-up`
  - `## Change Notes`
- If the current surface cannot write directly into the vault, create a downloadable markdown file using the canonical filename and tell the user the intended vault path
- After rendering, provide a one-sentence summary in chat — nothing more
- If the topic genuinely requires 2,000+ words to do justice, say so and offer to use the full create-artifact approach instead

## Research Protocol

Same standards as a full report — the brevity is in the writing, not the research.

1. **Use web search** for current data, figures, and developments
2. **Use Scholar Gateway** when academic sourcing is warranted
3. **Use Google Drive / conversation search** when the user references personal or prior context

Scale research to the topic, but expect 3–10 searches even for a brief. The document should be grounded in evidence, not training data.

## Document Standards

### Structure
- Open with a **bold thesis or key finding** — the reader should grasp the core point in the first 1-2 sentences
- Use 2-4 section headers maximum — enough to organize, not enough to fragment
- No conclusion section unless it adds genuine synthesis beyond what the body already states
- Tables are encouraged when comparing items — they compress information efficiently

### Depth and Rigor
- **Same evidence standards as a full report.** Short does not mean shallow
- Substantiate key claims with sources. Skip sourcing only for widely accepted facts
- State uncertainty explicitly — brevity is not an excuse for false confidence
- Quantify where possible. Numbers compress meaning better than adjectives
- One strong example beats three vague ones

### Length Calibration
- **Target:** 500–1000 words
- **Hard floor:** 300 words (below this, a chat response would suffice)
- **Hard ceiling:** 1,200 words (beyond this, switch to create-artifact)
- Ruthlessly cut filler. No throat-clearing paragraphs, no restating what was just said

### Tone
- Direct and analytical
- Write for a knowledgeable reader — no over-explaining
- Prefer active voice and concrete language
- Every qualifier should earn its place

## What NOT To Do

- Do not produce a bulleted listicle and call it a brief
- Do not skip research because the output is short
- Do not include a references section — citations are inline
- Do not pad to reach 500 words. If the topic is genuinely answered in 350 well-sourced words, that's fine
- Do not ask clarifying questions if the request is clear enough — produce the brief, then offer to adjust
